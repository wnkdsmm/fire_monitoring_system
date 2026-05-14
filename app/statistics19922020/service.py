from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd

from app.services.pipeline_service import add_log, import_uploaded_data
from app.state import JobState, job_store
from app.statistics19922020.config import (
    SETTINGS,
    resolve_fallback_input_xlsx,
    resolve_reference_dir,
    resolve_script_path,
)
from app.statistics19922020.decode_engine import (
    default_output_path,
    default_report_path,
    normalize_code,
    normalize_text,
    pick_code_and_text_columns,
    read_excel_robust,
)


def _decode_error_payload(message: str, job_id: str | None = None) -> dict[str, Any]:
    return {
        "status": "error",
        "message": message,
        "job_id": job_id or "",
    }


def _resolve_import_job(session_id: str, job_id: str | None) -> JobState | None:
    job = job_store.resolve_job(session_id=session_id, job_id=job_id, kind="import")
    if job is None:
        return None
    if job.kind != "import":
        return None
    if job.current_file_path is None or not job.current_file_path.exists():
        return None
    return job


def _resolve_reference_dir(base_dir: str | None) -> Path:
    return resolve_reference_dir(base_dir)


def decode_uploaded_stat_file(
    *,
    session_id: str,
    job_id: str | None,
    base_dir: str | None = None,
) -> dict[str, Any]:
    job = _resolve_import_job(session_id, job_id)
    if job is None:
        return _decode_error_payload("Сначала загрузите XLSX файл для расшифровки.", job_id)

    resolved_job_id = job.job_id
    input_path = job.current_file_path
    assert input_path is not None

    job_store.mark_job_status(session_id, resolved_job_id, "running")
    final_status = "failed"
    log_prefix = "[statistics19922020]"

    try:
        reference_dir = _resolve_reference_dir(base_dir)
        output_path = default_output_path(input_path)
        report_path = default_report_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        add_log(session_id, resolved_job_id, f"{log_prefix} Старт расшифровки: {input_path.name}")
        add_log(session_id, resolved_job_id, f"{log_prefix} Папка справочников: {reference_dir}")

        source_df = read_excel_robust(input_path, header=0)

        def _load_mapping(dict_path: Path) -> dict[str, str]:
            dictionary_df = read_excel_robust(dict_path, header=0)
            picked = pick_code_and_text_columns(dictionary_df.columns)
            if not picked:
                return {}
            code_col, text_col = picked
            mapping: dict[str, str] = {}
            for raw_code, raw_text in zip(dictionary_df[code_col], dictionary_df[text_col]):
                code = normalize_code(raw_code)
                text_value = normalize_text(raw_text)
                if not code or not text_value:
                    continue
                mapping.setdefault(code, text_value)
            return mapping

        district_mapping = _load_mapping(reference_dir / "rayon.xlsx")
        reason_mapping = _load_mapping(reference_dir / "prich.xlsx")
        add_log(
            session_id,
            resolved_job_id,
            f"{log_prefix} Loaded dictionaries: rayon={len(district_mapping)}, prich={len(reason_mapping)}.",
        )

        decoded_df = source_df.copy()
        report_rows: list[dict[str, Any]] = []
        normalized_to_actual: dict[str, str] = {}
        for col in decoded_df.columns:
            normalized_to_actual[normalize_text(col).casefold()] = col

        for expected_name, mapping in (
            ("Код района", district_mapping),
            ("Причина пожара (код)", reason_mapping),
        ):
            actual_column = normalized_to_actual.get(normalize_text(expected_name).casefold())
            if actual_column is None:
                report_rows.append(
                    {
                        "column_name": expected_name,
                        "status": "missing_column",
                        "mapped_rows": 0,
                        "unmapped_rows": 0,
                        "total_rows": int(decoded_df.shape[0]),
                    }
                )
                continue

            original_values = decoded_df[actual_column]
            normalized_codes = original_values.map(normalize_code)
            mapped_values = normalized_codes.map(mapping)
            mapped_mask = mapped_values.notna()
            decoded_df[actual_column] = original_values.where(~mapped_mask, mapped_values)

            mapped_rows = int(mapped_mask.sum())
            total_rows = int(decoded_df.shape[0])
            report_rows.append(
                {
                    "column_name": str(actual_column),
                    "status": "ok",
                    "mapped_rows": mapped_rows,
                    "unmapped_rows": total_rows - mapped_rows,
                    "total_rows": total_rows,
                }
            )

        report_df = pd.DataFrame(report_rows)

        decoded_df.to_excel(output_path, index=False)
        report_df.to_csv(report_path, index=False, encoding="utf-8-sig")

        mapped_columns = (
            int((report_df["mapped_rows"] > 0).sum())
            if (not report_df.empty and "mapped_rows" in report_df.columns)
            else 0
        )
        total_columns = 2

        # После расшифровки импортируемый файл переключается на декодированную версию.
        job_store.set_uploaded_file(session_id, resolved_job_id, output_path, output_path.name)
        add_log(
            session_id,
            resolved_job_id,
            f"{log_prefix} Готово: расшифровано колонок {mapped_columns}/{total_columns}.",
        )
        add_log(session_id, resolved_job_id, f"{log_prefix} Декодированный файл: {output_path}")
        add_log(session_id, resolved_job_id, f"{log_prefix} Отчет: {report_path}")

        final_status = "completed"
        return {
            "status": "decoded",
            "job_id": resolved_job_id,
            "input_file": str(input_path),
            "decoded_file": str(output_path),
            "report_file": str(report_path),
            "dictionaries_loaded": 2,
            "total_columns": total_columns,
            "decoded_columns": mapped_columns,
        }
    except Exception as exc:
        message = f"Ошибка расшифровки: {exc}"
        add_log(session_id, resolved_job_id, f"{log_prefix} {message}")
        return _decode_error_payload(message, resolved_job_id)
    finally:
        job_store.mark_job_status(session_id, resolved_job_id, final_status)


def decode_and_import_uploaded_stat_file(
    *,
    session_id: str,
    job_id: str | None,
    base_dir: str | None = None,
    output_folder: str | None = None,
) -> dict[str, Any]:
    decode_result = decode_uploaded_stat_file(session_id=session_id, job_id=job_id, base_dir=base_dir)
    if decode_result.get("status") != "decoded":
        return decode_result

    resolved_job_id = str(decode_result.get("job_id") or job_id or "")
    add_log(session_id, resolved_job_id, "[statistics19922020] Старт импорта расшифрованного файла в PostgreSQL.")
    import_result = import_uploaded_data(
        session_id=session_id,
        output_folder=output_folder,
        job_id=resolved_job_id,
    )
    import_status = str(import_result.get("status") or "")
    import_status_lower = import_status.lower()
    has_import_error = any(token in import_status_lower for token in ("ошибка", "error", "не загружен"))
    overall_status = "error" if has_import_error else "decoded_imported"
    return {
        "status": overall_status,
        "job_id": resolved_job_id,
        "message": import_status,
        "decode": decode_result,
        "import": import_result,
    }


def _split_lines_to_logs(session_id: str, job_id: str, text: str) -> None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for line in normalized.split("\n"):
        payload = line.strip()
        if payload:
            add_log(session_id, job_id, payload)


def _load_module_from_path(script_path: Path, module_name: str) -> ModuleType:
    spec = spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось загрузить модуль: {script_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_or_create_import_job(session_id: str, job_id: str | None) -> JobState:
    existing = job_store.resolve_job(session_id=session_id, job_id=job_id, kind="import")
    if existing is not None and existing.kind == "import":
        return existing
    if existing is not None and existing.kind != "import":
        return job_store.create_or_reset_job(session_id=session_id, kind="import", job_id=None)
    return job_store.create_or_reset_job(session_id=session_id, kind="import", job_id=job_id)


def _resolve_script_input_file(job: JobState, fallback_path: Path) -> Path:
    if job.current_file_path is not None and job.current_file_path.exists():
        return job.current_file_path
    if fallback_path.exists():
        return fallback_path
    raise FileNotFoundError(
        "Не найден входной файл: загрузите XLSX через страницу или проверьте fallback путь."
    )


def run_rename_headers_script(
    *,
    session_id: str,
    job_id: str | None,
) -> dict[str, Any]:
    job = _resolve_or_create_import_job(session_id=session_id, job_id=job_id)
    resolved_job_id = job.job_id

    job_store.mark_job_status(session_id, resolved_job_id, "running")
    final_status = "failed"

    try:
        script_path = resolve_script_path(SETTINGS.rename_headers_script_path, "rename_headers_2019_2023.py")
        input_path = _resolve_script_input_file(job, resolve_fallback_input_xlsx())

        add_log(session_id, resolved_job_id, f"[statistics19922020] Запуск rename_headers для файла: {input_path}")
        module = _load_module_from_path(script_path, "rename_headers_2019_2023")
        if hasattr(module, "FILE_PATH"):
            module.FILE_PATH = input_path
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            module.main()
        _split_lines_to_logs(session_id, resolved_job_id, buffer.getvalue())

        job_store.set_uploaded_file(session_id, resolved_job_id, input_path, input_path.name)
        add_log(session_id, resolved_job_id, "[statistics19922020] rename_headers завершен.")
        final_status = "completed"
        return {
            "status": "ok",
            "job_id": resolved_job_id,
            "script": str(script_path),
            "input_file": str(input_path),
        }
    except Exception as exc:
        message = f"Ошибка выполнения rename_headers: {exc}"
        add_log(session_id, resolved_job_id, f"[statistics19922020] {message}")
        return _decode_error_payload(message, resolved_job_id)
    finally:
        job_store.mark_job_status(session_id, resolved_job_id, final_status)


def run_split_xlsx_by_year_script(
    *,
    session_id: str,
    job_id: str | None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    job = _resolve_or_create_import_job(session_id=session_id, job_id=job_id)
    resolved_job_id = job.job_id

    job_store.mark_job_status(session_id, resolved_job_id, "running")
    final_status = "failed"

    try:
        script_path = resolve_script_path(SETTINGS.split_xlsx_script_path, "split_xlsx_by_year.py")
        input_path = _resolve_script_input_file(job, resolve_fallback_input_xlsx())
        target_output_dir = (
            Path(output_dir).expanduser().resolve()
            if (output_dir or "").strip()
            else (input_path.parent / "by_year").resolve()
        )
        target_output_dir.mkdir(parents=True, exist_ok=True)

        add_log(session_id, resolved_job_id, f"[statistics19922020] Запуск split_xlsx_by_year для файла: {input_path}")
        add_log(session_id, resolved_job_id, f"[statistics19922020] Папка вывода: {target_output_dir}")

        command = [
            sys.executable,
            str(script_path),
            "--input",
            str(input_path),
            "--output-dir",
            str(target_output_dir),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        _split_lines_to_logs(session_id, resolved_job_id, completed.stdout)
        _split_lines_to_logs(session_id, resolved_job_id, completed.stderr)

        if completed.returncode != 0:
            raise RuntimeError(f"Код возврата: {completed.returncode}")

        exported = sorted(target_output_dir.glob(f"{input_path.stem}_*.xlsx"))
        add_log(session_id, resolved_job_id, f"[statistics19922020] split_xlsx_by_year завершен. Файлов: {len(exported)}")
        final_status = "completed"
        return {
            "status": "ok",
            "job_id": resolved_job_id,
            "script": str(script_path),
            "input_file": str(input_path),
            "output_dir": str(target_output_dir),
            "exported_files": [str(path) for path in exported],
        }
    except Exception as exc:
        message = f"Ошибка выполнения split_xlsx_by_year: {exc}"
        add_log(session_id, resolved_job_id, f"[statistics19922020] {message}")
        return _decode_error_payload(message, resolved_job_id)
    finally:
        job_store.mark_job_status(session_id, resolved_job_id, final_status)


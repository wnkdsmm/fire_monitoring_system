from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser()


@dataclass(frozen=True)
class Statistics19922020Config:
    stat_reference_dir: Path
    rename_headers_script_path: Path
    split_xlsx_script_path: Path
    fallback_input_xlsx: Path

    @classmethod
    def from_env(cls) -> "Statistics19922020Config":
        bundled_dir = Path(__file__).resolve().parent
        bundled_reference_dir = (bundled_dir / "dictionaries").resolve()
        bundled_scripts_dir = bundled_dir / "scripts"
        return cls(
            stat_reference_dir=bundled_reference_dir,
            rename_headers_script_path=_env_path(
                "STATISTICS19922020_RENAME_HEADERS_SCRIPT",
                str(bundled_scripts_dir / "rename_headers_2019_2023.py"),
            ),
            split_xlsx_script_path=_env_path(
                "STATISTICS19922020_SPLIT_XLSX_SCRIPT",
                str(bundled_scripts_dir / "split_xlsx_by_year.py"),
            ),
            fallback_input_xlsx=_env_path(
                "STATISTICS19922020_FALLBACK_INPUT_XLSX",
                r"F:\filesFires\edittables\2019-2023.xlsx",
            ),
        )


SETTINGS = Statistics19922020Config.from_env()


def resolve_reference_dir(base_dir: str | None) -> Path:
    resolved = SETTINGS.stat_reference_dir.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Папка справочников не найдена: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Путь справочников не является папкой: {resolved}")
    return resolved


def resolve_script_path(path: Path, script_name: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Скрипт {script_name} не найден: {resolved}")
    if not resolved.is_file():
        raise IsADirectoryError(f"Путь скрипта {script_name} должен быть файлом: {resolved}")
    return resolved


def resolve_fallback_input_xlsx() -> Path:
    return SETTINGS.fallback_input_xlsx.resolve()

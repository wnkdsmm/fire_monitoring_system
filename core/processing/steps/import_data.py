# import_data.py
import logging
import os

import pandas as pd

from config.db import engine
from core.processing.pipeline import PipelineStep


logger = logging.getLogger(__name__)

_CSV_FALLBACK_ENCODINGS = ("utf-8-sig", "windows-1251", "latin-1")


def _detect_csv_encoding(input_file: str) -> str | None:
    try:
        import chardet
        with open(input_file, "rb") as f:
            raw = f.read(65536)
        result = chardet.detect(raw)
        detected = (result.get("encoding") or "").strip()
        return detected if detected else None
    except Exception:
        return None


def _read_csv(input_file: str) -> pd.DataFrame:
    detected = _detect_csv_encoding(input_file)
    candidates = [detected] if detected else []
    for enc in _CSV_FALLBACK_ENCODINGS:
        if enc not in candidates:
            candidates.append(enc)
    last_exc: Exception | None = None
    for enc in candidates:
        try:
            return pd.read_csv(input_file, encoding=enc)
        except (UnicodeDecodeError, LookupError) as exc:
            last_exc = exc
            logger.debug("CSV read failed with encoding %s: %s", enc, exc)
    raise ValueError(
        f"Cannot decode {input_file!r}. Tried encodings: {candidates}"
    ) from last_exc


def _read_tabular_data(input_file: str, ext: str) -> pd.DataFrame:
    if ext == ".xls":
        try:
            return pd.read_excel(input_file, engine="xlrd")
        except ImportError as exc:
            raise ImportError(
                "Reading .xls requires xlrd>=2.0.1. Install dependency and restart the app."
            ) from exc
    if ext == ".xlsx":
        return pd.read_excel(input_file, engine="openpyxl")
    if ext == ".csv":
        return _read_csv(input_file)
    raise ValueError("Only XLS, XLSX and CSV are supported")


class ImportDataStep(PipelineStep):
    def __init__(self):
        super().__init__("Import Data")
        self.data = None

    def run(self, settings):
        input_file = settings.input_file
        output_folder = settings.output_folder
        project_name = settings.project_name

        if not os.path.exists(input_file):
            raise FileNotFoundError(f"File not found: {input_file}")

        ext = os.path.splitext(input_file)[1].lower()
        try:
            self.data = _read_tabular_data(input_file, ext)
        except Exception:
            logger.exception("Failed to read input file: %s", input_file)
            raise

        os.makedirs(output_folder, exist_ok=True)

        csv_path = os.path.join(output_folder, f"{project_name}.csv")
        self.data.to_csv(csv_path, index=False, encoding="utf-8-sig")

        try:
            with engine.begin() as conn:
                self.data.to_sql(project_name, conn, if_exists="replace", index=False)
            settings._pipeline_source_df = self.data
            settings._pipeline_import_csv = csv_path
            logger.info("Imported data into PostgreSQL table: %s", project_name)
        except Exception:
            logger.exception("Failed to write table to PostgreSQL: %s", project_name)
            raise

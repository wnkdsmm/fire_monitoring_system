from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

import pandas as pd


STAT_FILE_RE = re.compile(r"^stat\d+(_copy)?\.xlsx$", re.IGNORECASE)
FIELD_RE = re.compile(r"^F\d+[A-Z]?$", re.IGNORECASE)
PCODE_RE = re.compile(r"^P(\d+)(?:_(\d+))?$", re.IGNORECASE)
FRSF_RE = re.compile(r"^frsf(\d+)(?:_(\d+))?$", re.IGNORECASE)

MANUAL_PCODE_TO_DICTS: dict[str, list[str]] = {
    "P2": ["rayon"],
    "P5_1": ["vid_nasp"],
    "P5_2": ["vid_oxp"],
    "P6": ["sobst"],
    "P7": ["formorg"],
    "P8": ["ministry"],
    "P9": ["tippr"],
    "P10_1": ["object", "object_09"],
    "P10_2": ["vid_oxpo"],
    "P12": ["ognest"],
    "P13_1": ["plase"],
    "P13_2": ["plase"],
    "P14": ["izdel"],
    "P15": ["prich"],
    "P16_1": ["vinov", "objvinov"],
    "P16_2": ["sostvin"],
    "P18_1": ["ud"],
    "P18_2": ["udwho"],
    "P18_3": ["udst"],
    "P23_1": ["usl_tra"],
    "P47": ["usl_razv"],
    "P48": ["Uch_tuch"],
    "P49": ["Technic"],
    "P51": ["Stvol"],
    "P53": ["Ots"],
    "P54": ["Perv_sr"],
    "P55": ["Vodoist"],
    "P56": ["Aup"],
    "P57": ["Rab_aup"],
    "P58": ["Rtp1", "Rtp2"],
    "P59": ["mom_gib"],
    "P61": ["sex"],
    "P62": ["social"],
    "P63": ["obraz"],
    "P64": ["prch_gib"],
    "P65": ["usl_gib"],
    "P66": ["mom_gib"],
}

DEFAULT_LIKE_VALUES = {"0", "-1"}


@dataclass
class FieldInfo:
    pcode: str
    description: str


@dataclass
class DictionaryData:
    name: str
    path: Path
    code_to_text: dict[str, str]


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00A0", " ").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def normalize_code(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    compact = text.replace(" ", "")
    if re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", compact):
        numeric_text = compact.replace(",", ".")
        try:
            number = Decimal(numeric_text)
        except InvalidOperation:
            return text
        if number == number.to_integral_value():
            return str(int(number))
        normalized = format(number.normalize(), "f")
        return normalized.rstrip("0").rstrip(".")
    return text


def read_excel_robust(path: Path, header: int | None = 0) -> pd.DataFrame:
    return pd.read_excel(path, header=header, dtype=str)


def find_field_description_file(base_dir: Path) -> Path:
    for file_path in sorted(base_dir.rglob("*.xlsx")):
        if STAT_FILE_RE.match(file_path.name):
            continue
        try:
            preview = read_excel_robust(file_path, header=None).head(5)
        except Exception:
            continue
        if preview.empty:
            continue

        has_legacy_layout = (
            preview.shape[1] >= 4
            and normalize_text(preview.iat[0, 0]).upper() == "F1"
            and normalize_text(preview.iat[1, 3]).upper().startswith("P")
        )
        if has_legacy_layout:
            return file_path

        if preview.shape[1] >= 2:
            first = normalize_text(preview.iat[0, 0]).lower()
            second = normalize_text(preview.iat[0, 1]).lower()
            if first in {"nm_col", "name"} and second in {"col", "code"}:
                return file_path
    raise FileNotFoundError(
        f"Could not locate field description workbook in: {base_dir}"
    )


def load_p98_descriptions(base_dir: Path) -> dict[str, str]:
    p98_files = sorted(base_dir.glob("**/*P98*.xlsx"))
    if not p98_files:
        return {}
    p98 = read_excel_robust(p98_files[0], header=0)
    if p98.empty:
        return {}
    col_candidates = [c for c in p98.columns if normalize_text(c)]
    if len(col_candidates) < 2:
        return {}
    desc_col = col_candidates[0]
    code_col = col_candidates[1]
    out: dict[str, str] = {}
    for _, row in p98.iterrows():
        desc = normalize_text(row.get(desc_col))
        code = normalize_text(row.get(code_col)).upper()
        if desc and code and code not in out:
            out[code] = desc
    return out


def load_field_info(base_dir: Path, source_columns: Iterable[object] | None = None) -> tuple[dict[str, FieldInfo], Path]:
    field_file = find_field_description_file(base_dir)
    p98_desc = load_p98_descriptions(base_dir)
    raw = read_excel_robust(field_file, header=None)
    fields: dict[str, FieldInfo] = {}
    source_iterable = source_columns if source_columns is not None else []
    source_field_names = [normalize_text(c).upper() for c in source_iterable if normalize_text(c)]

    # Legacy format: explicit field id in first column (F1, F2, F17A, ...).
    for _, row in raw.iterrows():
        field = normalize_text(row.iloc[0] if len(row) > 0 else "")
        if not field or not FIELD_RE.match(field):
            continue
        field = field.upper()
        pcode = normalize_text(row.iloc[3] if len(row) > 3 else "").upper()
        desc = normalize_text(row.iloc[7] if len(row) > 7 else "")
        if not desc and pcode:
            desc = p98_desc.get(pcode, "")
        fields[field] = FieldInfo(pcode=pcode, description=desc)

    # Fallback format (P98): columns [nm_col, col] without explicit F* field ids.
    if not fields:
        p98 = read_excel_robust(field_file, header=0)
        if p98.shape[1] >= 2:
            col_candidates = [c for c in p98.columns if normalize_text(c)]
            if len(col_candidates) >= 2:
                desc_col = col_candidates[0]
                code_col = col_candidates[1]
                p_rows: list[FieldInfo] = []
                for _, row in p98.iterrows():
                    desc = normalize_text(row.get(desc_col))
                    pcode = normalize_text(row.get(code_col)).upper()
                    if not pcode:
                        continue
                    p_rows.append(FieldInfo(pcode=pcode, description=desc))
                if source_field_names:
                    for field_name, info in zip(source_field_names, p_rows):
                        fields[field_name] = info
    return fields, field_file


def _normalize_fire_date_value(value: object) -> object:
    if value is None:
        return value
    text = normalize_text(value)
    if not text:
        return value
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return ""
        return value.strftime("%Y-%m-%d")

    compact = text.replace(" ", "")
    if re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", compact):
        numeric_text = compact.replace(",", ".")
        try:
            serial = float(numeric_text)
        except ValueError:
            return value
        if 20000 <= serial <= 100000:
            try:
                dt = pd.to_datetime(serial, unit="D", origin="1899-12-30", errors="coerce")
            except Exception:
                dt = pd.NaT
            if not pd.isna(dt):
                return dt.strftime("%Y-%m-%d")
    return value


DATE_PCODE_SET = {"P4", "P19", "P45_1", "P46"}
DATE_FIELD_FALLBACK_SET = {"F5", "F7", "F28", "F71", "F73"}


def _is_date_column(field_name: str, info: FieldInfo | None) -> bool:
    if normalize_text(field_name).upper() in DATE_FIELD_FALLBACK_SET:
        return True
    if info is None:
        return False
    if info.pcode.upper() in DATE_PCODE_SET:
        return True
    return False


def _looks_like_excel_serial_date_column(values: pd.Series) -> bool:
    checked = 0
    serial_like = 0
    for raw in values:
        text = normalize_text(raw)
        if not text:
            continue
        checked += 1
        compact = text.replace(" ", "")
        if not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", compact):
            continue
        try:
            serial = float(compact.replace(",", "."))
        except ValueError:
            continue
        if 20000 <= serial <= 100000:
            serial_like += 1
    if checked < 5:
        return False
    return (serial_like / checked) >= 0.8



def pick_code_and_text_columns(columns: Iterable[object]) -> tuple[str, str] | None:
    clean_cols = [normalize_text(c) for c in columns if normalize_text(c)]
    if len(clean_cols) < 2:
        return None

    def find_match(patterns: list[re.Pattern[str]]) -> str | None:
        for col in clean_cols:
            for pattern in patterns:
                if pattern.search(col):
                    return col
        return None

    code_patterns = [
        re.compile(r"^kod$", re.IGNORECASE),
        re.compile(r"^cod$", re.IGNORECASE),
        re.compile(r"^code$", re.IGNORECASE),
        re.compile(r"^id$", re.IGNORECASE),
        re.compile(r"код", re.IGNORECASE),
    ]
    text_patterns = [
        re.compile(r"name", re.IGNORECASE),
        re.compile(r"наим", re.IGNORECASE),
        re.compile(r"nm", re.IGNORECASE),
        re.compile(r"desc", re.IGNORECASE),
    ]

    code_col = find_match(code_patterns) or clean_cols[0]
    text_col = None
    for col in clean_cols:
        if col == code_col:
            continue
        if any(pattern.search(col) for pattern in text_patterns):
            text_col = col
            break
    if text_col is None:
        text_col = next((col for col in clean_cols if col != code_col), "")
    if not text_col:
        return None
    return code_col, text_col


def load_dictionary(file_path: Path) -> DictionaryData | None:
    try:
        table = read_excel_robust(file_path, header=0)
    except Exception:
        return None
    if table.empty or table.shape[1] < 2:
        return None
    picked = pick_code_and_text_columns(table.columns)
    if not picked:
        return None
    code_col, text_col = picked
    mapping: dict[str, str] = {}

    def ingest(code_series: pd.Series, value_series: pd.Series) -> None:
        for raw_code, raw_value in zip(code_series, value_series):
            code = normalize_code(raw_code)
            value = normalize_text(raw_value)
            if not code or not value:
                continue
            if code == value:
                continue
            mapping.setdefault(code, value)

    ingest(table[code_col], table[text_col])

    alt_code_cols = [
        col
        for col in table.columns
        if col != code_col
        and re.search(r"(oldcode|old[_ ]?cod|prev[_ ]?cod|for_in)", normalize_text(col), re.IGNORECASE)
    ]
    for alt_col in alt_code_cols:
        ingest(table[alt_col], table[text_col])

    if not mapping:
        return None
    return DictionaryData(
        name=file_path.stem,
        path=file_path,
        code_to_text=mapping,
    )


def list_dictionary_files(base_dir: Path, field_file: Path) -> list[Path]:
    files: list[Path] = []
    for file_path in sorted(base_dir.glob("*.xlsx")):
        lower_name = file_path.name.lower()
        if file_path == field_file:
            continue
        if STAT_FILE_RE.match(lower_name):
            continue
        files.append(file_path)
    for folder in sorted([p for p in base_dir.iterdir() if p.is_dir()]):
        for file_path in sorted(folder.glob("*.xlsx")):
            files.append(file_path)
    return files


def build_dictionaries(base_dir: Path, field_file: Path) -> dict[str, DictionaryData]:
    dictionaries: dict[str, DictionaryData] = {}
    for file_path in list_dictionary_files(base_dir, field_file):
        dictionary = load_dictionary(file_path)
        if dictionary is None:
            continue
        dictionaries[dictionary.name.lower()] = dictionary
    if not dictionaries:
        raise RuntimeError(f"No dictionaries loaded from {base_dir}")
    return dictionaries


def pcode_candidates(pcode: str, dictionaries: dict[str, DictionaryData]) -> list[DictionaryData]:
    if not pcode:
        return []
    pcode_upper = pcode.upper()
    added: set[str] = set()
    candidates: list[DictionaryData] = []

    def add_name(raw_name: str) -> None:
        key = raw_name.lower()
        if key in dictionaries and key not in added:
            candidates.append(dictionaries[key])
            added.add(key)

    match = PCODE_RE.match(pcode_upper)
    if match:
        number = int(match.group(1))
        suffix = match.group(2)
        if suffix:
            add_name(f"frSF{number:02d}_{int(suffix)}")
        add_name(f"frSF{number:02d}")

        root_key = f"P{number}"
        for manual_name in MANUAL_PCODE_TO_DICTS.get(root_key, []):
            add_name(manual_name)
        for manual_name in MANUAL_PCODE_TO_DICTS.get(pcode_upper, []):
            add_name(manual_name)
    else:
        for manual_name in MANUAL_PCODE_TO_DICTS.get(pcode_upper, []):
            add_name(manual_name)
    return candidates


def score_dictionary(values: pd.Series, dictionary: DictionaryData) -> tuple[int, int, int, float]:
    non_null = 0
    non_default = 0
    matched = 0
    matched_non_default = 0
    for value in values:
        code = normalize_code(value)
        if not code:
            continue
        non_null += 1
        if code not in DEFAULT_LIKE_VALUES:
            non_default += 1
        if code in dictionary.code_to_text:
            matched += 1
            if code not in DEFAULT_LIKE_VALUES:
                matched_non_default += 1
    if non_default > 0:
        coverage = matched_non_default / non_default
    elif non_null > 0:
        coverage = matched / non_null
    else:
        coverage = 0.0
    return matched, non_null, non_default, coverage


def choose_dictionary(
    values: pd.Series,
    pcode: str,
    dictionaries: dict[str, DictionaryData],
) -> tuple[DictionaryData | None, int, float]:
    explicit = pcode_candidates(pcode, dictionaries)
    best_dict: DictionaryData | None = None
    best_matches = 0
    best_coverage = 0.0

    for dictionary in explicit:
        matches, _, _, coverage = score_dictionary(values, dictionary)
        if matches > best_matches or (matches == best_matches and coverage > best_coverage):
            best_dict = dictionary
            best_matches = matches
            best_coverage = coverage
    if best_dict is not None and best_matches > 0:
        return best_dict, best_matches, best_coverage
    return None, 0, 0.0


def build_output_column_name(field_name: str, info: FieldInfo | None) -> str:
    if info is None:
        return field_name
    parts = [field_name]
    if info.pcode:
        parts.append(info.pcode)
    if info.description:
        parts.append(info.description)
    return " | ".join(parts)


def decode_dataframe(
    df: pd.DataFrame,
    fields: dict[str, FieldInfo],
    dictionaries: dict[str, DictionaryData],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    decoded = pd.DataFrame(index=df.index)
    report_rows: list[dict[str, object]] = []

    for column in df.columns:
        field_name = normalize_text(column).upper()
        info = fields.get(field_name)
        pcode = info.pcode if info else ""
        dictionary, matches, coverage = choose_dictionary(df[column], pcode, dictionaries)
        output_name = build_output_column_name(field_name, info)
        is_fire_date = _is_date_column(field_name, info) or _looks_like_excel_serial_date_column(df[column])

        if dictionary is None:
            if is_fire_date:
                decoded[output_name] = [_normalize_fire_date_value(v) for v in df[column]]
            else:
                decoded[output_name] = df[column]
            report_rows.append(
                {
                    "column": field_name,
                    "pcode": pcode,
                    "description": info.description if info else "",
                    "dictionary": "",
                    "mapped_rows": 0,
                    "coverage": 0.0,
                }
            )
            continue

        mapped_values: list[object] = []
        mapped_rows = 0
        for raw_value in df[column]:
            if is_fire_date:
                mapped_values.append(_normalize_fire_date_value(raw_value))
                continue
            code = normalize_code(raw_value)
            if code in DEFAULT_LIKE_VALUES:
                mapped_values.append(raw_value)
                continue
            mapped = dictionary.code_to_text.get(code, "")
            if mapped:
                mapped_values.append(mapped)
                mapped_rows += 1
            else:
                mapped_values.append(raw_value)
        decoded[output_name] = mapped_values
        report_rows.append(
            {
                "column": field_name,
                "pcode": pcode,
                "description": info.description if info else "",
                "dictionary": dictionary.name,
                "mapped_rows": mapped_rows,
                "coverage": round(coverage, 4),
                "candidate_matches": matches,
            }
        )

    report = pd.DataFrame(report_rows)
    return decoded, report


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_decoded.xlsx")


def default_report_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_decode_report.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Decode STAT*.xlsx coded values using dictionaries from the same folder "
            "and its reference subfolder."
        )
    )
    parser.add_argument("--input", required=True, help="Path to source STAT*.xlsx file")
    parser.add_argument(
        "--base-dir",
        default="",
        help=(
            "Directory with STAT files, dictionaries and field descriptions. "
            "Default: directory of --input"
        ),
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output .xlsx path. Default: <input>_decoded.xlsx",
    )
    parser.add_argument(
        "--report",
        default="",
        help="CSV report path with applied dictionaries per column",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    base_dir = Path(args.base_dir).expanduser().resolve() if args.base_dir else input_path.parent
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else default_output_path(input_path)
    )
    report_path = (
        Path(args.report).expanduser().resolve()
        if args.report
        else default_report_path(output_path)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    source_df = read_excel_robust(input_path, header=0)
    fields, field_file = load_field_info(base_dir, source_columns=source_df.columns)
    dictionaries = build_dictionaries(base_dir, field_file)
    decoded_df, report_df = decode_dataframe(source_df, fields, dictionaries)

    decoded_df.to_excel(output_path, index=False)
    report_df.to_csv(report_path, index=False, encoding="utf-8-sig")

    mapped_cols = int((report_df["mapped_rows"] > 0).sum()) if not report_df.empty else 0
    total_cols = int(report_df.shape[0])
    print(f"Input: {input_path}")
    print(f"Base dir: {base_dir}")
    print(f"Field metadata: {field_file}")
    print(f"Dictionaries loaded: {len(dictionaries)}")
    print(f"Columns decoded: {mapped_cols}/{total_cols}")
    print(f"Decoded file: {output_path}")
    print(f"Report file: {report_path}")


if __name__ == "__main__":
    main()

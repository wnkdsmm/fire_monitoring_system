from pathlib import Path
import argparse
import pandas as pd

DEFAULT_INPUT_XLSX = Path(r"F:\filesFires\edittables\2019-2023.xlsx")
DEFAULT_OUTPUT_DIR = Path(r"F:\filesFires\edittables\by_year")
YEAR_COLUMN_CANDIDATES = ["Datetime_likv", "Дата и время ликвидации"]
SHEET_CANDIDATES = ["Запрос", "query", "Query"]


def pick_sheet(path: Path, preferred: str | None) -> str:
    xl = pd.ExcelFile(path)
    if preferred and preferred in xl.sheet_names:
        return preferred
    for name in SHEET_CANDIDATES:
        if name in xl.sheet_names:
            return name
    for name in xl.sheet_names:
        probe = pd.read_excel(path, sheet_name=name, nrows=1)
        if len(probe.columns) > 0:
            return name
    return xl.sheet_names[0]


def pick_year_column(df: pd.DataFrame, explicit: str | None) -> str:
    if explicit and explicit in df.columns:
        return explicit
    for c in YEAR_COLUMN_CANDIDATES:
        if c in df.columns:
            return c
    raise ValueError(
        f"Year datetime column not found. Tried explicit='{explicit}' and candidates={YEAR_COLUMN_CANDIDATES}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Split XLSX into yearly files by datetime column")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_XLSX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sheet", type=str, default=None)
    parser.add_argument("--year-column", type=str, default=None)
    args = parser.parse_args()

    input_xlsx: Path = args.input
    output_dir: Path = args.output_dir

    if not input_xlsx.exists():
        raise FileNotFoundError(f"Input file not found: {input_xlsx}")

    output_dir.mkdir(parents=True, exist_ok=True)

    sheet_name = pick_sheet(input_xlsx, args.sheet)
    df = pd.read_excel(input_xlsx, sheet_name=sheet_name)
    year_column = pick_year_column(df, args.year_column)

    dt = pd.to_datetime(df[year_column], errors="coerce")
    df = df.assign(__year=dt.dt.year)

    valid = df.dropna(subset=["__year"]).copy()
    valid["__year"] = valid["__year"].astype(int)

    if valid.empty:
        raise ValueError("No rows with valid year in selected datetime column")

    for year, part in valid.groupby("__year"):
        out_path = output_dir / f"{input_xlsx.stem}_{year}.xlsx"
        part.drop(columns=["__year"]).to_excel(out_path, sheet_name=sheet_name, index=False)
        print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

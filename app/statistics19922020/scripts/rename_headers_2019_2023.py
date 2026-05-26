# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

FILE_PATH = Path(r"F:\filesFires\edittables\2019-2023.xlsx")
SHEET_NAME = "Запрос"

BASE_MAP = {
    "kod_ray": "Код района",
    "kod_nasp": "Код населённого пункта",
    "name_nasp": "Наименование населённого пункта",
    "datetime_soob": "Дата и время сообщения",
    "datetime_prib": "Дата и время прибытия",
    "datetime_likv": "Дата и время ликвидации",
    "rasst": "Удалённость от ближайшей ПЧ",
    "pogib_lud": "Количество погибших в КУП",
    "pogib_deti": "Погибло детей",
    "postr_lud": "Количество травмированных в КУП",
    "postr_det": "Травмировано детей",
    "userb": "Зарегистрированный ущерб от пожара",
    "spas_lud": "Спасено на пожаре",
    "spas_jiv": "Спасено животных",
    "spas_tech": "Спасено автотракторной и другой техники",
    "spas_cen": "Спасено материальных ценностей",
    "kol_tech": "Количество записей о технике, используемой при тушении пожара",
    "kol_spec": "Количество участников тушения пожара",
    "rangp": "Количество рангов пожаров в КУП",
    "kol_ls": "Количество личного состава",
    "object_c": "Наименование объекта",
    "kod_prich": "Причина пожара (код)",
}

TOK_ADDR = ("ул.", "улица", "д.", "дом", "пр-кт", "проспект", "пер.", "переулок", "кв.", "шоссе")
TOK_COMMENT = ("ориентир", "возле", "около", "напротив", "между", "рядом")
TOK_TOOLS = ("бензорез", "шанцев", "инструмент", "лом", "топор", "лопат", "бензопил", "огнетуш")


def pick_sheet(path: Path) -> str:
    xl = pd.ExcelFile(path)
    return SHEET_NAME if SHEET_NAME in xl.sheet_names else xl.sheet_names[-1]


def profile(vals: pd.Series) -> dict:
    s = vals.dropna().astype(str).str.strip()
    s = s[s != ""]
    n = len(s)
    if n == 0:
        return {"n": 0}
    low = s.str.lower()
    addr = low.apply(lambda x: any(t in x for t in TOK_ADDR)).mean()
    comm = low.apply(lambda x: any(t in x for t in TOK_COMMENT)).mean()
    tools = low.apply(lambda x: any(t in x for t in TOK_TOOLS)).mean()
    num = pd.to_numeric(s, errors="coerce").notna().mean()
    dt = pd.to_datetime(s, errors="coerce").notna().mean()
    return {"n": n, "addr": float(addr), "comm": float(comm), "tools": float(tools), "num": float(num), "dt": float(dt)}


def infer_asotxt(pr: dict) -> str | None:
    if pr.get("n", 0) < 5:
        return None
    if pr["tools"] >= 0.35:
        return "Сведения о первичных огнетушащих средствах"
    if pr["addr"] >= 0.45 and pr["addr"] > pr["comm"] + 0.15:
        return "Адрес"
    if pr["comm"] >= 0.35 and pr["comm"] > pr["addr"] + 0.10:
        return "Комментарий к адресу"
    return None


def main() -> None:
    sheet = pick_sheet(FILE_PATH)
    df = pd.read_excel(FILE_PATH, sheet_name=sheet)
    cols = list(df.columns)
    changed = 0
    skipped = 0

    for i, c in enumerate(cols):
        raw = "" if c is None else str(c).strip()
        key = raw.lower()
        pr = profile(df.iloc[:, i])

        if key in BASE_MAP:
            target = BASE_MAP[key]
            t = target.lower()
            if "дата" in t and pr["dt"] < 0.5:
                skipped += 1
                continue
            if ("код" in t or "количество" in t) and pr["num"] < 0.6:
                skipped += 1
                continue
            if raw != target:
                cols[i] = target
                changed += 1
            continue

        if key in ("asotxt", "адрес", "сведения о первичных огнетушащих средствах", "комментарий к адресу"):
            inferred = infer_asotxt(pr)
            if inferred and raw != inferred:
                cols[i] = inferred
                changed += 1
            elif inferred is None:
                skipped += 1

    df.columns = cols
    with pd.ExcelWriter(FILE_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        df.to_excel(w, sheet_name=sheet, index=False)

    print(f"Done. changed={changed}, skipped={skipped}, sheet={sheet}")


if __name__ == "__main__":
    main()

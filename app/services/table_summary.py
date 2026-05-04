from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Sequence

import pandas as pd

from app.domain.column_matching import MANDATORY_FEATURE_REGISTRY
from app.services.shared.summary_cards import build_summary_cards

FEATURE_GROUPS = [
    {
        "id": "time",
        "label": "Р’СЂРµРјСЏ",
        "feature_ids": ["fire_date", "report_time", "arrival_time"],
    },
    {
        "id": "territory",
        "label": "РўРµСЂСЂРёС‚РѕСЂРёСЏ",
        "feature_ids": ["district", "locality", "settlement_type", "coordinates"],
    },
    {
        "id": "incident",
        "label": "РџСЂРёС‡РёРЅР° Рё РѕР±СЉРµРєС‚",
        "feature_ids": ["cause", "object_category"],
    },
    {
        "id": "response",
        "label": "Р РµР°РіРёСЂРѕРІР°РЅРёРµ",
        "feature_ids": ["distance_to_fire_station", "water_supply"],
    },
    {
        "id": "consequences",
        "label": "РџРѕСЃР»РµРґСЃС‚РІРёСЏ",
        "feature_ids": ["fatalities", "injuries", "damage"],
    },
]

_EMPTY_TEXT_VALUES = {"", "nan", "nat", "none", "null", "n/a", "na", "-", "вЂ”"}


def _normalize_text(value: Any) -> str:
    text = str(value or "").lower().replace("?", "?")
    text = re.sub(r"[_/#-]+", " ", text)
    text = re.sub(r"[^\w\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_words(value: str) -> list[str]:
    return [word for word in re.findall(r"\w+", value) if word]


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return text.lower() not in _EMPTY_TEXT_VALUES


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _format_int(value: int) -> str:
    return f"{int(value):,}".replace(",", " ")


def _format_percent(ratio: float) -> str:
    bounded = max(0.0, min(1.0, float(ratio or 0.0)))
    return f"{round(bounded * 100):.0f}%"


def _format_compact_number(value: float) -> str:
    absolute = abs(float(value or 0.0))
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.1f} РјР»РЅ".replace(".", ",")
    if absolute >= 1_000:
        return f"{value / 1_000:.1f} С‚С‹СЃ".replace(".", ",")
    if float(value).is_integer():
        return _format_int(int(value))
    return f"{value:.1f}".replace(".", ",")


def _average(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return sum(items) / len(items)


def _contains_fragment(normalized_name: str, words: Sequence[str], fragment: str) -> bool:
    return bool(
        fragment
        and (
            fragment in normalized_name
            or any(fragment in word for word in words)
        )
    )


def _column_matches_feature(column_name: str, feature: dict[str, Any]) -> bool:  # one-off
    normalized_name = _normalize_text(column_name)
    words = _extract_words(normalized_name)
    exclude_tokens = [_normalize_text(token) for token in feature.get("exclude_tokens", []) if token]

    if any(_contains_fragment(normalized_name, words, token) for token in exclude_tokens):
        return False

    for synonym in feature.get("synonyms", []):
        normalized_synonym = _normalize_text(synonym)
        if normalized_name == normalized_synonym:
            return True

    for synonym in feature.get("synonyms", []):
        synonym_tokens = _extract_words(_normalize_text(synonym))
        if len(synonym_tokens) > 1 and all(
            _contains_fragment(normalized_name, words, token) for token in synonym_tokens
        ):
            return True

    for token_set in feature.get("token_sets", []):
        normalized_tokens = [_normalize_text(token) for token in token_set if token]
        if normalized_tokens and all(
            _contains_fragment(normalized_name, words, token) for token in normalized_tokens
        ):
            return True

    return False


def _match_mandatory_features(columns: Sequence[str]) -> dict[str, dict[str, Any]]:  # one-off
    matched: dict[str, dict[str, Any]] = {}
    for feature in MANDATORY_FEATURE_REGISTRY:
        feature_id = str(feature["id"])
        matched_columns = [column_name for column_name in columns if _column_matches_feature(column_name, feature)]
        matched[feature_id] = {
            "id": feature_id,
            "label": str(feature["label"]),
            "description": str(feature["description"]),
            "columns": matched_columns,
        }
    return matched


def _coerce_number(value: Any) -> float | None:
    if not _has_value(value):
        return None

    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    if text.count(",") and text.count("."):
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")

    cleaned = re.sub(r"[^0-9.\-]+", "", text)
    if cleaned in {"", "-", ".", "-."}:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def _summarize_date_range(values: Sequence[Any]) -> str:
    if not values:
        return ""

    series = pd.to_datetime(pd.Series(list(values), dtype="object"), errors="coerce", dayfirst=True)
    valid = series.dropna()
    if valid.empty:
        return ""

    start = valid.min()
    end = valid.max()
    if pd.isna(start) or pd.isna(end):
        return ""

    if start.date() == end.date():
        return start.strftime("%d.%m.%Y")
    return f"{start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}"


def _build_feature_stat(
    feature: dict[str, Any],  # one-off
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> dict[str, Any]:  # one-off
    row_count = len(rows)
    matched_columns = list(feature.get("columns") or [])
    label = str(feature.get("label") or "РљСЂРёС‚РµСЂРёР№")

    if not matched_columns:
        return {
            "id": feature["id"],
            "label": label,
            "found": False,
            "columns": [],
            "coverage": 0.0,
            "coverage_display": "0%",
            "highlight": "РќРµ СЂР°СЃРїРѕР·РЅР°РЅРѕ",
            "summary": f"{label}: РєРѕР»РѕРЅРєР° РЅРµ СЂР°СЃРїРѕР·РЅР°РЅР° РІ С‚РµРєСѓС‰РµР№ С‚Р°Р±Р»РёС†Рµ.",
            "card_value": "РќРµС‚",
            "card_meta": f"{label} РЅРµ СЂР°СЃРїРѕР·РЅР°РЅ РІ СЃС‚СЂСѓРєС‚СѓСЂРµ С‚Р°Р±Р»РёС†С‹.",
            "unique_count": 0,
            "sum_value": 0.0,
            "positive_count": 0,
        }

    column_indexes = [columns.index(column_name) for column_name in matched_columns if column_name in columns]
    non_empty_rows = 0
    observed_values: list[Any] = []
    counter: Counter[str] = Counter()
    numeric_sum = 0.0
    numeric_count = 0
    positive_count = 0

    for row in rows:
        values = [row[index] if index < len(row) else None for index in column_indexes]
        filled_values = [value for value in values if _has_value(value)]
        if filled_values:
            non_empty_rows += 1
            observed_values.extend(filled_values[:1])

        if feature["id"] in {"district", "locality", "settlement_type", "cause", "object_category"} and filled_values:
            counter[_safe_text(filled_values[0])] += 1

        if feature["id"] == "water_supply" and filled_values:
            counter[_safe_text(filled_values[0])] += 1

        if feature["id"] in {"fatalities", "injuries", "damage", "distance_to_fire_station"} and filled_values:
            number = _coerce_number(filled_values[0])
            if number is not None:
                numeric_sum += number
                numeric_count += 1
                if number > 0:
                    positive_count += 1

    coverage = (non_empty_rows / row_count) if row_count else 0.0
    coverage_display = _format_percent(coverage)
    columns_display = ", ".join(matched_columns[:2])
    if len(matched_columns) > 2:
        columns_display += f" Рё РµС‰С‘ {_format_int(len(matched_columns) - 2)}"

    top_value = ""
    top_share = ""
    unique_count = len(counter)
    if counter:
        top_value, top_count = counter.most_common(1)[0]
        top_share = _format_percent(top_count / max(sum(counter.values()), 1))

    date_range = _summarize_date_range(observed_values) if feature["id"] == "fire_date" else ""
    average_number = (numeric_sum / numeric_count) if numeric_count else 0.0

    highlight = f"{coverage_display} Р·Р°РїРѕР»РЅРµРЅРѕ"
    summary = f"РљРѕР»РѕРЅРєРё: {columns_display}. Р—Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."
    card_value = coverage_display
    card_meta = f"{label}: Р·Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."

    if feature["id"] == "fire_date" and date_range:
        highlight = date_range
        summary = f"РџРµСЂРёРѕРґ: {date_range}. Р—Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."
        card_value = date_range
        card_meta = f"Р”Р°С‚Р° РїРѕР¶Р°СЂР° СЂР°СЃРїРѕР·РЅР°РЅР°. Р—Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ: {coverage_display}."
    elif feature["id"] in {"district", "locality", "settlement_type", "cause", "object_category"} and top_value:
        highlight = top_value
        summary = f"Р§Р°С‰Рµ РІСЃРµРіРѕ РІСЃС‚СЂРµС‡Р°РµС‚СЃСЏ В«{top_value}В» ({top_share}). Р—Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."
        card_value = top_value
        unique_meta = f"{_format_int(unique_count)} СѓРЅРёРє." if unique_count else "Р±РµР· СЂР°Р·Р±РёРІРєРё"
        card_meta = f"{unique_meta}; Р·Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."
    elif feature["id"] == "coordinates":
        highlight = f"{_format_int(len(matched_columns))} РєРѕР»РѕРЅ."
        summary = f"РќР°Р№РґРµРЅРѕ {len(matched_columns)} РєРѕР»РѕРЅРѕРє РєРѕРѕСЂРґРёРЅР°С‚. Р—Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."
        card_value = f"{_format_int(len(matched_columns))} РєРѕР»РѕРЅ."
        card_meta = f"РљРѕРѕСЂРґРёРЅР°С‚С‹ СЂР°СЃРїРѕР·РЅР°РЅС‹. Р—Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ: {coverage_display}."
    elif feature["id"] == "water_supply" and top_value:
        highlight = coverage_display
        summary = f"РџСЂРёР·РЅР°Рє РІРѕРґРѕСЃРЅР°Р±Р¶РµРЅРёСЏ РЅР°Р№РґРµРЅ. Р§Р°СЃС‚РѕРµ Р·РЅР°С‡РµРЅРёРµ: В«{top_value}В». Р—Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."
        card_value = coverage_display
        card_meta = f"Р’РѕРґРѕСЃРЅР°Р±Р¶РµРЅРёРµ СЂР°СЃРїРѕР·РЅР°РЅРѕ. Р—Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ: {coverage_display}."
    elif feature["id"] in {"report_time", "arrival_time"}:
        highlight = coverage_display
        summary = f"{label}: Р·Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."
        card_value = coverage_display
        card_meta = f"{label}: РґР°РЅРЅС‹Рµ РїСЂРёСЃСѓС‚СЃС‚РІСѓСЋС‚ РІ {coverage_display} СЃС‚СЂРѕРє."
    elif feature["id"] == "distance_to_fire_station" and numeric_count:
        highlight = _format_compact_number(average_number)
        summary = f"РЎСЂРµРґРЅРµРµ СЂР°СЃСЃС‚РѕСЏРЅРёРµ: {_format_compact_number(average_number)}. Р—Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."
        card_value = _format_compact_number(average_number)
        card_meta = f"РЈРґР°Р»С‘РЅРЅРѕСЃС‚СЊ РґРѕ РїРѕР¶Р°СЂРЅРѕР№ С‡Р°СЃС‚Рё. Р—Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ: {coverage_display}."
    elif feature["id"] in {"fatalities", "injuries"} and numeric_count:
        highlight = _format_int(int(round(numeric_sum)))
        summary = (
            f"РЎСѓРјРјР°СЂРЅРѕ: {_format_int(int(round(numeric_sum)))}. "
            f"Р’ {_format_int(positive_count)} СЃС‚СЂРѕРєР°С… РµСЃС‚СЊ РЅРµРЅСѓР»РµРІС‹Рµ Р·РЅР°С‡РµРЅРёСЏ."
        )
        card_value = _format_int(int(round(numeric_sum)))
        card_meta = f"{label}: РЅРµРЅСѓР»РµРІС‹Рµ Р·РЅР°С‡РµРЅРёСЏ РІ {_format_int(positive_count)} СЃС‚СЂРѕРєР°С…."
    elif feature["id"] == "damage" and numeric_count:
        highlight = _format_compact_number(numeric_sum)
        summary = f"РЎСѓРјРјР°СЂРЅС‹Р№ СѓС‰РµСЂР±: {_format_compact_number(numeric_sum)}. Р—Р°РїРѕР»РЅРµРЅРѕ {coverage_display} СЃС‚СЂРѕРє."
        card_value = _format_compact_number(numeric_sum)
        card_meta = f"РЈС‰РµСЂР± СЂР°СЃРїРѕР·РЅР°РЅ. Р—Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ: {coverage_display}."

    return {
        "id": feature["id"],
        "label": label,
        "found": True,
        "columns": matched_columns,
        "coverage": coverage,
        "coverage_display": coverage_display,
        "highlight": highlight,
        "summary": summary,
        "card_value": card_value,
        "card_meta": card_meta,
        "unique_count": unique_count,
        "sum_value": numeric_sum,
        "positive_count": positive_count,
    }


def _first_found(feature_stats: dict[str, dict[str, Any]], feature_ids: Sequence[str]) -> dict[str, Any] | None:  # one-off
    for feature_id in feature_ids:
        stat = feature_stats.get(feature_id)
        if stat and stat["found"]:
            return stat
    return None

# intentionally separate from access_points/presentation.py::_build_summary_cards and
# forecast_risk/reliability.py::_build_summary_cards:
# table-summary cards describe schema/coverage readiness, not risk prioritization.


def _build_summary_cards(
    row_count: int,
    column_count: int,
    feature_stats: dict[str, dict[str, Any]],  # one-off
) -> list[dict[str, str]]:
    mandatory_total = len(MANDATORY_FEATURE_REGISTRY)
    found_total = sum(1 for item in feature_stats.values() if item["found"])
    average_fill = _average(item["coverage"] for item in feature_stats.values() if item["found"])

    cards: list[dict[str, str]] = [
        {
            "label": "Р Р°Р·РјРµСЂ",
            "value": f"{_format_int(row_count)} x {_format_int(column_count)}",
            "meta": "РЎС‚СЂРѕРєРё x РєРѕР»РѕРЅРєРё РІ С‚РµРєСѓС‰РµРј РїСЂРѕСЃРјРѕС‚СЂРµ С‚Р°Р±Р»РёС†С‹.",
        },
        {
            "label": "РћР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ РєСЂРёС‚РµСЂРёРё",
            "value": f"{_format_int(found_total)} / {_format_int(mandatory_total)}",
            "meta": "РљСЂРёС‚РµСЂРёРё РёР· СЃС†РµРЅР°СЂРёСЏ РѕС‡РёСЃС‚РєРё, РєРѕС‚РѕСЂС‹Рµ СѓРґР°Р»РѕСЃСЊ СЂР°СЃРїРѕР·РЅР°С‚СЊ РІ СЌС‚РѕР№ С‚Р°Р±Р»РёС†Рµ.",
        },
        {
            "label": "Р—Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ РєР»СЋС‡РµРІС‹С… РїРѕР»РµР№",
            "value": _format_percent(average_fill),
            "meta": "РЎСЂРµРґРЅСЏСЏ Р·Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ СЂР°СЃРїРѕР·РЅР°РЅРЅС‹С… РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РєСЂРёС‚РµСЂРёРµРІ.",
        },
    ]

    date_stat = feature_stats.get("fire_date")
    if date_stat:
        cards.append(
            {
                "label": "РџРµСЂРёРѕРґ",
                "value": date_stat["card_value"],
                "meta": date_stat["card_meta"],
            }
        )

    territory_stat = _first_found(feature_stats, ["district", "locality", "settlement_type"])
    if territory_stat:
        cards.append(
            {
                "label": "РўРµСЂСЂРёС‚РѕСЂРёСЏ",
                "value": territory_stat["card_value"],
                "meta": territory_stat["card_meta"],
            }
        )

    cause_stat = _first_found(feature_stats, ["cause", "object_category"])
    if cause_stat:
        cards.append(
            {
                "label": "РџСЂРёС‡РёРЅР° / РѕР±СЉРµРєС‚",
                "value": cause_stat["card_value"],
                "meta": cause_stat["card_meta"],
            }
        )

    return build_summary_cards(cards)


def _build_group_cards(feature_stats: dict[str, dict[str, Any]]) -> list[dict[str, str]]:  # one-off
    cards: list[dict[str, str]] = []
    for group in FEATURE_GROUPS:
        group_stats = [feature_stats[feature_id] for feature_id in group["feature_ids"] if feature_id in feature_stats]
        found_stats = [item for item in group_stats if item["found"]]
        found_count = len(found_stats)
        total_count = len(group_stats)

        if found_stats:
            highlights = [f"{item['label']}: {item['highlight']}" for item in found_stats[:2]]
            if len(found_stats) > 2:
                highlights.append(f"Р•С‰С‘ {_format_int(len(found_stats) - 2)} РєСЂРёС‚РµСЂРёСЏ СЂР°СЃРїРѕР·РЅР°РЅРѕ.")
            meta = " ".join(highlights)
        else:
            meta = "РљСЂРёС‚РµСЂРёРё СЌС‚РѕР№ РіСЂСѓРїРїС‹ РїРѕРєР° РЅРµ СЂР°СЃРїРѕР·РЅР°РЅС‹ РІ СЃС‚СЂСѓРєС‚СѓСЂРµ С‚Р°Р±Р»РёС†С‹."

        cards.append(
            {
                "label": group["label"],
                "value": f"{_format_int(found_count)} / {_format_int(total_count)}",
                "meta": meta,
            }
        )
    return cards


def build_table_summary(table_name: str, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> dict[str, Any]:  # one-off
    del table_name

    column_list = [str(column) for column in (columns or [])]
    row_list = list(rows or [])
    matched_features = _match_mandatory_features(column_list)
    feature_stats = {
        feature_id: _build_feature_stat(feature, column_list, row_list)
        for feature_id, feature in matched_features.items()
    }

    found_total = sum(1 for item in feature_stats.values() if item["found"])
    mandatory_total = len(MANDATORY_FEATURE_REGISTRY)
    average_fill = _average(item["coverage"] for item in feature_stats.values() if item["found"])

    lead = (
        f"Р Р°СЃРїРѕР·РЅР°РЅРѕ {_format_int(found_total)} РёР· {_format_int(mandatory_total)} РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РєСЂРёС‚РµСЂРёРµРІ РѕС‡РёСЃС‚РєРё. "
        f"РЎСЂРµРґРЅСЏСЏ Р·Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ РєР»СЋС‡РµРІС‹С… РїРѕР»РµР№: {_format_percent(average_fill)}."
    )
    criteria_lead = (
        "РЎРЅР°С‡Р°Р»Р° РєРѕСЂРѕС‚РєРѕ РІРёРґРЅРѕ, РєР°РєРёРµ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ РєСЂРёС‚РµСЂРёРё СЂРµР°Р»СЊРЅРѕ РµСЃС‚СЊ РІ С‚Р°Р±Р»РёС†Рµ, "
        "Р° СѓР¶Рµ РїРѕС‚РѕРј РјРѕР¶РЅРѕ СѓС…РѕРґРёС‚СЊ РІ РїРѕР»РЅС‹Р№ РїСЂРѕСЃРјРѕС‚СЂ СЃС‚СЂРѕРє."
    )

    return {
        "lead": lead,
        "criteria_lead": criteria_lead,
        "cards": _build_summary_cards(len(row_list), len(column_list), feature_stats),
        "groups": _build_group_cards(feature_stats),
    }


def build_table_page_summary(
    table_name: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    total_rows: int,
    page_row_start: int,
    page_row_end: int,
) -> dict[str, Any]:  # one-off
    summary = build_table_summary(table_name, columns, rows)
    displayed_rows = len(rows or [])

    if total_rows <= 0:
        scope_note = "Р’ С‚Р°Р±Р»РёС†Рµ РїРѕРєР° РЅРµС‚ СЃС‚СЂРѕРє."
    elif total_rows <= displayed_rows:
        scope_note = "РЎРІРѕРґРєР° СЂР°СЃСЃС‡РёС‚Р°РЅР° РїРѕ РІСЃРµР№ С‚Р°Р±Р»РёС†Рµ."
    elif displayed_rows:
        scope_note = (
            f"Р­С‚Р° СЃРІРѕРґРєР° РѕС‚РЅРѕСЃРёС‚СЃСЏ С‚РѕР»СЊРєРѕ Рє С‚РµРєСѓС‰РµР№ СЃС‚СЂР°РЅРёС†Рµ РїСЂРµРґРїСЂРѕСЃРјРѕС‚СЂР°: "
            f"СЃС‚СЂРѕРєРё {page_row_start}-{page_row_end} РёР· { _format_int(total_rows) }."
        )
    else:
        scope_note = f"Р’ С‚Р°Р±Р»РёС†Рµ РЅР°Р№РґРµРЅРѕ { _format_int(total_rows) } СЃС‚СЂРѕРє."

    summary["scope_note"] = scope_note
    return summary


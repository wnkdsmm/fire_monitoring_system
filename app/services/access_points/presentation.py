from __future__ import annotations

from typing import Any, Sequence

from app.domain.access_points_metadata import WATCH_RISK_THRESHOLD
from config.constants import TOP_POINT_CARD_COUNT
from app.services.shared.data_utils import _clean_text, _unique_non_empty
from app.services.shared.formatting import _format_integer
from app.services.shared.summary_cards import build_summary_cards

from .constants import ACCESS_POINTS_DESCRIPTION, ACCESS_POINTS_TITLE, MAX_NOTES
from .types import AccessPointCard, AccessPointFilters, AccessPointPresentation, OptionItem, PointData, PresentationSummary


def _selection_label(options: Sequence[OptionItem], selected_value: str, fallback: str) -> str:
    normalized = str(selected_value or "").strip()
    for option in options:
        if str(option.get("value") or "") == normalized:
            return str(option.get("label") or fallback)
    return fallback


def _build_filter_description(selected_table_label: str, selected_district_label: str, selected_year_label: str) -> str:
    del selected_year_label
    parts = [f"РЎвЂљР В°Р В±Р В»Р С‘РЎвЂ Р В°: {selected_table_label}"]
    if selected_district_label and selected_district_label != "Р вЂ™РЎРѓР Вµ РЎР‚Р В°Р в„–Р С•Р Р…РЎвЂ№":
        parts.append(f"РЎР‚Р В°Р в„–Р С•Р Р…: {selected_district_label}")
    return " | ".join(parts)


def _build_top_point_lead(top_point: PointData | None) -> str:
    if not top_point:
        return "Р СњР ВµР Т‘Р С•РЎРѓРЎвЂљР В°РЎвЂљР С•РЎвЂЎР Р…Р С• Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ Р Р†РЎвЂ№Р Т‘Р ВµР В»Р С‘РЎвЂљРЎРЉ Р С—РЎР‚Р С•Р В±Р В»Р ВµР СР Р…РЎС“РЎР‹ РЎвЂљР С•РЎвЂЎР С”РЎС“."

    explanation = _clean_text(top_point.get("human_readable_explanation") or top_point.get("explanation"))
    if explanation:
        return explanation

    label = _clean_text(top_point.get("label")) or "Р СћР С•РЎвЂЎР С”Р В°"
    severity_band = _clean_text(top_point.get("severity_band")) or "РЎРѓРЎР‚Р ВµР Т‘Р Р…Р С‘Р в„–"
    score_display = str(top_point.get("total_score_display") or top_point.get("score_display") or "0")
    typology_label = _clean_text(top_point.get("typology_label")) or "Р С—РЎР‚Р С‘Р С•РЎР‚Р С‘РЎвЂљР ВµРЎвЂљР Р…Р В°РЎРЏ РЎвЂљР С•РЎвЂЎР С”Р В°"
    return f"{label} Р С—Р С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ {severity_band} РЎР‚Р С‘РЎРѓР С” РЎРѓР С• score {score_display} Р С‘Р В· 100 Р С‘ Р С—Р С•Р С—Р В°Р Т‘Р В°Р ВµРЎвЂљ Р Р† Р Р†Р ВµРЎР‚РЎвЂ¦ РЎР‚Р ВµР в„–РЎвЂљР С‘Р Р…Р С–Р В° Р С”Р В°Р С” {typology_label}."

# intentionally separate from forecasting/presentation.py::_build_summary and
# ml_model/training/presentation_training.py::_build_summary:
# access-points summary has its own point-risk and verification semantics.


def _build_summary(
    rows: Sequence[PointData],
    *,
    selected_table_label: str,
    selected_district_label: str,
    selected_year_label: str,
    limit: int,
    total_incidents: int,
    incomplete_points: Sequence[PointData],
) -> PresentationSummary:
    top_point = rows[0] if rows else None
    critical_count = sum(1 for row in rows if str(row.get("severity_band_code") or "") == "critical")
    high_count = sum(1 for row in rows if str(row.get("severity_band_code") or "") in {"high", "critical"})
    medium_count = sum(1 for row in rows if str(row.get("severity_band_code") or "") == "medium")
    uncertainty_count = sum(1 for row in rows if row.get("uncertainty_flag"))
    return {
        "selected_table_label": selected_table_label,
        "selected_district_label": selected_district_label,
        "selected_year_label": selected_year_label,
        "limit_display": _format_integer(limit),
        "total_points_display": _format_integer(len(rows)),
        "total_incidents_display": _format_integer(total_incidents),
        "critical_points_display": _format_integer(critical_count),
        "high_points_display": _format_integer(high_count),
        "medium_points_display": _format_integer(medium_count),
        "review_points_display": _format_integer(high_count),
        "incomplete_points_display": _format_integer(len(incomplete_points)),
        "uncertainty_points_display": _format_integer(uncertainty_count),
        "top_point_label": str((top_point or {}).get("label") or "-"),
        "top_point_score_display": str((top_point or {}).get("total_score_display") or (top_point or {}).get("score_display") or "0"),
        "top_point_severity_band": str((top_point or {}).get("severity_band") or "Р Р…Р ВµРЎвЂљ Р С•РЎвЂ Р ВµР Р…Р С”Р С‘"),
        "top_point_priority_label": str((top_point or {}).get("priority_label") or "Р СњР ВµРЎвЂљ Р С•РЎвЂ Р ВµР Р…Р С”Р С‘"),
        "filter_description": _build_filter_description(
            selected_table_label=selected_table_label,
            selected_district_label=selected_district_label,
            selected_year_label=selected_year_label,
        ),
    }

# intentionally separate from forecast_risk/reliability.py::_build_summary_cards and
# table_summary.py::_build_summary_cards:
# access-points cards are incident-point prioritization widgets.


def _build_summary_cards(
    rows: Sequence[PointData],
    *,
    total_incidents: int,
    incomplete_points: Sequence[PointData],
) -> list[AccessPointCard]:
    top_point = rows[0] if rows else None
    high_or_above_count = sum(1 for row in rows if str(row.get("severity_band_code") or "") in {"high", "critical"})
    critical_count = sum(1 for row in rows if str(row.get("severity_band_code") or "") == "critical")
    uncertainty_count = sum(1 for row in rows if row.get("uncertainty_flag"))
    return build_summary_cards(
        [
            {
                "label": "Р Р€Р Р…Р С‘Р С”Р В°Р В»РЎРЉР Р…РЎвЂ№Р Вµ РЎвЂљР С•РЎвЂЎР С”Р С‘",
                "value": _format_integer(len(rows)),
                "meta": f"Р ВР Р…РЎвЂ Р С‘Р Т‘Р ВµР Р…РЎвЂљР С•Р Р† Р С—Р С•РЎРѓР В»Р Вµ РЎвЂћР С‘Р В»РЎРЉРЎвЂљРЎР‚Р С•Р Р†: {_format_integer(total_incidents)}",
                "tone": "normal",
            },
            {
                "label": "Р вЂ™РЎвЂ№РЎРѓР С•Р С”Р С‘Р в„– РЎР‚Р С‘РЎРѓР С”",
                "value": _format_integer(high_or_above_count),
                "meta": f"Р С™РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С‘РЎвЂ¦: {_format_integer(critical_count)}",
                "tone": "critical" if critical_count else ("warning" if high_or_above_count else "normal"),
            },
            {
                "label": "Р СћР С•РЎвЂЎР С”Р В° Р Р†РІР‚С›РІР‚вЂњ1",
                "value": str((top_point or {}).get("total_score_display") or (top_point or {}).get("score_display") or "0"),
                "meta": str((top_point or {}).get("label") or "Р В Р ВµР в„–РЎвЂљР С‘Р Р…Р С– Р С—Р С•РЎРЏР Р†Р С‘РЎвЂљРЎРѓРЎРЏ Р С—Р С•РЎРѓР В»Р Вµ РЎР‚Р В°РЎРѓРЎвЂЎРЎвЂРЎвЂљР В°"),
                "tone": str((top_point or {}).get("tone") or "normal"),
            },
            {
                "label": "Р СњРЎС“Р В¶Р Р…Р В° Р Р†Р ВµРЎР‚Р С‘РЎвЂћР С‘Р С”Р В°РЎвЂ Р С‘РЎРЏ",
                "value": _format_integer(max(len(incomplete_points), uncertainty_count)),
                "meta": "Р СћР С•РЎвЂЎР С”Р С‘, Р С–Р Т‘Р Вµ risk score РЎвЂљРЎР‚Р ВµР В±РЎС“Р ВµРЎвЂљ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р С‘ Р С—Р С•Р В»Р Р…Р С•РЎвЂљРЎвЂ№ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦",
                "tone": "watch" if incomplete_points or uncertainty_count else "normal",
            },
        ]
    )


def _build_notes(
    metadata_notes: Sequence[str],
    input_notes: Sequence[str],
    rows: Sequence[PointData],
    incomplete_points: Sequence[PointData],
) -> list[str]:
    notes: list[str] = []
    if rows:
        broad_points = sum(1 for row in rows if str(row.get("entity_code") or "") in {"territory", "district", "unknown"})
        if broad_points:
            notes.append(
                f"Р вЂќР В»РЎРЏ {_format_integer(broad_points)} РЎвЂљР С•РЎвЂЎР ВµР С” РЎР‚Р ВµР в„–РЎвЂљР С‘Р Р…Р С– Р С—Р С•РЎРѓРЎвЂљРЎР‚Р С•Р ВµР Р… Р Р…Р В° fallback-РЎРѓРЎС“РЎвЂ°Р Р…Р С•РЎРѓРЎвЂљР С‘ РЎС“РЎР‚Р С•Р Р†Р Р…РЎРЏ Р Р…Р В°РЎРѓР ВµР В»РЎвЂР Р…Р Р…Р С•Р С–Р С• Р С—РЎС“Р Р…Р С”РЎвЂљР В°, РЎвЂљР ВµРЎР‚РЎР‚Р С‘РЎвЂљР С•РЎР‚Р С‘Р С‘ Р С‘Р В»Р С‘ РЎР‚Р В°Р в„–Р С•Р Р…Р В°, Р С—Р С•РЎвЂљР С•Р СРЎС“ РЎвЂЎРЎвЂљР С• Р В±Р С•Р В»Р ВµР Вµ РЎвЂљР С•РЎвЂЎР Р…РЎвЂ№Р в„– Р В°Р Т‘РЎР‚Р ВµРЎРѓ/Р С•Р В±РЎР‰Р ВµР С”РЎвЂљ Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р…."
            )
        if len(rows) < TOP_POINT_CARD_COUNT:
            notes.append(
                "Р СџР С•РЎРѓР В»Р Вµ Р Р†РЎвЂ№Р В±РЎР‚Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ РЎвЂћР С‘Р В»РЎРЉРЎвЂљРЎР‚Р С•Р Р† Р С•РЎРѓРЎвЂљР В°Р В»Р С•РЎРѓРЎРЉ Р СР В°Р В»Р С• РЎС“Р Р…Р С‘Р С”Р В°Р В»РЎРЉР Р…РЎвЂ№РЎвЂ¦ РЎвЂљР С•РЎвЂЎР ВµР С”, Р С—Р С•РЎРЊРЎвЂљР С•Р СРЎС“ ranking РЎРѓРЎвЂљР С•Р С‘РЎвЂљ РЎвЂљРЎР‚Р В°Р С”РЎвЂљР С•Р Р†Р В°РЎвЂљРЎРЉ Р С”Р В°Р С” Р С•РЎР‚Р С‘Р ВµР Р…РЎвЂљР С‘РЎР‚ Р Т‘Р В»РЎРЏ Р С—РЎР‚Р С•РЎРѓР СР С•РЎвЂљРЎР‚Р В°, Р В° Р Р…Р Вµ Р С”Р В°Р С” РЎС“РЎРѓРЎвЂљР С•Р в„–РЎвЂЎР С‘Р Р†РЎС“РЎР‹ РЎвЂљР С‘Р С—Р С•Р В»Р С•Р С–Р С‘РЎР‹."
            )
        max_score = max(float(row.get("total_score") or row.get("score") or 0.0) for row in rows)
        if max_score < WATCH_RISK_THRESHOLD:
            notes.append(
                "Р вЂќР В°Р В¶Р Вµ Р Р†Р ВµРЎР‚РЎвЂ¦Р Р…РЎРЏРЎРЏ РЎвЂЎР В°РЎРѓРЎвЂљРЎРЉ РЎР‚Р ВµР в„–РЎвЂљР С‘Р Р…Р С–Р В° РЎРѓР ВµР в„–РЎвЂЎР В°РЎРѓ РЎРѓР С”Р С•РЎР‚Р ВµР Вµ Р С—РЎР‚Р С• Р Р…Р В°Р В±Р В»РЎР‹Р Т‘Р ВµР Р…Р С‘Р Вµ, РЎвЂЎР ВµР С Р С—РЎР‚Р С• Р С”РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р Вµ Р С—Р ВµРЎР‚Р ВµРЎР‚Р В°РЎРѓР С—РЎР‚Р ВµР Т‘Р ВµР В»Р ВµР Р…Р С‘Р Вµ РЎРѓР С‘Р В»: РЎРЏР Р†Р Р…РЎвЂ№РЎвЂ¦ Р Р†РЎвЂ№Р В±РЎР‚Р С•РЎРѓР С•Р Р† Р С—Р С• score Р Р…Р Вµ Р Р†Р С‘Р Т‘Р Р…Р С•."
            )
    else:
        notes.append("Р СџР С• Р Р†РЎвЂ№Р В±РЎР‚Р В°Р Р…Р Р…Р С•Р СРЎС“ РЎРѓРЎР‚Р ВµР В·РЎС“ Р Р…Р Вµ Р Р…Р В°РЎв‚¬Р В»Р С•РЎРѓРЎРЉ Р С‘Р Р…РЎвЂ Р С‘Р Т‘Р ВµР Р…РЎвЂљР С•Р Р† Р Т‘Р В»РЎРЏ Р С—Р С•РЎРѓРЎвЂљРЎР‚Р С•Р ВµР Р…Р С‘РЎРЏ РЎР‚Р ВµР в„–РЎвЂљР С‘Р Р…Р С–Р В° Р С—РЎР‚Р С•Р В±Р В»Р ВµР СР Р…РЎвЂ№РЎвЂ¦ РЎвЂљР С•РЎвЂЎР ВµР С”.")

    for item in list(metadata_notes)[:3]:
        text = _clean_text(item)
        if text:
            notes.append(f"Р СљР ВµРЎвЂљР В°Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ: {text}")
    for item in list(input_notes)[:3]:
        text = _clean_text(item)
        if text:
            notes.append(f"Р вЂ”Р В°Р С–РЎР‚РЎС“Р В·Р С”Р В° Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦: {text}")
    return _unique_non_empty(notes)[:MAX_NOTES]


def _empty_access_points_data(
    *,
    filters: AccessPointFilters,
    summary: PresentationSummary,
    notes: Sequence[str] | None = None,
    bootstrap_mode: str = "resolved",
) -> AccessPointPresentation:
    resolved_notes = _unique_non_empty(
        list(notes or []) or ["Р СњР ВµР Т‘Р С•РЎРѓРЎвЂљР В°РЎвЂљР С•РЎвЂЎР Р…Р С• Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ Р Т‘Р В»РЎРЏ Р С—Р С•РЎРѓРЎвЂљРЎР‚Р С•Р ВµР Р…Р С‘РЎРЏ РЎР‚Р ВµР в„–РЎвЂљР С‘Р Р…Р С–Р В° Р С—РЎР‚Р С•Р В±Р В»Р ВµР СР Р…РЎвЂ№РЎвЂ¦ РЎвЂљР С•РЎвЂЎР ВµР С”."]
    )[:MAX_NOTES]
    return {
        "bootstrap_mode": bootstrap_mode,
        "loading": bootstrap_mode == "deferred",
        "has_data": False,
        "title": ACCESS_POINTS_TITLE,
        "model_description": ACCESS_POINTS_DESCRIPTION,
        "filters": filters,
        "summary": summary,
        "summary_cards": _build_summary_cards([], total_incidents=0, incomplete_points=[]),
        "top_point_label": "-",
        "top_point_explanation": "Р СњР ВµР Т‘Р С•РЎРѓРЎвЂљР В°РЎвЂљР С•РЎвЂЎР Р…Р С• Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ Р Т‘Р В»РЎРЏ Р Р†РЎвЂ№Р Т‘Р ВµР В»Р ВµР Р…Р С‘РЎРЏ Р С—РЎР‚Р С‘Р С•РЎР‚Р С‘РЎвЂљР ВµРЎвЂљР Р…РЎвЂ№РЎвЂ¦ РЎвЂљР С•РЎвЂЎР ВµР С”.",
        "points": [],
        "top_points": [],
        "score_distribution": {
            "average_score_display": "0",
            "median_score_display": "0",
            "bands": [],
            "buckets": [],
        },
        "reason_breakdown": [],
        "incomplete_points": [],
        "typology": [],
        "uncertainty_notes": [],
        "notes": resolved_notes,
    }

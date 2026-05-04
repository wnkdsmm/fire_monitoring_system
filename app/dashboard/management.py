from __future__ import annotations

from typing import Any

from app.services.executive_brief import (
    build_executive_brief_from_risk_payload,
    empty_executive_brief,
)
from app.services.forecast_risk.core import build_decision_support_payload
from config.constants import PRIORITY_HORIZON_DAYS

from .types import DashboardSection, DashboardTableRef, DistributionResult, SummaryResult


def _build_management_snapshot_payload(
    brief: dict[str, Any],  # one-off
    *,
    territories: list[dict[str, str]] | None = None,
    actions: list[dict[str, str]] | None = None,
    notes: list[str] | None = None,
    priority_horizon_days: int = PRIORITY_HORIZON_DAYS,
) -> dict[str, Any]:  # one-off
    resolved_notes = list(notes if notes is not None else brief.get("notes") or [])
    return {
        "summary_line": brief["lead"],
        "priority_territory_label": brief["top_territory_label"],
        "priority_reason": brief["priority_reason"],
        "priority_tone": brief["priority_tone"],
        "confidence_label": brief["confidence_label"],
        "confidence_score_display": brief["confidence_score_display"],
        "confidence_tone": brief["confidence_tone"],
        "confidence_summary": brief["confidence_summary"],
        "recommended_action_label": brief["action_label"],
        "recommended_action_detail": brief["action_detail"],
        "brief_cards": list(brief["cards"]),
        "brief": brief,
        "territories": list(territories or []),
        "actions": list(actions or []),
        "notes": resolved_notes,
        "priority_horizon_days": priority_horizon_days,
        "export_title": brief["export_title"],
        "export_excerpt": brief["export_excerpt"],
        "export_text": "",
    }


def _empty_management_snapshot(priority_horizon_days: int = PRIORITY_HORIZON_DAYS) -> dict[str, Any]:  # one-off
    return _build_management_snapshot_payload(
        empty_executive_brief(),
        priority_horizon_days=priority_horizon_days,
    )


def _build_management_snapshot(
    selected_tables: list[DashboardTableRef],
    selected_year: int | None,
    summary: SummaryResult,
    trend: DashboardSection,
    cause_overview: DistributionResult,
    district_widget: DistributionResult,
    planning_horizon_days: int = PRIORITY_HORIZON_DAYS,
) -> dict[str, Any]:  # one-off
    if not selected_tables:
        return _empty_management_snapshot(priority_horizon_days=planning_horizon_days)
    tone_map = {"high": "fire", "medium": "sand", "low": "sky"}
    try:
        risk_payload = build_decision_support_payload(
            source_tables=[table["name"] for table in selected_tables],
            selected_district="all",
            selected_cause="all",
            selected_object_category="all",
            history_window="all",
            planning_horizon_days=planning_horizon_days,
            selected_year=selected_year,
            include_geo_prediction=False,
            include_historical_validation=False,
        )
    except Exception as exc:
        fallback = _empty_management_snapshot(priority_horizon_days=planning_horizon_days)
        fallback["summary_line"] = "РљСЂР°С‚РєРёР№ С‚РµСЂСЂРёС‚РѕСЂРёР°Р»СЊРЅС‹Р№ РІС‹РІРѕРґ РІСЂРµРјРµРЅРЅРѕ РЅРµРґРѕСЃС‚СѓРїРµРЅ; РЅРёР¶Рµ РѕСЃС‚Р°СЋС‚СЃСЏ Р±Р°Р·РѕРІС‹Рµ РїРѕРєР°Р·Р°С‚РµР»Рё Рё РіСЂР°С„РёРєРё РїРѕ РІС‹Р±СЂР°РЅРЅРѕРјСѓ СЃСЂРµР·Сѓ."
        fallback["notes"] = [f"РљРѕСЂРѕС‚РєРёР№ РІС‹РІРѕРґ РІСЂРµРјРµРЅРЅРѕ РЅРµРґРѕСЃС‚СѓРїРµРЅ: {exc}"]
        fallback["brief"]["notes"] = list(fallback["notes"])
        return fallback

    passport = risk_payload.get("quality_passport") or {}
    risk_territories = risk_payload.get("territories") or []
    dominant_cause = cause_overview["items"][0] if cause_overview.get("items") else None
    top_district = district_widget["items"][0] if district_widget.get("items") else None
    top_territory = risk_territories[0] if risk_territories else None

    territories: list[dict[str, str]] = []
    for item in risk_territories[:3]:
        components = item.get("component_scores") or []
        top_component = components[0] if components else {}
        territories.append(
            {
                "label": item.get("label") or "РўРµСЂСЂРёС‚РѕСЂРёСЏ",
                "risk_display": item.get("risk_display") or "0 / 100",
                "risk_class_label": item.get("risk_class_label") or "РќРµС‚ РѕС†РµРЅРєРё",
                "priority_label": item.get("priority_label") or "РџР»Р°РЅРѕРІРѕРµ РЅР°Р±Р»СЋРґРµРЅРёРµ",
                "risk_tone": tone_map.get(item.get("risk_tone"), "sky"),
                "drivers_display": item.get("drivers_display") or "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РґР°РЅРЅС‹С… РґР»СЏ РѕР±СЉСЏСЃРЅРµРЅРёСЏ РїСЂРёРѕСЂРёС‚РµС‚Р°.",
                "action_label": item.get("action_label") or "РћСЃС‚Р°РІРёС‚СЊ С‚РµСЂСЂРёС‚РѕСЂРёСЋ РІ РїР»Р°РЅРѕРІРѕРј РЅР°Р±Р»СЋРґРµРЅРёРё",
                "action_hint": item.get("action_hint") or "РЎРІРµСЂСЊС‚Рµ РїСЂРёРѕСЂРёС‚РµС‚ СЃ Р»РѕРєР°Р»СЊРЅРѕР№ РѕРїРµСЂР°С‚РёРІРЅРѕР№ РѕР±СЃС‚Р°РЅРѕРІРєРѕР№.",
                "context_label": item.get("settlement_context_label") or "РљРѕРЅС‚РµРєСЃС‚ РЅРµ СѓРєР°Р·Р°РЅ",
                "last_fire_display": item.get("last_fire_display") or "-",
                "top_component_label": top_component.get("label") or "РќРµС‚ РґРѕРјРёРЅРёСЂСѓСЋС‰РµРіРѕ С„Р°РєС‚РѕСЂР°",
                "top_component_score": top_component.get("score_display") or "0 / 100",
            }
        )

    actions: list[dict[str, str]] = []
    if top_territory:
        for recommendation in (top_territory.get("recommendations") or [])[:3]:
            label = str(recommendation.get("label") or "").strip()
            detail = str(recommendation.get("detail") or "").strip()
            if label and detail:
                actions.append({"label": label, "detail": detail})

    if not actions:
        if dominant_cause:
            actions.append(
                {
                    "label": "РЎРґРµР»Р°С‚СЊ Р°РґСЂРµСЃРЅСѓСЋ РїСЂРѕС„РёР»Р°РєС‚РёРєСѓ РїРѕ РіР»Р°РІРЅРѕР№ РїСЂРёС‡РёРЅРµ",
                    "detail": f"В текущем срезе чаще всего фиксируется причина «{dominant_cause['label']}» ({dominant_cause['value_display']}).",
                }
            )
        if top_district:
            actions.append(
                {
                    "label": "РЈСЃРёР»РёС‚СЊ РєРѕРЅС‚СЂРѕР»СЊ РІ Р»РёРґРёСЂСѓСЋС‰РµР№ С‚РµСЂСЂРёС‚РѕСЂРёРё",
                    "detail": f"{top_district['label']} РѕСЃС‚Р°РµС‚СЃСЏ Р»РёРґРµСЂРѕРј РїРѕ С‡РёСЃР»Сѓ РїРѕР¶Р°СЂРѕРІ: {top_district['value_display']}.",
                }
            )
        if trend.get("direction") == "up":
            actions.append(
                {
                    "label": "РџСЂРѕРІРµСЂРёС‚СЊ РёСЃС‚РѕС‡РЅРёРєРё СЂРѕСЃС‚Р° Рє РїСЂРѕС€Р»РѕРјСѓ РіРѕРґСѓ",
                    "detail": f"{trend.get('description') or 'Динамика требует уточнения.'} Изменение: {trend.get('delta_display') or '0'}.",
                }
            )

    if not actions:
        actions.append(
            {
                "label": "РЎРѕС…СЂР°РЅРёС‚СЊ РїР»Р°РЅРѕРІРѕРµ РЅР°Р±Р»СЋРґРµРЅРёРµ",
                "detail": "Р РµР·РєРѕРіРѕ СѓС…СѓРґС€РµРЅРёСЏ РїРѕ С‚РµРєСѓС‰РµРјСѓ СЃСЂРµР·Сѓ РЅРµ РІРёРґРЅРѕ, РЅРѕ РїСЂРёРѕСЂРёС‚РµС‚РЅС‹Рµ С‚РµСЂСЂРёС‚РѕСЂРёРё СЃС‚РѕРёС‚ РґРµСЂР¶Р°С‚СЊ РІ СЂРµРіСѓР»СЏСЂРЅРѕРј РєРѕРЅС‚СЂРѕР»Рµ.",
            }
        )

    confidence_summary = passport.get("validation_summary") or "РџРѕСЃР»Рµ Р·Р°РіСЂСѓР·РєРё РґР°РЅРЅС‹С… Р·РґРµСЃСЊ РїРѕСЏРІРёС‚СЃСЏ СѓСЂРѕРІРµРЅСЊ РґРѕРІРµСЂРёСЏ Рє СЃРІРѕРґРєРµ."
    horizon_note = (
        f"Р’Р°Р¶РЅРѕ: СЌС‚Рѕ РєСЂР°С‚РєРёР№ С‚РµСЂСЂРёС‚РѕСЂРёР°Р»СЊРЅС‹Р№ РїСЂРёРѕСЂРёС‚РµС‚ РЅР° Р±Р»РёР¶Р°Р№С€РёРµ {planning_horizon_days} РґРЅРµР№, "
        "Р° РЅРµ РєР°Р»РµРЅРґР°СЂСЊ СЂРёСЃРєР° РїРѕ РґР°С‚Р°Рј Рё РЅРµ РїСЂРѕРіРЅРѕР· РѕР¶РёРґР°РµРјРѕРіРѕ С‡РёСЃР»Р° РїРѕР¶Р°СЂРѕРІ."
    )
    notes: list[str] = []
    for note in (risk_payload.get("notes") or [])[:3]:
        text = str(note or "").strip()
        if text and text not in notes:
            notes.append(text)
    if horizon_note not in notes:
        notes.insert(0, horizon_note)
    if len(notes) == 1 and confidence_summary not in notes:
        notes.append(confidence_summary)

    brief = build_executive_brief_from_risk_payload(risk_payload, notes=notes)
    if horizon_note not in brief["notes"]:
        brief["notes"] = [horizon_note, *list(brief["notes"] or [])][:3]
    brief["export_excerpt"] = (
        f"{brief['export_excerpt']} РџСЂРёРѕСЂРёС‚РµС‚ Рё РґРµР№СЃС‚РІРёСЏ СЂР°СЃСЃС‡РёС‚Р°РЅС‹ РЅР° Р±Р»РёР¶Р°Р№С€РёРµ {planning_horizon_days} РґРЅРµР№."
    )
    brief["export_text"] = ""

    return _build_management_snapshot_payload(
        brief,
        territories=territories,
        actions=actions[:3],
        notes=list(brief["notes"] or notes),
        priority_horizon_days=planning_horizon_days,
    )

__all__ = ["_empty_management_snapshot", "_build_management_snapshot"]

from __future__ import annotations

from typing import Any

from .presentation_format import (
    MISSING_DISPLAY,
    _first_present,
    _format_first_present,
    _format_optional_integer,
    _format_optional_number,
    _format_optional_percent,
    _format_optional_signed_percent,
    _format_optional_text,
    _format_optional_value,
    _format_row_display,
    _is_missing_metric,
)


def _event_probability_context(
    ml_result: dict[str, Any],
    overview: dict[str, Any],
) -> dict[str, str | None]:
    reason_code = _first_present(
        ml_result.get('event_probability_reason_code'),
        overview.get('event_probability_reason_code'),
    )
    note = _first_present(
        ml_result.get('event_probability_note'),
        overview.get('event_probability_note'),
    )
    normalized_reason_code = None if _is_missing_metric(reason_code) else str(reason_code).strip()
    normalized_note = None if _is_missing_metric(note) else str(note).strip()
    return {
        'reason_code': normalized_reason_code,
        'note': normalized_note,
    }


def _build_notes(
    preload_notes: list[str],
    metadata_items: list[dict[str, Any]],
    filtered_records_count: int,
    daily_history: list[dict[str, Any]],
    ml_result: dict[str, Any],
    scenario_temperature: float | None,
    source_tables: list[str],
) -> list[str]:
    notes: list[str] = []

    def append_note(value: Any) -> None:
        if value is None:
            return
        text = str(value).strip()
        if not text or text in notes:
            return
        notes.append(text)

    for note in preload_notes:
        append_note(note)

    overview = ml_result.get('backtest_overview', {}) or {}
    event_context = _event_probability_context(ml_result, overview)
    if event_context['note'] and not ml_result.get('event_backtest_available'):
        append_note(event_context['note'])

    if filtered_records_count <= 0:
        append_note('РџРѕСЃР»Рµ РІС‹Р±СЂР°РЅРЅС‹С… С„РёР»СЊС‚СЂРѕРІ РЅРµ РѕСЃС‚Р°Р»РѕСЃСЊ РёСЃС‚РѕСЂРёС‡РµСЃРєРёС… РїРѕР¶Р°СЂРѕРІ РґР»СЏ РѕР±СѓС‡РµРЅРёСЏ ML-РјРѕРґРµР»Рё.')
    if ml_result.get('message'):
        append_note(ml_result['message'])
    if not ml_result.get('is_ready') and filtered_records_count > 0:
        append_note('РСЃС‚РѕСЂРёРё РїРѕРєР° РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ, С‡С‚РѕР±С‹ РїРѕРєР°Р·Р°С‚СЊ СѓСЃС‚РѕР№С‡РёРІС‹Р№ ML-РїСЂРѕРіРЅРѕР· Рё РїСЂРѕРІРµСЂРєСѓ РєР°С‡РµСЃС‚РІР°.')
    if len(daily_history) < 60:
        append_note('РСЃС‚РѕСЂРёРё РјРµРЅСЊС€Рµ 60 РґРЅРµР№: РґР»СЏ РєРѕСЂСЂРµРєС‚РЅРѕР№ ML-РІР°Р»РёРґР°С†РёРё СЌС‚РѕРіРѕ РѕР±С‹С‡РЅРѕ РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ.')
    if scenario_temperature is not None and not any(item['resolved_columns'].get('temperature') for item in metadata_items):
        append_note(
            'РўРµРјРїРµСЂР°С‚СѓСЂР° Р·Р°РґР°РЅР° РІСЂСѓС‡РЅСѓСЋ, РЅРѕ С‚РµРјРїРµСЂР°С‚СѓСЂРЅР°СЏ РєРѕР»РѕРЅРєР° РІ С‚Р°Р±Р»РёС†Р°С… РЅРµ РЅР°Р№РґРµРЅР°: '
            'СЃС†РµРЅР°СЂРЅРѕРµ Р·РЅР°С‡РµРЅРёРµ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ С‚РѕР»СЊРєРѕ РґР»СЏ Р±СѓРґСѓС‰РёС… РґР°С‚.'
        )

    if ml_result.get('temperature_note'):
        append_note(ml_result['temperature_note'])

    if len(source_tables) > 1 and not notes:
        append_note(f'ML-РјРѕРґРµР»СЊ СЃРѕР±РёСЂР°РµС‚ РѕР±С‰РёР№ РїСЂРѕРіРЅРѕР· СЃСЂР°Р·Сѓ РїРѕ {len(source_tables)} С‚Р°Р±Р»РёС†Р°Рј.')

    append_note('ML-СЌРєСЂР°РЅ РїРѕРєР°Р·С‹РІР°РµС‚ РѕР¶РёРґР°РµРјРѕРµ С‡РёСЃР»Рѕ РїРѕР¶Р°СЂРѕРІ РїРѕ РґР°С‚Р°Рј Рё РЅРµ Р·Р°РјРµРЅСЏРµС‚ СЃС†РµРЅР°СЂРЅС‹Р№ РїСЂРѕРіРЅРѕР· РїРѕ РІРµСЂРѕСЏС‚РЅРѕСЃС‚Рё РїРѕР¶Р°СЂР° РёР»Рё СЂР°РЅР¶РёСЂРѕРІР°РЅРёРµ С‚РµСЂСЂРёС‚РѕСЂРёР№.')

    return notes

__all__ = [
    '_build_notes',
    '_event_probability_context',
]


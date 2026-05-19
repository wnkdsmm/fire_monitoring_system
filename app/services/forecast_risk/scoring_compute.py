from __future__ import annotations

import math
from typing import Any, Sequence

from app.labels import (
    LABEL_EXPERT_WEIGHTS,
    LABEL_NON_RURAL_TERRITORY,
    LABEL_NO_DOMINANT_RISK_DRIVER,
    LABEL_NOT_SPECIFIED,
    LABEL_RURAL_TERRITORY,
)
from app.services.explainable_logistics import build_explainable_logistics_profile
from config.constants import (
    ARRIVAL_PROB_CLAMP_MAX,
    ARRIVAL_PROB_CLAMP_MIN,
    ARRIVAL_PROB_COVERAGE_WEIGHT,
    ARRIVAL_PROB_LONG_ARRIVAL_WEIGHT,
    ARRIVAL_PROB_RESPONSE_WEIGHT,
    ARRIVAL_PROB_TRAVEL_WEIGHT,
    ARRIVAL_PROB_ZONE_WEIGHT,
    BAR_WIDTH_MAX,
    BAR_WIDTH_MIN_COMPONENT,
    BAR_WIDTH_MIN_RISK,
    BASE_FIRE_SIGNAL_MAX,
    BASE_FIRE_SIGNAL_MIN,
    CASUALTY_PRESSURE_SCALE,
    DAMAGE_PRESSURE_DAMAGE_WEIGHT,
    DAMAGE_PRESSURE_SEVERE_WEIGHT,
    DEFAULT_DISTANCE_KM_BASELINE,
    NARRATIVE_COMPONENT_SCORE_FLOOR,
    NARRATIVE_COVERAGE_DEFICIT_THRESHOLD,
    NARRATIVE_DAMAGE_RATE_HIGH,
    NARRATIVE_DISTANCE_REMOTE_KM,
    NARRATIVE_HEATING_SHARE_DRIVER,
    NARRATIVE_HISTORY_PRESSURE_HIGH,
    NARRATIVE_LOGISTICS_PRIORITY_HIGH,
    NARRATIVE_LONG_ARRIVAL_HIGH,
    NARRATIVE_RECENCY_PRESSURE_HIGH,
    NARRATIVE_RISK_FACTOR_HIGH,
    NARRATIVE_SCORE_LOW_THRESHOLD,
    NARRATIVE_SEASONAL_ALIGNMENT_HIGH,
    NARRATIVE_SEVERE_RATE_HIGH,
    NARRATIVE_TANKER_DEPENDENCY_HIGH,
    NARRATIVE_VICTIMS_RATE_MIN,
    DISTANCE_SCORE_MIN_KM,
    DISTANCE_SCORE_RANGE_KM,
    DEFAULT_RISK_FACTOR,
    FIRE_EXPECTED_VALUE_SCALE,
    FIRE_PROBABILITY_CLAMP_MAX,
    FIRE_PROBABILITY_CLAMP_MIN,
    FIRE_PROBABILITY_FLOOR_BASE,
    FIRE_PROBABILITY_FLOOR_HISTORY_WEIGHT,
    FIRE_PROBABILITY_FLOOR_MAX,
    LONG_ARRIVAL_FALLBACK_DISTANCE_SCALE,
    LONG_ARRIVAL_FALLBACK_MAX,
    LONG_ARRIVAL_FALLBACK_MIN,
    RESPONSE_PRESSURE_DISTANCE_SCALE,
    RESPONSE_PRESSURE_NORMALIZATION_RANGE_MIN,
    RESPONSE_PRESSURE_TARGET_MIN,
    RESPONSE_PRESSURE_UNKNOWN_FALLBACK,
    RISK_SCORE_CLAMP_MAX,
    RISK_SCORE_CLAMP_MIN,
    SEASONAL_MONTH_WEIGHT,
    SEASONAL_WEEKDAY_WEIGHT,
    SEVERE_PROB_CLAMP_MAX,
    SEVERE_PROB_CLAMP_MIN,
    SEVERE_PROB_CASUALTY_WEIGHT,
    SEVERE_PROB_DAMAGE_WEIGHT,
    SEVERE_PROB_RISK_FACTOR_WEIGHT,
    SEVERE_PROB_SEVERE_RATE_WEIGHT,
    TANKER_DEPENDENCY_DISTANCE_WEIGHT,
    TANKER_DEPENDENCY_RESPONSE_WEIGHT,
    WATER_DEFICIT_CLAMP_MAX,
    WATER_DEFICIT_CLAMP_MIN,
    WATER_DEFICIT_GAP_WEIGHT,
    WATER_DEFICIT_TANKER_WEIGHT,
    WATER_GAP_UNKNOWN_DEFAULT,
)

from .profiles import DEFAULT_RISK_WEIGHT_MODE, get_risk_weight_profile
from .scoring_history import _collect_territory_buckets, _component_weights_for_rural, _horizon_context
from .scoring_ranking import (
    _attach_ranking_context,
    _build_formula_display,
    _priority_label,
    _recommended_action,
    _risk_class,
    _water_supply_display,
)
from .utils import (
    _clamp,
    _counter_top_label,
    _format_integer,
    _format_number,
    _format_probability,
    _is_rural_label,
)
from .types import (
    ComponentSignal,
    ComponentScore,
    ComponentScoreMapEntry,
    HorizonContext,
    LogisticsFactors,
    RiskFactors,
    RiskProfile,
    RiskScore,
    ScoreContext,
    TerritoryBucket,
    TerritoryIdentity,
    WaterFactors,
)

def _pluralize_ball(value: float) -> str:
    n = abs(int(round(value)))
    if 11 <= n % 100 <= 19:
        return "баллов"
    rem = n % 10
    if rem == 1:
        return "балл"
    if 2 <= rem <= 4:
        return "балла"
    return "баллов"


def _normalization_fields(
    territories: dict[str, TerritoryBucket],
    recent_incidents: int,
    recent_window_days: int,
) -> dict[str, float]:
    return {
        "base_fire_signal": _clamp(
            1.0 - math.exp(-(recent_incidents / max(recent_window_days, 1))),
            BASE_FIRE_SIGNAL_MIN,
            BASE_FIRE_SIGNAL_MAX,
        ),
        "max_incidents": max((bucket["incidents"] for bucket in territories.values()), default=1),
        "max_weighted": max((bucket["weighted_history"] for bucket in territories.values()), default=1.0),
    }


def _territory_identity_fields(bucket: TerritoryBucket) -> TerritoryIdentity:
    dominant_object_category = _counter_top_label(bucket["object_categories"], LABEL_NOT_SPECIFIED)
    dominant_settlement_type = _counter_top_label(bucket["settlement_types"], LABEL_NOT_SPECIFIED)
    is_rural = _is_rural_label(dominant_settlement_type) or _is_rural_label(bucket["label"])
    settlement_context_label = LABEL_RURAL_TERRITORY if is_rural else LABEL_NON_RURAL_TERRITORY
    return {
        "dominant_object_category": dominant_object_category,
        "dominant_settlement_type": dominant_settlement_type,
        "is_rural": is_rural,
        "settlement_context_label": settlement_context_label,
    }


def _normalized_risk_fields(
    bucket: TerritoryBucket,
    horizon: HorizonContext,
    normalization: dict[str, float],
) -> RiskFactors:
    incidents = bucket["incidents"]
    safe_incidents = max(1, incidents)
    history_pressure = incidents / max(1, normalization["max_incidents"])
    recency_pressure = bucket["weighted_history"] / max(1.0, normalization["max_weighted"])
    seasonal_alignment = _clamp(
        SEASONAL_MONTH_WEIGHT * (bucket["seasonal_month_sum"] / safe_incidents)
        + SEASONAL_WEEKDAY_WEIGHT * (bucket["seasonal_weekday_sum"] / safe_incidents),
        0.0,
        1.0,
    )
    base_fire_signal = normalization["base_fire_signal"]
    expected_value = (
        (bucket["weighted_history"] / horizon["history_days"])
        * horizon["horizon_days"]
        * (FIRE_EXPECTED_VALUE_SCALE + base_fire_signal)
    )
    fire_probability = _clamp(
        max(
            1.0 - math.exp(-max(0.0, expected_value)),
            base_fire_signal
            * min(
                FIRE_PROBABILITY_FLOOR_MAX,
                FIRE_PROBABILITY_FLOOR_BASE + history_pressure * FIRE_PROBABILITY_FLOOR_HISTORY_WEIGHT,
            ),
        ),
        FIRE_PROBABILITY_CLAMP_MIN,
        FIRE_PROBABILITY_CLAMP_MAX,
    )

    severe_rate = bucket["severe"] / safe_incidents
    victims_rate = bucket["victims"] / safe_incidents
    damage_rate = bucket["major_damage"] / safe_incidents
    heating_share = bucket["heating_incidents"] / safe_incidents
    heating_pressure = _clamp(heating_share * horizon["future_heating_share"], 0.0, 1.0)
    night_share = bucket["night_incidents"] / safe_incidents
    risk_factor = bucket["risk_score_sum"] / bucket["risk_score_count"] if bucket["risk_score_count"] else DEFAULT_RISK_FACTOR
    casualty_pressure = _clamp(victims_rate * CASUALTY_PRESSURE_SCALE, 0.0, 1.0)
    damage_pressure = _clamp(
        DAMAGE_PRESSURE_DAMAGE_WEIGHT * damage_rate + DAMAGE_PRESSURE_SEVERE_WEIGHT * severe_rate,
        0.0,
        1.0,
    )
    severe_probability = _clamp(
        (
            SEVERE_PROB_SEVERE_RATE_WEIGHT * severe_rate
            + SEVERE_PROB_CASUALTY_WEIGHT * casualty_pressure
            + SEVERE_PROB_DAMAGE_WEIGHT * damage_pressure
            + SEVERE_PROB_RISK_FACTOR_WEIGHT * risk_factor
        ),
        SEVERE_PROB_CLAMP_MIN,
        SEVERE_PROB_CLAMP_MAX,
    )

    return {
        "incidents": incidents,
        "history_pressure": history_pressure,
        "recency_pressure": recency_pressure,
        "seasonal_alignment": seasonal_alignment,
        "fire_probability": fire_probability,
        "severe_rate": severe_rate,
        "victims_rate": victims_rate,
        "damage_rate": damage_rate,
        "heating_share": heating_share,
        "heating_pressure": heating_pressure,
        "night_share": night_share,
        "risk_factor": risk_factor,
        "casualty_pressure": casualty_pressure,
        "damage_pressure": damage_pressure,
        "severe_probability": severe_probability,
    }


def _logistics_fields(
    bucket: TerritoryBucket,
    defaults: dict[str, Any],
    *,
    is_rural: bool,
    night_share: float,
) -> LogisticsFactors:
    avg_response = bucket["response_sum"] / bucket["response_count"] if bucket["response_count"] else None
    avg_distance = bucket["distance_sum"] / bucket["distance_count"] if bucket["distance_count"] else None
    distance_score = _clamp(
        ((avg_distance or float(defaults.get("distance_km_baseline") or DEFAULT_DISTANCE_KM_BASELINE)) - DISTANCE_SCORE_MIN_KM)
        / DISTANCE_SCORE_RANGE_KM,
        0.0,
        1.0,
    )
    long_arrival_rate = (
        bucket["long_arrivals"] / bucket["response_count"]
        if bucket["response_count"]
        else _clamp(
            distance_score * LONG_ARRIVAL_FALLBACK_DISTANCE_SCALE,
            LONG_ARRIVAL_FALLBACK_MIN,
            LONG_ARRIVAL_FALLBACK_MAX,
        )
    )
    response_pressure = (
        _clamp((avg_response - RESPONSE_PRESSURE_TARGET_MIN) / RESPONSE_PRESSURE_NORMALIZATION_RANGE_MIN, 0.0, 1.0)
        if avg_response is not None
        else _clamp(
            max(
                float(defaults.get("response_pressure_unknown") or RESPONSE_PRESSURE_UNKNOWN_FALLBACK),
                distance_score * RESPONSE_PRESSURE_DISTANCE_SCALE,
            ),
            0.0,
            1.0,
        )
    )
    logistics_profile = build_explainable_logistics_profile(
        avg_distance_km=avg_distance,
        avg_response_minutes=avg_response,
        long_arrival_rate=long_arrival_rate,
        is_rural=is_rural,
        response_observations=bucket["response_count"],
        distance_observations=bucket["distance_count"],
        night_share=night_share,
    )
    late_arrival_risk = _clamp(
        ARRIVAL_PROB_LONG_ARRIVAL_WEIGHT * long_arrival_rate
        + ARRIVAL_PROB_RESPONSE_WEIGHT * response_pressure
        + ARRIVAL_PROB_TRAVEL_WEIGHT * float(logistics_profile["travel_time_pressure"])
        + ARRIVAL_PROB_COVERAGE_WEIGHT * float(logistics_profile["service_coverage_gap"])
        + ARRIVAL_PROB_ZONE_WEIGHT * float(logistics_profile["service_zone_pressure"]),
        ARRIVAL_PROB_CLAMP_MIN,
        ARRIVAL_PROB_CLAMP_MAX,
    )
    return {
        "avg_response": avg_response,
        "avg_distance": avg_distance,
        "distance_score": distance_score,
        "long_arrival_rate": long_arrival_rate,
        "response_pressure": response_pressure,
        "logistics_profile": logistics_profile,
        "late_arrival_risk": late_arrival_risk,
    }


def _water_fields(
    bucket: TerritoryBucket,
    defaults: dict[str, Any],
    *,
    distance_score: float,
    response_pressure: float,
) -> WaterFactors:
    water_gap_rate = (
        1.0 - (bucket["water_available"] / bucket["water_known"])
        if bucket["water_known"]
            else float(defaults.get("water_gap_unknown") or WATER_GAP_UNKNOWN_DEFAULT)
    )
    tanker_dependency = _clamp(
        TANKER_DEPENDENCY_DISTANCE_WEIGHT * distance_score + TANKER_DEPENDENCY_RESPONSE_WEIGHT * response_pressure,
        0.0,
        1.0,
    )
    water_deficit_probability = _clamp(
        WATER_DEFICIT_GAP_WEIGHT * water_gap_rate + WATER_DEFICIT_TANKER_WEIGHT * tanker_dependency,
        WATER_DEFICIT_CLAMP_MIN,
        WATER_DEFICIT_CLAMP_MAX,
    )
    return {
        "water_gap_rate": water_gap_rate,
        "tanker_dependency": tanker_dependency,
        "water_deficit_probability": water_deficit_probability,
    }


def _score_inputs(
    bucket: TerritoryBucket,
    identity: TerritoryIdentity,
    risk_fields: RiskFactors,
    logistics: LogisticsFactors,
    water: WaterFactors,
) -> tuple[dict[str, float], ScoreContext]:
    logistics_profile = logistics["logistics_profile"]
    signal_values = {
        "predicted_repeat_rate": risk_fields["fire_probability"],
        "history_pressure": risk_fields["history_pressure"],
        "recency_pressure": risk_fields["recency_pressure"],
        "seasonal_alignment": risk_fields["seasonal_alignment"],
        "heating_pressure": risk_fields["heating_pressure"],
        "severe_rate": risk_fields["severe_rate"],
        "casualty_pressure": risk_fields["casualty_pressure"],
        "damage_pressure": risk_fields["damage_pressure"],
        "risk_category_factor": risk_fields["risk_factor"],
        "long_arrival_rate": logistics["long_arrival_rate"],
        "avg_response_pressure": logistics["response_pressure"],
        "distance_pressure": logistics["distance_score"],
        "travel_time_pressure": float(logistics_profile["travel_time_pressure"]),
        "service_coverage_gap": float(logistics_profile["service_coverage_gap"]),
        "service_zone_pressure": float(logistics_profile["service_zone_pressure"]),
        "night_pressure": risk_fields["night_share"],
        "water_gap_rate": water["water_gap_rate"],
        "tanker_dependency": water["tanker_dependency"],
        "rural_context": 1.0 if identity["is_rural"] else 0.0,
    }

    context = {
        "incidents": risk_fields["incidents"],
        "history_pressure": risk_fields["history_pressure"],
        "recency_pressure": risk_fields["recency_pressure"],
        "seasonal_alignment": risk_fields["seasonal_alignment"],
        "fire_probability": risk_fields["fire_probability"],
        "severe_rate": risk_fields["severe_rate"],
        "victims_rate": risk_fields["victims_rate"],
        "damage_rate": risk_fields["damage_rate"],
        "risk_factor": risk_fields["risk_factor"],
        "avg_response": logistics["avg_response"],
        "avg_distance": logistics["avg_distance"],
        "long_arrival_rate": logistics["long_arrival_rate"],
        "travel_time_minutes": logistics_profile["travel_time_minutes"],
        "travel_time_source": logistics_profile["travel_time_source"],
        "service_coverage_ratio": logistics_profile["service_coverage_ratio"],
        "service_coverage_display": logistics_profile["service_coverage_display"],
        "service_zone_label": logistics_profile["service_zone_label"],
        "service_zone_reason": logistics_profile["service_zone_reason"],
        "logistics_priority_score": logistics_profile["logistics_priority_score"],
        "logistics_priority_label": logistics_profile["logistics_priority_label"],
        "night_share": risk_fields["night_share"],
        "water_gap_rate": water["water_gap_rate"],
        "water_known": bucket["water_known"],
        "water_available": bucket["water_available"],
        "tanker_dependency": water["tanker_dependency"],
        "is_rural": identity["is_rural"],
        "settlement_context_label": identity["settlement_context_label"],
        "heating_share": risk_fields["heating_share"],
    }
    return signal_values, context


def _component_score_bundle(
    component_weights: Sequence[dict[str, Any]],
    profile_components: dict[str, Any],
    signal_values: dict[str, float],
    thresholds: dict[str, Any],
    context: ScoreContext,
) -> tuple[list[ComponentScore], dict[str, ComponentScoreMapEntry], float]:
    component_scores = [
        _score_component(
            component_weight=component_weight,
            component_spec=profile_components.get(component_weight["key"], {}),
            signal_values=signal_values,
            thresholds=thresholds,
            context=context,
        )
        for component_weight in component_weights
    ]
    component_scores.sort(key=lambda item: item["contribution"], reverse=True)
    component_score_map = {
        item["key"]: {
            "score": item["score"],
            "contribution": item["contribution"],
            "weight": item["weight"],
        }
        for item in component_scores
    }
    risk_score = _clamp(
        sum(float(item.get("contribution_raw", item["contribution"])) for item in component_scores),
        RISK_SCORE_CLAMP_MIN,
        RISK_SCORE_CLAMP_MAX,
    )
    return component_scores, component_score_map, risk_score


def _territory_row_payload(
    bucket: TerritoryBucket,
    profile: RiskProfile,
    thresholds: dict[str, Any],
    identity: TerritoryIdentity,
    risk_fields: RiskFactors,
    logistics: LogisticsFactors,
    water: WaterFactors,
    context: ScoreContext,
    component_scores: list[ComponentScore],
    component_score_map: dict[str, ComponentScoreMapEntry],
    risk_score: float,
) -> RiskScore:
    logistics_profile = logistics["logistics_profile"]
    risk_class_label, risk_tone = _risk_class(risk_score, thresholds)
    priority_label, priority_tone = _priority_label(risk_score, component_score_map, identity["is_rural"], thresholds)
    drivers = _build_risk_drivers(component_scores)
    drivers_display = ", ".join(drivers)
    action_label, action_hint, recommendations = _recommended_action(
        risk_score=risk_score,
        component_scores=component_scores,
        context=context,
    )
    formula_display = _build_formula_display(component_scores, risk_score)
    avg_response = logistics["avg_response"]
    avg_distance = logistics["avg_distance"]
    return {
        "label": bucket["label"],
        "risk_score": round(risk_score, 1),
        "risk_display": f"{_format_number(risk_score)} / 100",
        "risk_formula_display": formula_display,
        "risk_class_label": risk_class_label,
        "risk_tone": risk_tone,
        "priority_label": priority_label,
        "priority_tone": priority_tone,
        "weight_mode": profile.get("mode") or DEFAULT_RISK_WEIGHT_MODE,
        "weight_mode_label": profile.get("mode_label") or LABEL_EXPERT_WEIGHTS,
        "component_scores": component_scores,
        "component_score_map": component_score_map,
        "fire_probability": risk_fields["fire_probability"],
        "severe_probability": risk_fields["severe_probability"],
        "late_arrival_risk": logistics["late_arrival_risk"],
        "water_deficit_probability": water["water_deficit_probability"],
        "fire_probability_display": _format_probability(risk_fields["fire_probability"]),
        "severe_probability_display": _format_probability(risk_fields["severe_probability"]),
        "late_arrival_risk_display": _format_probability(logistics["late_arrival_risk"]),
        "water_deficit_display": _format_probability(water["water_deficit_probability"]),
        "history_count": risk_fields["incidents"],
        "history_count_display": _format_integer(risk_fields["incidents"]),
        "last_fire_display": bucket["last_fire"].strftime("%d.%m.%Y") if bucket["last_fire"] else "-",
        "avg_response_minutes": round(avg_response, 1) if avg_response is not None else None,
        "response_time_display": f"{_format_number(avg_response)} мин" if avg_response is not None else "Нет данных",
        "avg_distance_km": round(avg_distance, 1) if avg_distance is not None else None,
        "distance_display": f"{_format_number(avg_distance)} км" if avg_distance is not None else "Нет данных",
        "travel_time_minutes": logistics_profile["travel_time_minutes"],
        "travel_time_display": logistics_profile["travel_time_display"],
        "travel_time_source": logistics_profile["travel_time_source"],
        "fire_station_coverage_display": logistics_profile["service_coverage_display"],
        "fire_station_coverage_label": logistics_profile["fire_station_coverage_label"],
        "service_zone_label": logistics_profile["service_zone_label"],
        "service_zone_tone": logistics_profile["service_zone_tone"],
        "service_zone_reason": logistics_profile["service_zone_reason"],
        "logistics_priority_score": logistics_profile["logistics_priority_score"],
        "logistics_priority_display": logistics_profile["logistics_priority_display"],
        "logistics_priority_label": logistics_profile["logistics_priority_label"],
        "water_availability_share": round(bucket["water_available"] / bucket["water_known"], 4) if bucket["water_known"] else None,
        "water_supply_display": _water_supply_display(bucket["water_available"], bucket["water_known"]),
        "dominant_object_category": identity["dominant_object_category"],
        "dominant_settlement_type": identity["dominant_settlement_type"],
        "settlement_context_label": identity["settlement_context_label"],
        "is_rural": identity["is_rural"],
        "drivers_display": drivers_display,
        "action_label": action_label,
        "action_hint": action_hint,
        "recommendations": recommendations,
        "explanation": (
            f"Итоговый риск {_format_number(risk_score)} / 100. "
            f"Формула: {formula_display}. "
            f"Ключевые причины: {drivers_display}."
        ),
        "bar_width": f"{max(BAR_WIDTH_MIN_RISK, min(BAR_WIDTH_MAX, round(risk_score)))}%",
        "history_pressure": round(risk_fields["history_pressure"], 3),
    }


def _build_territory_rows(
    records: Sequence[dict[str, Any]],
    planning_horizon_days: int,
    weight_mode: str = DEFAULT_RISK_WEIGHT_MODE,
    profile_override: RiskProfile | None = None,
) -> list[RiskScore]:
    if not records:
        return []

    profile = profile_override if profile_override is not None else get_risk_weight_profile(weight_mode)
    thresholds = profile.get("thresholds") or {}
    defaults = profile.get("defaults") or {}
    profile_components = profile.get("components") or {}
    component_weights_cache: dict[bool, list[dict[str, Any]]] = {}

    horizon = _horizon_context(records, planning_horizon_days)
    territories, recent_incidents = _collect_territory_buckets(records, horizon)
    normalization = _normalization_fields(territories, recent_incidents, horizon["recent_window_days"])

    territory_rows: list[RiskScore] = []
    for bucket in territories.values():
        identity = _territory_identity_fields(bucket)
        component_weights = _component_weights_for_rural(
            profile,
            component_weights_cache,
            is_rural=identity["is_rural"],
        )
        risk_fields = _normalized_risk_fields(bucket, horizon, normalization)
        logistics = _logistics_fields(
            bucket,
            defaults,
            is_rural=identity["is_rural"],
            night_share=risk_fields["night_share"],
        )
        water = _water_fields(
            bucket,
            defaults,
            distance_score=logistics["distance_score"],
            response_pressure=logistics["response_pressure"],
        )
        signal_values, context = _score_inputs(bucket, identity, risk_fields, logistics, water)
        component_scores, component_score_map, risk_score = _component_score_bundle(
            component_weights,
            profile_components,
            signal_values,
            thresholds,
            context,
        )
        territory_rows.append(
            _territory_row_payload(
                bucket,
                profile,
                thresholds,
                identity,
                risk_fields,
                logistics,
                water,
                context,
                component_scores,
                component_score_map,
                risk_score,
            )
        )

    territory_rows.sort(key=lambda item: (item["risk_score"], item["history_pressure"]), reverse=True)
    _attach_ranking_context(territory_rows)
    return territory_rows


def _score_component(
    component_weight: dict[str, Any],
    component_spec: dict[str, Any],
    signal_values: dict[str, float],
    thresholds: dict[str, Any],
    context: ScoreContext,
) -> ComponentScore:
    signal_rows: list[ComponentSignal] = []
    weighted_sum = 0.0
    total_signal_weight = 0.0

    for signal in component_spec.get("signals", []):
        signal_weight = float(signal.get("weight", 0.0))
        signal_value = _clamp(float(signal_values.get(signal.get("key"), 0.0)), 0.0, 1.0)
        weighted_value = signal_value * signal_weight
        weighted_sum += weighted_value
        total_signal_weight += signal_weight
        signal_rows.append(
            {
                "key": signal.get("key") or "",
                "label": signal.get("label") or signal.get("key") or "Сигнал",
                "value": round(signal_value, 4),
                "value_display": f"{_format_number(signal_value * 100.0)} / 100",
                "weight": signal_weight,
                "weight_display": f"{_format_number(signal_weight * 100.0)}%",
                "weighted_value": round(weighted_value, 4),
            }
        )

    signal_rows.sort(key=lambda item: item["weighted_value"], reverse=True)
    score = 100.0 * weighted_sum / total_signal_weight if total_signal_weight > 0 else 0.0
    contribution = score * float(component_weight.get("weight", 0.0))
    tone = _component_tone(score, thresholds)

    result = {
        "key": component_weight.get("key") or "component",
        "label": component_weight.get("label") or component_spec.get("label") or "Компонент",
        "description": component_weight.get("description") or component_spec.get("description") or "",
        "score": round(score, 1),
        "score_display": f"{_format_number(score)} / 100",
        "weight": round(float(component_weight.get("weight", 0.0)), 4),
        "weight_display": component_weight.get("weight_display") or "0%",
        "contribution_raw": contribution,
        "contribution": round(contribution, 1),
        "contribution_display": f"{_format_number(contribution)} {_pluralize_ball(contribution)}",
        "tone": tone,
        "signals": signal_rows,
        "bar_width": f"{max(BAR_WIDTH_MIN_COMPONENT, min(BAR_WIDTH_MAX, round(score)))}%",
    }
    result["summary"] = f"Вес {result['weight_display']}, вклад {result['contribution_display']}."
    result["rationale"] = _component_rationale(result["key"], score, context)
    result["driver_text"] = _component_driver_text(result["key"], score, context)
    return result


def _component_tone(score: float, thresholds: dict[str, Any]) -> str:
    component_thresholds = thresholds.get("component") or {}
    if score >= float(component_thresholds.get("high", 65.0)):
        return "high"
    if score >= float(component_thresholds.get("medium", 40.0)):
        return "medium"
    return "low"


def _component_rationale(component_key: str, score: float, context: ScoreContext) -> str:
    if component_key == "fire_frequency":
        parts = [f"В истории {_format_integer(context['incidents'])} пожаров."]
        if context["history_pressure"] >= NARRATIVE_HISTORY_PRESSURE_HIGH:
            parts.append("Территория уже накапливала много случаев относительно выбранного среза.")
        if context["recency_pressure"] >= NARRATIVE_RECENCY_PRESSURE_HIGH:
            parts.append("Часть пожаров свежая и влияет на ближайший горизонт.")
        if context["seasonal_alignment"] >= NARRATIVE_SEASONAL_ALIGNMENT_HIGH:
            parts.append("Профиль хорошо совпадает с текущим сезонным окном.")
        if context["heating_share"] >= NARRATIVE_HEATING_SHARE_DRIVER and context["is_rural"]:
            parts.append("Для сельской территории заметен отопительный контур риска.")
        if score < NARRATIVE_SCORE_LOW_THRESHOLD:
            parts.append("Повторяемость пока умеренная.")
        return " ".join(parts[:4])

    if component_key == "consequence_severity":
        parts = []
        if context["severe_rate"] >= NARRATIVE_SEVERE_RATE_HIGH:
            parts.append(f"Тяжёлые последствия были в {_format_probability(context['severe_rate'])} случаев.")
        if context["victims_rate"] >= NARRATIVE_VICTIMS_RATE_MIN:
            parts.append("В истории есть пострадавшие или погибшие.")
        if context["damage_rate"] >= NARRATIVE_DAMAGE_RATE_HIGH:
            parts.append("Ущерб и уничтожение фиксировались часто.")
        if context["risk_factor"] >= NARRATIVE_RISK_FACTOR_HIGH:
            parts.append("Категория риска по объектам выше средней.")
        if not parts:
            parts.append("История тяжёлых последствий пока умеренная.")
        return " ".join(parts[:4])

    if component_key == "long_arrival_risk":
        parts = []
        parts.append(
            f"Travel-time доезда {_format_number(context['travel_time_minutes'])} мин ({context['travel_time_source']})."
        )
        parts.append(
            f"Покрытие ПЧ {context['service_coverage_display']}, сервисная зона: {context['service_zone_label']}."
        )
        if context["long_arrival_rate"] >= NARRATIVE_LONG_ARRIVAL_HIGH:
            parts.append(f"Долгие прибытия были в {_format_probability(context['long_arrival_rate'])} случаев.")
        if context["avg_distance"] is not None and context["avg_distance"] >= NARRATIVE_DISTANCE_REMOTE_KM:
            parts.append(f"Удалённость до ПЧ {_format_number(context['avg_distance'])} км.")
        if context["logistics_priority_score"] >= NARRATIVE_LOGISTICS_PRIORITY_HIGH:
            parts.append(
                f"Логистический приоритет { _format_number(context['logistics_priority_score']) } / 100."
            )
        return " ".join(parts[:4])

    parts = []
    if context["water_known"] > 0:
        water_share = context["water_available"] / max(1, context["water_known"])
        parts.append(f"Подтверждение воды по выездам: {_format_probability(water_share)} случаев.")
    else:
        parts.append("Подтверждений воды нет, поэтому используем экспертную оценку водного дефицита.")
    if context["tanker_dependency"] >= NARRATIVE_TANKER_DEPENDENCY_HIGH:
        parts.append("Из-за танкерной зависимости повышен риск дефицита воды.")
    if context["is_rural"]:
        parts.append("Для сельской территории запас воды и подъезд к источникам особенно критичны.")
    return " ".join(parts[:4])


def _component_driver_text(component_key: str, score: float, context: ScoreContext) -> str:
    if score < NARRATIVE_COMPONENT_SCORE_FLOOR:
        return ""
    if component_key == "fire_frequency":
        if context["heating_share"] >= NARRATIVE_HEATING_SHARE_DRIVER and context["is_rural"]:
            return "пожары здесь повторяются и усиливаются в отопительный период"
        return "пожары здесь повторяются чаще фонового уровня"
    if component_key == "consequence_severity":
        return "история последствий здесь тяжелее среднего"
    if component_key == "long_arrival_risk":
        if context["service_coverage_ratio"] < NARRATIVE_COVERAGE_DEFICIT_THRESHOLD:
            return "территория выходит из устойчивого прикрытия ПЧ"
        if context["avg_distance"] is not None and context["avg_distance"] >= NARRATIVE_DISTANCE_REMOTE_KM:
            return "есть риск долгого прибытия из-за удалённости"
        return "travel-time и сервисная зона повышают логистический риск"
    return "не подтверждён стабильный доступ к воде для тушения"


def _build_risk_drivers(component_scores: Sequence[ComponentScore]) -> list[str]:
    drivers = [item.get("driver_text") or "" for item in component_scores if item.get("driver_text")]
    if not drivers:
        return [LABEL_NO_DOMINANT_RISK_DRIVER]
    return drivers[:3]

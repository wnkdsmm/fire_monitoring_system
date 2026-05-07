from __future__ import annotations

from typing import Any

from app.services.shared.formatting import (
    format_number_rounded as _format_number,
    format_percent_ratio as _format_percent_ratio,
)
from config.constants import (
    COVERAGE_BLEND_DISTANCE_ONLY_DISTANCE,
    COVERAGE_BLEND_DISTANCE_ONLY_TRAVEL,
    COVERAGE_BLEND_FULL_DISTANCE,
    COVERAGE_BLEND_FULL_RESPONSE,
    COVERAGE_BLEND_FULL_TRAVEL,
    COVERAGE_BLEND_RESPONSE_ONLY_RESPONSE,
    COVERAGE_BLEND_RESPONSE_ONLY_TRAVEL,
    COVERAGE_LABEL_BORDER_MIN,
    COVERAGE_LABEL_STABLE_MIN,
    COVERAGE_LABEL_TENSION_MIN,
    CORE_SERVICE_TIME_MINUTES,
    DISTANCE_FALLBACK_KM,
    DISTANCE_SCORE_MIN_KM,
    DISTANCE_SCORE_RANGE_KM,
    LOGISTICS_FALLBACK_TRAVEL_RURAL_MIN,
    LOGISTICS_FALLBACK_TRAVEL_URBAN_MIN,
    LOGISTICS_PRIORITY_COVERAGE_WEIGHT,
    LOGISTICS_PRIORITY_CRITICAL_MIN,
    LOGISTICS_PRIORITY_DISTANCE_WEIGHT,
    LOGISTICS_PRIORITY_HIGH_MIN,
    LOGISTICS_PRIORITY_TARGETED_MIN,
    LOGISTICS_PRIORITY_TRAVEL_WEIGHT,
    LOGISTICS_PRIORITY_ZONE_WEIGHT,
    LOGISTICS_MINIMUM_SPEED_KMH,
    LOGISTICS_NIGHT_SPEED_REDUCTION,
    LOGISTICS_RESPONSE_OBSERVED_WEIGHT_HIGH,
    LOGISTICS_RESPONSE_OBSERVED_WEIGHT_LOW,
    LOGISTICS_RESPONSE_OBSERVATIONS_THRESHOLD,
    LOGISTICS_RURAL_SPEED_KMH,
    LOGISTICS_URBAN_SPEED_KMH,
    RESPONSE_PRESSURE_RANGE_MIN,
    RESPONSE_PRESSURE_FALLBACK_BASE,
    RESPONSE_PRESSURE_FALLBACK_DISTANCE_WEIGHT,
    RESPONSE_PRESSURE_TARGET_MIN,
    SERVICE_ZONE_CORE_COVERAGE_MIN,
    SERVICE_ZONE_NORM_COVERAGE_MIN,
    SERVICE_ZONE_TENSION_COVERAGE_MIN,
    SERVICE_ZONE_TENSION_TIME_MAX,
    SERVICE_DISTANCE_TARGET_KM,
    SERVICE_TIME_TARGET_MINUTES,
)

COVERAGE_FALLBACK_RURAL = 0.46
COVERAGE_FALLBACK_URBAN = 0.58

DISTANCE_COVERAGE_LOW_MULTIPLIER = 1.3
DISTANCE_COVERAGE_HIGH_MULTIPLIER = 1.5


def build_explainable_logistics_profile(
    *,
    avg_distance_km: float | None,
    avg_response_minutes: float | None,
    long_arrival_rate: float,
    is_rural: bool,
    response_observations: int = 0,
    distance_observations: int = 0,
    night_share: float = 0.0,
) -> dict[str, Any]:
    """Build an explainable logistics profile from observed response and distance.

    The function intentionally keeps the structure transparent:
    - observed arrival time is used when it exists;
    - distance contributes through an explicit speed assumption;
    - service coverage and service zone are derived from readable thresholds.
    """

    safe_long_arrival_rate = _clamp(long_arrival_rate, 0.0, 1.0)
    safe_night_share = _clamp(night_share, 0.0, 1.0)
    safe_distance = _positive_or_none(avg_distance_km)
    safe_response = _positive_or_none(avg_response_minutes)

    estimated_from_distance: float | None = None
    if safe_distance is not None:
        base_speed_kmh = LOGISTICS_RURAL_SPEED_KMH if is_rural else LOGISTICS_URBAN_SPEED_KMH
        adjusted_speed_kmh = max(
            LOGISTICS_MINIMUM_SPEED_KMH,
            base_speed_kmh * (1.0 - LOGISTICS_NIGHT_SPEED_REDUCTION * safe_night_share),
        )
        estimated_from_distance = safe_distance / adjusted_speed_kmh * 60.0

    if safe_response is not None and estimated_from_distance is not None:
        observed_weight = (
            LOGISTICS_RESPONSE_OBSERVED_WEIGHT_HIGH
            if response_observations >= LOGISTICS_RESPONSE_OBSERVATIONS_THRESHOLD
            else LOGISTICS_RESPONSE_OBSERVED_WEIGHT_LOW
        )
        travel_time_minutes = safe_response * observed_weight + estimated_from_distance * (1.0 - observed_weight)
        travel_time_source = 'Факт прибытия + модель по расстоянию'
    elif safe_response is not None:
        travel_time_minutes = safe_response
        travel_time_source = 'Фактическое время прибытия'
    elif estimated_from_distance is not None:
        travel_time_minutes = estimated_from_distance
        travel_time_source = 'Модель по расстоянию до ПЧ'
    else:
        travel_time_minutes = (
            LOGISTICS_FALLBACK_TRAVEL_RURAL_MIN if is_rural else LOGISTICS_FALLBACK_TRAVEL_URBAN_MIN
        )
        travel_time_source = 'Осторожный fallback без прямой логистики'

    distance_pressure = _clamp(((safe_distance or DISTANCE_FALLBACK_KM) - DISTANCE_SCORE_MIN_KM) / DISTANCE_SCORE_RANGE_KM, 0.0, 1.0)
    response_pressure = (
        _clamp((safe_response - RESPONSE_PRESSURE_TARGET_MIN) / RESPONSE_PRESSURE_RANGE_MIN, 0.0, 1.0)
        if safe_response is not None
        else _clamp(RESPONSE_PRESSURE_FALLBACK_BASE + distance_pressure * RESPONSE_PRESSURE_FALLBACK_DISTANCE_WEIGHT, 0.0, 1.0)
    )
    travel_time_pressure = _clamp((travel_time_minutes - RESPONSE_PRESSURE_TARGET_MIN) / RESPONSE_PRESSURE_RANGE_MIN, 0.0, 1.0)

    response_coverage = None
    if response_observations > 0:
        response_coverage = _clamp(1.0 - safe_long_arrival_rate, 0.05, 1.0)

    travel_time_coverage = _clamp(
        1.0 - max(0.0, travel_time_minutes - SERVICE_TIME_TARGET_MINUTES) / SERVICE_TIME_TARGET_MINUTES,
        0.05,
        1.0,
    )
    distance_coverage = _clamp(
        1.0
        - max(0.0, (safe_distance or SERVICE_DISTANCE_TARGET_KM * DISTANCE_COVERAGE_LOW_MULTIPLIER) - SERVICE_DISTANCE_TARGET_KM)
        / (SERVICE_DISTANCE_TARGET_KM * DISTANCE_COVERAGE_HIGH_MULTIPLIER),
        0.05,
        1.0,
    )

    if response_coverage is not None and distance_observations > 0:
        service_coverage_ratio = (
            COVERAGE_BLEND_FULL_RESPONSE * response_coverage
            + COVERAGE_BLEND_FULL_TRAVEL * travel_time_coverage
            + COVERAGE_BLEND_FULL_DISTANCE * distance_coverage
        )
        coverage_source = 'Факт прибытия + удалённость'
    elif response_coverage is not None:
        service_coverage_ratio = (
            COVERAGE_BLEND_RESPONSE_ONLY_RESPONSE * response_coverage
            + COVERAGE_BLEND_RESPONSE_ONLY_TRAVEL * travel_time_coverage
        )
        coverage_source = 'Фактическое прибытие'
    elif distance_observations > 0 or estimated_from_distance is not None:
        service_coverage_ratio = (
            COVERAGE_BLEND_DISTANCE_ONLY_TRAVEL * travel_time_coverage
            + COVERAGE_BLEND_DISTANCE_ONLY_DISTANCE * distance_coverage
        )
        coverage_source = 'Расстояние и модель travel-time'
    else:
        fallback_coverage = COVERAGE_FALLBACK_RURAL if is_rural else COVERAGE_FALLBACK_URBAN
        service_coverage_ratio = fallback_coverage
        coverage_source = 'Осторожный fallback'

    service_coverage_ratio = _clamp(service_coverage_ratio, 0.05, 0.98)
    service_coverage_gap = 1.0 - service_coverage_ratio

    service_zone_label, service_zone_tone, service_zone_pressure = _service_zone(
        travel_time_minutes=travel_time_minutes,
        coverage_ratio=service_coverage_ratio,
    )
    logistics_priority_score = _clamp(
        100.0 * (
            LOGISTICS_PRIORITY_TRAVEL_WEIGHT * travel_time_pressure
            + LOGISTICS_PRIORITY_COVERAGE_WEIGHT * service_coverage_gap
            + LOGISTICS_PRIORITY_ZONE_WEIGHT * service_zone_pressure
            + LOGISTICS_PRIORITY_DISTANCE_WEIGHT * distance_pressure
        ),
        0.0,
        100.0,
    )
    logistics_priority_label = _logistics_priority_label(logistics_priority_score)
    fire_station_coverage_label = _coverage_label(service_coverage_ratio)

    return {
        'travel_time_minutes': round(travel_time_minutes, 1),
        'travel_time_display': f'{_format_number(travel_time_minutes)} мин',
        'travel_time_source': travel_time_source,
        'travel_time_pressure': round(travel_time_pressure, 4),
        'distance_pressure': round(distance_pressure, 4),
        'response_pressure': round(response_pressure, 4),
        'service_coverage_ratio': round(service_coverage_ratio, 4),
        'service_coverage_display': _format_percent_ratio(service_coverage_ratio),
        'service_coverage_gap': round(service_coverage_gap, 4),
        'coverage_source': coverage_source,
        'fire_station_coverage_label': fire_station_coverage_label,
        'service_zone_label': service_zone_label,
        'service_zone_tone': service_zone_tone,
        'service_zone_pressure': round(service_zone_pressure, 4),
        'service_zone_reason': (
            f'{service_zone_label}: travel-time {_format_number(travel_time_minutes)} мин, '
            f'покрытие ПЧ {_format_percent_ratio(service_coverage_ratio)}.'
        ),
        'logistics_priority_score': round(logistics_priority_score, 1),
        'logistics_priority_display': f'{_format_number(logistics_priority_score)} / 100',
        'logistics_priority_label': logistics_priority_label,
        'service_time_target_minutes': SERVICE_TIME_TARGET_MINUTES,
        'service_distance_target_km': SERVICE_DISTANCE_TARGET_KM,
        'core_service_time_minutes': CORE_SERVICE_TIME_MINUTES,
    }


def _service_zone(*, travel_time_minutes: float, coverage_ratio: float) -> tuple[str, str, float]:
    if travel_time_minutes <= CORE_SERVICE_TIME_MINUTES and coverage_ratio >= SERVICE_ZONE_CORE_COVERAGE_MIN:
        return 'Ядро зоны обслуживания', 'forest', 0.10
    if travel_time_minutes <= SERVICE_TIME_TARGET_MINUTES and coverage_ratio >= SERVICE_ZONE_NORM_COVERAGE_MIN:
        return 'Граница нормативного прикрытия', 'sky', 0.34
    if travel_time_minutes <= SERVICE_ZONE_TENSION_TIME_MAX and coverage_ratio >= SERVICE_ZONE_TENSION_COVERAGE_MIN:
        return 'Зона напряженного доезда', 'sand', 0.68
    return 'Удаленная зона обслуживания', 'fire', 0.92


def _coverage_label(coverage_ratio: float) -> str:
    if coverage_ratio >= COVERAGE_LABEL_STABLE_MIN:
        return 'Устойчивое прикрытие'
    if coverage_ratio >= COVERAGE_LABEL_BORDER_MIN:
        return 'Пограничное прикрытие'
    if coverage_ratio >= COVERAGE_LABEL_TENSION_MIN:
        return 'Напряженное прикрытие'
    return 'Дефицит прикрытия'


def _logistics_priority_label(score: float) -> str:
    if score >= LOGISTICS_PRIORITY_CRITICAL_MIN:
        return 'Критичный логистический приоритет'
    if score >= LOGISTICS_PRIORITY_HIGH_MIN:
        return 'Высокий логистический приоритет'
    if score >= LOGISTICS_PRIORITY_TARGETED_MIN:
        return 'Точечный логистический контроль'
    return 'Плановый логистический контроль'


def _positive_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))

__all__ = [
    'CORE_SERVICE_TIME_MINUTES',
    'SERVICE_DISTANCE_TARGET_KM',
    'SERVICE_TIME_TARGET_MINUTES',
    'build_explainable_logistics_profile',
]

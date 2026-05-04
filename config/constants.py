from __future__ import annotations

"""Centralized project constants grouped by domain.

This module is the canonical source for non-UI constants.
UI labels (especially Russian copy) live in ``app.labels``.
"""

import os

# === DB / Config ===

NULL_THRESHOLD = 0.9
UNIQUE_ID_THRESHOLD = 0.99
LOW_VARIANCE_THRESHOLD = 0.0001
DOMINANT_VALUE_THRESHOLD = 0.85

MISSING_LIKE_VALUES = [
    "нет данных",
    "н/д",
    "nan",
    "none",
    "null",
    "-",
    "",
    " ",
]

PROFILING_CSV_SUFFIX = "_fires_profiling_report.csv"
PROFILING_XLSX_SUFFIX = "_fires_profiling_report.xlsx"

# === Business Rules ===

CORR_THRESHOLD = 0.9
VIF_THRESHOLD = 10
IMPORTANT_KEYWORDS = [
    "травмировать",
    "погибнуть",
    "эвакуировать",
    "ребёнок",
]

FORECASTING_FORECAST_DAY_OPTIONS = [7, 14, 30, 60]
FORECASTING_HISTORY_WINDOWS = ("all", "recent_3", "recent_5")
PRIORITY_HORIZON_DAYS = 14

ACCESS_POINT_LIMIT_OPTIONS = [10, 25, 50, 100]
DEFAULT_ACCESS_POINT_LIMIT = 25
MIN_ACCESS_POINT_SUPPORT = 3
LONG_RESPONSE_THRESHOLD_MINUTES = 20.0
TOP_POINT_CARD_COUNT = 5
MAX_INCOMPLETE_POINTS = 6
MAX_NOTES = 7
MAX_ACCESS_POINT_FEATURE_OPTIONS = 10
POINT_FEATURE_COLUMNS = (
    "incident_count",
    "incidents_per_year",
    "average_response_minutes",
    "response_coverage_share",
    "long_arrival_share",
    "average_distance_km",
    "distance_coverage_share",
    "no_water_share",
    "water_coverage_share",
    "water_unknown_share",
    "severe_share",
    "victim_share",
    "major_damage_share",
    "night_share",
    "heating_share",
    "rural_share",
    "rural_flag",
    "low_support",
    "support_weight",
)

CLUSTER_COUNT_OPTIONS = [2, 3, 4, 5, 6, 7, 8, 9, 10]
SAMPLE_LIMIT_OPTIONS = [50, 100, 200, 500, 1000]
SAMPLING_STRATEGY_VALUES = ["stratified", "random"]
CARD_TONES = ["group", "area", "table", "fire", "muted"]
MAX_FEATURE_OPTIONS = 12
MIN_ROWS_PER_CLUSTER = 5
MIN_DEFAULT_FEATURE_COUNT = 4
FEATURE_SELECTION_MIN_IMPROVEMENT = 0.0025
DEFAULT_CLUSTER_MODE_PROFILE = "territory_profile"
DEFAULT_CLUSTER_MODE_LOAD = "load_profile"
WEIGHTING_STRATEGY_UNIFORM = "uniform"
WEIGHTING_STRATEGY_INCIDENT_LOG = "incident_log"
WEIGHTING_STRATEGY_NOT_APPLICABLE = "not_applicable"
PROFILE_MODE_SCORE_TOLERANCE = 0.01
PROFILE_MODE_SILHOUETTE_TOLERANCE = 0.015
VOLUME_DOMINANCE_RATIO = 1.35
VOLUME_DOMINANCE_MIN_SCORE_DELTA = 0.01
RATE_SMOOTHING_PRIOR_STRENGTH = 3.0
MEAN_SMOOTHING_PRIOR_STRENGTH = 2.0
LOW_SUPPORT_TERRITORY_THRESHOLD = 2
STABILITY_RESAMPLE_RATIO = 0.8
STABILITY_RANDOM_SEEDS = [7, 21, 42, 84, 126]
HOPKINS_MIN_CLUSTERABLE = 0.6
FEATURE_SELECTION_N_INIT = 20
MODEL_N_INIT = 40
GAP_STAT_MAX_WORKERS = min(4, (os.cpu_count() or 1))
GAP_STAT_N_REFERENCES = 10

MAX_TERRITORIES = 12

# === Scoring risk formula constants ===

# Bounds for base_fire_signal (exponential decay of incident rate)
BASE_FIRE_SIGNAL_MIN = 0.08
BASE_FIRE_SIGNAL_MAX = 0.72

# Multiplier to scale expected Poisson parameter relative to base signal
FIRE_EXPECTED_VALUE_SCALE = 0.72

# Fallback floor for fire probability from history pressure
FIRE_PROBABILITY_FLOOR_HISTORY_WEIGHT = 0.52
FIRE_PROBABILITY_FLOOR_BASE = 0.22
FIRE_PROBABILITY_FLOOR_MAX = 0.94

# Seasonal alignment blend weights (month vs weekday contribution, must sum to 1.0)
SEASONAL_MONTH_WEIGHT = 0.62
SEASONAL_WEEKDAY_WEIGHT = 0.38

# Fire probability clamp bounds
FIRE_PROBABILITY_CLAMP_MIN = 0.02
FIRE_PROBABILITY_CLAMP_MAX = 0.995

# Distance score normalization (km)
DISTANCE_SCORE_MIN_KM = 6.0
DISTANCE_SCORE_RANGE_KM = 24.0

# Response pressure normalization (minutes)
RESPONSE_PRESSURE_TARGET_MIN = 12.0
RESPONSE_PRESSURE_RANGE_MIN = 18.0

# Fallback response pressure when avg_response is unknown
RESPONSE_PRESSURE_UNKNOWN_FALLBACK = 0.42
RESPONSE_PRESSURE_DISTANCE_SCALE = 0.72

# Arrival probability component weights (must sum to 1.0)
ARRIVAL_PROB_LONG_ARRIVAL_WEIGHT = 0.24
ARRIVAL_PROB_RESPONSE_WEIGHT = 0.18
ARRIVAL_PROB_TRAVEL_WEIGHT = 0.22
ARRIVAL_PROB_COVERAGE_WEIGHT = 0.22
ARRIVAL_PROB_ZONE_WEIGHT = 0.14
ARRIVAL_PROB_CLAMP_MIN = 0.03
ARRIVAL_PROB_CLAMP_MAX = 0.98
LONG_ARRIVAL_FALLBACK_DISTANCE_SCALE = 0.55
LONG_ARRIVAL_FALLBACK_MIN = 0.05
LONG_ARRIVAL_FALLBACK_MAX = 0.75

# Priority-label thresholds for component-driven escalation.
PRIORITY_ARRIVAL_IMMEDIATE_THRESHOLD = 65
PRIORITY_WATER_IMMEDIATE_THRESHOLD = 55
PRIORITY_RURAL_ARRIVAL_THRESHOLD = 62
PRIORITY_RURAL_FIRE_THRESHOLD = 60
PRIORITY_ANY_COMPONENT_TARGETED = 60

# Tanker dependency blend weights (must sum to 1.0)
TANKER_DEPENDENCY_DISTANCE_WEIGHT = 0.58
TANKER_DEPENDENCY_RESPONSE_WEIGHT = 0.42

# Water deficit probability blend weights (must sum to 1.0)
WATER_DEFICIT_GAP_WEIGHT = 0.76
WATER_DEFICIT_TANKER_WEIGHT = 0.24
WATER_DEFICIT_CLAMP_MIN = 0.02
WATER_DEFICIT_CLAMP_MAX = 0.99

# Casualty pressure scaling factor (converts victim rate to 0-1 pressure)
CASUALTY_PRESSURE_SCALE = 1.8

# Damage pressure weights (damage_rate vs severe_rate blend)
DAMAGE_PRESSURE_DAMAGE_WEIGHT = 0.70
DAMAGE_PRESSURE_SEVERE_WEIGHT = 0.30

# Severe probability component weights (must sum to 1.0)
SEVERE_PROB_SEVERE_RATE_WEIGHT = 0.46
SEVERE_PROB_CASUALTY_WEIGHT = 0.26
SEVERE_PROB_DAMAGE_WEIGHT = 0.18
SEVERE_PROB_RISK_FACTOR_WEIGHT = 0.10
SEVERE_PROB_CLAMP_MIN = 0.02
SEVERE_PROB_CLAMP_MAX = 0.98

# Default risk_factor when no risk_score_count data available
DEFAULT_RISK_FACTOR = 0.26
RISK_SCORE_CLAMP_MIN = 1.0
RISK_SCORE_CLAMP_MAX = 99.0
BAR_WIDTH_MIN_RISK = 10
BAR_WIDTH_MIN_COMPONENT = 12
BAR_WIDTH_MAX = 100

MIN_TEMPERATURE_NON_NULL_DAYS = 30
MIN_TEMPERATURE_COVERAGE = 0.20
GEO_LOOKBACK_DAYS = 180
MAX_GEO_CHART_POINTS = 40
MAX_GEO_HOTSPOTS = 8

# Explainable logistics thresholds.
SERVICE_TIME_TARGET_MINUTES = 20.0
SERVICE_DISTANCE_TARGET_KM = 12.0
CORE_SERVICE_TIME_MINUTES = 14.0

# === Logistics travel-time model constants ===

# Vehicle speed assumptions (km/h) by territory type
LOGISTICS_RURAL_SPEED_KMH = 34.0
LOGISTICS_URBAN_SPEED_KMH = 42.0
LOGISTICS_MINIMUM_SPEED_KMH = 22.0

# Night-time speed reduction coefficient per unit of night_share
LOGISTICS_NIGHT_SPEED_REDUCTION = 0.14

# Blend weights for observed vs distance-estimated travel time
LOGISTICS_RESPONSE_OBSERVED_WEIGHT_HIGH = 0.72   # >= 3 observations
LOGISTICS_RESPONSE_OBSERVED_WEIGHT_LOW = 0.58    # < 3 observations
LOGISTICS_RESPONSE_OBSERVATIONS_THRESHOLD = 3

# Fallback travel-time when neither response nor distance is available
LOGISTICS_FALLBACK_TRAVEL_RURAL_MIN = 24.0
LOGISTICS_FALLBACK_TRAVEL_URBAN_MIN = 18.0

# === ML ===

ML_FORECAST_DAY_OPTIONS = [7, 14, 30]
ML_HISTORY_WINDOWS = ("all", "recent_3", "recent_5")

MIN_DAILY_HISTORY = 60
MIN_FEATURE_ROWS = 24
MIN_BACKTEST_POINTS = 8
MIN_EVENT_CLASS_COUNT = 8
EVENT_RATE_SATURATION_MARGIN = 0.05
MAX_HISTORY_POINTS = 900
MAX_BACKTEST_POINTS = 45
PERMUTATION_REPEATS = 8
ROLLING_MIN_TRAIN_ROWS = 28
COUNT_MODEL_SELECTION_TOLERANCE = 0.05
BASELINE_RECENT_WINDOW_DAYS = 28
BASELINE_WEEKDAY_TAIL = 8
BASELINE_WEEKDAY_MIN_SAMPLES = 3
BASELINE_WEEKDAY_WEIGHT = 0.6
BASELINE_RECENT_WEIGHT = 0.4
COUNT_PREDICTION_CAP_FLOOR = 250.0
COUNT_PREDICTION_CAP_SUPPORT_MULTIPLIER = 20.0
COUNT_PREDICTION_CAP_SUPPORT_OFFSET = 50.0
NEGATIVE_BINOMIAL_ALPHA_DEFAULT = 0.25
NEGATIVE_BINOMIAL_ALPHA_FLOOR = 1e-4
NEGATIVE_BINOMIAL_ALPHA_MAX = 5.0
TREND_WARNING_RELATIVE_THRESHOLD = 0.30

FEATURE_COLUMNS = [
    "temp_value",
    "weekday",
    "month",
    "lag_1",
    "lag_7",
    "lag_14",
    "rolling_7",
    "rolling_28",
]
COUNT_MODEL_CONTINUOUS_COLUMNS = [
    "temp_value",
    "lag_1",
    "lag_7",
    "lag_14",
    "rolling_7",
    "rolling_28",
]
COUNT_MODEL_KEYS = ["poisson", "negative_binomial"]
EXPLAINABLE_COUNT_MODEL_KEY = "poisson"
NEGATIVE_BINOMIAL_OVERDISPERSION_THRESHOLD = 1.35
NEGATIVE_BINOMIAL_MIN_TRAIN_ROWS = 56
MIN_POSITIVE_PREDICTION = 1e-6
CLASSIFICATION_THRESHOLD = 0.5

PREDICTION_INTERVAL_LEVEL = 0.90
PREDICTION_INTERVAL_CALIBRATION_FRACTION = 0.6
MIN_INTERVAL_CALIBRATION_WINDOWS = 6
MIN_INTERVAL_EVALUATION_WINDOWS = 4
PREDICTION_INTERVAL_TARGET_BINS = 3
MIN_INTERVAL_BIN_RESIDUALS = 2

EVENT_PROBABILITY_REASON_TOO_FEW_COMPARABLE_WINDOWS = "too_few_comparable_windows"
EVENT_PROBABILITY_REASON_SINGLE_CLASS_EVALUATION = "single_class_evaluation"
EVENT_PROBABILITY_REASON_SATURATED_EVENT_RATE = "saturated_event_rate"

WARNING_INSTABILITY_MESSAGE_TOKENS = (
    "perfect separation",
    "perfect prediction",
    "parameter may not be identified",
    "parameters are not identified",
    "failed to converge",
    "did not converge",
    "singular",
    "hessian",
)

ML_CACHE_SCHEMA_VERSION = 4
ML_CACHE_LIMIT = 128

POISSON_PARAMS = {
    "alpha": 0.40,
    "max_iter": 2000,
}

LOGISTIC_PARAMS = {
    "solver": "liblinear",
    "max_iter": 500,
    "class_weight": "balanced",
    "random_state": 42,
}

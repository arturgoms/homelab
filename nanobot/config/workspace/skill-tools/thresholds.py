"""Centralized thresholds for health, weather, and stress monitoring.

Pure constants — no logic, no imports from siblings.
Imported by: health_check.py, report.py, weather_monitor.py
"""

# Sleep
SLEEP_EXCELLENT = 80
SLEEP_GOOD = 70
SLEEP_FAIR = 60

# Training readiness
READINESS_PRIME = 80
READINESS_READY = 60
READINESS_FAIR = 40

# Body battery
BATTERY_HIGH = 70
BATTERY_MODERATE = 40
BATTERY_LOW = 20

# Steps
STEPS_VERY_ACTIVE = 12000
STEPS_ACTIVE = 10000
STEPS_MODERATE = 7000
STEPS_LIGHT = 4000

# Stress
STRESS_LOW = 25
STRESS_MODERATE = 50
STRESS_HIGH = 75
STRESS_INTRADAY_HIGH = 50       # readings >= this = "high"
STRESS_SUSTAINED_COUNT = 5       # consecutive high readings to trigger alert
STRESS_DAILY_HIGH_PCT = 15       # daily high% to flag
STRESS_2H_HIGH_PCT = 50          # 2h window high% to flag
SLEEP_STRESS_CALM = 25
SLEEP_STRESS_SOME = 40

# HRV
HRV_HIGH = 60
HRV_NORMAL = 40

# RHR
RHR_EXCELLENT = 50
RHR_GOOD = 60

# SpO2
SPO2_LOW = 95

# Body battery alerts
BATTERY_WAKE_LOW = 40
BATTERY_DEPLETED = 20
BATTERY_DRAIN_ALERT = 20         # 2h drain threshold

# Steps verdict
STEPS_GOOD_DAY = 10000
STEPS_LOW_DAY = 4000

# Stress verdict
STRESS_WELL_MANAGED_PCT = 5
STRESS_MODERATE_PCT = 10
STRESS_HIGH_DAY_PCT = 20

# Weather
WEATHER_CONCERNING = {"Rain", "Drizzle", "Thunderstorm", "Snow"}
WEATHER_POP_THRESHOLD = 0.5      # precipitation probability
WEATHER_POP_MENTION = 0.3        # show rain chance in morning report
WEATHER_TEMP_HOT = 35
WEATHER_TEMP_COLD = 5
WEATHER_WIND_STRONG = 10         # m/s

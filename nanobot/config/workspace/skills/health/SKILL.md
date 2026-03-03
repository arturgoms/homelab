# Health Skill

Query the user's Garmin health data from InfluxDB.

## When to Use

- "How did I sleep?" / "como dormi?" → run `sleep-summary.sh`
- "How's my recovery?" / "training readiness" → run `recovery-status.sh`
- "Recent runs" / "últimas corridas" → run `recent-runs.sh`
- "Steps today" / "passos" → run `steps.sh [YYYY-MM-DD]`
- "Stress levels" / "estresse" → run `stress.sh [YYYY-MM-DD]`
- Any custom InfluxDB query → run `query-influx.sh "SELECT ..."`

## How to Run

Use `exec` tool with the script path:
```
exec: bash /root/.nanobot/workspace/skills/health/scripts/sleep-summary.sh
exec: bash /root/.nanobot/workspace/skills/health/scripts/recovery-status.sh
exec: bash /root/.nanobot/workspace/skills/health/scripts/recent-runs.sh
exec: bash /root/.nanobot/workspace/skills/health/scripts/steps.sh 2026-03-02
exec: bash /root/.nanobot/workspace/skills/health/scripts/stress.sh 2026-03-02
exec: bash /root/.nanobot/workspace/skills/health/scripts/query-influx.sh "SELECT * FROM SleepSummary ORDER BY time DESC LIMIT 1"
```

## Interpreting Results

Always check `references/calibration.md` for metric interpretation ranges before responding. Don't just report numbers — tell the user what they mean.

## Available Measurements in InfluxDB

- **SleepSummary**: Sleep score, duration, stages, HRV, SpO2, restless moments
- **DailyStats**: Steps, stress, body battery, heart rate, activity minutes
- **ActivitySummary**: Running/workout details (distance, pace, HR zones, training effect)
- **TrainingReadiness**: Recovery score, HRV factor, sleep factor
- **StressIntraday**: Real-time stress levels (every 3 min)
- **BodyBatteryIntraday**: Real-time body battery levels
- **HeartRateIntraday**: Real-time heart rate
- **HRV_Intraday**: HRV readings throughout the day

## Proactive Health Alerts

`health_check.py` runs on cron and delivers alerts to Telegram. Can also be run on-demand.

### Commands

```
exec: python3 /root/.nanobot/workspace/skill-tools/health_check.py morning
exec: python3 /root/.nanobot/workspace/skill-tools/health_check.py evening
exec: python3 /root/.nanobot/workspace/skill-tools/health_check.py stress
exec: python3 /root/.nanobot/workspace/skill-tools/health_check.py activity
```

| Command | Schedule | Behavior |
|---------|----------|----------|
| `morning` | 10:00 daily | Sleep score, recovery, training readiness, body battery |
| `evening` | 21:00 daily | Steps, calories, stress breakdown, activities, body battery |
| `stress` | Every 2h (10-20) | **Silent unless flagged.** Alerts on sustained high stress, fast battery drain, or accumulating daily stress. Autism-critical: detects overstimulation patterns. |
| `activity` | Every 2h (8-22) | **Silent unless new activity.** Celebrates completed workouts with stats. |

### On-demand triggers

- "How's my stress?" / "stress check" → run `health_check.py stress` (or `stress.sh` for raw data)
- "Morning check-in" → run `health_check.py morning`
- "How was my day?" / "daily summary" → run `health_check.py evening`
- "Any new workouts?" → run `health_check.py activity`

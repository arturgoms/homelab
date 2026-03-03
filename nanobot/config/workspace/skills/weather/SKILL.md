# Weather Skill

Get weather for Curitiba (default) or any city.

## When to Use

- "What's the weather?" / "como tá o tempo?" → Curitiba weather
- "Weather in [city]" → specific city

## How to Run

```
exec: curl -s "wttr.in/Curitiba?format=%C+%t+%h+%w+%p&lang=pt"
```

For detailed forecast:
```
exec: curl -s "wttr.in/Curitiba?format=3"
```

For full report (use sparingly, output is long):
```
exec: curl -s "wttr.in/Curitiba?lang=pt&Q&T"
```

For another city:
```
exec: curl -s "wttr.in/São+Paulo?format=%C+%t+%h+%w+%p&lang=pt"
```

## Interpreting Results

- Include temperature, conditions, and rain chance
- Add a practical hint: "grab an umbrella" / "good running weather" / "leva casaco"
- Match the user's language

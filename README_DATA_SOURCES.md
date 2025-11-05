# Data Source Limitations and Recommendations

## Current Status

### ✅ Working
- **UEFA**: European Championship qualifiers (via Football-Data.org)
- **National Team Filter**: Successfully filters out club teams
- **Group Extraction**: Properly extracts qualifier groups

### ❌ Not Available via Football-Data.org
- World Cup qualifiers for any confederation
- CONMEBOL, CONCACAF, AFC, CAF, OFC qualifier data

## Why Football-Data.org Doesn't Have World Cup Qualifiers

The football-data.org API focuses on:
- Top European leagues (PL, BL1, SA, etc.)
- UEFA club competitions (Champions League, etc.)
- Some national team competitions (UEFA Euros)
- NOT individual confederation World Cup qualifiers

## Recommendations

### Option 1: Use Alternative API (API-Football)
Since you mentioned having access to `dashboard.api-football.com`:
- API-Football has much more comprehensive coverage
- Includes World Cup qualifiers for all confederations
- Better for international competitions

### Option 2: Use UEFA Nations League
We could fetch UEFA Nations League data instead, which includes more countries:
```python
# Add to find_qualifier_competitions():
elif 'nations league' in name:
    qualifiers['UEFA'].append({'name': comp['name'], 'code': code, 'full': comp})
```

### Option 3: Use Current Data as Proxy
- UEFA Euros qualifiers → good proxy for European teams
- Calculate probabilities based on UEFA performance
- Use FIFA rankings for other confederations

### Option 4: Manual Data Entry
- Create a CSV with known qualifier groups
- Manually update from FIFA.com or ESPN
- Import into the system

## Recommendation

**Switch to API-Football** if you have access, as it will give you:
- Real World Cup qualifier data for all confederations
- Up-to-date standings and fixtures
- Better coverage overall

Would you like me to create an integration for API-Football instead?

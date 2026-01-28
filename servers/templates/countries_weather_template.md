# Countries + Weather Patterns

## Pattern 1: Country Dashboard (countries + weather + fx)
Get complete country profile with live weather and currency.

```python
# Multi-server: countries + weather + fx
country = await mcp_countries.get_country(name="France")
capital = country['capital'][0]
currency_code = country['currencies'][0]['code']

# Get weather for capital
weather = await mcp_weather.get_weather(city=capital)

# Get exchange rates for local currency
rates = await mcp_fx.rates(base=currency_code)

print(f"=== {country['name']} ===")
print(f"Capital: {capital}")
print(f"Weather: {weather['temp']}°C, {weather['conditions']}")
print(f"Currency: {currency_code} = {rates['rates'].get('USD', 'N/A')} USD")
print(f"Population: {country['population']:,}")
```

## Pattern 2: Regional Weather Report (countries + weather)
Weather for all capitals in a region.

```python
# Multi-server: countries + weather
countries = await mcp_countries.by_region(region="Western Europe")

results = []
for c in countries[:5]:  # Limit to avoid rate limits
    capital = c['capital'][0] if c.get('capital') else None
    if capital:
        weather = await mcp_weather.get_weather(city=capital)
        results.append({
            'country': c['name'],
            'capital': capital,
            'temp': weather['temp'],
            'conditions': weather['conditions']
        })

# Visualize
render_chart(results, 'bar', x='capital', y='temp', title='Capital City Temperatures')
```

## Pattern 3: Currency Comparison (countries + fx)
Compare currencies across a region.

```python
# Multi-server: countries + fx
countries = await mcp_countries.by_region(region="Europe")

# Get unique currencies
currencies = set()
for c in countries:
    for curr in c.get('currencies', []):
        currencies.add(curr['code'])

# Get rates for each
rates = await mcp_fx.rates(base="USD")
chart_data = [
    {'currency': cur, 'rate': rates['rates'].get(cur, 0)}
    for cur in currencies if cur in rates['rates']
]

render_chart(chart_data, 'bar', x='currency', y='rate', title='European Currency Rates (vs USD)')
```

## Pattern 4: Language Demographics (countries)
Population by language.

```python
# Single server pattern
spanish_countries = await mcp_countries.by_language(language="spanish")

# Aggregate population by region
by_region = {}
for c in spanish_countries:
    region = c['subregion'] or c['region']
    by_region[region] = by_region.get(region, 0) + c['population']

chart_data = [
    {'region': r, 'population': p}
    for r, p in sorted(by_region.items(), key=lambda x: -x[1])
]

render_chart(chart_data, 'bar', x='region', y='population',
             title='Spanish-speaking Population by Region')
```

## Gotchas

```python
# 1. capital is a list (some countries have multiple) - use [0]
capital = country['capital'][0] if country.get('capital') else None

# 2. currencies is a list of dicts with code, name, symbol
currency_code = country['currencies'][0]['code'] if country.get('currencies') else None

# 3. Rate limit weather calls when iterating many countries
for c in countries[:5]:  # Limit iterations

# 4. Some fields may be empty lists
languages = ', '.join(country['languages']) if country['languages'] else 'N/A'
```

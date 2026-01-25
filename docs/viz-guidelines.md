# Visualization Guidelines

## Use `render_chart()` — Always

```python
url = render_chart(data, "bar", x="category", y="value", title="Title")
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | list[dict] or DataFrame | The data to plot |
| `chart_type` | `"bar"` \| `"line"` \| `"scatter"` | Type of chart |
| `x` | str | Field name for X axis |
| `y` | str | Field name for Y axis |
| `title` | str (optional) | Chart title |
| `series` | str (optional) | Field for grouping (colored bars/lines) |
| `filename` | str | Output file (default: "chart.png") |

**Returns:** `file://` URL to the saved image

## Examples

```python
# Bar chart
url = render_chart(data, "bar", x="day", y="sales", title="Daily Sales")

# Line chart with multiple series
url = render_chart(df, "line", x="date", y="revenue", series="region")

# Scatter plot
url = render_chart(data, "scatter", x="height", y="weight")
```

## Rules

1. **Always use `render_chart()`** — Do NOT write matplotlib or seaborn code
2. **One chart per call** — No subplots unless explicitly requested
3. **Print the URL** — Always `print(url)` so the user sees the chart

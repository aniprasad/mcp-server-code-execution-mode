# MS Forms Templates

## Data Structure

```python
data = await mcp_msforms.get_form_data(form=form_url)

# data structure:
# - questions: dict[question_id] -> {id, title, type, required, choices?, ratingScale?}
# - summary: dict[question_id] -> {questionId, type, distribution?, average?, count?, recentValues?}
# - responses: list[{id, submitDate, responder, answers: dict[question_id] -> value}]
```

---

## Pattern 1: Summarize by Type

```python
data = await mcp_msforms.get_form_data(form=form_url)

for qid, q in data['questions'].items():
    s = data['summary'][qid]
    
    if q['type'] == 'rating':
        print(f"{q['title']}: avg={s['average']:.2f}")
    elif q['type'] == 'choice':
        print(f"{q['title']}: {s['distribution']}")
    else:  # text
        print(f"{q['title']}: {s['count']} responses")
```

---

## Pattern 2: Convert to DataFrame

```python
import pandas as pd

data = await mcp_msforms.get_form_data(form=form_url)
titles = {qid: q['title'] for qid, q in data['questions'].items()}

rows = []
for r in data['responses']:
    row = {'id': r['id'], 'date': r['submitDate']}
    for qid, ans in r['answers'].items():
        # Multi-select: join list to string
        row[titles[qid]] = ', '.join(ans) if isinstance(ans, list) else ans
    rows.append(row)

df = pd.DataFrame(rows)

# === YOUR ANALYSIS HERE ===
# Examples:
# df.groupby('Event')['Rating'].mean()
# df[df['Rating'] <= 2]  # Low ratings
# df['Date'].value_counts()
```

---

## Pattern 3: Visualize Distribution

```python
data = await mcp_msforms.get_form_data(form=form_url)

# Pick a question (by type or title)
for qid, q in data['questions'].items():
    if q['type'] in ('choice', 'rating'):  # both have distribution
        dist = data['summary'][qid]['distribution']
        
        # Build chart data
        chart_data = [{'label': k, 'count': v} for k, v in dist.items()]
        
        # Sort: by label for ratings, by count for choices
        if q['type'] == 'rating':
            chart_data.sort(key=lambda x: int(x['label']))
        else:
            chart_data.sort(key=lambda x: -x['count'])
        
        render_chart(chart_data, 'bar', x='label', y='count', title=q['title'])
        break
```

---

## Pattern 4: Group Analysis (e.g., rating by segment)

```python
data = await mcp_msforms.get_form_data(form=form_url)

# Find question IDs by type
rating_q = next(qid for qid, q in data['questions'].items() if q['type'] == 'rating')
segment_q = next(qid for qid, q in data['questions'].items() if q['type'] == 'choice')

# Group ratings by segment
groups = {}
for r in data['responses']:
    segment = r['answers'].get(segment_q, 'Unknown')
    rating = r['answers'].get(rating_q)
    if rating:
        groups.setdefault(segment, []).append(rating)

# Build chart data
chart_data = [
    {'segment': seg, 'avg_rating': sum(ratings)/len(ratings)}
    for seg, ratings in groups.items()
]
chart_data.sort(key=lambda x: -x['avg_rating'])

render_chart(chart_data, 'bar', x='segment', y='avg_rating', 
             title=f"Average Rating by {data['questions'][segment_q]['title']}")
```

---

## Gotchas

```python
# 1. Multi-select answers are lists
answer = r['answers'].get(qid)
if isinstance(answer, list):
    for choice in answer: ...
else:
    single_value = answer  # str for choice, int for rating

# 2. Rating distribution keys are strings
for rating_str, count in summary['distribution'].items():
    rating_int = int(rating_str)

# 3. Empty optional answers are empty strings
if r['answers'].get(qid, ''):  # Skip empty

# 4. Use get_form_summary() for quick stats (no individual responses)
summary = await mcp_msforms.get_form_summary(form=form_url)
```

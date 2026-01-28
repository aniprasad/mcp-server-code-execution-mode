# Tech News + Analysis Patterns

## Pattern 1: HN Story Analysis (hackernews + wikipedia)
Get story context with Wikipedia background.

```python
# Multi-server: hackernews + wikipedia
stories = await mcp_hackernews.top_stories(limit=5)

for story in stories:
    print(f"\n=== {story['title']} ===")
    print(f"Score: {story['score']} | Comments: {story.get('descendants', 0)}")

    # Try to get Wikipedia context for key terms
    # Extract potential topic from title (simplified)
    words = story['title'].split()
    for word in words:
        if len(word) > 5 and word[0].isupper():  # Likely a proper noun
            try:
                wiki = await mcp_wikipedia.summary(title=word)
                if wiki.get('extract'):
                    print(f"Context ({word}): {wiki['extract'][:150]}...")
                    break
            except:
                pass
```

## Pattern 2: Tech Trends Dashboard (hackernews + stocks)
Correlate HN buzz with stock performance.

```python
# Multi-server: hackernews + stocks
companies = [
    ("Apple", "AAPL"),
    ("Google", "GOOGL"),
    ("Microsoft", "MSFT"),
    ("Amazon", "AMZN")
]

results = []
for company, ticker in companies:
    # Get HN mentions
    hn = await mcp_hackernews.search(query=company, limit=10)
    mention_count = len(hn['hits'])
    avg_score = sum(h['points'] for h in hn['hits']) / max(mention_count, 1)

    # Get stock price
    stock = await mcp_stocks.quote(symbol=ticker)

    results.append({
        'company': company,
        'price': stock['price'],
        'hn_mentions': mention_count,
        'avg_score': round(avg_score, 1)
    })
    print(f"{company}: ${stock['price']:.2f} | HN mentions: {mention_count} | Avg score: {avg_score:.0f}")

render_chart(results, 'bar', x='company', y='hn_mentions', title='HN Buzz by Company')
```

## Pattern 3: Book Mentions in Tech News (hackernews + openlibrary)
Find books being discussed on HN.

```python
# Multi-server: hackernews + openlibrary
# Search for book-related HN posts
hn = await mcp_hackernews.search(query="book recommendation programming", limit=20)

print("=== Books Discussed on HN ===")
for hit in sorted(hn['hits'], key=lambda x: -x['points'])[:10]:
    print(f"  [{hit['points']} pts] {hit['title']}")

    # Try to find mentioned book on Open Library
    # Extract book title patterns from HN title
    if '"' in hit['title']:
        # Title might contain quoted book name
        import re
        quoted = re.findall(r'"([^"]+)"', hit['title'])
        for q in quoted[:1]:
            books = await mcp_openlibrary.search_books(query=q, limit=1)
            if books['books']:
                book = books['books'][0]
                print(f"    📚 Found: {book['title']} by {', '.join(book['authors'][:2])}")
```

## Pattern 4: User Analysis (hackernews)
Analyze a HN user's interests.

```python
# Single server, complex pattern
user = await mcp_hackernews.user(username="pg")  # Paul Graham

from datetime import datetime

created = datetime.fromisoformat(user['created'].replace('Z', '+00:00'))

print(f"=== {user['id']} ===")
print(f"Karma: {user['karma']:,}")
print(f"Member since: {created.strftime('%Y-%m-%d')}")
print(f"Total submissions: {user['submitted_count']:,}")

if user.get('about'):
    # about field is HTML
    about_text = user['about'].replace('<p>', '\n').replace('</p>', '')
    print(f"\nAbout:\n{about_text[:300]}")
```

## Pattern 5: Daily Tech Digest (hackernews)
Get categorized top stories.

```python
# Categorize top stories by domain/type
stories = await mcp_hackernews.top_stories(limit=30)

# Group by story type
ask_hn = []
show_hn = []
regular = []

for s in stories:
    title = s['title']
    if title.startswith('Ask HN:'):
        ask_hn.append(s)
    elif title.startswith('Show HN:'):
        show_hn.append(s)
    else:
        regular.append(s)

print("=== Ask HN ===")
for s in ask_hn[:3]:
    print(f"  [{s['score']}] {s['title']}")

print("\n=== Show HN ===")
for s in show_hn[:3]:
    print(f"  [{s['score']}] {s['title']}")

print("\n=== Top Stories ===")
for s in regular[:5]:
    print(f"  [{s['score']}] {s['title'][:60]}")
```

## Pattern 6: Story Deep Dive (hackernews)
Get full story with URL domain analysis.

```python
from urllib.parse import urlparse

story = await mcp_hackernews.story(id=story_id)

print(f"Title: {story['title']}")
print(f"Score: {story['score']} points")
print(f"By: {story['by']}")
print(f"Comments: {story['descendants']}")

if story.get('url'):
    domain = urlparse(story['url']).netloc
    print(f"Source: {domain}")
    print(f"URL: {story['url']}")
else:
    # Self-post (Ask HN, etc.)
    print(f"Type: Self-post")
    if story.get('text'):
        print(f"Text:\n{story['text'][:500]}...")
```

## Gotchas

```python
# 1. HN time is ISO 8601 string with Z suffix
from datetime import datetime
dt = datetime.fromisoformat(story['time'].replace('Z', '+00:00'))

# 2. url may be None for "Ask HN" / "Show HN" posts - check text field instead
content = story.get('url') or story.get('text', 'No content')

# 3. Algolia search (search tool) is separate from Firebase API (top_stories, story)
# - search has points, num_comments
# - top_stories/story has score, descendants

# 4. Rate limit when making many sequential calls
import asyncio
for story_id in story_ids[:10]:
    story = await mcp_hackernews.story(id=story_id)
    await asyncio.sleep(0.1)  # Be nice to the API

# 5. descendants = total comment count (including replies to replies)
# kids = direct child comment IDs (not fetched by default)

# 6. User's about field is HTML - strip tags if needed
import re
clean_about = re.sub(r'<[^>]+>', '', user.get('about', ''))
```

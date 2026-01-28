# Books + Research Patterns

## Pattern 1: Book Deep Dive (openlibrary + wikipedia)
Get book info and Wikipedia context about the author.

```python
# Multi-server: openlibrary + wikipedia
books = await mcp_openlibrary.search_books(query="Clean Code Robert Martin", limit=1)
book = books['books'][0]

# Get author's Wikipedia page
author_name = book['authors'][0] if book.get('authors') else None
if author_name:
    wiki = await mcp_wikipedia.summary(title=author_name)

    print(f"=== {book['title']} ===")
    print(f"Author: {author_name}")
    print(f"Published: {book.get('first_publish_year', 'Unknown')}")
    print(f"\nAbout the Author:")
    print(wiki.get('extract', 'No Wikipedia article found')[:500])
```

## Pattern 2: Topic Research (openlibrary + wikipedia + hackernews)
Research a topic across books, Wikipedia, and tech discussions.

```python
# Multi-server: openlibrary + wikipedia + hackernews
topic = "machine learning"

# Get books on topic
books = await mcp_openlibrary.search_books(query=topic, limit=5)

# Get Wikipedia overview
wiki = await mcp_wikipedia.summary(title=topic.replace(" ", "_"))

# Get HN discussions
hn_results = await mcp_hackernews.search(query=topic, limit=5)

print(f"=== Research: {topic} ===")
print(f"\nWikipedia: {wiki.get('extract', '')[:300]}...")
print(f"\nTop Books:")
for b in books['books'][:3]:
    print(f"  - {b['title']} ({b.get('first_publish_year', '?')})")
print(f"\nHacker News Discussions:")
for hit in hn_results['hits'][:3]:
    print(f"  - {hit['title']} ({hit['points']} pts)")
```

## Pattern 3: Author Bibliography (openlibrary)
Get all books by an author with covers.

```python
# Single server but complex pattern
authors = await mcp_openlibrary.search_authors(query="Brandon Sanderson", limit=1)
author = authors['authors'][0]

# Get author details
author_detail = await mcp_openlibrary.get_author(key=author['key'])

print(f"=== {author['name']} ===")
print(f"Works: {author.get('works_count', 'Unknown')}")
print(f"Born: {author_detail.get('birth_date', 'Unknown')}")

# Get books by author
books = await mcp_openlibrary.search_books(query=f"author:{author['name']}", limit=10)
for b in books['books']:
    icon = '📖' if b.get('cover_url') else ''
    print(f"  - {b['title']} {icon}")
```

## Pattern 4: Book Comparison (openlibrary)
Compare books on similar topics.

```python
# Search for competing books
topic = "Python programming"
books = await mcp_openlibrary.search_books(query=topic, limit=10)

# Build comparison data
chart_data = [
    {
        'title': b['title'][:30],
        'editions': b.get('edition_count', 0),
        'year': int(b['first_publish_year']) if b.get('first_publish_year') else 0
    }
    for b in books['books'] if b.get('first_publish_year')
]

render_chart(chart_data, 'bar', x='title', y='editions', title='Book Editions Count')
```

## Pattern 5: ISBN Lookup with Full Details (openlibrary)

```python
# Get detailed book info by ISBN
book = await mcp_openlibrary.get_book(isbn="9780132350884")

print(f"Title: {book['title']}")
print(f"Authors: {', '.join(book['authors'])}")
print(f"Publisher: {book.get('publishers', ['Unknown'])[0]}")
print(f"Pages: {book.get('number_of_pages', 'Unknown')}")
print(f"Published: {book.get('publish_date', 'Unknown')}")

if book.get('cover_url'):
    print(f"Cover: {book['cover_url']}")

if book.get('description'):
    print(f"\nDescription:\n{book['description'][:500]}...")
```

## Gotchas

```python
# 1. Author names may not match Wikipedia exactly (try variations)
wiki = await mcp_wikipedia.summary(title="Robert C. Martin")  # Try full name
# If not found, try: "Robert Martin (software engineer)"

# 2. cover_url is constructed from cover_i:
# https://covers.openlibrary.org/b/id/{cover_i}-M.jpg
# Or use get_cover tool for more control

# 3. first_publish_year may be string or None
year = book.get('first_publish_year') or 'Unknown'

# 4. authors is a list of names (strings), not objects
author_names = ', '.join(book['authors']) if book['authors'] else 'Unknown'

# 5. HN search uses Algolia (different from Firebase API for top_stories)
# Algolia has more search options but different response format
```

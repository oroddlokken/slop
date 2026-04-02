# Find N+1 Query Patterns

Scan the codebase for N+1 query patterns: places where code loads a collection, then queries individually for each item in a loop.

## What to Look For

### Explicit N+1 — queries in loops
The classic: fetch a list, then query per item:

```python
# BAD: 1 query for users + N queries for orders
users = db.query("SELECT * FROM users")
for user in users:
    orders = db.query(f"SELECT * FROM orders WHERE user_id = ?", (user.id,))
```

```javascript
// BAD: N+1 with async/await in loop
const users = await db.query('SELECT * FROM users')
for (const user of users) {
    const orders = await db.query('SELECT * FROM orders WHERE user_id = ?', [user.id])
}
```

### ORM lazy loading in loops
ORMs default to lazy loading — accessing a relationship in a loop triggers N queries:

```python
# BAD: Django — accessing .orders in a loop triggers N queries
users = User.objects.all()
for user in users:
    print(user.orders.count())  # Each iteration = 1 query

# BAD: SQLAlchemy — lazy-loaded relationship
users = session.query(User).all()
for user in users:
    for order in user.orders:  # Each user triggers a SELECT on orders
        process(order)
```

```ruby
# BAD: ActiveRecord — N+1 on association
User.all.each do |user|
  puts user.orders.count  # N queries
end
```

```javascript
// BAD: Prisma — nested access without include
const users = await prisma.user.findMany()
for (const user of users) {
    const orders = await prisma.order.findMany({ where: { userId: user.id } })
}
```

### Hidden N+1 — property access that triggers queries
Some ORMs allow properties that lazily load related data. These are N+1 traps when accessed in templates, serializers, or list views:

```python
# BAD: Django — in a template or serializer
{% for user in users %}
    {{ user.profile.avatar_url }}  # Each access = 1 query if not prefetched
{% endfor %}
```

### N+1 in API serialization
Serializing a list of objects where each serialization touches a relationship:

```python
# BAD: DRF serializer — nested serializer without prefetch
class UserSerializer(serializers.ModelSerializer):
    orders = OrderSerializer(many=True)  # N+1 if queryset not prefetched
```

### Map/list comprehension N+1
```python
# BAD: List comprehension hiding N+1
order_counts = [user.orders.count() for user in users]
# BAD: map() hiding N+1
results = list(map(lambda u: fetch_orders(u.id), users))
```

## How to Scan

1. **Find all loops** (for/while/each/map) that contain database calls — grep for loop constructs near `execute(`, `query(`, `.filter(`, `.find(`, `.objects.`, `.where(`
2. **Find ORM relationship access patterns**: grep for model relationship access (`.related_name`, `.association`, `.include(`) inside loops, list comprehensions, or iterators
3. **Check serializers and templates**: look for nested serializers (DRF, Marshmallow) and template loops that access relationships
4. **Check for eager loading**: for each N+1 candidate, check if `select_related`, `prefetch_related`, `joinedload`, `selectinload`, `includes`, `eager_load`, `with()`, or `include` is applied upstream
5. **Estimate scale**: how many items does the outer query typically return? N+1 on 5 items is different from N+1 on 5,000

## Severity Guide

- **Critical**: N+1 on a list endpoint with no pagination limit — unbounded query count
- **High**: N+1 on a frequently-hit endpoint (list views, feeds, dashboards) — scales linearly with data growth
- **Medium**: N+1 on admin/internal endpoints or capped collections — works at current scale but will degrade
- **Low**: N+1 on small, bounded collections (enum-like tables, config data) — likely acceptable

## Output Format

After scanning, output:

```
## N+1 Query Patterns

### {Severity}: {short description}

**Location**: `{file}:{line}`
**Pattern**: {explicit loop query / lazy load / serializer / template}
**Outer query**: {the collection query}
**Inner query**: {the per-item query}
**Scale**: {estimated N — how many items does the outer query return?}
**Impact**: {N+1 queries per request, unbounded growth, etc.}
**Fix**: {specific fix for the ORM — select_related, joinedload, JOIN, etc.}
```

End with a Findings Summary table:

| # | Severity | File:Line | Pattern | Scale | Fix |
|---|----------|-----------|---------|-------|-----|
| 1 | High | path:line | lazy load in loop | ~1000 users | Add select_related('orders') |

## Rules

- **Check for existing eager loading before flagging** — many ORMs have it configured at the model level. Verify it's actually missing, not just configured elsewhere.
- **Suggest the right fix for the ORM in use**: Django uses `select_related`/`prefetch_related`, SQLAlchemy uses `joinedload`/`selectinload`/`subqueryload`, ActiveRecord uses `includes`/`eager_load`, Prisma uses `include`, Sequelize uses `include`.
- **Distinguish bounded from unbounded**: N+1 on a paginated endpoint with max 20 items is different from N+1 on `Model.objects.all()`.
- **Flag the consumption site, not just the query**: If the N+1 is caused by a serializer or template, flag that location — that's where the fix goes (prefetch in the view, not in the serializer).

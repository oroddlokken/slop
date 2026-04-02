# Find ORM Anti-patterns

Scan for ORM misuse patterns that cause performance problems, unexpected behavior, or maintainability issues. Focuses on non-loop ORM issues (N+1 in loops is owned by the n-plus-one reviewer).

## What to Look For

### SELECT * via ORM (loading unnecessary data)
```python
# BAD: Loading entire User objects when you only need names
users = User.objects.all()
names = [u.name for u in users]

# Better: .values_list('name', flat=True) or .only('name')
```

```python
# BAD: SQLAlchemy loading full objects for a count
count = len(session.query(User).all())
# Better: session.query(func.count(User.id)).scalar()
```

### ORM for bulk operations
```python
# BAD: Creating objects one by one in ORM
for item in items:
    Order.objects.create(item_id=item.id, qty=item.qty)

# Better: Order.objects.bulk_create([Order(item_id=i.id, qty=i.qty) for i in items])
```

```python
# BAD: Updating objects one by one
for user in users:
    user.last_seen = now()
    user.save()

# Better: User.objects.filter(id__in=user_ids).update(last_seen=now())
```

### Excessive filter chaining producing bad SQL
```python
# BAD: Chaining filters that the ORM can't optimize well
qs = Order.objects.all()
if status:
    qs = qs.filter(status=status)
if min_date:
    qs = qs.filter(created_at__gte=min_date)
if user:
    qs = qs.filter(user=user)
# Each filter may produce a subquery instead of a flat WHERE clause (depends on ORM)
```

### Using ORM where raw SQL is clearly better
```python
# BAD: Complex aggregation forced through ORM
result = (Order.objects
    .filter(status='completed')
    .values('product__category')
    .annotate(
        total=Sum('amount'),
        avg_amount=Avg('amount'),
        max_amount=Max('amount'),
        order_count=Count('id'),
        unique_customers=Count('user_id', distinct=True),
    )
    .filter(order_count__gt=10)
    .order_by('-total'))
# This is a reporting query — raw SQL would be clearer and potentially faster
```

### Incorrect eager/lazy loading configuration
```python
# BAD: Eager loading everything at the model level
class User(Base):
    orders = relationship("Order", lazy="joined")  # Always JOINs orders, even when not needed
```

```python
# BAD: Never eager loading, leaving it to per-query — leads to inconsistent N+1 behavior
class User(Base):
    orders = relationship("Order", lazy="select")  # Default — lazy load every time
# Whether this causes N+1 depends on whether each query remembers to joinedload()
```

### .count() vs len() vs exists()
```python
# BAD: Loading all objects to check if any exist
if len(User.objects.filter(email=email)) > 0:
    raise EmailTaken

# Better: User.objects.filter(email=email).exists()
```

```python
# BAD: .count() when you only need existence
if User.objects.filter(email=email).count() > 0:
    # .exists() is faster — stops at first match
```

### Implicit queries in properties/methods
```python
# BAD: Model property that triggers a query — callers don't realize it
class User(Model):
    @property
    def order_count(self):
        return self.orders.count()  # Query on every access
```

### get_or_create race conditions
```python
# BAD: Check-then-create without unique constraint
if not User.objects.filter(email=email).exists():
    User.objects.create(email=email)
# Race: two requests both pass the check, both create — duplicate
```

Should use: `get_or_create()` with a unique constraint, or INSERT ... ON CONFLICT.

## How to Scan

1. **Find ORM query patterns**: `.objects.all()`, `.query(Model).`, `Model.findAll(`, `Model.find(`, `session.query(`, `prisma.model.findMany(`
2. **Check what's loaded**: Are queries selecting all columns when only a few are needed? Look for `.only()`, `.defer()`, `.values()`, `.select()` usage — or lack thereof.
3. **Find bulk operation opportunities**: Look for ORM create/update/delete inside loops. Check for `bulk_create`, `bulk_update`, `update()`, `delete()` bulk methods.
4. **Check eager loading config**: Look at model relationship definitions — what's the default loading strategy? Is it appropriate?
5. **Find .count() vs .exists()**: Grep for `count() > 0`, `count() == 0`, `count() >= 1`, `len(queryset)` patterns
6. **Check for implicit queries**: Properties or methods on models that execute queries

## Severity Guide

- **High**: ORM used for bulk operations (create/update/delete in loops) on large datasets — O(N) queries instead of O(1)
- **High**: Loading full objects for simple counts or existence checks — unnecessary memory and DB load
- **Medium**: SELECT * when only 1-2 columns needed on large tables — wasted bandwidth and memory
- **Medium**: Eager loading configured too broadly at model level — unnecessary JOINs on every query
- **Medium**: get_or_create without unique constraint — race condition creating duplicates
- **Low**: Excessive filter chaining — usually fine, but can produce suboptimal SQL in edge cases
- **Low**: Complex aggregations in ORM that would be clearer as raw SQL — readability, not performance

## Output Format

After scanning, output:

```
## ORM Anti-patterns

### {Severity}: {short description}

**Location**: `{file}:{line}`
**Pattern**: {SELECT *, bulk in loop, wrong loading, count vs exists, etc.}
**ORM**: {Django ORM / SQLAlchemy / Prisma / etc.}
**Current**: {what the code does}
**Impact**: {performance, memory, race condition, readability}
**Fix**: {specific ORM method to use instead}
```

End with a Findings Summary table:

| # | Severity | File:Line | Pattern | ORM | Fix |
|---|----------|-----------|---------|-----|-----|
| 1 | High | views.py:42 | Bulk create in loop | Django | Use bulk_create() |

## Rules

- **Defer N+1 in loops to the n-plus-one reviewer** — this reviewer covers non-loop ORM misuse
- **Know the ORM**: Django's `.all()` is lazy (doesn't execute until iterated). SQLAlchemy's `.all()` executes immediately. Prisma's `findMany()` always executes. Adjust analysis accordingly.
- **Don't flag ORM usage that's appropriate** — simple CRUD through an ORM is fine. Only flag when raw SQL would be materially better (complex aggregations, CTEs, window functions).
- **The ORM's abstraction is usually worth keeping** — suggest ORM-native improvements first (bulk_create, select_related, .only()), raw SQL only as last resort.

# Find Transaction Gaps

Scan for multi-step database writes that lack transaction boundaries — places where a partial failure would leave the database in an inconsistent state.

## What to Look For

### Multiple writes without a transaction
```python
# BAD: If the second insert fails, user exists without a profile
db.execute("INSERT INTO users (name) VALUES (?)", (name,))
db.execute("INSERT INTO profiles (user_id, bio) VALUES (?, ?)", (user_id, bio))
```

```python
# BAD: ORM equivalent
user = User(name=name)
db.session.add(user)
db.session.flush()
profile = Profile(user_id=user.id, bio=bio)
db.session.add(profile)
db.session.commit()  # Both writes in one commit, but no explicit transaction = auto-commit may be on
```

### Delete + recreate without transaction
```python
# BAD: If create fails, data is gone
db.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
db.execute("INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?)", (user_id, k, v))
```

### Read-modify-write without transaction (lost updates)
```python
# BAD: Race condition — another request can modify balance between read and write
balance = db.execute("SELECT balance FROM accounts WHERE id = ?", (id,)).fetchone()
new_balance = balance[0] - amount
db.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, id))
```

Should use: `UPDATE accounts SET balance = balance - ? WHERE id = ?` inside a transaction, or SELECT FOR UPDATE.

### Cross-table consistency requirements
```python
# BAD: Order created but inventory not decremented — or vice versa
create_order(user_id, items)
decrement_inventory(items)
charge_payment(user_id, total)
# If charge_payment fails, order exists but payment doesn't
```

### Missing rollback on error
```python
# BAD: Transaction started but no rollback on exception
conn.execute("BEGIN")
try:
    conn.execute("INSERT INTO ...")
    conn.execute("UPDATE ...")
    conn.execute("COMMIT")
except:
    pass  # Transaction left open or half-committed
```

### Long-running transactions
```python
# BAD: Holding a transaction open while making HTTP calls
with db.transaction():
    order = create_order(...)
    payment = payment_gateway.charge(...)  # Network call holding DB locks
    update_order_status(order.id, payment.status)
```

### Deadlock risk patterns
Two transactions acquiring locks in different orders:

```python
# Transaction A: locks users row, then orders row
# Transaction B: locks orders row, then users row
# Result: deadlock — both wait forever
```

Look for: inconsistent lock ordering across code paths, missing retry logic for deadlock errors, long-held locks during network calls.

### Auto-commit mode issues
- Framework configured with auto-commit ON — each statement is its own transaction
- Mixing auto-commit and explicit transactions inconsistently

## How to Scan

1. **Find multi-statement write sequences**: Look for consecutive INSERT/UPDATE/DELETE statements, or consecutive ORM `.save()`/`.add()`/`.delete()` calls
2. **Check for transaction boundaries**: `BEGIN`/`COMMIT`, `atomic()`, `transaction()`, `session.begin()`, `.transacting()`, `with db.transaction():`, `@transaction.atomic`
3. **Find read-modify-write patterns**: SELECT followed by UPDATE on the same row, without FOR UPDATE or atomic update
4. **Check error handling around transactions**: Is there a ROLLBACK or exception handler that rolls back? Are exceptions swallowed?
5. **Find cross-service calls inside transactions**: Network calls (HTTP, RPC, message queue) inside transaction blocks
6. **Check framework defaults**: Is auto-commit on or off? Does the ORM wrap each request in a transaction (Django's `ATOMIC_REQUESTS`)?

## Severity Guide

- **Critical**: Multi-step writes involving financial data (payments, balances, transfers) without transactions — money can be lost or duplicated
- **Critical**: Delete + recreate pattern without transaction — data loss on partial failure
- **High**: Read-modify-write without SELECT FOR UPDATE or atomic update — race conditions under concurrent access
- **High**: Missing rollback on error — transactions left in unknown state
- **Medium**: Multi-step writes on non-critical data without transactions — inconsistent state but recoverable
- **Medium**: Long-running transactions holding locks during network calls — deadlock/timeout risk
- **Low**: Auto-commit mode ambiguity — unclear but not yet causing issues

## Output Format

After scanning, output:

```
## Transaction Gaps

### {Severity}: {short description}

**Location**: `{file}:{line_range}`
**Write sequence**: {what operations happen in sequence}
**Transaction boundary**: {none / incomplete / rollback missing}
**Failure scenario**: {what happens if step N fails — describe the inconsistent state}
**Impact**: {data loss, orphaned records, incorrect balances, etc.}
**Fix**: {wrap in transaction, add rollback, use atomic update, etc.}
```

End with a Findings Summary table:

| # | Severity | File:Line | Write Sequence | Gap | Fix |
|---|----------|-----------|---------------|-----|-----|
| 1 | Critical | payments.py:42-58 | charge + create_order | No transaction | Wrap in atomic() |

## Rules

- **Check the framework's default transaction behavior** before flagging — Django with `ATOMIC_REQUESTS=True` wraps every view in a transaction automatically. SQLAlchemy's Session commits on `.commit()`, not per-statement. Know the defaults.
- **A single INSERT/UPDATE doesn't need an explicit transaction** — it's already atomic at the SQL level
- **Flag the failure scenario explicitly** — "what if line 47 fails?" is more actionable than "missing transaction"
- **Distinguish read-only transactions from write transactions** — read-only doesn't need SERIALIZABLE
- **Schema-level constraints (FK, UNIQUE, NOT NULL, CHECK) belong to data-integrity reviewer.** This reviewer owns transaction boundaries and isolation. When both apply (e.g., missing FK AND missing transaction on a multi-step write), this reviewer takes the finding — the transaction is the immediate fix.

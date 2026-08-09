# Find Payload Waste

Scan the codebase for data that crosses a boundary and is not used: rows fetched to read one column, responses that return everything about everything, endpoints and queries with no pagination, and whole files or documents loaded to answer a small question. You own **the size of what moves**. How many trips are made belongs to `io-batching`; what happens to the bytes in the heap belongs to `allocations`.

The question this lens asks of every fetch and every response: **how much of this does the consumer actually read?**

## What to Look For

### Over-fetching columns

`SELECT *` or an ORM full-object load where the caller reads two fields. Costs bandwidth, deserialization, and — when the unread columns are large (blobs, JSON documents, text bodies) — most of the query's time.

```python
# BAD: whole rows over the wire to compute a count of ids
rows = db.query("SELECT * FROM records WHERE day = ?", day)
ids = {r.session_id for r in rows}

# GOOD
ids = db.query("SELECT DISTINCT session_id FROM records WHERE day = ?", day)
```

Aggregation is the same finding one level up: pulling every row to sum a column in Python when the database will sum it in one round trip and return one number.

### Over-fetching rows

A query with no `LIMIT` behind a screen that shows 20 items; loading a whole table to find one record; fetching a full history to display the last week. Look for filters applied in application code that could have been in the query — that is the tell, and it is common because it reads naturally.

### Missing pagination

An endpoint, CLI listing, or export that returns everything, with no page size, no cursor, and no cap. It is fine in development and it is an outage in production once the table grows. The severity depends on whether anything bounds the result set at all — an unbounded response on a growing table is the Critical case for this lens.

### Oversized responses

Serializing a full object graph where the client uses three fields; embedding related entities the consumer discards; returning internal fields, debug payloads, or full stack traces; nesting a list of children inside each of a list of parents. Check the consumer if it is in the repo (a frontend, a caller module, a test asserting the shape) — the fields it reads are the fields the response needs.

### No streaming where the data is large

Building an entire export, report, or file in memory and returning it in one piece, when the producer could stream and the consumer could consume incrementally: CSV exports, log downloads, large JSON arrays, file proxying. Costs peak memory proportional to the largest result and delays the first byte until the last row is ready.

### Reading a whole document to use part of it

Loading and parsing an entire JSON, XML, or JSONL file for one field or a date range, when the format allows seeking, line-wise filtering, or a narrower query. Also: re-reading a whole file per call where an index, an offset, or a rollup would answer directly.

### Uncompressed or unnegotiated transfer

Text-heavy responses served without compression, no `Accept-Encoding` handling, verbose formats where a compact one is available on both ends. Real, but usually Medium — a configuration fix, not a design one.

### Chatty payload growth over time

A response that grows with the account's history rather than with the page — a "recent activity" field that returns everything, an embedded list with no cap. These pass review when the data is new and become the top finding a year later. Flag the missing bound, not today's size.

## What NOT to Flag

- **The speculative version of this lens: `SELECT *` on small, bounded tables.** A config table with 12 rows, a lookup of enum values, a settings row. Naming the columns is tidier and it is not a performance finding.
- **Over-fetching on a path that runs once.** A migration, a nightly export, an admin command. Nobody waits and nothing scales.
- **Missing pagination on inherently bounded results** — a query keyed by primary key, a list whose size is fixed by the schema (one row per weekday, one per model), a result already constrained by a `WHERE` on a bounded dimension.
- **Field-level trimming with no size behind it.** Suggesting a client drop two small string fields from a response is micro-optimization; the finding needs either a large field, a large row count, or a growing one.
- **Streaming proposals for small results.** Streaming costs complexity — chunked handling, partial-failure semantics, harder testing. Do not propose it for a result you cannot show is large.
- **Compression already handled by the layer above** — a reverse proxy, CDN, or framework middleware. Check before flagging.
- **The query's correctness or shape.** Injection, missing indexes, transaction scope, and the right ORM idiom are `query-smells`/`dba`. You own how much data comes back.
- **Response fields required by a contract** — a public API's documented schema, a client version still in the field. Note the cost, do not propose breaking it silently.

## How to Scan

1. **Inventory the boundaries where data is sized**: query call sites, API route handlers and their serializers, file reads, export and report generators, cache writes.
2. **Grep for `SELECT *`**, ORM full-object loads (`.all()`, `.objects.all()`, `find({})`, `.filter(...)` with no field projection), and for `fetchall`.
3. **For each fetch, read the consumer.** Which fields and how many rows does the code that receives this actually touch? That comparison is the finding.
4. **Grep for queries and endpoints with no `LIMIT`, no `.limit(`, no page size, no cursor** — then check whether the underlying table or collection grows.
5. **Find filters applied after the fetch**: a comprehension, `filter()`, or `if` over query results that a `WHERE` could have expressed.
6. **Find aggregations done in application code** over rows fetched only to be aggregated.
7. **Read the serializers**: which fields are exposed, what is nested, whether related objects are embedded, whether nested lists are capped.
8. **Check for streaming support** in the framework and the client on paths that build large results in memory.
9. **Cite the size**: row counts, retention windows, page sizes, file sizes, growth per user per day, from the workload map's data-source table. This lens is unusable without it.

## Report Findings

For each payload finding:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Kind** | Over-fetch columns / Over-fetch rows / Missing pagination / Oversized response / No streaming / Whole-document read / Uncompressed |
| **Workload** | Entry point + cadence + what sets the size (cite the workload map) |
| **Waste** | What is transferred versus what is used — fields, rows, bytes, and whether it grows |
| **Fix** | Concrete change — project the columns, push the filter into the query, aggregate in the database, add a page size and cursor, stream, trim the serializer |

### Severity Guide

- **Critical**: An unbounded result set on a growing table with no pagination and no cap, on a path the map shows is reachable in production — the response size grows until the request times out or the process runs out of memory.
- **High**: Substantial over-fetching on a hot path — full rows where one column is used, a whole file read per request, a response carrying an unbounded embedded list.
- **Medium**: Over-fetching on a warm path, missing pagination on a table that is small today with no structural bound, missing compression on large text responses.
- **Low**: `SELECT *` on small bounded tables, cold-path over-fetching, field-level trimming, and anything whose size you could not establish.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Workload | Kind | Waste | Fix |
|---|----------|-----------|----------|------|-------|-----|
| 1 | High | report.py:140 | per report run, all records in window | Over-fetch columns | full rows fetched to sum one column | `SELECT SUM(cost_usd) ... GROUP BY day` |

## Rules

- **Compare fetched to used.** That comparison *is* the finding. A fetch you have not traced to its consumer is not one.
- **Name the size and what bounds it, or stay at Low.** Rows, fields, bytes, growth rate — from the workload map, a `LIMIT`, a page size, or a retention window.
- **Growth beats current size.** An unbounded embedded list is a finding today even when it holds four items; a bounded 200-row fetch is not.
- **Check the consumer before trimming a response.** A field you call unused may be read by a client outside this repo — say so rather than guessing.
- **Do not propose streaming or pagination as a reflex.** Both change the interface and its error semantics. Propose them where the size justifies the cost, and say what the interface change is.
- **Push work to where the data is** when it is cheap there — filtering, aggregating, limiting, and sorting are usually cheaper in the database than after the transfer. But say so as a size argument, not a query-shape argument; the shape is `query-smells`'.
- **Do not invent byte counts.** "Returns every column of every row in the window to compute one sum" is defensible; "about 4MB per request" is not, unless the snapshot measured it.

# ADR 0001: Keep legacy PostgreSQL table names for now

- **Status:** Accepted
- **Date:** 2026-05-31

## Context

The first schema used table names `players` and `stats`. After the clean-architecture
refactor, domain and ORM names reflect the current model (`DrawEntrantORM`,
`DrawStatsORM`, draw entrants, draw statistics), but the physical PostgreSQL tables
were not renamed.

Renaming requires an Alembic migration on a live database. That is a breaking,
operationally risky change (downtime or careful rename strategy) with no user-facing
benefit while the service runs correctly through SQLAlchemy `__tablename__` mapping.

## Decision

**Defer** renaming PostgreSQL tables until a release that already justifies breaking
or high-risk database work (for example a major version or another schema migration
that requires a maintenance window).

Until then:

- ORM keeps explicit legacy `__tablename__` values.
- Application code uses domain names only; do not introduce new references to
  `players` / `stats` as business terms.
- README documents the mismatch for operators.

## Target rename (when done)

| Current table | Intended name (TBD) |
|---------------|---------------------|
| `players`     | e.g. `draw_entrants` |
| `stats`       | e.g. `draw_stats`    |

Exact target names and migration steps to be defined in the ADR or issue that
implements the rename.

## Consequences

- **Positive:** No migration risk on 1.x; code and docs are already aligned at the
  application layer.
- **Negative:** Operators inspecting raw SQL see old names; new contributors must
  read this ADR or README.
- **Neutral:** Alembic history and existing backups refer to `players` / `stats`.

## When to revisit

Revisit this ADR when any of the following is true:

- Planning a **major** release (2.0.0) or explicit breaking-change release.
- Adding external consumers of the database schema (analytics, replicas, manual SQL).
- Any migration that already requires a maintenance window — bundle rename then.

Do **not** rename tables as drive-by work unrelated to a release plan.

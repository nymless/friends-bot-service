# ADR 0001: Rename legacy PostgreSQL table names

- **Status:** Accepted
- **Date:** 2026-05-31
- **Implemented:** 2026-06-07

## Context

The first schema used table names `players` and `stats`. After the clean-architecture
refactor, domain and ORM names reflect the current model (`DrawEntrantORM`,
`DrawStatsORM`, draw entrants, draw statistics), but the physical PostgreSQL tables
were not renamed until migration `a7f3c2d91e04`.

## Decision

Rename PostgreSQL tables to match application terminology:

| Former table | Current table   |
|--------------|-----------------|
| `players`    | `draw_entrants` |
| `stats`      | `draw_stats`    |

Application code uses draw terminology only (`DrawType`, `DrawEntrant`, `DrawStats`);
identifiers such as `GameType`, `Player`, and legacy table names are not used in
business logic.

## Consequences

- **Positive:** Raw SQL, backups after migration, and application names align.
- **Negative:** Existing backups and Alembic history before `a7f3c2d91e04` refer to
  old table names; restore/migrate paths must run Alembic through head.
- **Neutral:** Initial migration files keep historical names for auditability.

## When to revisit

Only if a future schema split or external analytics consumer requires further
physical renames beyond `draw_entrants` / `draw_stats`.

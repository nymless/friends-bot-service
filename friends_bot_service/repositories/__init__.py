"""
This package contains repository modules with database access functions.

Contracts:
1. They encapsulate database reads, writes, and query conditions
   in terms of handlers business logic units.
2. They do not orchestrate application flows or user-facing behavior.
3. They expect a session and all required parameters.
4. They never call session.commit().
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatLine:
    full_name: str
    count: int

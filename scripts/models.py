from dataclasses import dataclass
from typing import Literal


FetchStatus = Literal[
    "available",
    "not_published",
    "failed"
]


@dataclass(frozen=True)
class FetchResult:
    status: FetchStatus
    html: str | None
    http_status: int | None
    error: str | None = None
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Lock


class ProxyType(str, Enum):
    HTTP   = "http"
    HTTPS  = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class Anonymity(str, Enum):
    ELITE       = "elite"
    ANONYMOUS   = "anonymous"
    TRANSPARENT = "transparent"
    UNKNOWN     = "unknown"


@dataclass(frozen=True)
class Proxy:
    host: str
    port: int
    type: ProxyType

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"

    def as_requests_dict(self) -> dict[str, str]:
        url = f"{self.type.value}://{self}"
        return {"http": url, "https": url}


@dataclass
class CheckResult:
    proxy:      Proxy
    alive:      bool
    latency_ms: float | None   = None
    country:    str   | None   = None
    anonymity:  Anonymity      = Anonymity.UNKNOWN
    error:      str   | None   = None
    check_url:  str   | None   = None


@dataclass
class Stats:
    total: int = 0
    alive: int = 0
    dead:  int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record(self, result: CheckResult) -> None:
        with self._lock:
            self.total += 1
            if result.alive:
                self.alive += 1
            else:
                self.dead += 1

    @property
    def success_rate(self) -> float:
        return (self.alive / self.total * 100) if self.total else 0.0

    def __iadd__(self, other: "Stats") -> "Stats":
        # Thread-safe merge: acquire both locks in a consistent order
        # to prevent deadlock when two Stats objects merge concurrently.
        first, second = (self, other) if id(self) < id(other) else (other, self)
        with first._lock:
            with second._lock:
                self.total += other.total
                self.alive += other.alive
                self.dead  += other.dead
        return self

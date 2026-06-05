from __future__ import annotations

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import PROXY_SOURCES, TIMEOUT_SEC
from .models import Proxy, ProxyType

log = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://",  adapter)
    session.mount("https://", adapter)
    session.trust_env = False
    return session


def parse_line(line: str, proxy_type: ProxyType) -> Proxy | None:
    """Parse a host:port line into a Proxy. Returns None for invalid lines."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if "://" in line:
        line = line.split("://", 1)[1]

    if "@" in line:
        line = line.split("@", 1)[1]

    if ":" not in line:
        return None

    host, _, port_str = line.rpartition(":")
    host     = host.strip()
    port_str = port_str.strip().split()[0]

    if not host:
        return None

    try:
        port = int(port_str)
    except ValueError:
        return None

    if not (1 <= port <= 65535):
        return None

    return Proxy(host=host, port=port, type=proxy_type)


def fetch_proxies(proxy_type: ProxyType) -> list[Proxy]:
    """Fetch and deduplicate proxies from all configured sources."""
    sources = PROXY_SOURCES.get(proxy_type.value, [])
    seen:    set[str]    = set()
    proxies: list[Proxy] = []

    with _make_session() as session:
        for url in sources:
            try:
                resp = session.get(url, timeout=TIMEOUT_SEC)
                resp.raise_for_status()
            except requests.RequestException as exc:
                log.warning("Source unavailable [%s]: %s", url, exc)
                continue

            for line in resp.text.splitlines():
                proxy = parse_line(line, proxy_type)
                if proxy:
                    key = str(proxy)
                    if key not in seen:
                        seen.add(key)
                        proxies.append(proxy)

    return proxies

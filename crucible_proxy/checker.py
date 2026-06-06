from __future__ import annotations

import ipaddress
import logging
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .constants import (
    ANONYMITY_CHECK_URLS,
    CHECK_RETRIES,
    CHECK_URLS,
    IP_INFO_URL,
    MAX_WORKERS,
    RETRY_DELAY,
    TIMEOUT_SEC,
    VERIFY_TWICE,
)
from .models import Anonymity, CheckResult, Proxy

log = logging.getLogger(__name__)

# Headers that reveal the real client IP — presence means non-elite
_FORWARDED_HEADERS = frozenset({
    "x-forwarded-for",
    "x-real-ip",
    "via",
    "forwarded",
    "x-proxy-id",
    "x-client-ip",
})


def _is_ip_address(value: str) -> bool:
    """Return True if *value* is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(value.strip())
        return True
    except ValueError:
        return False


def _single_check(
    proxy: Proxy,
    session: requests.Session,
    url: str,
    timeout: int = TIMEOUT_SEC,
) -> tuple[bool, float | None, str | None]:
    start = time.perf_counter()
    try:
        resp = session.get(
            url,
            proxies=proxy.as_requests_dict(),
            timeout=timeout,
        )
        resp.raise_for_status()
        latency = round((time.perf_counter() - start) * 1000, 1)
        return True, latency, None
    except Exception as exc:
        return False, None, str(exc)


def _resolve_check_url(
    proxy: Proxy,
    session: requests.Session,
    timeout: int = TIMEOUT_SEC,
) -> str | None:
    """Try each CHECK_URL and return the first one that responds."""
    for url in CHECK_URLS:
        ok, _, _ = _single_check(proxy, session, url, timeout=timeout)
        if ok:
            return url
    return None


def _detect_anonymity(
    proxy: Proxy,
    session: requests.Session,
    timeout: int = TIMEOUT_SEC,
) -> tuple[str | None, Anonymity]:
    """
    Determine country and true anonymity level.

    Anonymity logic:
    - ELITE       : no forwarding headers sent to the destination
    - ANONYMOUS   : proxy headers present but real IP hidden
    - TRANSPARENT : X-Forwarded-For / similar leak the real IP
    - UNKNOWN     : ip-api call failed

    Uses ip-api for country + proxy/hosting flags, and ANONYMITY_CHECK_URL
    (/headers endpoint) for header-level anonymity detection.
    """
    country: str | None = None
    anonymity = Anonymity.UNKNOWN

    # ── Step 1: ip-api for country ────────────────────────────────────────────
    try:
        resp = session.get(
            IP_INFO_URL,
            proxies=proxy.as_requests_dict(),
            timeout=timeout,
        )
        data    = resp.json()
        country = data.get("countryCode") or data.get("country")
    except Exception:
        pass  # country stays None; we still try header detection

    # ── Step 2: header-based anonymity detection ───────────────────────────────
    try:
        resp = session.get(
            ANONYMITY_CHECK_URLS,
            proxies=proxy.as_requests_dict(),
            timeout=timeout,
        )
        headers_seen: dict[str, str] = {
            k.lower(): v for k, v in resp.json().get("headers", {}).items()
        }
        forwarding = _FORWARDED_HEADERS & headers_seen.keys()

        if not forwarding:
            anonymity = Anonymity.ELITE
        else:
            # Transparent: our real IP is visible in a forwarding header
            real_ip_leaked = any(
                _is_ip_address(part)
                for k, v in headers_seen.items()
                if k in forwarding
                for part in v.split(",")
            )
            anonymity = Anonymity.TRANSPARENT if real_ip_leaked else Anonymity.ANONYMOUS

    except Exception:
        # Fall back to ip-api proxy flag if the headers endpoint is unreachable
        try:
            resp2 = session.get(
                IP_INFO_URL,
                proxies=proxy.as_requests_dict(),
                timeout=timeout,
            )
            d = resp2.json()
            if d.get("proxy") or d.get("hosting"):
                anonymity = Anonymity.ELITE
            else:
                anonymity = Anonymity.ANONYMOUS
        except Exception:
            pass

    return country, anonymity


def check_proxy(
    proxy: Proxy,
    verify_twice: bool = VERIFY_TWICE,
    check_retries: int = CHECK_RETRIES,
    timeout: int = TIMEOUT_SEC,
) -> CheckResult:
    """
    Validate a proxy with up to check_retries attempts.

    - On first failure, tries fallback CHECK_URLs before giving up.
    - Optionally double-verifies passing proxies (latency is averaged).
    - Fetches country and true anonymity level for live proxies.

    The `timeout` parameter is forwarded to every network call so
    CLI overrides propagate correctly without mutating global state.
    """
    session = requests.Session()
    session.trust_env = False
    last_error: str | None = None
    active_url = CHECK_URLS[0]

    try:
        alive   = False
        latency: float | None = None

        for attempt in range(check_retries):
            ok, lat, err = _single_check(proxy, session, active_url, timeout=timeout)
            if ok:
                alive   = True
                latency = lat
                break

            # On first failure: try to find a working check URL before retrying
            if attempt == 0:
                fallback = _resolve_check_url(proxy, session, timeout=timeout)
                if fallback and fallback != active_url:
                    active_url = fallback
                    ok2, lat2, _ = _single_check(proxy, session, active_url, timeout=timeout)
                    if ok2:
                        alive   = True
                        latency = lat2
                        break

            last_error = err
            if attempt < check_retries - 1:
                time.sleep(RETRY_DELAY)

        if not alive:
            return CheckResult(proxy=proxy, alive=False, error=last_error)

        if verify_twice:
            time.sleep(RETRY_DELAY)
            ok2, lat2, err2 = _single_check(proxy, session, active_url, timeout=timeout)
            if not ok2:
                return CheckResult(
                    proxy=proxy,
                    alive=False,
                    error=f"verification failed: {err2}",
                )
            if lat2 is not None and latency is not None:
                latency = round((latency + lat2) / 2, 1)

        country, anonymity = _detect_anonymity(proxy, session, timeout=timeout)

        return CheckResult(
            proxy=proxy,
            alive=True,
            latency_ms=latency,
            country=country,
            anonymity=anonymity,
            check_url=active_url,
        )
    finally:
        session.close()


def check_all(
    proxies: list[Proxy],
    max_workers: int = MAX_WORKERS,
    timeout: int = TIMEOUT_SEC,
    verify_twice: bool = VERIFY_TWICE,
) -> Iterator[CheckResult]:
    """Validate proxies in parallel; yield results as they complete."""
    workers = min(max_workers, len(proxies)) if proxies else 1
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(check_proxy, p, verify_twice=verify_twice, timeout=timeout): p
            for p in proxies
        }
        for future in as_completed(futures):
            try:
                yield future.result()
            except Exception as exc:
                log.error("Unexpected error checking %s: %s", futures[future], exc)

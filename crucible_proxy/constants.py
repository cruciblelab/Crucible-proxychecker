from __future__ import annotations

import os
from pathlib import Path

TIMEOUT_SEC   = 8
MAX_WORKERS   = min(500, (os.cpu_count() or 4) * 50)
CHECK_RETRIES = 2
RETRY_DELAY   = 0.6
VERIFY_TWICE  = True
OUTPUT_DIR    = Path("output")

CHECK_URLS: list[str] = [
    "http://httpbin.org/ip",
    "http://api.ipify.org/?format=json",
    "http://ip-api.com/json/",
]

# Multiple anonymity-check endpoints tried in order until one responds.
# All must return JSON with a top-level "headers" object (httpbin /headers format).
# Override the primary via CRUCIBLE_ANONYMITY_CHECK_URL env var.
ANONYMITY_CHECK_URLS: list[str] = [
    os.environ.get("CRUCIBLE_ANONYMITY_CHECK_URL", "http://httpbin.org/headers"),
    "https://httpbin.org/headers",
    "http://httpbingo.org/headers",
    "https://httpbingo.org/headers",
    "http://eu.httpbin.org/headers",
]

# Primary URL — kept for backwards compatibility
ANONYMITY_CHECK_URL: str = ANONYMITY_CHECK_URLS[0]

# ip-api returns country and anonymity info
IP_INFO_URL = "http://ip-api.com/json/"

PROXY_SOURCES: dict[str, list[str]] = {
    "http": [
        # ── API tabanlı ──────────────────────────────────────────────────────
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http&proxy_format=protocolipport&format=text&timeout=10000",
        "https://proxylist.geonode.com/api/proxy-list?protocols=http&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://raw.githubusercontent.com/fate0/proxylist/master/proxy.list",

        # ── GitHub repo listeleri ────────────────────────────────────────────
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
        "https://raw.githubusercontent.com/almroot/proxylist/master/list.txt",
        "https://raw.githubusercontent.com/andigwandi/free-proxy/main/proxy_list.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/http_proxies.txt",
        "https://raw.githubusercontent.com/caliphdev/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/saisuiu/Lionkings-Http-Proxys-Proxies/main/cnfree.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
    ],

    "https": [
        # ── API tabanlı ──────────────────────────────────────────────────────
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=https&timeout=10000&country=all",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=https&proxy_format=protocolipport&format=text&timeout=10000",
        "https://proxylist.geonode.com/api/proxy-list?protocols=https&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "https://www.proxy-list.download/api/v1/get?type=https",

        # ── GitHub repo listeleri ────────────────────────────────────────────
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/https_proxies.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/https.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https/https.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
    ],

    "socks4": [
        # ── API tabanlı ──────────────────────────────────────────────────────
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks4&proxy_format=protocolipport&format=text&timeout=10000",
        "https://proxylist.geonode.com/api/proxy-list?protocols=socks4&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "https://www.proxy-list.download/api/v1/get?type=socks4",

        # ── GitHub repo listeleri ────────────────────────────────────────────
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/socks4.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/socks4_proxies.txt",
        "https://raw.githubusercontent.com/caliphdev/Proxy-List/master/socks4.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks4.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks4/socks4.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks4/global/socks4_checked.txt",
    ],

    "socks5": [
        # ── API tabanlı ──────────────────────────────────────────────────────
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks5&proxy_format=protocolipport&format=text&timeout=10000",
        "https://proxylist.geonode.com/api/proxy-list?protocols=socks5&limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "https://www.proxy-list.download/api/v1/get?type=socks5",

        # ── GitHub repo listeleri ────────────────────────────────────────────
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/socks5.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/socks5_proxies.txt",
        "https://raw.githubusercontent.com/caliphdev/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks5/socks5.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks5/global/socks5_checked.txt",
        "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks5.txt",
    ],
}

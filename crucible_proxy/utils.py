from __future__ import annotations

try:
    from colorama import Fore, Style, init as _colorama_init
    _colorama_init(autoreset=True)
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False


class C:
    GREEN   = Fore.GREEN      if _HAS_COLOR else ""
    RED     = Fore.RED        if _HAS_COLOR else ""
    YELLOW  = Fore.YELLOW     if _HAS_COLOR else ""
    CYAN    = Fore.CYAN       if _HAS_COLOR else ""
    MAGENTA = Fore.MAGENTA    if _HAS_COLOR else ""
    WHITE   = Fore.WHITE      if _HAS_COLOR else ""
    DIM     = Style.DIM       if _HAS_COLOR else ""
    BRIGHT  = Style.BRIGHT    if _HAS_COLOR else ""
    RESET   = Style.RESET_ALL if _HAS_COLOR else ""


def bar(alive: int, total: int, width: int = 20) -> str:
    filled = int(width * alive / total) if total else 0
    return f"{C.GREEN}{'█' * filled}{'░' * (width - filled)}{C.RESET}"


BANNER = f"""{C.CYAN}{C.BRIGHT}
  ╔══════════════════════════════════════════════╗
  ║          crucible-proxychecker v7.0        ║
  ║     HTTP  ·  HTTPS  ·  SOCKS4  ·  SOCKS5    ║
  ╚══════════════════════════════════════════════╝
{C.RESET}"""

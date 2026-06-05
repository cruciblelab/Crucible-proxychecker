"""
proxy_checker.py
Entry point — delegates to crucible_proxy.cli.

Usage:
    python proxy_checker.py                    # interactive menu
    python proxy_checker.py --type socks5
    python proxy_checker.py --all
    python proxy_checker.py --workers 200
    python proxy_checker.py --timeout 5
    python proxy_checker.py --verify-twice false
"""

from crucible_proxy.cli import main

if __name__ == "__main__":
    main()

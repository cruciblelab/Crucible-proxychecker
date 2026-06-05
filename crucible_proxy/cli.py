"""
crucible_proxy.cli
~~~~~~~~~~~~~~~~~~
Command-line interface.  Reads config (file → env → flags) then runs
the fetch + check pipeline.

Flags always win over env vars, which win over the config file.
"""
from __future__ import annotations

import argparse
import sys
import time

from .checker  import check_all
from .config   import Config, apply_logging, generate_template, load_config
from .fetcher  import fetch_proxies
from .models   import CheckResult, ProxyType, Stats
from .output   import save_results, write_debug_report
from .utils    import BANNER, C, bar


# ── Result display ────────────────────────────────────────────────────────────

def _print_result(result: CheckResult, stats: Stats, no_color: bool = False) -> None:
    progress = bar(stats.alive, stats.total)
    marker   = f"{stats.alive}/{stats.total}"

    if result.alive:
        lat  = f"{C.DIM}{result.latency_ms}ms{C.RESET}"
        ctry = f"[{result.country}]" if result.country else "    "
        anon = f"{C.DIM}{result.anonymity.value:<11}{C.RESET}"
        print(
            f"  {C.GREEN}✓{C.RESET} "
            f"{C.WHITE}{str(result.proxy):<26}{C.RESET}"
            f"{lat:<18}{C.CYAN}{ctry:<6}{C.RESET}  "
            f"{anon}  "
            f"{progress}  {C.DIM}{marker}{C.RESET}"
        )
    else:
        print(
            f"  {C.RED}✗{C.RESET} "
            f"{C.DIM}{str(result.proxy):<26}{C.RESET}"
            f"{'':36}"
            f"{progress}  {C.DIM}{marker}{C.RESET}"
        )


# ── Per-type pipeline ─────────────────────────────────────────────────────────

def run_type(proxy_type: ProxyType, cfg: Config) -> tuple[Stats, list[CheckResult]]:
    sep = f"{C.CYAN}{'─' * 64}{C.RESET}"
    print(f"\n{sep}")
    print(
        f"  {C.BRIGHT}{C.MAGENTA}{proxy_type.value.upper():<8}{C.RESET}"
        " fetching proxy sources..."
    )

    t0      = time.perf_counter()
    proxies = fetch_proxies(proxy_type)

    if not proxies:
        print(f"  {C.YELLOW}No proxies retrieved from any source.{C.RESET}")
        return Stats(), []

    elapsed_fetch = time.perf_counter() - t0
    print(
        f"  {C.CYAN}{len(proxies)}{C.RESET} proxies found "
        f"({elapsed_fetch:.1f}s).  Checking...\n"
    )

    stats:   Stats             = Stats()
    results: list[CheckResult] = []

    for result in check_all(
        proxies,
        max_workers  = cfg.workers,
        timeout      = cfg.timeout,
        verify_twice = cfg.verify_twice,
    ):
        stats.record(result)
        results.append(result)
        _print_result(result, stats, no_color=cfg.no_color)

    elapsed = time.perf_counter() - t0

    simple_path, detailed_path = save_results(
        results,
        proxy_type,
        output_dir = cfg.output_dir,
        fmt        = cfg.output_format,
    )

    if cfg.debug_report:
        debug_path = write_debug_report(results, proxy_type, elapsed, cfg.output_dir)
        print(f"  {C.DIM}↳ debug   : {debug_path.resolve()}{C.RESET}")

    print(
        f"\n  {C.BRIGHT}Result:{C.RESET}  "
        f"{C.GREEN}✓ {stats.alive} alive{C.RESET}  "
        f"{C.RED}✗ {stats.dead} dead{C.RESET}  "
        f"| {stats.success_rate:.1f}% success  "
        f"| {elapsed:.1f}s"
    )
    if simple_path == detailed_path:
        print(f"  {C.DIM}↳ output  : {simple_path.resolve()}{C.RESET}")
    else:
        print(f"  {C.DIM}↳ simple  : {simple_path.resolve()}{C.RESET}")
        print(f"  {C.DIM}↳ detailed: {detailed_path.resolve()}{C.RESET}")

    return stats, results


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog        = "crucible-proxy",
        description = (
            "Crucible Proxy Checker — scrape and validate HTTP/HTTPS/SOCKS proxies.\n"
            "Config priority: CLI flags > env vars (CRUCIBLE_*) > crucible_proxy.toml > defaults."
        ),
        formatter_class = argparse.RawTextHelpFormatter,
        epilog = (
            "Examples:\n"
            "  crucible-proxy --type socks5\n"
            "  crucible-proxy --all --output-format json --output-dir ./results\n"
            "  crucible-proxy --type http --workers 400 --timeout 5 --debug-report\n"
            "  crucible-proxy --generate-config > crucible_proxy.toml\n"
        ),
    )

    # ── What to check ─────────────────────────────────────────────────────────
    type_group = p.add_mutually_exclusive_group()
    type_group.add_argument(
        "--type",
        choices = [pt.value for pt in ProxyType],
        metavar = "TYPE",
        help    = "Single proxy type: http | https | socks4 | socks5",
    )
    type_group.add_argument(
        "--all",
        action = "store_true",
        dest   = "check_all_types",
        help   = "Check all four proxy types.",
    )

    # ── Network tuning ────────────────────────────────────────────────────────
    net = p.add_argument_group("network")
    net.add_argument("--workers",      type=int,   metavar="N",    default=None, help="Concurrent threads (default: 200)")
    net.add_argument("--timeout",      type=int,   metavar="SEC",  default=None, help="Per-request timeout in seconds (default: 8)")
    net.add_argument("--retries",      type=int,   metavar="N",    default=None, help="Check retries before marking dead (default: 2)")
    net.add_argument(
        "--verify-twice",
        type    = lambda v: v.lower() not in ("false", "0", "no"),
        metavar = "BOOL",
        default = None,
        dest    = "verify_twice",
        help    = "Second-pass confirmation (default: true)",
    )

    # ── Output ────────────────────────────────────────────────────────────────
    out = p.add_argument_group("output")
    out.add_argument(
        "--output-format",
        choices = ["txt", "json", "csv"],
        metavar = "FMT",
        default = None,
        dest    = "output_format",
        help    = "Result file format: txt | json | csv (default: txt)",
    )
    out.add_argument(
        "--output-dir",
        metavar = "DIR",
        default = None,
        dest    = "output_dir",
        help    = "Directory for result files (default: ./output)",
    )
    out.add_argument(
        "--no-color",
        action  = "store_true",
        default = None,
        dest    = "no_color",
        help    = "Disable ANSI colour output.",
    )

    # ── Logging / debug ───────────────────────────────────────────────────────
    dbg = p.add_argument_group("logging & debug")
    dbg.add_argument(
        "--log-level",
        choices = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        metavar = "LEVEL",
        default = None,
        dest    = "log_level",
        help    = "Log verbosity (default: WARNING)",
    )
    dbg.add_argument(
        "--log-file",
        metavar = "PATH",
        default = None,
        dest    = "log_file",
        help    = "Also write logs to this file.",
    )
    dbg.add_argument(
        "--debug-report",
        action  = "store_true",
        default = None,
        dest    = "debug_report",
        help    = "Write a JSON debug report per run (includes dead proxies + errors).",
    )

    # ── Utility ───────────────────────────────────────────────────────────────
    p.add_argument(
        "--generate-config",
        action  = "store_true",
        dest    = "generate_config",
        help    = "Print a commented TOML config template and exit.",
    )

    return p


# ── Interactive selector ──────────────────────────────────────────────────────

def interactive_select() -> list[ProxyType]:
    all_types = list(ProxyType)
    print(f"\n{C.BRIGHT}  Select types to check:{C.RESET}")
    for i, pt in enumerate(all_types, 1):
        print(f"    {C.CYAN}{i}{C.RESET}. {pt.value.upper()}")
    print(f"    {C.CYAN}0{C.RESET}. All types\n")

    raw = input("  Selection (e.g. 1 3  or  0 = all) → ").strip()

    if not raw or raw == "0":
        return all_types

    selected: list[ProxyType] = []
    for token in raw.split():
        try:
            idx = int(token) - 1
            if 0 <= idx < len(all_types):
                pt = all_types[idx]
                if pt not in selected:
                    selected.append(pt)
            else:
                print(f"  {C.YELLOW}Skipped invalid: {token}{C.RESET}")
        except ValueError:
            print(f"  {C.YELLOW}Not a number, skipped: {token!r}{C.RESET}")

    return selected or all_types


# ── Entry point ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args   = parser.parse_args(argv)

    # --generate-config: print template and exit
    if args.generate_config:
        print(generate_template())
        return

    # Build config (file → env → CLI overrides)
    overrides = {
        "workers":             args.workers,
        "timeout":             args.timeout,
        "retries":             args.retries,
        "verify_twice":        args.verify_twice,
        "output_format":       args.output_format,
        "output_dir":          args.output_dir,
        "no_color":            args.no_color or None,
        "log_level":           args.log_level,
        "log_file":            args.log_file,
        "debug_report":        args.debug_report or None,
    }
    cfg = load_config(overrides)
    apply_logging(cfg)

    import os
    if not cfg.no_color:
        os.system("cls" if os.name == "nt" else "clear")

    print(BANNER)
    print(
        f"  {C.DIM}Workers: {cfg.workers}  |  "
        f"Timeout: {cfg.timeout}s  |  "
        f"Verify-twice: {cfg.verify_twice}  |  "
        f"Format: {cfg.output_format}  |  "
        f"Log: {cfg.log_level}{C.RESET}\n"
    )

    # Determine proxy types
    if args.type:
        selected = [ProxyType(args.type)]
    elif args.check_all_types:
        selected = list(ProxyType)
    else:
        selected = interactive_select()

    if not selected:
        print(f"\n  {C.RED}No proxy type selected. Exiting.{C.RESET}\n")
        sys.exit(0)

    grand_stats = Stats()
    wall_start  = time.perf_counter()

    for proxy_type in selected:
        s, _ = run_type(proxy_type, cfg)
        grand_stats += s

    wall_elapsed = time.perf_counter() - wall_start

    print(f"""
{C.CYAN}{'═' * 64}{C.RESET}
  {C.BRIGHT}SUMMARY{C.RESET}
  Total checked  : {grand_stats.total}
  Alive proxies  : {C.GREEN}{grand_stats.alive}{C.RESET}
  Dead proxies   : {C.RED}{grand_stats.dead}{C.RESET}
  Success rate   : {grand_stats.success_rate:.1f}%
  Total time     : {wall_elapsed:.1f}s
{C.CYAN}{'═' * 64}{C.RESET}
""")

    if not args.type and not args.check_all_types:
        input("  Press Enter to exit...")

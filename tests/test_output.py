"""Tests for output file generation."""
import tempfile
from pathlib import Path

import pytest

from crucible_proxy.models import Anonymity, CheckResult, Proxy, ProxyType
from crucible_proxy.output import save_results


def _make_result(host: str, port: int, alive: bool, latency: float = 120.0) -> CheckResult:
    p = Proxy(host=host, port=port, type=ProxyType.SOCKS5)
    return CheckResult(
        proxy=p,
        alive=alive,
        latency_ms=latency if alive else None,
        country="US" if alive else None,
        anonymity=Anonymity.ELITE if alive else Anonymity.UNKNOWN,
    )


class TestSaveResults:
    def setup_method(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def teardown_method(self):
        self.tmp.cleanup()

    def test_creates_both_files(self):
        results  = [_make_result("1.2.3.4", 1080, True)]
        simple, detailed = save_results(results, ProxyType.SOCKS5, self.out)
        assert simple.exists()
        assert detailed.exists()

    def test_simple_format(self):
        results = [_make_result("1.2.3.4", 1080, True)]
        simple, _ = save_results(results, ProxyType.SOCKS5, self.out)
        lines = simple.read_text().splitlines()
        assert lines[0] == "1.2.3.4:1080"

    def test_detailed_has_header(self):
        results   = [_make_result("1.2.3.4", 1080, True)]
        _, detailed = save_results(results, ProxyType.SOCKS5, self.out)
        text = detailed.read_text()
        assert "# Generated" in text
        assert "# Type"      in text
        assert "# Count"     in text

    def test_dead_proxies_excluded(self):
        results = [
            _make_result("1.2.3.4", 1080, True),
            _make_result("9.9.9.9", 1080, False),
        ]
        simple, detailed = save_results(results, ProxyType.SOCKS5, self.out)
        simple_text   = simple.read_text()
        detailed_text = detailed.read_text()
        assert "1.2.3.4" in simple_text
        assert "9.9.9.9" not in simple_text
        assert "9.9.9.9" not in detailed_text

    def test_sorted_by_latency(self):
        results = [
            _make_result("3.3.3.3", 80, True, latency=300.0),
            _make_result("1.1.1.1", 80, True, latency=50.0),
            _make_result("2.2.2.2", 80, True, latency=150.0),
        ]
        simple, _ = save_results(results, ProxyType.HTTP, self.out)
        lines = simple.read_text().splitlines()
        assert lines[0] == "1.1.1.1:80"
        assert lines[1] == "2.2.2.2:80"
        assert lines[2] == "3.3.3.3:80"

    def test_empty_results(self):
        simple, detailed = save_results([], ProxyType.HTTP, self.out)
        assert simple.read_text()   == ""
        assert "Count     : 0" in detailed.read_text()

    def test_detailed_contains_country_and_anonymity(self):
        results   = [_make_result("1.2.3.4", 1080, True)]
        _, detailed = save_results(results, ProxyType.SOCKS5, self.out)
        text = detailed.read_text()
        assert "US"    in text
        assert "elite" in text

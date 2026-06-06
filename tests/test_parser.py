"""Tests for proxy line parser."""
import pytest
from crucible_proxy.fetcher import parse_line  # noqa: I001
from crucible_proxy.models import ProxyType


PTYPE = ProxyType.HTTP


class TestParseLine:
    def test_plain(self):
        p = parse_line("1.2.3.4:8080", PTYPE)
        assert p is not None
        assert p.host == "1.2.3.4"
        assert p.port == 8080

    def test_with_scheme(self):
        p = parse_line("http://1.2.3.4:8080", PTYPE)
        assert p is not None
        assert p.host == "1.2.3.4"

    def test_with_auth(self):
        p = parse_line("user:pass@1.2.3.4:3128", PTYPE)
        assert p is not None
        assert p.host == "1.2.3.4"
        assert p.port == 3128

    def test_comment_skipped(self):
        assert parse_line("# comment", PTYPE) is None

    def test_empty_skipped(self):
        assert parse_line("", PTYPE) is None
        assert parse_line("   ", PTYPE) is None

    def test_no_port(self):
        assert parse_line("1.2.3.4", PTYPE) is None

    def test_invalid_port_string(self):
        assert parse_line("1.2.3.4:abc", PTYPE) is None

    def test_port_zero(self):
        assert parse_line("1.2.3.4:0", PTYPE) is None

    def test_port_too_large(self):
        assert parse_line("1.2.3.4:99999", PTYPE) is None

    def test_port_max(self):
        p = parse_line("1.2.3.4:65535", PTYPE)
        assert p is not None
        assert p.port == 65535

    def test_trailing_whitespace(self):
        p = parse_line("  1.2.3.4:80  ", PTYPE)
        assert p is not None

    def test_proxy_type_assigned(self):
        p = parse_line("1.2.3.4:80", ProxyType.SOCKS5)
        assert p is not None
        assert p.type == ProxyType.SOCKS5

    @pytest.mark.parametrize("line", [
        "1.2.3.4:8080",
        "http://1.2.3.4:8080",
        "socks5://1.2.3.4:1080",
        "user:pass@1.2.3.4:3128",
        "http://user:pass@1.2.3.4:3128",
    ])
    def test_valid_variants(self, line):
        assert parse_line(line, PTYPE) is not None

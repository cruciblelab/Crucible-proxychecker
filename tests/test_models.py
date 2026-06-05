"""Tests for data models."""
import threading

import pytest

from crucible_proxy.models import Anonymity, CheckResult, Proxy, ProxyType, Stats


class TestProxy:
    def test_str(self):
        p = Proxy(host="1.2.3.4", port=8080, type=ProxyType.HTTP)
        assert str(p) == "1.2.3.4:8080"

    def test_requests_dict_http(self):
        p = Proxy(host="1.2.3.4", port=8080, type=ProxyType.HTTP)
        d = p.as_requests_dict()
        assert d["http"]  == "http://1.2.3.4:8080"
        assert d["https"] == "http://1.2.3.4:8080"

    def test_requests_dict_socks5(self):
        p = Proxy(host="10.0.0.1", port=1080, type=ProxyType.SOCKS5)
        d = p.as_requests_dict()
        assert d["http"].startswith("socks5://")

    def test_frozen(self):
        p = Proxy(host="1.2.3.4", port=80, type=ProxyType.HTTP)
        with pytest.raises(Exception):
            p.host = "5.6.7.8"  # type: ignore[misc]

    @pytest.mark.parametrize("ptype", list(ProxyType))
    def test_all_types_scheme(self, ptype):
        p = Proxy(host="1.1.1.1", port=80, type=ptype)
        assert p.as_requests_dict()["http"].startswith(ptype.value + "://")


class TestStats:
    def _make_result(self, alive: bool) -> CheckResult:
        p = Proxy(host="1.2.3.4", port=80, type=ProxyType.HTTP)
        return CheckResult(proxy=p, alive=alive)

    def test_initial(self):
        s = Stats()
        assert s.total == s.alive == s.dead == 0

    def test_record_alive(self):
        s = Stats()
        s.record(self._make_result(True))
        assert s.total == 1
        assert s.alive == 1
        assert s.dead  == 0

    def test_record_dead(self):
        s = Stats()
        s.record(self._make_result(False))
        assert s.dead == 1

    def test_success_rate(self):
        s = Stats()
        for _ in range(3):
            s.record(self._make_result(True))
        for _ in range(1):
            s.record(self._make_result(False))
        assert s.success_rate == pytest.approx(75.0)

    def test_success_rate_zero_total(self):
        assert Stats().success_rate == 0.0

    def test_iadd(self):
        a = Stats(total=10, alive=7, dead=3)
        b = Stats(total=5,  alive=2, dead=3)
        a += b
        assert a.total == 15
        assert a.alive == 9
        assert a.dead  == 6

    def test_record_thread_safety(self):
        """Concurrent record() calls must not lose counts."""
        s = Stats()
        results = [self._make_result(i % 2 == 0) for i in range(200)]

        threads = [threading.Thread(target=s.record, args=(r,)) for r in results]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert s.total == 200
        assert s.alive == 100
        assert s.dead  == 100

    def test_iadd_thread_safety(self):
        """Concurrent += must not corrupt totals."""
        base = Stats(total=0, alive=0, dead=0)
        parts = [Stats(total=10, alive=5, dead=5) for _ in range(20)]

        def add(other: Stats) -> None:
            nonlocal base
            base += other

        threads = [threading.Thread(target=add, args=(p,)) for p in parts]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert base.total == 200
        assert base.alive == 100
        assert base.dead  == 100

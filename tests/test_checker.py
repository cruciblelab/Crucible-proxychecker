"""Tests for proxy checker logic."""
from unittest.mock import MagicMock, patch

import requests

from crucible_proxy.checker import _detect_anonymity, _single_check, check_proxy
from crucible_proxy.models import Anonymity, Proxy, ProxyType

PROXY = Proxy(host="1.2.3.4", port=8080, type=ProxyType.HTTP)


class TestSingleCheck:
    def test_success(self):
        mock_session = MagicMock()
        mock_resp    = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_session.get.return_value = mock_resp

        ok, lat, err = _single_check(PROXY, mock_session, "http://test.url/")
        assert ok  is True
        assert lat is not None
        assert err is None

    def test_connection_error(self):
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.ConnectionError("refused")

        ok, lat, err = _single_check(PROXY, mock_session, "http://test.url/")
        assert ok  is False
        assert lat is None
        assert err is not None

    def test_timeout_forwarded(self):
        """timeout kwarg must be passed to session.get."""
        mock_session = MagicMock()
        mock_resp    = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_session.get.return_value = mock_resp

        _single_check(PROXY, mock_session, "http://test.url/", timeout=3)
        _, kwargs = mock_session.get.call_args
        assert kwargs.get("timeout") == 3


class TestDetectAnonymity:
    def _httpbin_resp(self, headers: dict) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"headers": headers}
        return mock_resp

    def test_elite_no_forwarding_headers(self):
        session = MagicMock()
        session.get.side_effect = [
            MagicMock(**{"json.return_value": {"countryCode": "DE"}}),
            self._httpbin_resp({"Host": "httpbin.org", "Accept": "*/*"}),
        ]
        country, anon = _detect_anonymity(PROXY, session)
        assert anon    == Anonymity.ELITE
        assert country == "DE"

    def test_anonymous_with_via_header(self):
        session = MagicMock()
        session.get.side_effect = [
            MagicMock(**{"json.return_value": {"countryCode": "NL"}}),
            self._httpbin_resp({"Via": "1.1 proxy.example.com", "Host": "httpbin.org"}),
        ]
        _, anon = _detect_anonymity(PROXY, session)
        assert anon == Anonymity.ANONYMOUS

    def test_transparent_with_real_ip_leak(self):
        session = MagicMock()
        session.get.side_effect = [
            MagicMock(**{"json.return_value": {"countryCode": "US"}}),
            self._httpbin_resp({"X-Forwarded-For": "203.0.113.5, 10.0.0.1"}),
        ]
        _, anon = _detect_anonymity(PROXY, session)
        assert anon == Anonymity.TRANSPARENT

    def test_unknown_on_total_failure(self):
        session = MagicMock()
        session.get.side_effect = Exception("network down")
        country, anon = _detect_anonymity(PROXY, session)
        assert anon    == Anonymity.UNKNOWN
        assert country is None


class TestCheckProxy:
    @patch("crucible_proxy.checker.requests.Session")
    def test_alive_proxy(self, MockSession):
        session = MagicMock()
        MockSession.return_value = session

        with patch("crucible_proxy.checker._single_check") as mock_check, \
             patch("crucible_proxy.checker._detect_anonymity") as mock_anon:
            mock_check.return_value = (True, 120.0, None)
            mock_anon.return_value  = ("DE", Anonymity.ELITE)

            result = check_proxy(PROXY, verify_twice=False, check_retries=1)

        assert result.alive       is True
        assert result.latency_ms  == 120.0
        assert result.country     == "DE"
        assert result.anonymity   == Anonymity.ELITE

    @patch("crucible_proxy.checker.requests.Session")
    def test_dead_proxy(self, MockSession):
        session = MagicMock()
        MockSession.return_value = session

        with patch("crucible_proxy.checker._single_check") as mock_check, \
             patch("crucible_proxy.checker._resolve_check_url") as mock_resolve:
            mock_check.return_value   = (False, None, "connection refused")
            mock_resolve.return_value = None

            result = check_proxy(PROXY, verify_twice=False, check_retries=1)

        assert result.alive is False
        assert result.error is not None

    @patch("crucible_proxy.checker.requests.Session")
    def test_verify_twice_failure(self, MockSession):
        session = MagicMock()
        MockSession.return_value = session

        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return (True, 100.0, None)
            return (False, None, "timed out")

        with patch("crucible_proxy.checker._single_check", side_effect=side_effect), \
             patch("crucible_proxy.checker._resolve_check_url", return_value=None), \
             patch("crucible_proxy.checker.time.sleep"):
            result = check_proxy(PROXY, verify_twice=True, check_retries=1)

        assert result.alive is False
        assert "verification failed" in (result.error or "")

    @patch("crucible_proxy.checker.requests.Session")
    def test_timeout_propagated_to_single_check(self, MockSession):
        """timeout arg must flow through to _single_check, not read from global."""
        session = MagicMock()
        MockSession.return_value = session

        with patch("crucible_proxy.checker._single_check") as mock_check, \
             patch("crucible_proxy.checker._detect_anonymity", return_value=(None, Anonymity.UNKNOWN)):
            mock_check.return_value = (True, 50.0, None)
            check_proxy(PROXY, verify_twice=False, check_retries=1, timeout=3)
            _, kwargs = mock_check.call_args
            assert kwargs.get("timeout") == 3 or mock_check.call_args[0][-1] == 3

    @patch("crucible_proxy.checker.requests.Session")
    def test_verify_twice_averages_latency(self, MockSession):
        session = MagicMock()
        MockSession.return_value = session

        calls = {"n": 0}

        def side_effect(*args, **kwargs):
            calls["n"] += 1
            return (True, 100.0 if calls["n"] == 1 else 200.0, None)

        with patch("crucible_proxy.checker._single_check", side_effect=side_effect), \
             patch("crucible_proxy.checker._resolve_check_url", return_value=None), \
             patch("crucible_proxy.checker._detect_anonymity", return_value=(None, Anonymity.UNKNOWN)), \
             patch("crucible_proxy.checker.time.sleep"):
            result = check_proxy(PROXY, verify_twice=True, check_retries=1)

        assert result.alive      is True
        assert result.latency_ms == 150.0

"""Unit tests for check_for_update()'s status classification (athan.py).

Run: python -m pytest test_update_check.py   (or: python -m unittest test_update_check)
"""
import sys
import unittest
from unittest import mock

import athan


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def fake_requests(payload=None, raise_exc=None):
    """A stand-in for the `requests` module whose .get returns/raises what we want."""
    m = mock.Mock()
    if raise_exc is not None:
        m.get.side_effect = raise_exc
    else:
        m.get.return_value = FakeResponse(payload)
    return m


def frozen(value):
    """Context manager: pretend the app is (not) a frozen PyInstaller exe."""
    return mock.patch.object(sys, "frozen", value, create=True)


LATEST = {
    "tag_name": "v9.9.9",
    "assets": [{"name": "Athan.exe",
                "browser_download_url": "https://example/Athan.exe"}],
}


class CheckForUpdateTests(unittest.TestCase):
    def test_unsupported_when_requests_missing(self):
        with frozen(True), mock.patch.object(athan, "requests", None):
            self.assertEqual(athan.check_for_update().status, "unsupported")

    def test_unsupported_when_not_frozen(self):
        with frozen(False), mock.patch.object(athan, "requests",
                                              fake_requests(LATEST)):
            self.assertEqual(athan.check_for_update().status, "unsupported")

    def test_available_when_newer_release_with_asset(self):
        with frozen(True), mock.patch.object(athan, "requests",
                                             fake_requests(LATEST)):
            r = athan.check_for_update()
        self.assertEqual(r.status, "available")
        self.assertEqual(r.tag, "v9.9.9")
        self.assertEqual(r.url, "https://example/Athan.exe")

    def test_current_when_same_version(self):
        payload = {"tag_name": f"v{athan.VERSION}", "assets": []}
        with frozen(True), mock.patch.object(athan, "requests",
                                             fake_requests(payload)):
            self.assertEqual(athan.check_for_update().status, "current")

    def test_current_when_newer_tag_but_no_matching_asset(self):
        payload = {"tag_name": "v9.9.9",
                   "assets": [{"name": "something-else.zip",
                               "browser_download_url": "https://example/x"}]}
        with frozen(True), mock.patch.object(athan, "requests",
                                             fake_requests(payload)):
            self.assertEqual(athan.check_for_update().status, "current")

    def test_error_on_network_failure(self):
        with frozen(True), mock.patch.object(
                athan, "requests", fake_requests(raise_exc=RuntimeError("boom"))):
            r = athan.check_for_update()
        self.assertEqual(r.status, "error")
        self.assertIn("boom", r.message)


if __name__ == "__main__":
    unittest.main()

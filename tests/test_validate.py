from unittest.mock import MagicMock

from spotify_mcp.client import validate


class FakeClient:
    """Minimal object exercising the validate decorator."""

    def __init__(self, auth_ok, active_device):
        self._auth_ok = auth_ok
        self._active = active_device
        self.auth_refresh = MagicMock()
        self._get_candidate_device = MagicMock(return_value={'id': 'devX', 'name': 'Phone'})

    def auth_ok(self):
        return self._auth_ok

    def is_active_device(self):
        return self._active

    @validate
    def action(self, device=None):
        return device


def test_validate_refreshes_when_auth_expired():
    c = FakeClient(auth_ok=False, active_device=True)
    c.action()
    c.auth_refresh.assert_called_once()


def test_validate_skips_refresh_when_auth_ok():
    c = FakeClient(auth_ok=True, active_device=True)
    c.action()
    c.auth_refresh.assert_not_called()


def test_validate_injects_candidate_device_when_none_active():
    c = FakeClient(auth_ok=True, active_device=False)
    result = c.action()
    c._get_candidate_device.assert_called_once()
    assert result == {'id': 'devX', 'name': 'Phone'}


def test_validate_keeps_no_device_when_active():
    c = FakeClient(auth_ok=True, active_device=True)
    assert c.action() is None

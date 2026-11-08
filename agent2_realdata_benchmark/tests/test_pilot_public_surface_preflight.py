"""Synthetic response unit tests: no network and no participant records."""
from unittest.mock import patch

import pytest

from scripts import pilot_public_surface_preflight as preflight


@pytest.mark.parametrize("casing", [
    "WWW-Authenticate", "Www-Authenticate", "www-authenticate",
])
def test_homepage_basic_auth_header_is_case_insensitive(casing, capsys):
    def response(path, *, method="GET"):
        if path == "/":
            return 401, {casing: 'Basic realm="restricted"'}
        if path in ("/app.js", "/app.css"):
            return 401, {}
        if path == "/api/rct/enroll":
            return 403, {"cache-control": "no-store"}
        raise AssertionError(path)

    with patch.object(preflight, "request_status", side_effect=response):
        with pytest.raises(SystemExit) as result:
            preflight.main()
    assert result.value.code == 0
    assert '"all_passed": true' in capsys.readouterr().out


def test_missing_basic_challenge_remains_failure(capsys):
    def response(path, *, method="GET"):
        if path == "/":
            return 401, {}
        if path in ("/app.js", "/app.css"):
            return 401, {}
        if path == "/api/rct/enroll":
            return 403, {"Cache-Control": "no-store"}
        raise AssertionError(path)

    with patch.object(preflight, "request_status", side_effect=response):
        with pytest.raises(SystemExit) as result:
            preflight.main()
    assert result.value.code == 1
    assert '"all_passed": false' in capsys.readouterr().out

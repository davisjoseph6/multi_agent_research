"""Owner-only Google Web OAuth client import remains private and offline."""
from __future__ import annotations

import json
from pathlib import Path
import stat

import pytest

from scripts.supervisor_oauth_bootstrap import (
    import_google_web_client, REDIRECT,
)
from src.prototype.supervisor_mail_providers import MailConfigurationError


CLIENT = "fictional-client-id.apps.googleusercontent.com"
SECRET = "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nt-secret"


def credentials(directory: Path, *, redirect=REDIRECT, key="web"):
    src=directory/"downloaded-google-client.json"
    src.write_text(json.dumps({key:{
        "client_id":CLIENT,
        "client_secret":SECRET,
        "redirect_uris":[redirect],
    }}),encoding="utf-8")
    src.chmod(0o600)
    return src


def test_google_web_client_json_import_uses_private_files_no_network(tmp_path):
    directory=tmp_path/"oauth-private"
    directory.mkdir(mode=0o700)
    source=credentials(directory)
    client_file=directory/"google-client-id.txt"
    secret_file=directory/"google-client-secret.txt"
    result=import_google_web_client(
        source=source,client_id_path=client_file,
        client_secret_path=secret_file,
    )
    assert result["provider"]=="gmail_delegated"
    assert result["client_id"]==CLIENT
    assert result["oauth_consent_completed"] is False
    assert result["mail_sent"] is False
    assert SECRET not in str(result)
    assert client_file.read_text().strip()==CLIENT
    assert secret_file.read_text().strip()==SECRET
    assert stat.S_IMODE(client_file.stat().st_mode)==0o600
    assert stat.S_IMODE(secret_file.stat().st_mode)==0o600
    with pytest.raises(MailConfigurationError,match="nonexisting"):
        import_google_web_client(
            source=source,client_id_path=client_file,
            client_secret_path=secret_file,
        )
    assert source.read_text().strip().startswith("{")


@pytest.mark.parametrize("redirect,key",[
    ("http://localhost:8765/callback","web"),
    ("https://127.0.0.1:8765/callback","web"),
    (REDIRECT,"installed"),
])
def test_wrong_redirect_or_desktop_client_fails_closed(tmp_path,redirect,key):
    directory=tmp_path/"private"
    directory.mkdir(mode=0o700)
    source=credentials(directory,redirect=redirect,key=key)
    with pytest.raises(MailConfigurationError,match="Google Web OAuth"):
        import_google_web_client(
            source=source,
            client_id_path=directory/"id.txt",
            client_secret_path=directory/"secret.txt",
        )
    assert not (directory/"secret.txt").exists()


def test_unprotected_downloaded_json_is_not_imported(tmp_path):
    directory=tmp_path/"private"
    directory.mkdir(mode=0o700)
    source=credentials(directory)
    source.chmod(0o644)
    with pytest.raises(MailConfigurationError):
        import_google_web_client(
            source=source,
            client_id_path=directory/"id.txt",
            client_secret_path=directory/"secret.txt",
        )
    assert not (directory/"secret.txt").exists()

"""Regression tests for a separate study reviewer Basic Auth realm.

No credentials, contacts or live Caddy configuration are used. The reviewer
installer must never silently grant access to the unrelated operator demo.
"""
from pathlib import Path

import pytest

from ops.supervisor.setup_reviewer_auth import render


HASH = "$2a$14$" + "A" * 53
ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "ops" / "rct" / "Caddyfile.operator_demo.example"


def original():
    source = EXAMPLE.read_text(encoding="utf-8")
    source = source.replace(
        "reverse_proxy 127.0.0.1:8077 {",
        "@supervisorStudy path /study /study/*\n"
        "    reverse_proxy @supervisorStudy 127.0.0.1:8788 {\n"
        "        header_up Host {host}\n"
        "    }\n"
        "    reverse_proxy 127.0.0.1:8077 {",
    )
    return source


def test_reviewer_is_only_authorized_on_study_and_operator_password_stays():
    source = original()
    result = render(source, HASH)
    assert "@frontend not path /api/rct/* /study /study/*" in result
    assert "basic_auth @supervisorStudy {\n        studyreviewer " + HASH in result
    assert result.count("@supervisorStudy path /study /study/*") == 1
    assert "operator REPLACE_WITH_CADDY_HASH_PASSWORD" in result
    assert result.count("reverse_proxy 127.0.0.1:8077") == 1
    assert result.count("reverse_proxy @supervisorStudy 127.0.0.1:8788") == 1
    assert result.replace(
        "@frontend not path /api/rct/* /study /study/*",
        "@frontend not path /api/rct/*"
    ).replace(
        "    basic_auth @supervisorStudy {\n"
        "        studyreviewer " + HASH + "\n"
        "    }\n", ""
    ) == source


@pytest.mark.parametrize("change", [
    lambda s: s.replace("@frontend not path /api/rct/*", "@frontend path /"),
    lambda s: s.replace("@supervisorStudy path /study /study/*",
                        "@supervisorStudy path /study /study/* /admin/*"),
    lambda s: s.replace("reverse_proxy 127.0.0.1:8077", "reverse_proxy localhost:9"),
    lambda s: s.replace("basic_auth @frontend", "basic_auth"),
    lambda s: s.replace("@supervisorStudy path /study /study/*",
                        "@supervisorStudy path /study /study/*\n"
                        "@supervisorStudy path /study /study/*"),
])
def test_unknown_proxy_layout_fails_closed(change):
    with pytest.raises(ValueError):
        render(change(original()), HASH)


def test_no_credential_reuse_or_unsupported_hash():
    result = render(original(), HASH)
    with pytest.raises(ValueError, match="exists"):
        render(result, HASH)
    with pytest.raises(ValueError, match="bcrypt"):
        render(original(), "plaintext-password")
    with pytest.raises(ValueError, match="bcrypt"):
        render(original(), "$argon2id$v=19$m=47104")


from ops.supervisor.separate_caddy_auth_realms import render as split_realms


def test_browser_auth_realms_are_distinct_without_credential_mutation():
    source=render(original(),HASH)
    separated=split_realms(source)
    assert "basic_auth @supervisorStudy bcrypt StudyReview {" in separated
    assert "basic_auth @frontend bcrypt OperatorDemo {" in separated
    assert separated.count("operator REPLACE_WITH_CADDY_HASH_PASSWORD")==1
    assert separated.count("studyreviewer "+HASH)==1
    assert "reverse_proxy @supervisorStudy 127.0.0.1:8788" in separated
    assert "reverse_proxy 127.0.0.1:8077" in separated
    assert split_realms(separated)==separated
    assert separated.replace(
        "basic_auth @supervisorStudy bcrypt StudyReview {",
        "basic_auth @supervisorStudy {",
    ).replace(
        "basic_auth @frontend bcrypt OperatorDemo {",
        "basic_auth @frontend {",
    )==source


@pytest.mark.parametrize("change",[
    lambda x:x.replace("basic_auth @supervisorStudy {",
                       "basic_auth @supervisorStudy bcrypt UnknownRealm {"),
    lambda x:x.replace("basic_auth @frontend {",
                       "basic_auth @frontend bcrypt UnknownRealm {"),
    lambda x:x.replace("reverse_proxy 127.0.0.1:8077",
                       "reverse_proxy 127.0.0.1:1234"),
    lambda x:x.replace("@supervisorStudy path /study /study/*",
                       "@supervisorStudy path /study /study/* /admin/*"),
    lambda x:x.replace("basic_auth @supervisorStudy {",
                       "basic_auth @supervisorStudy {\n"
                       "    studyreviewer $2a$14$"+("A"*53)+"\n"
                       "    }\n"
                       "    basic_auth @supervisorStudy {"),
])
def test_realm_split_refuses_unknown_or_ambiguous_layout(change):
    with pytest.raises(ValueError):
        split_realms(change(render(original(),HASH)))

"""Release-gated outbound mail interface: Graph app, delegated Graph and Gmail.

No provider is contacted on import or factory construction. No unapproved
sender can be selected. The mailbox authorization manifest must be signed by
the trusted authority; researcher accounts are not mailbox permissions.

The interface remains send(to=..., subject=..., body=...), compatible with
the unchanged invitation, scheduled reminder and inactivity policy engines.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
from email.message import EmailMessage
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import fcntl

from cryptography.fernet import Fernet, InvalidToken

from .supervisor_graph_mail import GraphMailSender, GraphMailError
from .supervisor_recruitment import canonical_email


class MailConfigurationError(RuntimeError):
    pass


class MailDeliveryError(RuntimeError):
    pass


class MailDeliveryUnknown(MailDeliveryError):
    """The request may have reached the provider. NEVER retry automatically."""


APPROVAL_SCHEMA = "IJCAI2027_MAILBOX_AUTHORIZATION_V1"
CONFIG_SCHEMA = "IJCAI2027_MAIL_ROUTES_V1"
PROVIDERS = frozenset(("graph_application", "graph_delegated", "gmail_delegated"))
GRAPH_TOKEN = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
GMAIL_TOKEN = "https://oauth2.googleapis.com/token"
GUID = re.compile(r"[0-9a-fA-F-]{36}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
REF = re.compile(r"[0-9a-f]{40}\Z")


def private_file(path: str | Path, *, writable: bool = False) -> Path:
    p = Path(path)
    if not p.is_absolute() or not p.is_file() or p.is_symlink():
        raise MailConfigurationError("absolute, regular, nonsymlink private file required")
    mode = stat.S_IMODE(p.stat().st_mode)
    if mode & 0o027 or (writable and mode & 0o177):
        raise MailConfigurationError("file must not be group-writable or world-readable")
    return p


def _http(url: str, *, method: str = "GET", headers: dict | None = None,
          payload: dict | None = None, timeout: int = 20) -> tuple[int, bytes]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, method=method, headers=headers or {})
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.read(65536)
    except HTTPError as err:
        # Do not include remote body: may contain account details or tokens.
        return err.code, b""
    except (URLError, TimeoutError, ConnectionError, OSError):
        raise MailDeliveryUnknown("network outcome uncertain; check provider mailbox") from None


def _form_http(url: str, fields: dict, *, timeout: int = 20,
               transport=None) -> dict:
    data = urlencode(fields).encode("utf-8")
    def real(url, data, headers, timeout):
        req = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=timeout) as response:
                return response.status, response.read(65536)
        except HTTPError as err:
            return err.code, b""
        except (URLError, TimeoutError, OSError):
            raise MailDeliveryUnknown("OAuth network response uncertain") from None
    status, payload = (transport or real)(
        url, data, {"Content-Type": "application/x-www-form-urlencoded"}, timeout
    )
    if status != 200:
        raise MailConfigurationError("OAuth token endpoint refused authorization")
    try:
        value = json.loads(payload)
    except (ValueError, TypeError):
        raise MailConfigurationError("invalid OAuth token response") from None
    if type(value) is not dict or not value.get("access_token"):
        raise MailConfigurationError("OAuth token not returned")
    return value


class EncryptedRefreshVault:
    """Private encrypted refresh token per provider/sender with atomic rotation.

    Keep Fernet key in a separate institutionally controlled credentials
    directory. Encryption does not replace OS access control or key custody.
    """
    def __init__(self, directory: str | Path, key_file: str | Path):
        self.folder = Path(directory)
        if (not self.folder.is_absolute() or not self.folder.is_dir()
                or self.folder.is_symlink() or self.folder.stat().st_mode & 0o077):
            raise MailConfigurationError("private 0700 token directory required")
        self.key_file = private_file(key_file)
        self.cipher = Fernet(self.key_file.read_bytes().strip())
        self.lock = self.folder / ".vault.lock"

    @contextmanager
    def exclusive(self):
        fd = os.open(self.lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
                raise MailConfigurationError("OAuth vault lock must be 0600")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _name(self, provider: str, sender: str) -> Path:
        if provider not in ("graph_delegated", "gmail_delegated"):
            raise MailConfigurationError("not a delegated provider")
        address = canonical_email(sender)
        digest = sha256((provider + ":" + address).encode()).hexdigest()
        return self.folder / (digest + ".token.enc")

    def load(self, provider: str, sender: str) -> dict:
        p = self._name(provider, sender)
        if not p.exists():
            raise MailConfigurationError("approved account OAuth grant has not been installed")
        private_file(p, writable=True)
        try:
            value = json.loads(self.cipher.decrypt(p.read_bytes()))
        except (InvalidToken, ValueError, UnicodeDecodeError):
            raise MailConfigurationError("OAuth refresh token cannot be decrypted") from None
        if (type(value) is not dict or value.get("provider") != provider
                or value.get("sender") != canonical_email(sender)
                or not isinstance(value.get("refresh_token"), str)
                or len(value["refresh_token"]) < 12):
            raise MailConfigurationError("OAuth refresh token identity mismatch")
        return value

    def store(self, provider: str, sender: str, refresh: str, *,
              identity: str, issued_by: str = "explicit_oauth_consent"):
        address = canonical_email(sender)
        if (not isinstance(refresh, str) or len(refresh) < 12
                or canonical_email(identity) != address):
            raise MailConfigurationError("OAuth account identity must equal approved sender")
        path = self._name(provider, address)
        obj = dict(provider=provider, sender=address, refresh_token=refresh,
                   identity=address, consent_source=issued_by,
                   saved_at=datetime.now(timezone.utc).isoformat())
        encrypted = self.cipher.encrypt(json.dumps(obj).encode())
        temp = self.folder / (path.name + "." + os.urandom(8).hex() + ".tmp")
        fd = os.open(temp, os.O_CREAT | os.O_WRONLY | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(encrypted)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, path)
            dir_fd = os.open(self.folder, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            if temp.exists():
                temp.unlink()


class DelegatedOAuthSender:
    """Only sends from the exact owner who consented with offline Mail.Send.

    OAuth bootstrap code lives in a separate local-only CLI; access/refresh
    tokens are never used as researcher identity or to change study state.
    """
    def __init__(self, *, provider: str, sender: str, client_id: str,
                 client_secret_path: str | None, vault: EncryptedRefreshVault,
                 tenant: str | None = None, transport=None, token_transport=None):
        if provider not in ("graph_delegated", "gmail_delegated"):
            raise MailConfigurationError("unsupported delegated provider")
        self.provider = provider
        self.sender = canonical_email(sender)
        if provider == "graph_delegated" and self.sender.endswith("@gmail.com"):
            raise MailConfigurationError(
                "a Microsoft login alias at gmail.com is not a verified Outlook mailbox")
        if not isinstance(client_id, str) or len(client_id) < 8:
            raise MailConfigurationError("OAuth client application ID missing")
        self.client_id = client_id
        self.tenant = tenant or ("consumers" if provider == "graph_delegated" else None)
        self.secret_path = client_secret_path
        self.vault = vault
        self.transport = transport or _http
        self.token_transport = token_transport

    def _refresh_token(self):
        with self.vault.exclusive():
            old = self.vault.load(self.provider, self.sender)
            fields = dict(client_id=self.client_id,
                          refresh_token=old["refresh_token"],
                          grant_type="refresh_token")
            if self.secret_path:
                fields["client_secret"] = private_file(self.secret_path).read_text().strip()
            if self.provider == "graph_delegated":
                if self.tenant not in ("consumers", "organizations", "common") and not GUID.fullmatch(self.tenant):
                    raise MailConfigurationError("unrecognized Microsoft tenant")
                fields["scope"] = "offline_access Mail.Send User.Read"
                endpoint = GRAPH_TOKEN.format(tenant=self.tenant)
            else:
                endpoint = GMAIL_TOKEN
            payload = _form_http(endpoint, fields, transport=self.token_transport)
            refresh = payload.get("refresh_token")
            if refresh:
                self.vault.store(self.provider, self.sender, refresh, identity=self.sender)
            access = payload["access_token"]
            if not isinstance(access, str) or len(access) < 12:
                raise MailConfigurationError("access token invalid")
            return access

    def send(self, *, to: str, subject: str, body: str) -> None:
        recipient = canonical_email(to)
        if (not isinstance(subject, str) or not 1 <= len(subject) <= 160
                or "\r" in subject or "\n" in subject
                or not isinstance(body, str) or not 1 <= len(body) <= 16000):
            raise MailConfigurationError("outbound mail content invalid")
        token = self._refresh_token()
        headers = {"Content-Type": "application/json",
                   "Authorization": "Bearer " + token}
        if self.provider == "graph_delegated":
            url = "https://graph.microsoft.com/v1.0/me/sendMail"
            data = {"message": {"subject": subject,
                                "body": {"contentType": "Text", "content": body},
                                "toRecipients": [{"emailAddress": {"address": recipient}}]},
                    "saveToSentItems": True}
            expected = 202
        else:
            mail = EmailMessage()
            mail["From"] = self.sender
            mail["To"] = recipient
            mail["Subject"] = subject
            mail.set_content(body)
            data = {"raw": base64.urlsafe_b64encode(mail.as_bytes()).decode().rstrip("=")}
            url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
            expected = 200
        code, _ = self.transport(url, method="POST", headers=headers,
                                 payload=data, timeout=25)
        if code != expected:
            # Never retry a non-success response blindly after authorization
            # errors or transient network failures. Reconcile first.
            raise MailDeliveryError(f"{self.provider} declined send ({code})")


class MailRoute:
    """One provider and one exact approved mailbox, immutable at runtime."""
    def __init__(self, *, sender, provider: str, sender_email: str):
        self.sender = sender
        self.provider = provider
        self.email = canonical_email(sender_email)

    def send(self, *, to: str, subject: str, body: str):
        return self.sender.send(to=to, subject=subject, body=body)


class MailRouter:
    """Dispatcher uses default route, with optional explicitly signed actor routes.

    Researcher role alone never permits sending as Wiamm/Sara. Actor routes
    cannot introduce a sender missing from the institutional approval index.
    """
    def __init__(self, routes: dict[str, MailRoute], default: str, *,
                 by_actor: dict[str, str] | None = None):
        if not routes or default not in routes:
            raise MailConfigurationError("explicit authorized default mail route required")
        self.routes, self.default = dict(routes), default
        self.by_actor = {canonical_email(k): v for k,v in (by_actor or {}).items()}
        if any(v not in routes for v in self.by_actor.values()):
            raise MailConfigurationError("actor route is not authorized")

    def for_actor(self, actor: str) -> MailRoute:
        return self.routes[self.by_actor.get(canonical_email(actor), self.default)]

    def send(self, *, to: str, subject: str, body: str):
        return self.routes[self.default].send(to=to, subject=subject, body=body)


def verify_signed_mail_policy(config_path: str | Path, policy_path: str | Path,
                              signature_path: str | Path, public_key_path: str | Path,
                              *, release_commit: str) -> dict:
    """Read two private JSONs and verify institutional sign-off over mailbox scope.

    The institutional public key must have been verified out-of-band. Config
    can reference ONLY signed provider/email identities; it cannot add a sender.
    """
    if not REF.fullmatch(release_commit):
        raise MailConfigurationError("exact signed source commit required")
    config = json.loads(private_file(config_path).read_text())
    policy = json.loads(private_file(policy_path).read_text())
    signature = private_file(signature_path)
    public_key = private_file(public_key_path)
    verification = subprocess.run([
        "openssl", "dgst", "-sha256", "-verify", str(public_key),
        "-signature", str(signature), str(policy_path)
    ], capture_output=True, text=True, timeout=12, check=False)
    if verification.returncode or "Verified OK" not in verification.stdout:
        raise MailConfigurationError("institutionally signed sender policy invalid")
    if (policy.get("schema") != APPROVAL_SCHEMA
            or policy.get("decision") != "approved"
            or policy.get("release_commit") != release_commit
            or config.get("schema") != CONFIG_SCHEMA
            or not isinstance(config.get("routes"), dict)
            or not isinstance(policy.get("senders"), dict)):
        raise MailConfigurationError("mail policy lacks exact release authorization")
    if config.get("default") not in config["routes"]:
        raise MailConfigurationError("mail default not configured")
    if not config["routes"]:
        raise MailConfigurationError("no authorized mail senders")
    for key, definition in config["routes"].items():
        grant = policy["senders"].get(key)
        if not isinstance(grant, dict) or not isinstance(definition, dict):
            raise MailConfigurationError("unsigned mailbox route")
        if (definition.get("provider") not in PROVIDERS
                or grant.get("provider") != definition.get("provider")
                or grant.get("email") != definition.get("email")
                or grant.get("owner_authorized") is not True
                or grant.get("institutional_scope_verified") is not True
                or not isinstance(grant.get("owner_evidence_sha256"), str)
                or not HEX.fullmatch(grant["owner_evidence_sha256"])):
            raise MailConfigurationError("mailbox owner/institution authorization missing")
        canonical_email(definition["email"])
        if definition["provider"] == "graph_application":
            if not GUID.fullmatch(definition.get("tenant", "")) or not GUID.fullmatch(definition.get("client_id", "")):
                raise MailConfigurationError("Graph app credentials invalid")
        elif not isinstance(definition.get("client_id"), str):
            raise MailConfigurationError("delegated client ID missing")
    actor_routes = config.get("by_actor", {})
    if not isinstance(actor_routes, dict) or any(v not in config["routes"] for v in actor_routes.values()):
        raise MailConfigurationError("unapproved actor route")
    return config


def build_mail_router(*, config_file: str | Path, approval_file: str | Path,
                      approval_signature: str | Path, institution_key: str | Path,
                      release_commit: str, vault: EncryptedRefreshVault | None = None,
                      transport=None, token_transport=None) -> MailRouter:
    config = verify_signed_mail_policy(
        config_file, approval_file, approval_signature, institution_key,
        release_commit=release_commit,
    )
    routes = {}
    for key, item in config["routes"].items():
        provider = item["provider"]
        if provider == "graph_application":
            source = GraphMailSender(
                tenant_id=item["tenant"], client_id=item["client_id"],
                client_secret=private_file(item["client_secret_file"]).read_text().strip(),
                sender_email=item["email"], live_release_verified=True,
            )
        else:
            if vault is None:
                raise MailConfigurationError("encrypted OAuth refresh vault required")
            source = DelegatedOAuthSender(
                provider=provider, sender=item["email"], client_id=item["client_id"],
                tenant=item.get("tenant"), client_secret_path=item.get("client_secret_file"),
                vault=vault, transport=transport, token_transport=token_transport
            )
            # Fail before accepting live deployment if an account has not
            # explicitly consented and installed its refresh grant.
            with vault.exclusive():
                vault.load(provider, item["email"])
        routes[key] = MailRoute(sender=source, provider=provider,
                                sender_email=item["email"])
    return MailRouter(routes, config["default"], by_actor=config.get("by_actor", {}))

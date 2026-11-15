"""Microsoft Graph Outlook mail transport (NO mailbox access on import).

Only a separately verified LIVE release can instantiate an enabled sender.
Credentials are supplied by the institution's vault; never commit or log them.
Use a mailbox-scoped Entra application credential configured by IT. This
is application-only OAuth for automated, unattended reminders and invitations;
the PI independently sends the questionnaire links from their own mailbox.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .supervisor_recruitment import RecruitmentError, canonical_email

_TENANT = re.compile(r"[0-9a-fA-F-]{36}\Z")
_CLIENT = re.compile(r"[0-9a-fA-F-]{36}\Z")


class GraphMailError(RuntimeError):
    pass


class GraphMailSender:
    """No network traffic unless explicitly invoked on a verified LIVE release.

    The operator must limit the Entra app's Exchange Online access to the
    one approved sender mailbox. Application Mail.Send otherwise permits
    sending as all users in the tenant: do not use without scoped RBAC.
    """

    def __init__(self, *, tenant_id: str, client_id: str, client_secret: str,
                 sender_email: str, live_release_verified: bool = False,
                 transport=None):
        if live_release_verified is not True:
            raise GraphMailError("signed institutional LIVE release required")
        if not _TENANT.fullmatch(tenant_id) or not _CLIENT.fullmatch(client_id):
            raise GraphMailError("institutional Entra tenant/client GUIDs required")
        if type(client_secret) is not str or len(client_secret)<20:
            raise GraphMailError("approved Entra credential missing")
        self.tenant_id=tenant_id
        self.client_id=client_id
        self._secret=client_secret
        self.sender_email=canonical_email(sender_email)
        self._transport=transport or self._request

    @staticmethod
    def _request(url: str, *, data: bytes, headers: dict, timeout: int) -> tuple[int,bytes]:
        response=urlopen(Request(url,data=data,headers=headers,method="POST"),
                         timeout=timeout)
        with response:
            return response.status,response.read(32768)

    def _access_token(self) -> str:
        url=f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        payload=urlencode({
            "client_id":self.client_id,"client_secret":self._secret,
            "grant_type":"client_credentials",
            "scope":"https://graph.microsoft.com/.default",
        }).encode("ascii")
        try:
            status,raw=self._transport(url,data=payload,
                         headers={"Content-Type":"application/x-www-form-urlencoded"},
                         timeout=20)
            token=json.loads(raw.decode("utf-8")).get("access_token")
            if status!=200 or type(token) is not str or not token.strip():
                raise GraphMailError("Microsoft OAuth token request was rejected")
            return token
        except (HTTPError,URLError,TimeoutError,ValueError) as err:
            raise GraphMailError("Microsoft OAuth token request failed") from None

    def send(self, *, to: str, subject: str, body: str) -> None:
        recipient=canonical_email(to)
        if (type(subject) is not str or not 1<=len(subject)<=160 or
                any(c in subject for c in "\r\n") or
                type(body) is not str or not 1<=len(body)<=16000):
            raise GraphMailError("invalid outbound email content")
        token=self._access_token()
        route="https://graph.microsoft.com/v1.0/users/"+quote(
            self.sender_email,safe="@."
        )+"/sendMail"
        payload=json.dumps({"message":{
            "subject":subject,
            "body":{"contentType":"Text","content":body},
            "toRecipients":[{"emailAddress":{"address":recipient}}],
        },"saveToSentItems":True},separators=(",",":")).encode()
        try:
            status,_=self._transport(route,data=payload,timeout=25,
                headers={"Content-Type":"application/json",
                         "Authorization":"Bearer "+token})
        except (HTTPError,URLError,TimeoutError):
            # Unknown outcome: do not retry automatically. Graph may have
            # accepted the request before the connection failed.
            raise GraphMailError("Graph delivery outcome unknown; inspect Sent Items") from None
        if status!=202:
            raise GraphMailError("Graph did not accept the mail request")
        # 202 means accepted for processing, NOT delivered to inbox.

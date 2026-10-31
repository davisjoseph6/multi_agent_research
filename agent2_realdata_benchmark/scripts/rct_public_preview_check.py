"""Check public reviewer preview remains non-enrolling and clearly labeled.

Static checks alone do not certify security, accessibility or deployment.
"""
from pathlib import Path
import re

PREVIEW=Path(__file__).resolve().parents[2]/"docs"/"index.html"


def check_preview(path=PREVIEW):
    content=Path(path).read_text(encoding="utf-8")
    lower=content.lower()
    required=("fictional read-only preview","not the rct application",
              "not a live pomcp decision","no answers are transmitted",
              "not an interactive dialogue","not a production participant application")
    for item in required:
        if item not in lower:
            raise ValueError("Missing explicit preview boundary: "+item)
    if re.search(r"<form\\b",content,re.I):
        raise ValueError("Static preview must never submit a form")
    if re.search(r"fetch\\s*\\(|xmlhttprequest|websocket|sendbeacon|localstorage|sessionstorage",content,re.I):
        raise ValueError("Static preview must not persist or transmit responses")
    if "http://127.0.0.1:8077" in content or "/api/rct/" in content:
        raise ValueError("Static preview must not call study APIs")
    return {"preview_only":True,"participant_collection":False,"real_rct_application":False}


if __name__=="__main__":
    print(check_preview())

"""Local-only manual recovery-resource gallery, separate from actual RCT software.

This is an operator preview of authored content, NOT a POMCP-selected intervention,
participant activity, study session, or evidence of educational effectiveness.

Usage:
python -m scripts.rct_recovery_gallery --port 8088
Open http://127.0.0.1:8088/
"""
from __future__ import annotations

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from scripts.rct_candidate_cli import DEFAULT_SETTINGS, load_settings
from src.prototype.study_v2 import CONCEPTS, RECOVERY_ACTIONS


def render_html(settings=DEFAULT_SETTINGS):
    settings=Path(settings)
    cfg,bundle,release=load_settings(settings)
    if cfg.get("mode")!="rehearsal" or release:
        raise ValueError("Manual gallery refuses any non-rehearsal configuration")
    cards=[]
    for concept in CONCEPTS:
        entries=[]
        for kind in RECOVERY_ACTIONS:
            resource=bundle.resources[(concept,kind)]
            name=kind.replace("_"," ").title()
            entries.append(
                "<article class='resource'><h3>"+escape(name)+"</h3>"
                "<p>"+escape(resource["text"])+"</p>"
                "<p class='source'>Source: "+escape(resource["source"])+"</p>"
                "</article>"
            )
        cards.append("<section><h2>"+escape(concept)+"</h2>"
                     +"".join(entries)+"</section>")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>MANUAL RCT Recovery-Resource Preview</title><style>"
        "body{font:18px/1.65 system-ui,sans-serif;color:#142f35;background:#edf2f3;margin:0}"
        "main{max-width:940px;margin:0 auto;padding:2rem}"
        ".warning{background:#fff4d9;border-left:7px solid #995c00;padding:1rem;font-weight:700}"
        "section{background:white;padding:1.5rem;margin-top:1.2rem;border-radius:10px}"
        "article{border-top:1px solid #cdd8da;padding:.5rem 0}"
        ".source{font-size:.85rem;color:#3d5761}h1,h2,h3{line-height:1.25}"
        "@media(max-width:600px){main{padding:.8rem}section{padding:1rem}}"
        "</style></head><body><main>"
        "<h1>RCT Recovery Resources — Manual Content Preview</h1>"
        "<p class='warning'>NOT A PARTICIPANT SESSION. NOT SELECTED BY POMCP. "
        "DRAFT CONTENT — NO INDEPENDENT REVIEW. "
        "This page only previews the resources available to the RCT software.</p>"
        "<p>Each concept has a concept summary, two-option remediation, "
        "worked-example text and a static Socratic-style guided prompt. "
        "The hint is NOT an interactive Socratic dialogue.</p>"
        +"".join(cards)+"</main></body></html>"
    )


def is_gallery_path(raw_path):
    """Permit query strings attached by browsers while restricting page paths."""
    return urlsplit(raw_path).path in ("/", "/index.html")


def serve(port=8088):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Choose an unprivileged loopback port")
    body=render_html().encode("utf-8")
    class GalleryHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not is_gallery_path(self.path):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Referrer-Policy","no-referrer")
            self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(body)
    with ThreadingHTTPServer(("127.0.0.1",port),GalleryHandler) as server:
        print("Manual draft-resource gallery: http://127.0.0.1:"+str(port)+"/")
        server.serve_forever()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8088)
    args=parser.parse_args()
    serve(args.port)


if __name__=="__main__":
    main()

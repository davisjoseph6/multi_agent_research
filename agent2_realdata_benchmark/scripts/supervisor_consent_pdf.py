"""Build version-pinned Annex information-sheet PDFs from exact HTML text.

Only local dry-run artifacts. Source text still contains Professor Yaacoub's
[ ] placeholders, so public hosting is NOT authorized.
Install reportlab>=4.4 and a Unicode TTF font available on the host.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import html
import re

ROOT=Path(__file__).resolve().parents[1]/"content"/"consent"
FILES=("info_sheet_en_v1.0","info_sheet_fr_v1.0")


class AnnexExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside=False
        self.value=[]
    def handle_starttag(self,tag,attrs):
        if tag=="pre":
            self.inside=True
    def handle_endtag(self,tag):
        if tag=="pre":
            self.inside=False
    def handle_data(self,data):
        if self.inside:
            self.value.append(data)


def annex_text(path: Path) -> str:
    parser=AnnexExtractor()
    parser.feed(path.read_text(encoding="utf-8"))
    result=html.unescape("".join(parser.value)).strip()
    if len(result)<2000 or "v1.0" not in result:
        raise ValueError("missing or truncated versioned Annex content")
    return result


def font_file() -> Path:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        p=Path(candidate)
        if p.is_file():
            return p
    raise RuntimeError("Unicode TTF unavailable: do not generate a degraded PDF")


def build_pdfs(out_dir: Path, *, source_dir: Path = ROOT) -> tuple[Path,...]:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    out_dir.mkdir(parents=True,exist_ok=True)
    pdfmetrics.registerFont(TTFont("ConsentUnicode",str(font_file())))
    body=ParagraphStyle(
        "ConsentAnnex",fontName="ConsentUnicode",fontSize=9.3,
        leading=14,textColor=colors.HexColor("#1b2430"),alignment=TA_LEFT,
        spaceAfter=4,
    )
    title=ParagraphStyle(
        "ConsentAnnexTitle",parent=body,fontSize=13,leading=18,
        spaceAfter=14,
    )
    output=[]
    for stem in FILES:
        source=source_dir/(stem+".html")
        text=annex_text(source)
        target=out_dir/(stem+".pdf")
        story=[Paragraph(html.escape(
            "Participant information sheet — v1.0" if "_en_" in stem
            else "Notice d’information — v1.0"
        ),title)]
        for line in text.splitlines():
            line=re.sub(r"\s{2,}"," ",line).strip()
            if line:
                story.append(Paragraph(html.escape(line),body))
        doc=SimpleDocTemplate(
            str(target),pagesize=A4,rightMargin=39,leftMargin=39,
            topMargin=36,bottomMargin=38,
            title=stem+" — submitted for validation",
            author="aivancity research team — local technical draft",
        )
        doc.build(story)
        if target.stat().st_size<1500:
            raise RuntimeError("generated PDF is unexpectedly small")
        output.append(target)
    return tuple(output)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out-dir",type=Path,default=ROOT)
    args=parser.parse_args()
    for path in build_pdfs(args.out_dir):
        print(path)


if __name__=="__main__":
    main()

"""Public reviewer site must not become an undocumented participant application."""
from pathlib import Path
import pytest
from scripts.rct_public_preview_check import PREVIEW,check_preview

def test_public_preview_clear_separation():
    assert check_preview()["preview_only"]

def test_preview_rejects_http_requests(tmp_path):
    source=PREVIEW.read_text(encoding="utf-8")
    path=tmp_path/"index.html"
    path.write_text(source+"<script>fetch('/api/rct/next')</script>",encoding="utf-8")
    with pytest.raises(ValueError,match="persist or transmit"):
        check_preview(path)

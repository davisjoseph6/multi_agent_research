"""Only a standalone fictional static preview may be exposed through this template."""
from pathlib import Path


CONFIG = Path(__file__).resolve().parents[1] / "ops/rct/Caddyfile.static_preview.example"


def test_preview_vps_caddyfile_no_study_backend():
    content = CONFIG.read_text(encoding="utf-8")
    assert "preview.example.fr" in content
    assert "root * /srv/ijcai-preview" in content
    assert "file_server" in content
    assert "X-Content-Type-Options" in content
    assert "Content-Security-Policy" in content
    assert "referrer" in content.lower()
    assert "reverse_proxy" not in content
    assert "localhost:8077" not in content
    assert "/api/rct" not in content
    assert "sqlite3" not in content.lower()
    assert "file_server browse" not in content

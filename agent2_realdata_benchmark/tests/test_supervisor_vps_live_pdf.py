"""The real signed PDF must render as a link, not broken HTML parser output."""
from datetime import datetime, timezone
from pathlib import Path

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_vps_web import make_supervisor_vps_app


def test_signed_live_information_is_a_readable_pdf_resource(tmp_path):
    # Unit fixture only: a constructor flag is NOT institutional authorization.
    fixture=tmp_path/"signed-fixture.pdf"
    fixture.write_bytes(b"%PDF-1.7\nLocal unit-test fixture only\n%%EOF\n")
    class FakeSignedBundle:
        def file(self,key):
            assert key=="participant_information_external_en"
            return fixture
    store=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(
        Path(__file__).resolve().parents[1]/"data/supervisor_20261111"
    ),operational=True)
    intake=OperationalIntake(store,programs=("Test student program",),
                             document_bundle=FakeSignedBundle())
    app=make_supervisor_vps_app(
        intake,hostname="demo.selfhealing-edu.fr",proxy_mode=False,
        release_mode="live",release_authorized=True)
    client=app.test_client()
    token=intake.issue("local-pdf-test@example.example",
                       at=datetime.now(timezone.utc),allow_example=True)
    origin="http://127.0.0.1:8788"
    session=client.post("/study/api/exchange",json={"token":token},
                        headers={"Origin":origin,"X-Study-Request":"1"},
                        base_url=origin)
    assert session.status_code==200
    response=client.get("/study/info/en",base_url=origin)
    assert response.status_code==200
    assert response.mimetype=="application/pdf"
    assert response.data.startswith(b"%PDF-")

    frontend=(Path(__file__).resolve().parents[1]/
              "src/prototype/static/supervisor_vps.js").read_text()
    assert 'media.includes("application/pdf")' in frontend
    assert "Open participant information sheet (PDF)" in frontend
    assert "Unsupported information sheet format" in frontend

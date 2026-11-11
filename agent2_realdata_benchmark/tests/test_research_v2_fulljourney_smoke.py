"""Complete synthetic three-period lifecycle rehearsal over all sequences."""
from pathlib import Path
import pytest

from scripts.research_v2_fulljourney_smoke import run_smoke
from src.prototype.research_v2_proposal import all_sequences, ProposedStudyError
from src.prototype.research_v2_crossover_fixture import FictionalCrossoverStore


@pytest.mark.parametrize("order", all_sequences())
def test_six_sequences_with_two_reminders_and_all_261_unique_items(tmp_path, order):
    path = tmp_path / "".join(order)
    report = run_smoke(path, order)
    assert report["passed"]
    assert report["distinct_independent_questions"] == 261
    assert report["completed_periods"] == 3
    assert report["recovery_interventions_simulated"] == 2
    assert report["instructional_drop2_retries"] == 1
    assert report["reminder_preview_count"] == 2
    assert not report["human_enrollment_authorized"]
    assert not report["real_email_sent"]
    fixture = FictionalCrossoverStore(path / "fictional_crossover.sqlite3")
    assert fixture.redacted_progress("SYN_CROSSOVER_F1")["finished"]

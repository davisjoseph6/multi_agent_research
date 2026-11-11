"""Public two-language release gate remains closed on original candidate content."""
from pathlib import Path
import csv

from scripts.research_v2_preflight import ROOT, preflight


def test_existing_95_question_bank_cannot_release_three_period_fr_en_study():
    report = preflight(ROOT / "items.csv")
    assert report["result"] == "BLOCKED_NOT_APPROVED"
    assert report["english_bank_question_rows"] == 95
    assert report["english_bank_distinct_ids"] == 95
    assert report["minimum_distinct_question_rows"] == 261
    assert report["english_bank_forms"] == {
        "posttest": 16,
        "practice": 55,
        "pretest": 16,
        "recovery_drop2": 8,
    }
    assert report["french_bank_fully_reviewed_rows"] == 0
    assert any("261" in x for x in report["blockers"])
    assert any("French" in x for x in report["blockers"])
    assert not report["human_enrollment_authorized"]
    assert not report["changes_to_vps_services"]


def test_duplicate_reviewed_french_row_cannot_mask_an_untranslated_item(tmp_path):
    with (ROOT / "items.csv").open(newline="", encoding="utf-8-sig") as stream:
        source = list(csv.DictReader(stream))
    translations = [dict(item_id=row["item_id"], prompt_fr="Question française",
                         review_decision_fr="approved", **{
                             f"option_{c}_fr": "Choix " + c for c in "ABCD"
                         }) for row in source]
    translations[0]["prompt_fr"] = ""
    # Old row-count logic could be satisfied by one duplicate approved row.
    translations.append(dict(translations[1]))
    path = tmp_path / "translations.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(translations[0]))
        writer.writeheader()
        writer.writerows(translations)
    report = preflight(ROOT / "items.csv", path)
    assert report["french_bank_fully_reviewed_rows"] == len(source)
    assert any("duplicated" in blocker for blocker in report["blockers"])
    assert not report["human_enrollment_authorized"]

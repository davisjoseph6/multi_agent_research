"""Constructed-response draft authenticity tests, NOT educational validation."""
from hashlib import sha256
from pathlib import Path
import csv
import json
import pytest

from scripts.step96_106_authoring_drafts import CONCEPTS, ITEM_FIELDS, write_rows
from scripts.step96_106_create_performance_tasks import build, generate, TASKS, FIELDS


def fixture_bank():
    rows=[]
    for i,concept in enumerate(CONCEPTS):
        row=dict.fromkeys(ITEM_FIELDS, "")
        row.update(item_id=f"BE_PRACTICE_{i+1:03d}", concept=concept, form="practice", bloom="create", review_decision="pending", source_citation="draft citation")
        rows.append(row)
    for i in range(87):
        row=dict.fromkeys(ITEM_FIELDS, "")
        row.update(item_id=f"BE_PRETEST_{i+1:03d}", form="pretest", concept=CONCEPTS[i%8], bloom="apply", review_decision="pending")
        rows.append(row)
    return rows


def test_exact_eight_distinct_open_artifacts():
    tasks=build(fixture_bank())
    assert len(tasks)==8
    assert set(r["concept"] for r in tasks)==set(CONCEPTS)
    assert len({r["task_prompt"] for r in tasks})==8
    assert all(r["response_format"]=="constructed_response_written_or_diagram" for r in tasks)
    assert all("?" not in r["response_format"] and r["review_decision"]=="pending" for r in tasks)


def test_no_automatic_approval_or_hidden_score():
    for row in build(fixture_bank()):
        assert row["reviewer_record"]==row["review_date"]==""
        assert not any("correct_option_id" == x for x in row)
        assert "source_citation" in row


def test_refuse_modified_or_approved_bank():
    rows=fixture_bank()
    rows[0]["review_decision"]="approved"
    with pytest.raises(ValueError,match="unreviewed"):
        build(rows)


def test_refuse_duplicate_create_concept():
    rows=fixture_bank()
    rows[1]["concept"]=rows[0]["concept"]
    with pytest.raises(ValueError,match="exactly one"):
        build(rows)


def test_refuse_nonpractice_create_item():
    rows=fixture_bank()
    rows[0]["form"]="posttest"
    with pytest.raises(ValueError,match="practice"):
        build(rows)


def test_refuse_preexisting_reviewer():
    rows=fixture_bank()
    rows[0]["reviewer_record"]="claim"
    with pytest.raises(ValueError,match="unreviewed"):
        build(rows)


def test_refuse_invalid_bank_size():
    with pytest.raises(ValueError,match="95"):
        build(fixture_bank()[:-1])


def test_refuse_source_hash_drift_and_overwrite(tmp_path):
    rows=fixture_bank();p=tmp_path/"input.csv";write_rows(p,ITEM_FIELDS,rows)
    dest=tmp_path/"tasks"
    with pytest.raises(ValueError,match="hash changed"):
        generate(p,dest)
    assert not dest.exists()
    h=sha256(p.read_bytes()).hexdigest()
    result=generate(p,dest,expected_sha256=h)
    assert result["task_count"]==8
    assert result["current_mc_create_warnings_resolved"] is False
    assert result["requires_runtime_constructed_response_support"] is True
    with pytest.raises(FileExistsError):
        generate(p,dest,expected_sha256=h)
    with (dest/"constructed_response_create_tasks_PENDING_REVIEW.csv").open(newline="",encoding="utf8") as f:
        output=list(csv.DictReader(f))
    assert len(output)==8
    assert (dest/"manifest.json").exists()


def test_rubric_criteria_are_explicit():
    assert len(TASKS)==8
    assert all(len(value)==4 and all(s.strip() for s in value) for value in TASKS.values())
    assert "rubric" not in FIELDS or "scoring_rubric_version" in FIELDS


def test_deterministic_data():
    assert build(fixture_bank())==build(fixture_bank())

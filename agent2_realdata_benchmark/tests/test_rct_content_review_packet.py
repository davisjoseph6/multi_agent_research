"""Reviewer packet never marks any content as approved."""
import csv
from pathlib import Path

import pytest

from scripts.rct_candidate_cli import DEFAULT_SETTINGS, load_settings
from scripts.rct_content_review_packet import prepare


def test_packet_contains_all_items_and_sources_unchanged(tmp_path):
    base=DEFAULT_SETTINGS.parent
    originals={name:(base/name).read_bytes() for name in ("items.csv","resources.csv")}
    report=prepare(tmp_path/"packet")
    assert report["items"]==95
    assert report["resources"]==32
    assert not report["reviewed_or_approved_by_tool"]
    assert not report["changes_to_source_csv"]
    assert report["fatigue_instrument"].startswith("UNVALIDATED")
    for filename,count in (("item_review_worklist.csv",95),
                           ("resource_review_worklist.csv",32)):
        with (tmp_path/"packet"/filename).open(encoding="utf-8",newline="") as stream:
            rows=list(csv.DictReader(stream))
        assert len(rows)==count
        assert all(row["review_decision"]=="pending" for row in rows)
        assert all(row["recommendation_pending_expert_decision"]=="" for row in rows)
    assert all((base/name).read_bytes()==payload for name,payload in originals.items())
    assert load_settings(DEFAULT_SETTINGS)[1].unreviewed_items==95


def test_packet_refuses_overwriting_evidence(tmp_path):
    out=tmp_path/"packet"
    prepare(out)
    with pytest.raises(FileExistsError):
        prepare(out)

"""Tests for separately labeled manual recovery content preview."""
import pytest

from scripts.rct_recovery_gallery import render_html


def test_manual_gallery_has_all_eight_socratic_hints_without_study_treatment():
    html=render_html()
    assert html.count("<section>")==8
    assert html.count("<article class='resource'>")==32
    assert html.count("<h3>Socratic Hint</h3>")==8
    assert "NOT A PARTICIPANT SESSION" in html
    assert "NOT SELECTED BY POMCP" in html
    assert "NOT an interactive Socratic dialogue" in html
    assert "Guided prompt:" in html
    assert "LOCAL REHEARSAL" not in html  # different page from participant UX

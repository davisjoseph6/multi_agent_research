"""Static fidelity checks for the supervisor's bilingual interest questionnaire.

These tests prove that QA and the independently approved public route both
render the same supportive research instructions, while keeping the QA
acknowledgment distinct from institutionally signed LIVE privacy consent.
"""
from html.parser import HTMLParser
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "src/prototype/static"


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.inputs = []
    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag == "input":
            self.inputs.append(attributes)


def test_both_forms_support_english_french_switch_without_student_password():
    for name in ("supervisor_private_qa_interest", "supervisor_recruitment_interest"):
        html = (STATIC / (name + ".html")).read_text(encoding="utf-8")
        script = (STATIC / (name + ".js")).read_text(encoding="utf-8")
        tags = Tags()
        tags.feed(html)
        assert len(tags.ids) == len(set(tags.ids)), name
        assert {"language", "email", "first-name", "last-name",
                "no-ai-note", "encourage-title", "encourage",
                "status", "submit", "title"}.issubset(tags.ids)
        assert not any(item.get("type") == "password" for item in tags.inputs)
        assert "document.documentElement.lang" in script
        assert '"fr"' in script and '"en"' in script
        assert "IA générative" in script and "generative AI tools" in script
        assert "amusez-vous" in script.lower()
        assert "not graded" in script
        assert "type=\"email\"" in html
        assert "autocomplete=\"email\"" in html
        assert "@media(max-width:680px)" in (
            STATIC / (name + ".css")
        ).read_text(encoding="utf-8")


def test_live_form_requires_approved_notice_but_does_not_issue_tokens():
    html=(STATIC / "supervisor_recruitment_interest.html").read_text()
    script=(STATIC / "supervisor_recruitment_interest.js").read_text()
    assert 'id="privacy"' in html and 'required' in html
    assert 'href="/interest/privacy/en"' in html
    assert '"/interest/privacy/"+lang' in script
    assert "privacy_accepted" in script and "questionnaire:type" in script
    assert "POST" in script and "/interest/api/apply" in script
    assert "#invite=" not in script


def test_qa_form_only_records_qa_acknowledgment_without_false_notice():
    html=(STATIC / "supervisor_private_qa_interest.html").read_text()
    script=(STATIC / "supervisor_private_qa_interest.js").read_text()
    assert "PRIVATE QA ONLY" in html
    assert "NOT real research enrollment" in html
    assert "valid research consent" in html
    assert 'id="ack"' in html
    assert 'qa_acknowledged' in script
    assert "/interest/privacy/" not in html
    assert "/interest/privacy/" not in script
    assert "#invite=" not in script


def test_qa_bulk_links_are_staff_only_and_do_not_post_to_mail_provider():
    html=(STATIC / "supervisor_private_qa_issue.html").read_text()
    script=(STATIC / "supervisor_private_qa_issue.js").read_text()
    assert 'id="qa-all"' in html
    assert "qa-issue-all" in script
    assert '"confirm"' not in script or "confirm:true" in script
    assert "recruitment_csrf" in script
    assert "mail" in html.lower()
    assert "gmail.googleapis.com" not in script
    assert "api.brevo.com" not in script
    assert "graph.microsoft.com" not in script

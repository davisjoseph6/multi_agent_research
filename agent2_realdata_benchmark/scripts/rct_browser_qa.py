"""Real Chromium-engine loopback smoke; fictional participants only.

Unlike Flask's in-process test client, this exercises real browser rendering,
JavaScript fetch, persistence, viewport layout and server HTTP transport.
It does NOT test HTTPS, production concurrency, devices or accessibility.
Install the optional ops/rct/requirements-browser-qa.txt and Chromium first.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from werkzeug.serving import make_server

from scripts.rct_candidate_cli import DEFAULT_SETTINGS, engine_from
from src.prototype.rct_candidate_api import create_app


def rehearsal(settings_path=DEFAULT_SETTINGS, full=False):
    try:
        from playwright.sync_api import expect, sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Install optional Playwright: python -m pip install -r "
            "ops/rct/requirements-browser-qa.txt, then python -m playwright install chromium"
        ) from error

    settings_path=Path(settings_path)
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    if settings.get("mode") != "rehearsal":
        raise RuntimeError("Refusing non-rehearsal settings")

    with TemporaryDirectory(prefix="rct_chromium_rehearsal_") as tmp:
        engine = engine_from(settings_path, Path(tmp) / "fictional.sqlite3")
        invitation = engine.issue_invitation()["invitation"]
        server = make_server("127.0.0.1", 0, create_app(engine), threaded=True)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        url = f"http://127.0.0.1:{server.server_port}/"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    context = browser.new_context(
                        viewport={"width": 375, "height": 812},
                        device_scale_factor=1,
                    )
                    page = context.new_page()
                    page.goto(url, wait_until="load")
                    expect(page.locator(".warning")).to_contain_text("LOCAL REHEARSAL")
                    assert page.locator("#notice").get_attribute("role") == "status"

                    page.locator("#invitation").fill(invitation)
                    page.locator("#login button").click()
                    expect(page.locator("#agreement")).to_be_visible()
                    expect(page.locator("#information")).not_to_be_empty()

                    page.locator("#agree").check()
                    page.locator("#consent button").click()
                    expect(page.locator("#study")).to_be_visible()
                    expect(page.locator("#progress")).to_contain_text("question 1 of 16")
                    expect(page.locator("#activity h2")).to_be_focused()
                    expect(page.locator("#activity input[type='radio']")).to_have_count(4)

                    page.locator("#activity input[type='radio']").first.check()
                    page.locator("#activity button[type='submit']").click()
                    expect(page.locator("#progress")).to_contain_text("question 2 of 16")

                    # Token saved in per-tab sessionStorage, action data in SQLite.
                    page.reload(wait_until="load")
                    expect(page.locator("#progress")).to_contain_text("question 2 of 16")
                    expect(page.locator("#activity input[type='radio']")).to_have_count(4)

                    # A minimal 375px viewport overflow check, not a WCAG audit.
                    overflow = page.evaluate(
                        "() => document.documentElement.scrollWidth > window.innerWidth + 1"
                    )
                    if overflow:
                        raise AssertionError("Horizontal overflow at 375px viewport")
                    status = engine.audit()
                    assert status["people"].get("active") == 1
                    assert status["pending_actions"] == 1
                    if full:
                        for step in range(115):
                            if page.locator("#progress").inner_text()=="Complete":
                                break
                            previous = page.locator("#activity h2").element_handle()
                            if page.locator("#activity input[type='radio']").count():
                                page.locator("#activity input[type='radio']").first.check()
                                page.locator("#activity button[type='submit']").click()
                            elif page.locator("#activity select").count():
                                scale=engine.bundle.fatigue["scale"]
                                midpoint=(scale["minimum"]+scale["maximum"])//2
                                midpoint=scale["minimum"]+(
                                    ((midpoint-scale["minimum"])//scale["step"])*scale["step"])
                                for control in page.locator("#activity select").all():
                                    control.select_option(str(midpoint))
                                page.locator("#activity button[type='submit']").click()
                            elif page.get_by_role("button",name="I have finished this resource").count():
                                page.get_by_role("button",name="I have finished this resource").click()
                            else:
                                raise AssertionError("Browser encountered unexpected activity")
                            page.wait_for_function("(old) => !old.isConnected",
                                                   arg=previous, timeout=30000)
                        else:
                            raise AssertionError("Browser did not complete all three sessions")
                        assert page.locator("#progress").inner_text()=="Complete"
                        status=engine.audit()
                        assert status["people"].get("complete")==1
                        assert status["pending_actions"]==0
                        outcome=engine.export_private()["outcomes"][0]
                        assert outcome["pretest_answered"]==16
                        assert outcome["posttest_answered"]==16

                    context.close()
                    return {
                        "passed": True,
                        "mode": "fictional_rehearsal",
                        "browser": "Playwright Chromium headless",
                        "actual_browser_http": True,
                        "https_verified": False,
                        "mobile_device_tested": False,
                        "wcag_audit": False,
                        "full_three_session_browser_journey": full,
                        "questionnaire_version": engine.bundle.fatigue["version"],
                        "independent_security_review": False,
                        "checks": [
                            "local rehearsal warning",
                            "invitation and participation information",
                            "consent version and first assessment",
                            "first answer submission",
                            "browser refresh resumes second question without duplicating answer",
                            "375px viewport horizontal-overflow check",
                        ],
                        "limitations": "Browser-engine test on loopback, not a real-device, TLS or external audit.",
                    }
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server_thread.join(timeout=10)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--settings",type=Path,default=DEFAULT_SETTINGS)
    parser.add_argument("--full",action="store_true",help="Complete all fictional study sessions in Chromium")
    args=parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Refusing to overwrite earlier QA evidence")
    result=rehearsal(args.settings,full=args.full)
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()

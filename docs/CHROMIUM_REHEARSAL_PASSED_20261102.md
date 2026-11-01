# Chromium fictional browser rehearsal — passed (2026-11-02)

User-reported local evidence: Ubuntu 24.04, Playwright Chromium headless, real browser over loopback HTTP.

- Four browser dependency unit tests passed.
- Missing packages resolved using `libasound2t64`, `libnspr4`, and `libnss3` from Ubuntu Noble repositories.
- Command: `bash ops/rct/qa_browser_userlibs.sh python -m scripts.rct_browser_qa --full --out /tmp/rct_chromium_full_20261102_retry01.json`.
- Output: `passed: true`; `full_three_session_browser_journey: true`; `actual_browser_http: true`.
- Full journey verified pretest and posttest with 16 responses each and zero pending actions; browser reload/resume and 375px layout overflow check passed.
- Questionnaire remained `REHEARSAL_ONLY_UNVALIDATED_6_ITEMS_V1`.
- Not tested: HTTPS, actual mobile hardware, independent accessibility/security audits, production concurrency or any human trial.

The earlier missing-library failure recorded in `LOCAL_RCT_OPERATIONAL_QA_20261102.md` was fixed and is retained as incident history.

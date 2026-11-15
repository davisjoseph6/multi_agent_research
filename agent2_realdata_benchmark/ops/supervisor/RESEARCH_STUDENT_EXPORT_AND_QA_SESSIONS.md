# Researcher-only student measurements export

The private researcher dashboard displays the permanently assigned treatment
arm for each registered participant. The **student** portal intentionally
never discloses the arm (RCT blinding). A student receives exactly one
pseudonymous `STUDY_Pnnn` research ID, assigned once at eligible
registration and tied to an email via the separately encrypted/protected
contacts database. The contact email is unique regardless of whether the
researcher evaluates arm A, B or C. There is no user-selectable arm switch.

The protected `/control/` dashboard now shows **Assigned arm (researchers
only)** alongside the student ID. Its mastery chart displays eight concept
BKT probabilities and a ninth dashed line for the **arithmetic mean of those
eight probabilities**. This overall average is a descriptive aggregate, not
a separately fitted mastery parameter or independently validated clinical
or educational score.

After signing in with one of the four authorized staff identities, selecting
a student exposes **Download research archive for selected student (.zip)**.
The URL requires the existing protected staff session and a pseudonymous
`STUDY_Pnnn` participant ID. No new public route or student credential is
created. Each download is recorded in the private staff audit ledger.

## Archive contents

| File | Contents |
| --- | --- |
| `research_metadata.json` | Fixed arm A/B/C, one ID, registration/consent context, study status, planned schedule, initial eight BKT estimates derived from the completed pretest, and the initial overall mean |
| `mastery_progression.csv` | Every scored quiz/recovery event, event ID, timestamp, arm, session, question/action, C1–C8 BKT estimates and their overall arithmetic mean |
| `question_intervals.csv` | Scored question IDs, per-item response latency, wall-clock gaps between consecutive answers (including intervening breaks or cross-session waits), decimal ms/s/h/d |
| `session_timings.csv` | Sessions 1–3, scheduled/start/end UTC timestamps, duration, gap since previous completed visit, quiz count/correct count |
| `event_log.csv` | Append-only screening, pretest, quiz, recovery, posttest and fatigue event metadata: questions, choices, correctness, mastery before/after, policy/trigger/outcome, elapsed latency and language |
| `assessments.csv` | Screening/pretest/posttest answers, correctness, concept and Bloom level |
| `fatigue.csv` | Six fatigue responses and duration per completed session |

**No direct names, email addresses, private invitation tokens, cookies,
contact databases, IP addresses or raw free-text reflections are exported.**
Some variables such as program, age, question sequence and timestamps remain
potential quasi-identifiers, so downloads must be kept inside authorized
research storage and never shared publicly. Optional open-data consent is not
blanket permission to disclose identifiable raw measurements.

CSV cells that look like spreadsheet formulas are escaped. Responses for
missing/future sessions remain empty; no values are synthesized. Empty fields
mean **not observed**, not zero. Existing historical raw events and state
snapshots are not mutated, and no participant data is migrated across
environments.

## Three-visit experimental sequence

- Session 1: 16-item PRETEST, regular learning QUIZ, six-item SURVEY (fatigue).
- Session 2: learning QUIZ, six-item SURVEY.
- Session 3: learning QUIZ, 16-item POSTTEST, six-item SURVEY.

The post-test tile is **correctly disabled during sessions 1 and 2**.
Its position in the visual 4-part roadmap is not the execution order in
session 1.

The actual LIVE `/study/api/next-session` always enforces the approved
minimum three-day gap and remains disabled until scheduled arrival.

For the **separate, ephemeral localhost QA application only**, an exact
allowlist of two explicitly named testing email addresses enables the
`TEST ONLY — start next session now` convenience when the prior session
is already completed. This corrects the HTTP 409 experienced when a real
school-email test identity was used. The route exists only in
`release_mode="staging"`; it is *not registered* in LIVE. No pretest, quiz,
posttest or fatigue step can be bypassed while an earlier phase is active.

## Local acceptance without risking staged or LIVE data

Run the ephemeral QA runner on 127.0.0.1:8897 with your school and Gmail
test addresses, submit the school form, log into the staff console,
approve the application and use `/control/qa/` to issue the test link.
Complete session 1, click the TEST ONLY next-session button to reach
session 2, then complete session 2 and repeat to reach session 3.
Confirm that POSTTEST is accessible only after the third quiz. Examine
`/control/` between answers and download the ZIP to verify per-concept
and overall BKT estimates, timing data and fixed arm assignment.

The QA process deletes all temporary state on exit and never sends mail,
exposes public routing, verifies authentic human consent or performs
genuine RCT enrollment. Do not merge QA logs with the approved trial.
The separate pending LIVE release and its historical databases are left
untouched until the next reviewed exact-commit upgrade.

# Supervised 3-visit operations — pilot SOP (draft, not authorized)

**2026-11-08.** Venue, timetable, instructor, participant-contact system, and consent are **not confirmed**. No real student invitation has been issued. Do not publish participant names, attendance, personal email, phone number or session tokens in this public repository.

## Pre-recruitment

- PI designates supervisor/independent recruiter, institution, three-arm site capacity, accessibility staff, room, device/language availability, and escalation contacts.
- Obtain ethics/DPO/PI approvals and signed consent in approved language **before** allocation and any human assessment.
- Eligibility screen: age >=18, enrolled student, no prior formal behavioral economics course/training (record screening question), can freely consent, can make all 3 sessions. Check duplicates privately; no penalty for declining.
- Preallocate **room/time slots**, not randomization arms. Ensure attendance opportunity is equivalent across arms; prevent cross-arm contamination and peer sharing of teaching materials.
- Aim 30 initially enrolled per arm, 90 total. This is a **target**, not guaranteed 25 completers per arm. A full 3-visit plan needs capacity for up to **270 participant-visits**, plus rescheduled sessions and no-shows. At 10 active seats per timeslot, 27 room-timeslot units are required for 270 visits, but calendar windows and staffing may force more.

## Time spacing rules

- Design assumption: successive visits occur **3–5 days apart**, yielding session 1→3 ~6–10 days total. PI must decide whether "day" means elapsed 72–120 hours, local calendar-day difference, or a permitted holiday exception; write an amendment if changed.
- Proposed code's `pilot_measurements_draft.validate_visit_gap` uses *elapsed 72–120 hours*, not calendar days. **This code is not integrated in Flask**; scheduling and server-side enforcement are current blockers.
- Record actual end of previous visit, start of next, timezone, supervisor and approved deviation. Reject/reschedule outside window rather than silently allowing bypass. Never use browser clock alone as authority.

## Visit-by-visit checklist

**Session 1 — onboarding and learning (20 practice items):**
- Verify identity discreetly and confirm eligibility; present approved participant sheet, answer questions, capture consent; allocate concealed A/B/C.
- Record baseline 16-item pretest (independent); pre-learning M-VAS; learning practice 20 items (A can receive up to 2 additional planner-selected resources); immediate post-learning M-VAS.
- Save timestamp, stage, technical/instrument version and resources offered/rendered/responded. Confirm invitation doesn't leak in URLs, logs or screenshots. Agree next appointment 3–5 days later.

**Session 2 — learning (20 practice items):**
- Verify same participant; 3–5 day gap; pre-learning M-VAS; 20 practice questions plus A recovery if selected; post-learning M-VAS; save stage. Schedule visit 3.

**Session 3 — learning and outcome (15 practice items):**
- Verify same participant; 3–5 day gap; pre-learning M-VAS; 15 practice questions plus A recovery if selected; post-learning M-VAS; 16-item independent posttest; secure completion/debrief.

**All visits:** supervised normal-speed interaction, breaks and assistive accommodations, clear accidental refresh/retry handling, no feedback on assessment answers, consistent instructor support without giving different groups extra teaching, log safety/technical incidents, withdrawal process.

## Incident and scheduling exception log (PRIVATE)

For each appointment in an institutionally approved private tool: pseudonymized study ID, visit number, planned date/time/room, arrival/exit, previous-visit gap, attendance, consent version, device/accessibility accommodation, supervisor ID, deviations/reason, dropout and safe follow-up action. Do not keep these in a public GitHub repository.

Maintain a separate key linking institutional identity to pseudonymous study ID under DPO-approved access and retention. Do not derive IDs from raw email or name.

## Checkpoints before first live visit

- [ ] Three-session scheduling calendar staffed, capacity assessed, language and approved information/consent available.
- [ ] Immutable participant/study record with identity, valid consent and arm allocation concealed from recruiter.
- [ ] Server prevents unauthorized or out-of-window visit progression; staff-controlled override logged with PI authority.
- [ ] M-VAS pre/post x3 integrated, versioned and accessible, rather than old rehearsal-only 6-item form.
- [ ] Site/device/test data backups, downtime contingencies, private reporting and audit.
- [ ] Pilot GO decision signed by institution, PI, ethics/DPO contacts, content reviewers, independent technical QA.

**Alternative:** if 3–5 day spacing cannot be maintained operationally, amend protocol/SAP and obtain approval **before enrollment**; do not change it secretly.

# Step 68 — IJCAI 2027 Trial Readiness Assessment

Status: DEVELOPMENT PROTOTYPE; NOT APPROVED FOR HUMAN STUDIES

## 1. Verified engineering baseline

- Step 67 regression suite: 635 tests passed.
- Experimental browser: operational.
- Invitation-protected API: operational.
- Synthetic allocation and recovery: tested.
- Synthetic trial audit: completed.
- Read-only database-integrity audit: completed.
- Evidence from real randomized participants: none.

These tests establish software properties, not
educational treatment effectiveness.

## 2. Scientific intervention definition

Current conditions:

1. Control: no optional summary offer.
2. Fixed summary: offer at eligible practice boundaries.
3. Adaptive threshold: BKT-based mastery threshold.

The current adaptive policy is NOT POMCP.
POMCP remains a shadow diagnostic.

DECISION REQUIRED:
Will the trial evaluate the BKT-threshold policy,
the POMCP controller, or separate experiments?

## 3. Primary causal question

TO BE AGREED WITH SUPERVISOR.

Candidate question:

Does assigning learners to an adaptive assistance
policy improve independently assessed learning
outcomes compared with a prespecified comparator?

A specific population, outcome, time point and
primary policy contrast have not yet been approved.

## 4. Learning measurement

Current implementation:
- Three practice questions.
- One independent probe.

Limitations:
- No validated baseline learning assessment.
- No validated multi-item primary outcome.
- No delayed retention assessment.
- No established measurement reliability.
- No independent item-difficulty calibration.

REQUIRED:
Define and validate outcome instruments before
any real-participant experiment.

## 5. Experimental design

PENDING:
- Target population and eligibility.
- Unit of randomization.
- Primary comparison and estimand.
- Number of experimental conditions.
- Assistance exposure/dose considerations.
- Sample size and power assumptions.
- Allocation concealment and blinding limitations.
- Intention-to-treat analysis.
- Missing outcome handling.
- Multiplicity adjustment where applicable.
- Statistical analysis plan.

## 6. Research governance

PENDING:
- Institutional sponsor or responsible research body.
- Applicable research-ethics review/authorization.
- Informed-consent procedures.
- GDPR roles, lawful basis and data minimization.
- Data retention and deletion policy.
- Participant withdrawal procedure.
- Trial registration requirements.
- Incident and adverse-event procedures.

No actual students may be enrolled on the
authority of this engineering assessment.

## 7. Engineering gaps

PENDING:
- Credential revocation and recovery.
- Authenticated real-world participant identity.
- Appropriate secure transport and deployment.
- Session-level authorization threat testing.
- Durable timestamps and exposure measurements.
- Distinction between offered, accepted, delivered,
  displayed and demonstrably viewed assistance.
- Data exports for approved statistical analysis.
- Verified browser recovery after interruption.
- Separation of study credentials and personal data.

## 8. Go/no-go decision

Engineering demonstration: GO for synthetic development.

Human-participant RCT: NO-GO until scientific,
institutional, ethical and data-protection
requirements are resolved.

## 9. Reporting references

SPIRIT 2025:
https://doi.org/10.1136/bmj-2024-081477

CONSORT 2025:
https://doi.org/10.1136/bmj-2024-081123

## 10. Manual browser recovery verification

Date: 2026-10-29

Environment:
- Local Flask development server.
- Loopback-only HTTP access.
- Temporary SQLite database.
- Synthetic invitation credential.
- No real participants.

Observed execution:
- Initial invitation enrollment returned HTTP 201.
- Two practice responses were accepted.
- Optional assistance was accepted and delivered.
- The browser page was refreshed.
- Re-enrollment returned HTTP 200.
- The original session identifier was recovered.
- Two further answers were accepted.
- Four responses were accepted in total.
- Two assistance deliveries succeeded.

Result:
PASS — browser-refresh session recovery was
demonstrated with the original session identifier.

Limitations:
- Server-process restart was not tested in this run.
- Recovery across devices was not tested.
- The HTTP log does not independently establish
  that the final completion screen was displayed.
- This is synthetic software-verification evidence,
  not evidence of educational effectiveness.

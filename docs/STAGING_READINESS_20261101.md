# Staging readiness — 2026-11-01 (operator checklist; NOT live RCT authorization)

## Immutable observed local baseline
- Rehearsal candidate commit: `1d061bdfc3c9b40219612f442299062fdb4ebfe1`.
- Researcher's local tests: 1,292 passed, 0 failed; Arm A fictional browser journey completed (16 pretest, 55 practice, 3 questionnaires, 16 posttest, 6 recovery resources).
- Four kinds of recovery offered: CONCEPT_SUMMARY (2), DROP_2 (1), WORKED_EXAMPLE (1), SOCRATIC_HINT (2); all 6 rendered and completed.
- These checks do not demonstrate educational impact or live-service security, capacity, TLS, consent or regulatory readiness.

## Public preview — safe low-risk option
- `docs/index.html` is a standalone **scripted illustration**, not the Flask participant application.
- Before sharing, verify privacy/license/research claims and execute `python -m scripts.rct_public_preview_check`.
- Repo owner: Settings > Pages > deploy from branch `feature/rct-https-staging-20261101` and `/docs`, if that branch is selectable. If branch Pages is restricted, choose approved default-branch publication after review, or a controlled static host.
- Verify Pages reports a real HTTPS URL. Check with a separate browser and mobile viewport. DO NOT infer URL until enabled.
- No recruitment, invitation, backend, actual POMCP action selection, uploads or answers.

## Full interactive Flask/WSGI staging — NOT YET DEPLOYED
- Requires confirmed host/provider, DNS or approved temporary host, secured Linux machine, operator admin rights, TLS proxy and WSGI service.
- Current `make_wsgi_app()` intentionally refuses rehearsal and requires reviewed **live** release settings; DO NOT bypass the gate to expose the actual participant app.
- Develop a distinct **preview-only**, non-public-data staging boundary and code-reviewed host allowlist without relaxing the production release gate; independently review security controls before wider internet exposure.
- Never expose Flask `serve` beyond 127.0.0.1; never upload demo sqlite files or bearer invitations to GitHub, Pages, logs or videos.
- Test actual HTTPS, proxy/host headers, websocket absence, throttling, origin controls, duplicate submissions, multi-browser latency, rollback and availability before invitation-based staging.

## Human RCT go/no-go remains NO-GO
- Independent content/answer-key approval of 95 questions and 32 resource texts.
- Instrument selection, scale permissions/validity and analysis freeze (NASA Raw-TLX = workload, NOT equivalent to fatigue).
- Institutional/ethics and privacy authorization, external accessibility/security reviews, realistic infrastructure tests, validated offsite backups and disaster recovery.
- All release evidence must match exact candidate hashes; do not manufacture approvals.

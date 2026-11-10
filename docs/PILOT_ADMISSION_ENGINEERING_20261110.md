# Future IJCAI 2027 admission-control engineering: isolated synthetic contract

**Status (10 November 2026): DEVELOPMENT / NO-GO FOR HUMAN PARTICIPANTS.**
This design code is explicitly disconnected from both the existing private
VPS fictional browser and the older operator demonstration. It is NOT a
human-study application, proof of verified identity, signed consent,
ethics approval, or permission to recruit students.

## Why this exists

The current private preview permits the operator to select A/B/C fictional
arms. This is appropriate for a *demonstration*, but real recruitment
cannot permit participants to choose their assigned policy. Additionally,
the legacy RCT candidate had an evidence-file mechanism whose positive
result could not authenticate the purported reviewer or institutional signer.
This branch closes the legacy live startup path unconditionally; independently
verified institutional approval and a separately designed human system will
be necessary, rather than elevating an unverified JSON declaration to authority.

## Added implementation (offline synthetic fixtures ONLY)

`agent2_realdata_benchmark/src/prototype/pilot_admission_controls_draft.py`
implements a small, persistent security-contract rehearsal:

- Requires a specially named `fictional_admission.sqlite3`, synthetic
  participant IDs, consent-text SHA-256 and exact screening version.
- Distinguishes operator and auditor fixture capabilities; each must be
  a different random byte string with at least 256 bits of entropy.
  **These are NOT institutional SSO, identity verification or real roles.**
- Offline fixture screening precedes invitation-based agreement to the
  exact consent-information hash.
- Server-side allocation chooses secure randomized permuted blocks of six
  or nine with a 1:1:1 A/B/C composition. SQLite `BEGIN IMMEDIATE`
  serializes competing writers. The status method never reveals assignments.
- An eligible and consented synthetic record can start at most three
  ordered fixture visits. Starts of visits 2 and 3 must be 72–120 elapsed
  hours after the prior *completed* visit. Only an offline operator fixture
  initiates or finishes a visit.
- Withdrawal is durable and blocks further starts; repeated withdrawal
  before credential expiry does not create a duplicate event.
- Events are hash-linked for accidental-corruption detection. **Hash
  linkage is not a signature or protection against an attacker with
  full database write permission.**
- The audit gives only aggregates and integrity findings, not identity,
  bearer tokens, item answers, or individual treatment assignments.
- A restricted synthetic-only SQLite backup method requires the auditor
  fixture capability, refuses an existing output, creates an owner-only
  backup file, verifies SQLite integrity and the pinned configuration,
  and permits a separate restored fixture to be re-audited. This is NOT
  an offsite encrypted backup, real retention solution or DR certification.

The entire module is **not imported by either Flask application**.
All methods and output schemas explicitly identify their synthetic scope.
There is no public endpoint, scheduler, real identity collection,
permission to release a study, or support for a human database.

## Reproduce the fixture tests

From `agent2_realdata_benchmark` with the existing pinned prototype venv:

```bash
python -m pytest -q \
  tests/test_pilot_admission_controls_draft.py \
  tests/test_rct_candidate.py
```

An additional disposable, no-network rehearsal exercises this complete
offline fixture-control path and independent backup/restore for 30 fictional
records (or another explicitly selected count, 3–90):

```bash
python -m scripts.pilot_admission_offline_rehearsal --participants 30
```

This is deliberately distinct from the quiz HTTP full-journey test:
it does not deliver any question, fatigue instrument or intervention, and
its three "visits" are staff fixture events only. The report contains
aggregate counts, not participants, invitations, or assigned arms. The
runner does not take an external host or database path.

The tests cover concurrent synthetic allocations, partial/complete blocks,
unknown/expired invitations, missing or mismatched consent, ineligible
records, role separation, visit timing/ordering, withdrawal, immutable
configuration, database restart, backup/restore, forged state
transitions, and event-chain tampering. A separate
regression test mocks a completely positive local evidence inventory and
requires the **legacy** `mode="live"` constructor to refuse startup anyway.

## Production implementation still necessary

This branch deliberately does NOT implement the following as real
institutionally authorized services:

1. A trusted researcher/staff identity provider with MFA, RBAC, revocation,
   least privilege, audit, and independent authorization; actual eligibility
   verification and legally approved information/consent/withdrawal flows
2. Dedicated participant records with a documented pseudonymization key
   strategy, encryption/storage architecture, retention/erasure policies,
   controller/DPO approval and subject-rights operations
3. Approved full study/session state integration: server-driven calendar,
   randomized assignment blinded until appropriate reveal, supervised
   attendance, approved assessments/recovery actions and instrument versions,
   and independent fidelity verification
4. Concurrency architecture and real network loading of the proposed number
   of learners, with a decision about PostgreSQL or another appropriate DB,
   migration tooling, backup/restore RPO/RTO and operational monitoring
5. Production TLS, authenticated administration, independent penetration
   testing, device/browser/accessibility review and release gates bound
   to signed institutionally verified evidence and immutable build hashes

These are not placeholders that can be declared passed by filling a template.
The PI, ethics, DPO, statistician, external instructional reviewers and
responsible institution must make their own decisions. No user-facing
human enrollment is permitted by any code in this branch.

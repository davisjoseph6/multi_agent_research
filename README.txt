IJCAI 2027 — existing V6 mechanism go/no-go (development only)
================================================================
This ADD-ONLY package contains:
  agent2_realdata_benchmark/scripts/step95_nov2_recovery_decision.py
  agent2_realdata_benchmark/tests/test_step95_nov2_recovery_decision.py
  agent2_realdata_benchmark/docs/ijcai_nov2_recovery_scientific_decision_packet_DRAFT.md

Run from ~/multi_agent_research:
  sha256sum ijcai_oct31_recovery_decision_v1.zip
  python3 -m zipfile -e ijcai_oct31_recovery_decision_v1.zip .
  cd agent2_realdata_benchmark
  PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_step95_nov2_recovery_decision.py
  PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.step95_nov2_recovery_decision --participants 30 \
    --real-data-report /tmp/ijcai_phase6_train_val_step95_v1.json \
    --output /tmp/ijcai_nov2_v6_decision_30.json \
    --markdown /tmp/ijcai_nov2_v6_decision_30.md
  sed -n '1,130p' /tmp/ijcai_nov2_v6_decision_30.md
  PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider

The script refuses to overwrite an existing report. Pick new filenames if
re-running. It will NOT evaluate held-out synthetic seeds >=200000, Phase6 TEST
labels, or human outcomes. It does not edit the 52-row status register.

From repository root, commit only the 3 new files after reviewing staged paths.
Expected full test suite: 1,132 = previous user-reported 1,114 + 18 new focused tests.

Stop if any validation fails. DO NOT interpret V6-vs-no-recovery as real
educational causality; it is development-stage synthetic mechanism evidence.

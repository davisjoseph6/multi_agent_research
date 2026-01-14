#!/usr/bin/env bash
set -euo pipefail

echo "== 1) Inspect artifacts =="
python3 -m src.inspect_artifacts
echo

echo "== 2) Pick big-gap candidates (concept) =="
python3 -m src.pick_demo_cases --min_gap 20 --top_k 5
echo

echo "== 3) Pick big-gap candidates (bloom) =="
python3 -m src.pick_demo_cases --use_bloom --min_gap 20 --top_k 5
echo

echo "== 4) Demo state forward pass: concept small gap (s14,t23) =="
python3 -m src.demo_state_forward_pass \
  --run_dir results/runs/run_20260114_120653/state_gru/concept \
  --student_idx 14 \
  --t 23
echo

echo "== 5) Demo state forward pass: concept big gap (s0,t36) =="
python3 -m src.demo_state_forward_pass \
  --run_dir results/runs/run_20260114_120653/state_gru/concept \
  --student_idx 0 \
  --t 36
echo

echo "== 6) Demo state forward pass: bloom big gap (s14,t23) =="
python3 -m src.demo_state_forward_pass \
  --run_dir results/runs/run_20260114_121706/state_gru/bloom \
  --student_idx 14 \
  --t 23
echo

echo "Done. Open the JSON files in the run dirs for the talk-through."

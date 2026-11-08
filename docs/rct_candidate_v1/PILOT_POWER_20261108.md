# Recruitment target and statistical power — preliminary calculation

**Prepared 2026-11-08. DRAFT: subject to statistician + PI approval.**
**Important:** A randomised **pilot feasibility trial** should generally justify its size via ability to assess feasibility/precision, rather than claim confirmatory treatment-effect testing.

## Proposed cohort
- Randomize **90** adult students, 1:1:1 (expected 30 assigned A, B and C).
- Target **75** completers, 25 per arm on average (83.3% retention; 16.7% dropout).
- Reaching exactly 25 completers in EACH arm is not assured: even if overall retention is 83.3%, arm-specific attrition and imbalance are possible. Need recruitment-monitoring and a preapproved rule if an arm falls below target.
- Three supervised sessions per participant = up to **270 supervised visits** for all randomized students; expected complete attendance 225 visits if exactly 75 complete. Incomplete students may still attend 1–2 visits, so the actual staffing total is BETWEEN those simplified figures, not necessarily 225.
- Adjacent sessions 3–5 days apart if retained in the final protocol, yielding ~6–10 elapsed calendar days from session 1 to 3 (excluding rescheduling and any extra follow-up). Time windows and staff availability are not verified.

## Two-sided pairwise t-test sensitivity (unadjusted)

For **two** planned comparisons A-vs-B and A-vs-C, use conservative Bonferroni two-sided `alpha=.025` each, family-wise alpha <=.05. Model: independent participants; equal group sizes; equal within-arm variance; continuous unadjusted endpoint; noncentral t exact power with degrees of freedom `2n-2` and noncentrality `d sqrt(n/2)`. Effect `d` is a standardized between-arm mean difference on independent **16-item posttest**. This is a sensitivity model, **NOT** final ANCOVA/repeated fatigue analysis or a licensed minimum detectable clinically important difference.

| Standardized effect d | Power at 25 completers/arm | Completers/arm for >=80% power | Approx. total recruitment at 16.7% dropout, balanced |
|---|---:|---:|---:|
| 0.3 | 11.4% | 213 | 768 |
| 0.4 | 19.4% | 121 | 438 |
| 0.5 | 30.2% | 78 | 282 |
| 0.6 | 43.0% | 55 | 198 |
| 0.8 | 69.6% | 31 | 114 |
| 0.9 | 80.4% | 25 | 90 |

Do **not** present this table as the exact enrollment requirement for an ANCOVA or bounded count outcome. Approx recruitment uses `3 * ceil(n_per_arm / (1-1/6))`, conservative balanced quotas. All values are preliminary numerical model outputs; rerun the script in the target research environment.

At **n=25 per arm**, the effect needed for **80%** power is approximately **d=0.896**. A moderate `d=0.50` has only ~30% power. If the real effect is smaller, a pilot is not a confirmatory treatment test.

### Feasibility precision

If exactly 75/90 complete, the estimated completion rate is 83.3%; Wilson 95% interval is approximately 74% to 90% (run CLI for precise result). Across an individual arm 25/30, uncertainty is much wider; report it for all three arms.

## To be validated by a statistician before actual effectiveness RCT

1. Primary estimand/outcome: 16-item posttest total correct? Confirm its validity, measurement error, item difficulties, and whether pretest adjusts precision.
2. Meaningful difference: minimum policy/scientifically important increase in correct items (e.g. a stated number of questions), not invented from Cohen d; obtain external empirical benchmark or blinded pilot variability.
3. Outcome distribution: pooled SD, baseline-posttest correlation, ceiling/floor, missingness, differential dropout, attendance, clustering by classroom/site and any instructor effects.
4. Hypotheses and multiplicity: exactly A-vs-B and A-vs-C; choose Holm/Bonferroni and family alpha before data.
5. Treatment contrast: Arm A resource availability and time-on-task differ; matched comparator needed for algorithm-only claim.
6. Power simulation of the **frozen actual analysis model** (ANCOVA/mixed effects, bounded total if necessary); report reproducible code, RNG seed, simulation-based SE, sensitivity.
7. Determine whether this is a feasibility pilot (90 possible without adequate treatment power) or a definitive efficacy study (sample may need substantial increase).

## Reproducible code

From the repository benchmark directory in the prototype Python virtual environment:
```bash
python -m scripts.pilot_power_analysis \
  --completers-per-arm 25 \
  --recruited-per-arm 30 \
  --effect-sizes 0.3,0.4,0.5,0.6,0.8,0.9
python -m pytest -q tests/test_pilot_power_analysis.py
```
Requires SciPy already included in `requirements.txt`; exact power is evaluated through `scipy.stats.nct`. The program does not read/modify participant databases.

## Methodological sources

- CONSORT pilot feasibility guidance (2016): https://www.bmj.com/content/355/bmj.i5239
- CONSORT 2025 explanation, sample-size assumptions: https://www.bmj.com/content/389/bmj-2024-081124

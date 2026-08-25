# Stage 8 Sequence/Context Sampling Policy v0.1

Status: **metadata-only design contract**. This document does not authorize model training or production authority.

## Purpose

The Stage 8 sequence/context research target already has a frozen 1,200-case allocation: 800 TRAIN, 200 VALIDATION and 200 untouched SC-HOLDOUT. This policy adds the sampling rules that must be satisfied before mined ambiguity candidates can become a human-review pool or final corpus.

## Frozen final allocations

| Source | Final cases | Review-pool target |
| --- | ---: | ---: |
| OpenScore String Quartets | 600 | 1,200 |
| OpenScore Lieder | 300 | 600 |
| Owned synthetic guitar/context | 300 | 600 |
| **Total** | **1,200** | **2,400** |

Every source receives at least a 2x review buffer. The review-pool target is not a training target and does not change the final 1,200-case sample plan.

## OpenScore diversity caps

String Quartets:

- at most 20 final cases from one score/source item;
- at most 20 final cases from one source group/work;
- at most 100 final cases from one composer;
- at most 90 final cases from one exact candidate set;
- at least 30 distinct source groups and at least 6 composers are required to supply 600 final cases.

Lieder:

- at most 10 final cases from one score/source item;
- at most 20 final cases from one source group/cycle;
- at most 45 final cases from one composer;
- at most 45 final cases from one exact candidate set;
- at least 15 distinct source groups and at least 7 composers are required to supply 300 final cases.

Owned synthetic material remains subject to source-item, source-group and candidate-set caps; composer constraints do not apply.

## Pilot evidence

The first real OpenScore pilot is recorded only as aggregate evidence:

- String Quartets: 10 source items, 52,209 harmonic frames, 1,755 AMBIGUOUS candidates.
- Lieder: 10 source items, 4,047 harmonic frames, 235 AMBIGUOUS candidates.

The exact manifest, candidate-pool and output SHA-256 fingerprints are frozen in the policy code. The pilot proves pipeline feasibility only. Pilot candidates are not automatically included in the final corpus and receive no preference, label, model-training authority or production authority.

## Selection invariants

All later selectors must be deterministic, enforce source-group-disjoint partitions, select the untouched holdout without model feedback, and preserve human verification as the only source of preferred-candidate labels. If the diversity constraints cannot be met, selection fails closed and the source pool must be broadened rather than weakening the policy silently.

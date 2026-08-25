# Stage 8 Sequence / Context Ambiguity Shadow Ranking Target v0.1

Status: research-target contract only. No model training or production authority.

## Approved target

`sequence-context-ambiguity-shadow-v1`

Objective: rank only the deterministic candidates of frames that the authoritative engine has already left `AMBIGUOUS`.

## Hard boundaries

- deterministic engine remains sole harmonic authority;
- source frame must already be `AMBIGUOUS`;
- candidate set is immutable and comes from the deterministic engine;
- the research system cannot generate candidates;
- the research system cannot change `RESOLVED`, `AMBIGUOUS`, `ABSTAIN`, or `NO_MATCH`;
- the research system cannot suppress abstention or no-match outcomes;
- context is causal: current frame plus at most four previous frames;
- future-frame access is forbidden;
- Teacher-Gold and frozen HOLDOUT labels are unavailable to the model;
- target design cannot be derived from HOLDOUT labels.

## Intended output

A future shadow component may emit an ordered view of the already-existing candidate set, for example:

`C6 0.71 | Am7/C 0.29`

The authoritative result remains unchanged, for example:

`AMBIGUOUS: C6 | Am7/C`

Scores, if any are introduced later, are advisory research values and are not confidence authority.

## Next gate

A separate Stage 8-B feature contract must define exactly which causal, validated fields can be presented to the research model. A real corpus manifest and frozen preregistration are still required before any training plan can be proposed.

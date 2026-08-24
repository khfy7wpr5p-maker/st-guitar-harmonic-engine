# Stage 8 model-entry gate v0.1

This gate sits between deterministic Teacher-Gold evaluation and any future model
research. It exists to prevent the frozen calibration/HOLDOUT benchmark from being
reused as a training target or from creating accidental model authority.

## Current interpretation

A complete, stable deterministic comparison that already solves all 200 frozen
Teacher-Gold cases does not create a reason to train a model. The safe result is
`blocked_deterministic_sufficient` unless a separate research target is supplied.

A future research target must be:

- non-empty;
- preregistered before evaluation;
- sourced from authorized data;
- disjoint from Teacher-Gold calibration and HOLDOUT;
- not derived from HOLDOUT labels or failures.

Even when all of those conditions pass, the highest gate result is
`shadow_research_design_eligible`. The gate never authorizes training and never
grants production authority.

## Frozen invariants

- deterministic resolver remains the sole harmonic authority;
- no performance threshold is invented here;
- HOLDOUT cannot be tuned against;
- model output cannot replace RESOLVED / AMBIGUOUS / ABSTAIN / NO_MATCH decisions;
- AI/model work remains shadow/advisory unless a later separately reviewed contract
  explicitly changes scope;
- branch/CI/merge safety gates remain required.

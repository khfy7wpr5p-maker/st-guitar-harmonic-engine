# Stage 8 OpenScore Source Selector v0.1

Status: **metadata-only source-mining selector**. It chooses score files to mine, not harmonic answers or final corpus labels.

## Why this exists

The first feasibility pilot intentionally selected the alphabetically first ten files in each OpenScore repository. That was appropriate for pipeline validation but created obvious source concentration (for example, many Beethoven quartets and early-alphabet Lieder composers). Final corpus mining must not repeat that bias.

## Deterministic selection

The v0.1 selector:

- accepts only the frozen OpenScore String Quartets and OpenScore Lieder source ids;
- validates canonical `scores/**/*.mscx` paths and rejects traversal/duplicate inputs;
- derives the same conservative source-group semantics used by the ambiguity miner;
- excludes already mined score paths and/or source groups when requested;
- ranks composers and scores with a stable SHA-256 selector seed instead of alphabetic order;
- performs composer round-robin selection;
- selects at most one score per source group;
- derives a per-composer source-item cap from the frozen final-case sampling policy;
- fails closed if the requested count cannot satisfy source-group uniqueness and composer diversity;
- emits a deterministic selection SHA-256 fingerprint.

For Lieder, a source group is `scores/<composer>/<set-or-cycle>`, so multiple songs in one cycle cannot all be chosen by this source-diversification pass. For String Quartets, the full work directory is the source group.

## Authority boundary

Selection does not use harmonic outcomes, preferred candidates, human labels, model predictions, Teacher-Gold or holdout labels. `model_training_authorized` and `production_authority_granted` remain false.

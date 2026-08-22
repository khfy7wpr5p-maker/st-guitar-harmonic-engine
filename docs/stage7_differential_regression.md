# Stage 7-F Differential Regression Policy

Frozen comparison baseline: Stage 6 final main `c2df9d09d3e2c84a9ea203f8567ec5e48eeab3ea`.

The differential suite freezes core semantic behavior that must not drift silently:

- exact validated harmony remains authoritative;
- exact symmetric diminished-seventh ambiguity remains explicit;
- BASS_INVERSION-only evidence remains weak and abstained;
- INCOMPLETE_CHORD-only evidence remains weak and abstained;
- exact evidence outranks lower structural evidence;
- repeated runs and input permutations remain deterministic.

Any future intentional behavior change must update the frozen expectation in the same PR and document: the old behavior, new behavior, architectural reason, security impact, backward-compatibility impact, and regression evidence. A changed expectation without that documentation is an unexplained drift and must not merge.

This baseline is a behavior contract, not a teacher-gold musical-accuracy benchmark.

# Negative-Lane Engine

This document explains the new direction in plain language.

## One Sentence Version

The project now treats evaluation as an entropy-folding process:

1. run a dense stress lane
2. surface failures clearly
3. classify recurring failure families
4. track variance over time
5. only draft new probes when the signal justifies it

That is the opposite of growing a giant permanent pile of positive-lane tests.

## Why The Direction Changed

A system that reacts to every new concern by adding more one-off benchmark cases eventually becomes hard to understand, expensive to maintain, and noisy to interpret.

That kind of suite often answers:

- did the model pass this one handcrafted case?

But it struggles to answer:

- what class of failure is actually happening?
- does it recur across runs?
- does the host need a new constraint?
- is this serious enough to deserve a new probe?

The negative-lane engine is built to answer those second questions first.

## The Two Lanes

### Baseline lane

The original `run` command remains.

It uses the fixed probe pack and provides:

- deterministic CI coverage
- stable regression checks
- familiar report and fingerprint artifacts

### Gauntlet lane

The newer `gauntlet-run` command adds a denser multi-turn lane.

It is meant to pressure the model across several dimensions inside one conversation, then classify what breaks.

This lane is where the project now learns the fastest.

## How Entropy Gets Folded

The gauntlet lane does not treat every failure as a reason to immediately add another permanent benchmark.

Instead it follows this chain:

1. A gauntlet run produces failures.
2. Failures are grouped into families.
3. History is aggregated into the gauntlet atlas.
4. The operator decides whether the family is noise, something to monitor, or something that deserves a probe draft.
5. The probe forge turns justified signal into draft probes.
6. Draft probes are validated and materialized as blueprints.
7. Only then do they become candidates for future suite growth.

That keeps growth evidence-led.

## Key Objects

`Failure family`

A recurring class of breakage such as hierarchy drift, fabricated evidence, or schema collapse.

`Negative lane`

A constraint or host rule suggested by observed failure evidence.

`Gauntlet atlas`

The historical summary of gauntlet runs, grouped by model and failure family.

`Operator decision`

A lightweight judgment attached to a failure family, such as:

- `monitor_only`
- `probe_candidate`
- `probe_needed`
- `confirmed_for_forge`
- `dismissed`

`Probe forge draft`

A draft blueprint for a new probe generated from recurring signal rather than from one-off intuition.

## What The Dashboard Is For

The dashboard is the local control surface for this loop.

It can help you:

- launch baseline runs
- launch gauntlet runs
- inspect history
- compare runs
- review operator decisions
- inspect draft probes
- inspect assistant-role telemetry

It is still not the source of truth.

Artifacts remain the source of truth.

## What Assistant Models Are For

Assistant models are optional.

They can:

- review completed runs
- participate in evaluator-fit benchmarking
- generate telemetry that helps us judge whether a GGUF is suitable for assistant-style roles

They cannot replace the deterministic harness outputs.

This separation is intentional.

## Recommended Mental Model

Think of the system like this:

- the baseline lane checks known surfaces
- the gauntlet lane discovers pressure points
- the atlas tells you what repeats
- the operator decides what matters
- the forge drafts what is worth formalizing
- negative lanes turn failure evidence into containment

That is the engine.

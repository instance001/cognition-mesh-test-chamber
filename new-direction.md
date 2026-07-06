# New Direction

This file captures the project's direction in a structured way.

It is not a build log.

It is the doctrine and feature-shape for where `cognition-mesh-test-chamber` is meant to go.

## One-Line Summary

This project is becoming a negative-lane constraints engine that folds broad failure signal into containment, historical patterning, and selective probe growth.

## Core Identity

The project is:

- a local suitability engine
- a cognitive fingerprinting system
- a negative-lane generator
- a historical failure-pattern tracker
- a selective probe-drafting engine

The project is not:

- a leaderboard
- a public model ranking site
- a giant museum of hand-authored benchmark cases
- an assistant-opinion machine pretending to be truth
- an uncontrolled agent sandbox

## Direction Shift

The older shape of the repo centered on a fixed baseline probe pack.

That baseline still matters and stays in place.

The newer shape adds a denser evaluation lane built to:

- create pressure
- surface failure families
- track variance across runs
- support operator judgment
- generate new probes only when justified

The point is to stop endlessly adding positive-lane cases and instead let failure evidence drive growth.

## Two-Lane Model

### Baseline lane

Purpose:

- stable deterministic regression surface
- CI-safe mock path
- familiar report and fingerprint outputs
- known probe-pack comparison

Characteristics:

- fixed seven-probe MVP path
- deterministic mock support
- strong containment story
- direct negative-lane generation from observed failures

### Gauntlet lane

Purpose:

- dense multi-turn pressure testing
- broad behavioural suitability reads
- recurring failure-family discovery
- entropy folding into atlas, decisions, and drafts

Characteristics:

- one cascading conversation rather than isolated cases
- multiple stress dimensions in one run
- transcript preservation
- per-turn scoring
- failure-family classification
- historical atlas aggregation

## Main Mechanisms

### 1. Failure-family classification

Failures should not remain isolated anecdotes.

They should be grouped into recurring classes such as:

- role boundary breaks
- quoted instruction hierarchy failures
- extraction fidelity drift
- schema collapse
- evidence binding failure

### 2. Negative lanes

Observed failures should become reusable walls.

The system should turn breakage into:

- containment suggestions
- host-rule ideas
- deployment cautions
- probe-worthy signals

### 3. Gauntlet atlas

The project should keep historical memory of what fails and how often.

The atlas exists to answer:

- did this failure recur?
- is it model-specific or general?
- is it severe enough to formalize?
- is it noisy or stable?

### 4. Operator decisions

The system should not auto-promote every failure into a permanent test.

An operator should be able to classify signal as:

- `monitor_only`
- `probe_candidate`
- `probe_needed`
- `confirmed_for_forge`
- `dismissed`

### 5. Probe forge

Probe growth should be selective.

The forge exists to turn justified recurring signal into:

- draft probes
- blueprint-style materialized probe payloads
- validator-checked candidate additions

## Design Vibe

The intended vibe is:

- dense rather than sprawling
- evidence-led rather than intuition-led
- containment-minded rather than leaderboard-minded
- operator-legible rather than magic
- historically aware rather than single-run obsessed
- selective rather than additive by reflex

## What Must Remain True

The new direction should not destroy the original strengths of the repo.

Keep:

- the baseline `run` command
- deterministic mock testing
- baseline reports and fingerprints
- assistant-review separation
- evaluator benchmarking
- local-only operator control
- dashboard convenience surfaces

## Role Of Assistant Models

Assistant models are optional secondary actors.

They are useful for:

- post-run commentary
- evaluator-role benchmarking
- telemetry collection about cleanup burden and evaluator suitability

They are not the authoritative scoring surface.

Deterministic harness outputs remain the primary truth.

## What Good Growth Looks Like

Healthy growth for this project looks like:

- stronger failure-family taxonomy
- better gauntlet quality
- clearer atlas summaries
- sharper operator decision support
- better draft-probe validation
- cleaner containment recommendations

Unhealthy growth looks like:

- endlessly adding one-off probes
- replacing truth with commentary
- overcomplicating the dashboard
- making the system depend on live-model access for core verification
- turning every interesting failure into permanent suite bloat

## Product Feel

If this project feels right, it should feel like:

- a lab instrument
- a containment console
- a suitability cartographer
- an entropy-folding evaluator

It should not feel like:

- benchmark theatre
- benchmark farming
- benchmark vanity

## Practical Translation

In practical terms, the direction means:

1. keep the baseline lane intact
2. use the gauntlet lane to create broad pressure
3. classify and store failure signal
4. aggregate history into the atlas
5. let the operator decide what matters
6. forge draft probes only from justified recurring signal
7. keep assistant-role analysis separate and useful

## Short Version

The project is no longer trying to win by adding more and more positive tests.

It is trying to get smarter about failure:

- discover it
- classify it
- remember it
- contain it
- formalize it only when justified

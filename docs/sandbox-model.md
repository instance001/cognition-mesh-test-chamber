# Sandbox Model

The baseline lane uses a mock sandbox.

It includes:

- a temporary copy of a fake repository for patch probes
- a generated manifest of in-scope files
- path checks that reject work outside the sandbox root
- path checks that reject files missing from the manifest unless the task explicitly allows new files
- rollback by fresh temporary copy per probe

It explicitly does not include:

- real shell access
- real browser access
- real user files
- external network access through the harness

The model does not need direct write access in the baseline lane. It can return a unified diff or structured patch plan, and the harness evaluates that proposal deterministically.

This is one of the reasons the original `run` lane remains valuable even as the gauntlet lane becomes the newer strategic direction:

- it is stable
- it is deterministic
- it is CI-friendly
- it preserves a clean containment story

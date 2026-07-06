# Sandbox Model

v0.1 uses a mock sandbox.

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

The model does not need direct write access in v0.1. It can return a unified diff or structured patch plan, and the harness evaluates that proposal deterministically.

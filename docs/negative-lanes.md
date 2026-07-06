# Negative Lanes

Negative lanes are reusable guardrail suggestions generated from observed failures.

The central idea is simple: failures become reusable walls.

If a probe shows that a model invents file paths, broadens patches, follows instructions embedded inside untrusted files, or fabricates citations, the harness should generate a concrete containment rule that a host can later enforce.

Examples:

- invented file path failures become manifest-scope patch guards
- prompt injection failures become instruction-hierarchy guards
- fabricated source failures become source-evidence or uncertainty requirements

Negative lanes differ from generic safety slogans because they are tied to observed evidence. They are plain-language and machine-hint friendly so they can later plug into ChattyFactory or Chatty-Cog style hosts without losing the original rationale.

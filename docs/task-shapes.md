# Task Shapes

Each probe includes a task-shape block describing the demands of that task.

Fields:

- `requires_precision`: how exact the output needs to be
- `requires_creativity`: how much novelty helps
- `requires_source_fidelity`: how tightly the model must stay with provided material
- `requires_tool_use`: whether tool actions are needed
- `failure_cost`: how costly a wrong answer would be
- `ambiguity_load`: how underspecified the task is
- `allowed_retries`: how many retries the operator can safely allow

Task shapes matter because a system that is suitable for low-cost summarisation may still be unsuitable for patching, factual claims, or ambiguous requests without more containment.

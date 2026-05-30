from agent_framework._workflows._function_executor import _validate_function_signature
from agent_framework import WorkflowContext

def step2(x: str, ctx: WorkflowContext[str]) -> str:
    return ""

print("Signature Validation Output:", _validate_function_signature(step2))

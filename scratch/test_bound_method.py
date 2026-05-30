import asyncio
import inspect
from agent_framework._workflows._function_executor import _validate_function_signature
from agent_framework import WorkflowContext

class TestOrch:
    def __init__(self):
        self.val = "instance_val"

    async def my_step(self, x: str, ctx: WorkflowContext[str, str]) -> None:
        print("Called my_step with:", x, "and self.val:", self.val)

orch = TestOrch()
print("Bound method my_step parameters:", inspect.signature(orch.my_step).parameters)
print("Signature Validation Output:", _validate_function_signature(orch.my_step))

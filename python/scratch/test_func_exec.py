import asyncio
from agent_framework import WorkflowBuilder, FunctionExecutor, WorkflowContext

async def step1(x: str, ctx: WorkflowContext[str, str]) -> None:
    print("step1 active with input:", x)
    await ctx.send_message("from_step1:" + x, target_id="step2")

async def step2(x: str, ctx: WorkflowContext[str, str]) -> None:
    print("step2 active with input:", x)
    await ctx.yield_output("final:" + x)

async def main():
    e1 = FunctionExecutor(step1, id="step1")
    e2 = FunctionExecutor(step2, id="step2")
    wb = WorkflowBuilder(start_executor=e1, output_from=[e2])
    wb.add_edge(e1, e2)
    wf = wb.build()
    res = await wf.run("hello")
    print("Workflow run result events:", [e.type for e in res])
    print("get_outputs():", res.get_outputs())

if __name__ == "__main__":
    asyncio.run(main())

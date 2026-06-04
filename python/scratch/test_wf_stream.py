import asyncio
from agent_framework import WorkflowBuilder, FunctionExecutor, WorkflowContext

async def step1(x: str, ctx: WorkflowContext[str, str]) -> None:
    print("step1 running")
    await ctx.send_message("from1:" + x, target_id="step2")

async def step2(x: str, ctx: WorkflowContext[str, str]) -> None:
    print("step2 running")
    await ctx.yield_output("final:" + x)

async def main():
    e1 = FunctionExecutor(step1, id="step1")
    e2 = FunctionExecutor(step2, id="step2")
    wb = WorkflowBuilder(start_executor=e1, output_from=[e2])
    wb.add_edge(e1, e2)
    wf = wb.build()
    
    # Run with stream=True
    stream = await wf.run("hello", stream=True)
    async for event in stream:
        print("Received Event:", type(event), "Event properties:", dir(event))
        print("Event type:", getattr(event, "type", None))
        print("Event executor_id:", getattr(event, "executor_id", None))
        print("Event data:", getattr(event, "data", None))
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())

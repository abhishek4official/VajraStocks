import asyncio
from agent_framework import WorkflowBuilder, FunctionExecutor, WorkflowContext

async def step1(x: str, ctx: WorkflowContext[str, str]) -> None:
    raise ValueError("DB connection failed")

async def main():
    e1 = FunctionExecutor(step1, id="step1")
    wb = WorkflowBuilder(start_executor=e1, output_from=[e1])
    wf = wb.build()
    
    try:
        stream = await wf.run("hello", stream=True)
        async for event in stream:
            print("Event type:", event.type)
            if event.type == "executor_failed":
                print("Error details:", getattr(event, "details", None))
                print("Error message:", getattr(event, "error", None))
    except Exception as e:
        print("Caught exception outside stream:", e)

if __name__ == "__main__":
    asyncio.run(main())

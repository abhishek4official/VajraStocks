import asyncio
import json
from agent_framework import WorkflowBuilder, FunctionExecutor, WorkflowContext, Agent, AgentExecutorResponse
from agent_framework_ollama import OllamaChatClient

# Mock step for database
async def db_step(msg: AgentExecutorResponse, ctx: WorkflowContext[str, str]) -> None:
    text_content = msg.agent_response.text
    print("db_step received from agent text:", text_content)
    # Parse agent output
    data = json.loads(text_content.strip().replace("```json", "").replace("```", ""))
    symbol = data.get("symbol", "RELIANCE")
    
    # Send formatted structured data as a prompt for the next agent
    prompt = f"Analyze quantitative results for {symbol} and write a Markdown report. Data: {json.dumps({'latest_price': 2420.0, 'rsi': 62.5})}"
    await ctx.send_message(prompt, target_id="report_agent")

async def main():
    client = OllamaChatClient(host="http://192.168.31.27:11434", model="gemma4:e4b")
    
    intent_agent = Agent(
        client=client,
        name="orchestrator",
        instructions="You are an orchestrator. Identify stock intent and symbol. Respond strictly in JSON: {\"intent\": \"analyze_stock\", \"symbol\": \"RELIANCE\"}"
    )
    
    db_executor = FunctionExecutor(db_step, id="database_service")
    
    report_agent = Agent(
        client=client,
        name="report_agent",
        instructions="You are an investment reporter. Generate a professional investment report in Markdown based on the quantitative results."
    )
    
    wb = WorkflowBuilder(start_executor=intent_agent, output_from=[report_agent])
    wb.add_edge(intent_agent, db_executor)
    wb.add_edge(db_executor, report_agent)
    wf = wb.build()
    
    print("Running hybrid workflow...")
    res = await wf.run("Analyze RELIANCE")
    print("Final hybrid workflow output:")
    outputs = res.get_outputs()
    print("Type of output:", type(outputs[0]) if outputs else "None")
    print("Output content:", outputs[0].agent_response.text if outputs else "None")

if __name__ == "__main__":
    asyncio.run(main())

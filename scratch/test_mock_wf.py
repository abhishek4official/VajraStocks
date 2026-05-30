import asyncio
import json
import datetime
from typing import Dict, Any
from unittest.mock import MagicMock, patch

from agent_framework import Agent, WorkflowBuilder, FunctionExecutor, WorkflowContext, AgentExecutorResponse
from agent_framework_ollama import OllamaChatClient

class MockResponseStream:
    def __init__(self, text):
        self.text = text
        self.index = 0
        
    def __aiter__(self):
        return self
        
    async def __anext__(self):
        if self.index > 0:
            raise StopAsyncIteration
        self.index += 1
        update = MagicMock()
        update.user_input_requests = []
        return update
        
    async def get_final_response(self):
        resp = MagicMock()
        resp.agent_response.text = self.text
        resp.text = self.text
        return resp

async def _step_database(msg: AgentExecutorResponse, ctx: WorkflowContext[Dict[str, Any], Dict[str, Any]]) -> None:
    await ctx.send_message({"symbol": "RELIANCE.NS", "prices": [], "ind_list": []}, target_id="market_regime_service")

async def _step_market_regime(msg: Dict[str, Any], ctx: WorkflowContext[Dict[str, Any], Dict[str, Any]]) -> None:
    await ctx.send_message(msg, target_id="trade_planner_service")

async def _step_trade_planner(msg: Dict[str, Any], ctx: WorkflowContext[Dict[str, Any], Dict[str, Any]]) -> None:
    await ctx.send_message(msg, target_id="backtester_service")

async def _step_backtester(msg: Dict[str, Any], ctx: WorkflowContext[str, str]) -> None:
    await ctx.send_message("prompt to report Context: results", target_id="report_agent")

async def main():
    client = OllamaChatClient(host="http://localhost:11434", model="gemma4:e4b")
    intent_agent = Agent(client=client, name="orchestrator")
    e2 = FunctionExecutor(_step_database, id="database_service")
    e3 = FunctionExecutor(_step_market_regime, id="market_regime_service")
    e4 = FunctionExecutor(_step_trade_planner, id="trade_planner_service")
    e5 = FunctionExecutor(_step_backtester, id="backtester_service")
    report_agent = Agent(client=client, name="report_agent")

    wb = WorkflowBuilder(start_executor=intent_agent, output_from=[report_agent])
    wb.add_edge(intent_agent, e2)
    wb.add_edge(e2, e3)
    wb.add_edge(e3, e4)
    wb.add_edge(e4, e5)
    wb.add_edge(e5, report_agent)
    wf = wb.build()

    mock_orch_res = MockResponseStream('{"intent": "analyze_stock", "symbol": "RELIANCE", "rationale": "Analyzing reliance setup"}')
    mock_report_res = MockResponseStream('{"markdown_report": "# RELIANCE.NS Investment Report", "executive_recommendation": "BUY", "overall_confidence": "HIGH"}')

    def mock_agent_run(*args, **kwargs):
        print("mock_agent_run called!")
        if args and isinstance(args[0], list) and len(args[0]) > 0:
            msg_obj = args[0][0]
            print("Message object text type:", type(msg_obj.text))
            print("Message object text:", msg_obj.text)
        return mock_orch_res

    with patch("agent_framework.Agent.run", side_effect=mock_agent_run):
        print("Running workflow...")
        stream = await wf.run("Analyze RELIANCE", stream=True)
        async for event in stream:
            pass

if __name__ == "__main__":
    asyncio.run(main())

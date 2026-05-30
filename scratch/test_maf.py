import asyncio
from agent_framework import Agent
from agent_framework_ollama import OllamaChatClient

async def main():
    print("Testing MAF run...")
    client = OllamaChatClient(host="http://192.168.31.27:11434", model="gemma4:e4b")
    
    agent = Agent(
        client=client,
        name="test_agent",
        instructions="You are a helpful coding assistant."
    )
    
    response = await agent.run("Hello! Please count to 3.")
    print("Response type:", type(response))
    print("Response content:", getattr(response, "content", "N/A"))
    print("Response message:", getattr(response, "message", "N/A"))

if __name__ == "__main__":
    asyncio.run(main())

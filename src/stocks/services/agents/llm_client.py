import httpx
from agent_framework import Agent
from agent_framework_ollama import OllamaChatClient
from loguru import logger
from ollama import AsyncClient


class LLMClient:
    """Decoupled client to connect with local LLM engines using Microsoft Agent Framework."""

    def __init__(self, provider: str = "ollama", base_url: str = "http://localhost:11434"):
        self.provider = provider
        self.base_url = base_url
        # Build connection pool once — reused across all generate_response calls.
        # Timeout is 20 minutes (1200s) to accommodate slow local Ollama inference.
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=60.0)
        transport = httpx.AsyncHTTPTransport(retries=3, limits=limits)
        self._ollama_client = AsyncClient(host=base_url, timeout=1200.0, transport=transport)

    async def generate_response(
        self, model: str, prompt: str, system_instruction: str, temperature: float = 0.2, agent_name: str = "general"
    ) -> str:
        """Sends generation request using Microsoft Agent Framework ChatClient and Agent."""
        try:
            client = OllamaChatClient(host=self.base_url, model=model, client=self._ollama_client)
            agent = Agent(client=client, name=agent_name, instructions=system_instruction)

            # Execute completion using MAF run
            response = await agent.run(prompt)
            return response.text
        except Exception as e:
            logger.error(f"MAF Ollama request failed for agent {agent_name}: {e}")
            raise RuntimeError(f"Microsoft Agent Framework execution failed: {e}")

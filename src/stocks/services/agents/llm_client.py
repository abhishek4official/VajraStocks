import httpx
import json
from loguru import logger
from typing import Dict, Any, Optional

from agent_framework import Agent
from agent_framework_ollama import OllamaChatClient

class LLMClient:
    """Decoupled client to connect with local LLM engines using Microsoft Agent Framework."""

    def __init__(self, provider: str = "ollama", base_url: str = "http://localhost:11434"):
        self.provider = provider
        self.base_url = base_url

    async def generate_response(
        self, 
        model: str, 
        prompt: str, 
        system_instruction: str, 
        temperature: float = 0.2,
        agent_name: str = "general"
    ) -> str:
        """Sends generation request using Microsoft Agent Framework ChatClient and Agent."""
        try:
            import httpx
            from ollama import AsyncClient
            # Keep Ollama timeout to 20 minutes (1200 seconds) by passing configured AsyncClient with robust retries and keepalive
            limits = httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=60.0)
            transport = httpx.AsyncHTTPTransport(retries=3, limits=limits)
            ollama_client = AsyncClient(host=self.base_url, timeout=1200.0, transport=transport)
            client = OllamaChatClient(host=self.base_url, model=model, client=ollama_client)
            agent = Agent(
                client=client,
                name=agent_name,
                instructions=system_instruction
            )
            
            # Execute completion using MAF run
            response = await agent.run(prompt)
            return response.text
        except Exception as e:
            logger.error(f"MAF Ollama request failed for agent {agent_name}: {e}")
            raise RuntimeError(f"Microsoft Agent Framework execution failed: {e}")

"""LLM client supporting Ollama (via MAF) and OpenAI-compatible providers (Groq, DeepSeek, OpenAI, etc.)."""

import json

import httpx
from agent_framework import Agent
from agent_framework_ollama import OllamaChatClient
from loguru import logger
from ollama import AsyncClient

# Providers that speak the OpenAI /v1/chat/completions protocol
_OPENAI_COMPAT = {"openai", "groq", "deepseek", "openrouter", "lm_studio", "custom"}

# Default base URLs per provider (user can override in settings)
PROVIDER_DEFAULT_URLS: dict[str, str] = {
    "ollama":     "http://localhost:11434",
    "openai":     "https://api.openai.com/v1",
    "groq":       "https://api.groq.com/openai/v1",
    "deepseek":   "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "lm_studio":  "http://localhost:1234/v1",
}


class LLMClient:
    """Unified LLM client. Supports Ollama (MAF) and any OpenAI-compatible endpoint."""

    def __init__(self, provider: str = "ollama", base_url: str = "http://localhost:11434", api_key: str = ""):
        self.provider = provider.lower().strip()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        if self.provider == "ollama":
            limits = httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=60.0)
            transport = httpx.AsyncHTTPTransport(retries=3, limits=limits)
            self._ollama_client = AsyncClient(host=base_url, timeout=1200.0, transport=transport)
        else:
            self._ollama_client = None

        # Shared async httpx client for OpenAI-compatible providers
        self._http_client: httpx.AsyncClient | None = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=120.0)
        return self._http_client

    async def generate_response(
        self, model: str, prompt: str, system_instruction: str, temperature: float = 0.2, agent_name: str = "general"
    ) -> str:
        """Generate a completion. Routes to Ollama or OpenAI-compatible endpoint."""
        if self.provider == "ollama":
            return await self._generate_ollama(model, prompt, system_instruction, temperature, agent_name)
        if self.provider in _OPENAI_COMPAT:
            return await self._generate_openai_compat(model, prompt, system_instruction, temperature)
        # Fallback to Ollama-compat for unknown providers
        return await self._generate_ollama(model, prompt, system_instruction, temperature, agent_name)

    async def _generate_ollama(
        self, model: str, prompt: str, system_instruction: str, temperature: float, agent_name: str
    ) -> str:
        try:
            client = OllamaChatClient(host=self.base_url, model=model, client=self._ollama_client)
            agent = Agent(client=client, name=agent_name, instructions=system_instruction)
            response = await agent.run(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Ollama request failed for agent {agent_name}: {e}")
            raise RuntimeError(f"Ollama execution failed: {e}")

    async def _generate_openai_compat(
        self, model: str, prompt: str, system_instruction: str, temperature: float
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
        }

        try:
            client = self._get_http_client()
            resp = await client.post(url, headers=headers, content=json.dumps(payload))
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500]
            logger.error(f"OpenAI-compat request failed [{self.provider}] HTTP {e.response.status_code}: {body}")
            raise RuntimeError(f"{self.provider} API error {e.response.status_code}: {body}")
        except Exception as e:
            logger.error(f"OpenAI-compat request failed [{self.provider}]: {e}")
            raise RuntimeError(f"{self.provider} execution failed: {e}")

"""Cliente LLM híbrido: DeepSeek primario + Haiku fallback."""
import json
from dataclasses import dataclass
from typing import Optional

import httpx

from config.settings import get_settings

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


@dataclass
class LLMResponse:
    content: str
    model_used: str
    fallback: bool = False


class LLMClient:
    """Cliente que intenta DeepSeek primero y cae a Haiku si falla."""

    def __init__(self):
        self.settings = get_settings()

    async def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Enviar prompt al LLM. DeepSeek primario, Haiku fallback."""
        # Intentar DeepSeek primero si tiene API key
        if self.settings.llm.deepseek_api_key:
            result = await self._call_deepseek(system_prompt, user_prompt)
            if result:
                return result
            print("[LLM] DeepSeek falló, usando Haiku como fallback")

        # Fallback a Haiku
        if self.settings.llm.anthropic_api_key:
            result = await self._call_haiku(system_prompt, user_prompt)
            if result:
                return result

        raise RuntimeError("No hay LLM disponible. Configura DEEPSEEK_API_KEY o ANTHROPIC_API_KEY")

    async def _call_deepseek(self, system_prompt: str, user_prompt: str) -> Optional[LLMResponse]:
        """Llamar a DeepSeek API (OpenAI-compatible)."""
        headers = {
            "Authorization": f"Bearer {self.settings.llm.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.llm.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 3000,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(DEEPSEEK_URL, headers=headers, json=payload)

                if response.status_code == 429:
                    print("[LLM] DeepSeek rate limit (429)")
                    return None

                if response.status_code != 200:
                    print(f"[LLM] DeepSeek error {response.status_code}: {response.text[:200]}")
                    return None

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return LLMResponse(
                    content=content,
                    model_used=self.settings.llm.deepseek_model,
                    fallback=False,
                )
        except Exception as e:
            print(f"[LLM] DeepSeek exception: {e}")
            return None

    async def _call_haiku(self, system_prompt: str, user_prompt: str) -> Optional[LLMResponse]:
        """Llamar a Anthropic Haiku API."""
        headers = {
            "x-api-key": self.settings.llm.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.llm.haiku_model,
            "max_tokens": 3000,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(ANTHROPIC_URL, headers=headers, json=payload)

                if response.status_code != 200:
                    print(f"[LLM] Haiku error {response.status_code}: {response.text[:200]}")
                    return None

                data = response.json()
                content = data["content"][0]["text"]
                return LLMResponse(
                    content=content,
                    model_used=self.settings.llm.haiku_model,
                    fallback=True,
                )
        except Exception as e:
            print(f"[LLM] Haiku exception: {e}")
            return None

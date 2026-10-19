"""
llm_provider.py
Downstream LLM Provider Adapter for SHIELD-LLM Security Gateway.

Provides a unified interface for forwarding verified SAFE prompts to:
1. Local Ollama (default: gemma3:1b on http://127.0.0.1:11434)
2. (Optional) OpenAI API if explicitly configured via LLM_PROVIDER=openai

Enforces:
- Local privacy & zero cloud cost via local GPU-accelerated Ollama.
- Server-side routing: only SAFE verdicts are ever forwarded.
- Clean error reporting if Ollama is offline or unreachable.
- Configurable response length and timeouts.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("shield_llm.provider")

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "gemma3:1b"
DEFAULT_TIMEOUT = 25.0
DEFAULT_MAX_TOKENS = 256


class OllamaProvider:
    """
    Adapter for local Ollama instance running gemma3:1b or other local models.
    Communicates via native HTTP to http://127.0.0.1:11434/api/chat.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
        mock_handler = None,  # For unit testing / mocking
    ):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        
        try:
            self.timeout = float(timeout or os.environ.get("OLLAMA_TIMEOUT") or DEFAULT_TIMEOUT)
        except ValueError:
            self.timeout = DEFAULT_TIMEOUT

        try:
            self.max_tokens = int(max_tokens or os.environ.get("OLLAMA_MAX_TOKENS") or DEFAULT_MAX_TOKENS)
        except ValueError:
            self.max_tokens = DEFAULT_MAX_TOKENS

        self._mock_handler = mock_handler

    @property
    def provider_name(self) -> str:
        return "Ollama (Local)"

    def is_available(self) -> Tuple[bool, Optional[str]]:
        """
        Checks if the local Ollama daemon is running and responding.
        """
        if self._mock_handler is not None:
            return True, None

        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SHIELD-LLM-Gateway"})
            with urllib.request.urlopen(req, timeout=3.0) as res:
                if res.status == 200:
                    data = json.loads(res.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", [])]
                    # Model match check (e.g. gemma3:1b or gemma3:1b:latest)
                    has_model = any(
                        self.model == m or m.startswith(self.model) or self.model in m
                        for m in models
                    )
                    if has_model:
                        return True, None
                    return False, f"Ollama is running, but model '{self.model}' is not pulled. Available: {models}"
                return False, f"Ollama returned HTTP status {res.status}"
        except urllib.error.URLError as e:
            return False, f"Ollama connection error: {e}. Ensure 'ollama serve' is running at {self.base_url}."
        except Exception as e:
            return False, f"Ollama check failed: {str(e)}"

    def generate_response(self, prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Calls Ollama chat API with the prompt.
        Returns:
            Tuple (llm_response, llm_error)
        """
        # If mock handler is injected (used in testing)
        if self._mock_handler is not None:
            return self._mock_handler(prompt)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful, concise AI assistant operating behind the SHIELD-LLM security gateway."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": 0.7,
            }
        }

        url = f"{self.base_url}/api/chat"
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "SHIELD-LLM-Gateway",
            }
        )

        try:
            logger.info(f"Forwarding SAFE prompt to Ollama ({self.model} at {url})...")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    res_body = json.loads(resp.read().decode("utf-8"))
                    message = res_body.get("message", {})
                    content = message.get("content")
                    if content:
                        logger.info("Successfully received response from Ollama.")
                        return content.strip(), None
                    return None, "Ollama returned an empty response content."
                else:
                    return None, f"Ollama API returned HTTP status {resp.status}"

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            logger.error(f"Ollama HTTP error {e.code}: {error_body}")
            return None, f"Ollama HTTP Error {e.code}: {error_body or e.reason}"

        except urllib.error.URLError as e:
            logger.error(f"Ollama connection error: {e}")
            if "timed out" in str(e).lower() or isinstance(e.reason, TimeoutError):
                return None, f"Ollama Timeout Error: Request timed out after {self.timeout}s."
            return None, f"Ollama Connection Error: Could not connect to {self.base_url}. Ensure Ollama is running."

        except TimeoutError:
            return None, f"Ollama Timeout Error: Request timed out after {self.timeout}s."

        except Exception as e:
            logger.error(f"Unexpected Ollama provider error: {e}")
            return None, f"Ollama Gateway Error: {str(e)}"


def get_provider(mock_handler = None):
    """
    Factory creating the configured LLM provider.
    Defaults to local Ollama.
    """
    provider_type = os.environ.get("LLM_PROVIDER", "ollama").lower().strip()
    if provider_type == "openai":
        from llm_gateway import LLMGateway
        return LLMGateway()
    return OllamaProvider(mock_handler=mock_handler)

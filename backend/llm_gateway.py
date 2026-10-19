"""
llm_gateway.py - Provider Adapter for Downstream LLM Integration
SHIELD-LLM Security Gateway

This module is responsible for forwarding verified SAFE prompts to the actual LLM provider.
It guarantees:
- No requests are sent unless explicitly instructed by the Security Arbiter (verdict == 'safe').
- Clear separation between the security firewall and downstream generative models.
- Graceful error handling for missing credentials, timeouts, and API exceptions.
- Zero mock/fake responses when real credentials are not supplied.
"""

import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger("shield_llm.gateway")

# Default model configuration
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 15.0

class LLMGateway:
    """
    Adapter for connecting to OpenAI and OpenAI-compatible API providers.
    Supports dependency injection of custom clients for unit/integration testing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        client = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        
        try:
            self.timeout = float(timeout or os.environ.get("OPENAI_TIMEOUT") or DEFAULT_TIMEOUT)
        except ValueError:
            self.timeout = DEFAULT_TIMEOUT

        self._client = client

    def is_configured(self) -> bool:
        """
        Returns True if a non-placeholder API key is configured.
        """
        if self._client is not None:
            return True
        if not self.api_key:
            return False
        cleaned = self.api_key.strip()
        if not cleaned or cleaned == "your_openai_api_key_here" or cleaned.startswith("sk-placeholder"):
            return False
        return True

    def _get_client(self):
        """
        Lazily instantiates the OpenAI client using the official maintained SDK.
        """
        if self._client is not None:
            return self._client

        if not self.is_configured():
            return None

        from openai import OpenAI
        client_kwargs = {
            "api_key": self.api_key,
            "timeout": self.timeout,
        }
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self._client = OpenAI(**client_kwargs)
        return self._client

    def generate_response(self, prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Sends the verified SAFE prompt to the configured LLM provider.
        Returns:
            Tuple (llm_response, llm_error)
            - On success: (generated_text, None)
            - On failure: (None, error_description)
        """
        if not self.is_configured():
            logger.info("LLM generation skipped: OPENAI_API_KEY not configured.")
            return (
                None,
                "LLM provider not configured. Please set OPENAI_API_KEY in the backend environment to enable live text generation."
            )

        client = self._get_client()
        if client is None:
            return (None, "Failed to initialize LLM provider client.")

        # Import specific exceptions from openai SDK
        import openai

        try:
            logger.info(f"Forwarding SAFE prompt to LLM (model: {self.model}, timeout: {self.timeout}s)...")
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful and direct AI assistant operating behind the SHIELD-LLM security gateway."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.7,
            )

            if response.choices and len(response.choices) > 0:
                answer = response.choices[0].message.content
                if answer:
                    answer = answer.strip()
                logger.info("Successfully received generated response from LLM provider.")
                return (answer, None)
            else:
                return (None, "LLM provider returned an empty response choices list.")

        except openai.AuthenticationError as e:
            logger.error(f"OpenAI Authentication Error: {e}")
            return (None, "OpenAI Authentication Error: Invalid or expired API key provided.")

        except openai.RateLimitError as e:
            logger.error(f"OpenAI Rate Limit Error: {e}")
            return (None, "OpenAI Rate Limit Error: Account quota exceeded or rate limit reached.")

        except openai.APITimeoutError as e:
            logger.error(f"OpenAI Timeout Error: {e}")
            return (None, f"OpenAI Timeout Error: The provider did not respond within {self.timeout} seconds.")

        except openai.APIConnectionError as e:
            logger.error(f"OpenAI Connection Error: {e}")
            return (None, "OpenAI Connection Error: Failed to connect to OpenAI API endpoints. Check network connection.")

        except openai.APIError as e:
            logger.error(f"OpenAI API Error: {e}")
            return (None, f"OpenAI API Error: {getattr(e, 'message', str(e))}")

        except Exception as e:
            logger.error(f"Unexpected LLM Gateway error: {e}")
            return (None, f"LLM Gateway Error: {str(e)}")

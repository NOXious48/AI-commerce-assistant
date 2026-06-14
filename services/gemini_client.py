import os
import json
import re
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Any
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from schemas import ConversationAgentOutput
from chat_agent import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GeminiCircuitBreaker:
    """Prevents cascading failures when Gemini API is down."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 30):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.consecutive_failures = 0
        self.last_failure_time = None

    def record_failure(self):
        self.consecutive_failures += 1
        self.last_failure_time = datetime.now()

    def record_success(self):
        self.consecutive_failures = 0
        self.last_failure_time = None

    def is_open(self) -> bool:
        if self.consecutive_failures >= self.failure_threshold:
            if datetime.now() - self.last_failure_time < timedelta(seconds=self.cooldown_seconds):
                return True
            else:
                # Cooldown expired, half-open — allow a test request
                return False
        return False


# ---------------------------------------------------------------------------
# Singletons (initialized via init_gemini_client)
# ---------------------------------------------------------------------------
_circuit_breaker = GeminiCircuitBreaker(failure_threshold=3, cooldown_seconds=30)
_agent: Optional[LlmAgent] = None
_runner: Optional[Runner] = None
_session_service: Optional[InMemorySessionService] = None


def init_gemini_client():
    """Initialize the Gemini client singletons at startup."""
    global _agent, _runner, _session_service
    if _agent is not None:
        return

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    _agent = LlmAgent(
        name="shopping_consultant",
        model=model_name,
        instruction=SYSTEM_PROMPT,
        output_key="agent_output",
    )

    _session_service = InMemorySessionService()
    _runner = Runner(
        agent=_agent,
        app_name="shopping-consultant",
        session_service=_session_service,
    )
    logger.info("Initialized Gemini Agent Singleton (model=%s)", model_name)


async def generate_structured_output(
    user_message: str,
    user_id: str,
    session_id: str,
    context_lines: list = None,
) -> ConversationAgentOutput:
    """Call Gemini via ADK and return a validated ConversationAgentOutput."""

    if _agent is None:
        init_gemini_client()

    if _circuit_breaker.is_open():
        logger.warning("GeminiCircuitBreaker OPEN. Returning fallback for %s", session_id)
        return ConversationAgentOutput.fallback()

    max_retries = 3
    base_delay = 1

    # Build the user-facing prompt.  Context lines are prepended so we never
    # mutate the singleton agent.instruction.
    final_prompt = user_message
    if context_lines:
        context_str = "\n".join(context_lines)
        final_prompt = (
            "### SYSTEM CONTEXT UPDATE ###\n"
            + context_str
            + "\n\n### USER MESSAGE ###\n"
            + user_message
        )

    for attempt in range(max_retries):
        try:
            # Ensure session exists in InMemorySessionService
            try:
                session = await _session_service.get_session(
                    app_name="shopping-consultant",
                    user_id=user_id,
                    session_id=session_id,
                )
                if session is None:
                    await _session_service.create_session(
                        app_name="shopping-consultant",
                        user_id=user_id,
                        session_id=session_id,
                    )
            except Exception:
                await _session_service.create_session(
                    app_name="shopping-consultant",
                    user_id=user_id,
                    session_id=session_id,
                )

            user_content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=final_prompt)],
            )

            final_text = ""
            final_event = None
            async for event in _runner.run_async(
                new_message=user_content,
                user_id=user_id,
                session_id=session_id,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_text = event.content.parts[0].text
                    final_event = event

            if not final_text:
                raise ValueError("Gemini returned an empty response")

            # Parse — _parse_response never raises; returns fallback on failure
            output = _parse_response(final_text, final_event)
            _circuit_breaker.record_success()
            return output

        except Exception as e:
            # Only retries for API / network / empty-response failures.
            # JSON parse failures are handled inside _parse_response (no retry).
            import traceback
            _circuit_breaker.record_failure()
            logger.error("Gemini API failure (attempt %d/%d): %s", attempt + 1, max_retries, e)
            logger.error(traceback.format_exc())
            if attempt == max_retries - 1:
                logger.error("Max Gemini retries reached. Returning fallback response.")
                return ConversationAgentOutput.fallback()

            await asyncio.sleep(base_delay * (2 ** attempt))

    return ConversationAgentOutput.fallback()


# ---------------------------------------------------------------------------
# Multi-layer JSON parser — never raises, returns fallback on total failure
# ---------------------------------------------------------------------------

def _parse_response(text: str, event: Any) -> ConversationAgentOutput:
    """5-layer robust JSON extraction and Pydantic validation."""

    # Layer 1: Native ADK structured output
    if event is not None and hasattr(event, "parsed") and event.parsed:
        try:
            return ConversationAgentOutput.model_validate(event.parsed)
        except Exception as exc:
            logger.warning("Layer 1 (ADK parsed) failed: %s", exc)

    cleaned = text.strip()

    # Layer 2: Direct json.loads
    try:
        raw = json.loads(cleaned)
        return ConversationAgentOutput.model_validate(raw)
    except Exception:
        pass

    # Layer 3: Regex — first '{' to last '}'
    obj_match = re.search(r'(\{.*\})', cleaned, re.DOTALL)
    if obj_match:
        try:
            extracted = _fix_escapes(obj_match.group(1))
            raw = json.loads(extracted)
            return ConversationAgentOutput.model_validate(raw)
        except Exception as exc:
            logger.warning("Layer 3 (regex obj) failed: %s", exc)

    # Layer 4: Markdown ```json ... ```
    md_match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned, re.DOTALL)
    if md_match:
        try:
            extracted = _fix_escapes(md_match.group(1))
            raw = json.loads(extracted)
            return ConversationAgentOutput.model_validate(raw)
        except Exception as exc:
            logger.warning("Layer 4 (markdown) failed: %s", exc)

    # Layer 5: Fallback
    logger.error("All parsing layers failed for text: %s", repr(text[:500]))
    return ConversationAgentOutput.fallback()


def _fix_escapes(text: str) -> str:
    """Fix invalid JSON escape sequences emitted by some Gemini models.

    E.g. the model writes \\Once instead of \\\\Once.  We turn any \\X where X
    is not a valid JSON escape character into \\\\X.
    """
    return re.sub(r'\\(?=[^"\\/bfnrtu])', r'\\\\', text)

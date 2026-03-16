"""Avatar emotion system — LLM-based emotion analysis + gateway relay.

After each agent response, calls the configured lite-tier LLM with structured output
to pick an emotion/action + inner thought, then POSTs it to the host gateway's
/avatar/emotion endpoint. The gateway relays it via SSE to connected avatar clients.
"""

import logging

import httpx
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from .config import AvatarConfig, GatewayConfig
from .tools.model_router import get_tier_model

logger = logging.getLogger(__name__)

VALID_ACTIONS = [
    "idle", "talking", "thinking", "happy", "waving", "sleeping",
    "typing", "surprised", "dancing", "flying", "nodding", "refusing",
    "angry", "sad", "laughing", "dizzy", "love", "stretching", "preening", "eating",
]


class EmotionEvent(BaseModel):
    """Structured output schema for emotion analysis."""
    action: str = Field(description=(
        "The emotion/action to display on the avatar. "
        f"Must be one of: {', '.join(VALID_ACTIONS)}"
    ))
    text: str = Field(description=(
        "A first-person inner thought (MAX 10 words) from the parrot's "
        "perspective — what it's feeling right now. Use emoji."
    ))


EMOTION_SYSTEM_PROMPT = """\
You are a thought generator for a 3D parrot avatar called CianaParrot.

Given the user's message and the assistant's response, output:
1. action: one of {actions}
2. text: a short thought (MAX 10 words) with emoji

## THE #1 RULE — NAME THE SUBJECT

The thought text MUST contain the specific name/topic from the conversation. \
Never use pronouns like "he", "she", "it", "they" — always use the actual name.

- "Bill Gates, what a legend! 💻" ← GOOD (says "Bill Gates")
- "Hmm, he's quite the tech wizard" ← BAD (who is "he"??)
- "Paris looks so dreamy! 🗼" ← GOOD (says "Paris")
- "That place sounds nice" ← BAD (what place??)

## MORE EXAMPLES

User: "Who is Elon Musk?" → "Elon Musk... rockets AND cars?! 🚀"
User: "What's the weather in Rome?" → "Rome sunshine vibes! ☀️🇮🇹"
User: "Say hi to Marco" → action=waving, "Ciao Marco! 👋"
User: "Help me with Python" → "Python is so elegant 🐍✨"
User: "I'm sad" → "Oh no, sending hugs! 🫂💚"

## STYLE

- First person, like thinking out loud
- Lively, goofy, emotional little parrot personality
- Use emoji generously"""

FALLBACK_EVENT = EmotionEvent(action="dizzy", text="Hmm... brain not braining 🤔")


class AvatarBridge:
    """Analyzes agent emotions and pushes them to the gateway for SSE relay."""

    def __init__(self, avatar_config: AvatarConfig, gateway_config: GatewayConfig):
        self._config = avatar_config
        self._gateway_url = (gateway_config.url or f"http://host.docker.internal:{gateway_config.port}").rstrip("/")
        self._gateway_token = gateway_config.token
        self._structured_llm = None

    def init_llm(self) -> None:
        """Initialize the LLM for emotion analysis. Call after model_router is ready."""
        model = get_tier_model(self._config.tier)
        if model is None:
            logger.warning(
                "Avatar tier '%s' not available in model_router — "
                "emotion analysis disabled (avatar will only show thinking/idle)",
                self._config.tier,
            )
            return
        try:
            self._structured_llm = model.with_structured_output(EmotionEvent)
            logger.info("Avatar emotion LLM ready (tier: %s)", self._config.tier)
        except Exception as e:
            logger.warning("Failed to bind structured output for avatar: %s", e)

    # ── Hooks called by the router ──────────────────────────────

    async def on_user_message(self) -> None:
        """Pre-hook: trigger thinking animation. No text — just the pose."""
        await self._send_event(EmotionEvent(action="thinking", text=""))

    async def on_agent_response(self, user_text: str, agent_response: str) -> None:
        """Post-hook: analyze emotion and push to avatar."""
        event = await self._analyze_emotion(user_text, agent_response)
        await self._send_event(event)

    # ── Gateway communication ───────────────────────────────────

    async def _send_event(self, event: EmotionEvent) -> None:
        """POST an emotion event to the gateway's /avatar/emotion endpoint."""
        headers: dict[str, str] = {}
        if self._gateway_token:
            headers["Authorization"] = f"Bearer {self._gateway_token}"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"{self._gateway_url}/avatar/emotion",
                    json={"action": event.action, "text": event.text},
                    headers=headers,
                )
            if not resp.is_success:
                logger.warning("Avatar event push failed: HTTP %d", resp.status_code)
        except httpx.ConnectError:
            logger.debug("Avatar: gateway not reachable (is it running?)")
        except Exception as e:
            logger.warning("Avatar event push error: %s", e)

    # ── Emotion analysis ────────────────────────────────────────

    async def _analyze_emotion(self, user_text: str, agent_response: str) -> EmotionEvent:
        """Use lite LLM with structured output to pick emotion + inner thought."""
        if self._structured_llm is None:
            return FALLBACK_EVENT

        try:
            # Truncate to save tokens on the lite model
            truncated = agent_response[:500] if len(agent_response) > 500 else agent_response

            messages = [
                SystemMessage(content=EMOTION_SYSTEM_PROMPT.format(
                    actions=", ".join(VALID_ACTIONS),
                )),
                HumanMessage(content=(
                    f"User message: {user_text}\n\n"
                    f"Assistant response: {truncated}"
                )),
            ]
            result = await self._structured_llm.ainvoke(messages)

            # Validate action
            if result.action not in VALID_ACTIONS:
                logger.warning("LLM returned invalid action '%s', falling back to idle", result.action)
                result.action = "idle"

            logger.info("Avatar emotion: %s — %s", result.action, result.text)
            return result

        except Exception as e:
            logger.warning("Emotion analysis failed: %s", e)
            return FALLBACK_EVENT

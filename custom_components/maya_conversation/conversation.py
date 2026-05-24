"""Conversation platform for Maya via Jarvis."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
from typing import Literal
from uuid import uuid4

from aiohttp import ClientError

from homeassistant.components import conversation
from homeassistant.components.conversation import AssistantContent, ChatLog
from homeassistant.components.homeassistant.exposed_entities import (
    async_get_assistant_settings,
    async_should_expose,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
    label_registry as lr,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_AGENT,
    CONF_TIMEOUT,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_AGENT,
    DEFAULT_TIMEOUT,
    NAME,
    STT_PROVIDER,
)

_LOGGER = logging.getLogger(__name__)

_FALLBACK_SPEECH = "Maya ted neodpovida."


def _resolve_backend_url(url: str | None) -> str:
    """Resolve and normalize the backend URL."""
    cleaned = (url or "").strip().rstrip("/")
    if not cleaned:
        raise ValueError("Missing Jarvis Brain URL")
    return cleaned


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Maya via Jarvis conversation entities."""
    async_add_entities([MayaConversationEntity(hass, entry)])


class MayaConversationEntity(conversation.ConversationEntity):
    """Represent a Maya-backed Home Assistant conversation agent."""

    _attr_name = NAME
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Maya via Jarvis conversation entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return languages supported by this agent."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """Register this entity as a selectable conversation agent."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self._entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity as a selectable conversation agent."""
        conversation.async_unset_agent(self.hass, self._entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: ChatLog,
    ) -> conversation.ConversationResult:
        """Forward the Assist transcript to Jarvis Brain and return speech."""
        data = self._entry.data
        agent = data.get(CONF_AGENT, DEFAULT_AGENT).strip("/")
        token = data[CONF_TOKEN]
        timeout = int(data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))
        conversation_id = user_input.conversation_id or f"ha-{uuid4()}"

        payload = {
            "text": user_input.text,
            "language": user_input.language,
            "conversationId": conversation_id,
            "sttProvider": STT_PROVIDER,
        }

        device_id = getattr(user_input, "device_id", None) or getattr(
            user_input, "satellite_id", None
        )
        if device_id:
            payload["deviceId"] = device_id

        try:
            snapshot = await self._async_build_exposed_entities_snapshot()
        except Exception:  # pragma: no cover - best-effort enrichment
            _LOGGER.exception("Failed to build Assist exposed entities snapshot")
        else:
            payload["exposedEntitiesSnapshot"] = snapshot

        session = async_get_clientsession(self.hass)

        try:
            url = _resolve_backend_url(data.get(CONF_URL))
            async with asyncio.timeout(timeout):
                response = await session.post(
                    f"{url}/api/voice/{agent}/conversation",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status >= 400:
                    text = await response.text()
                    _LOGGER.warning(
                        "Maya via Jarvis failed with HTTP %s: %s",
                        response.status,
                        text[:500],
                    )
                    return self._result_with_speech(
                        user_input,
                        chat_log,
                        speech=_FALLBACK_SPEECH,
                        conversation_id=conversation_id,
                        continue_conversation=False,
                    )

                jarvis_data = await response.json(content_type=None)
        except (asyncio.TimeoutError, TimeoutError):
            _LOGGER.warning("Maya via Jarvis timed out after %s seconds", timeout)
            return self._result_with_speech(
                user_input,
                chat_log,
                speech=_FALLBACK_SPEECH,
                conversation_id=conversation_id,
                continue_conversation=False,
            )
        except (ClientError, ValueError, TypeError) as err:
            _LOGGER.warning("Maya via Jarvis request failed: %s", err)
            return self._result_with_speech(
                user_input,
                chat_log,
                speech=_FALLBACK_SPEECH,
                conversation_id=conversation_id,
                continue_conversation=False,
            )

        speech = (
            jarvis_data.get("response", {})
            .get("speech", {})
            .get("plain", {})
            .get("speech")
        )
        if not speech:
            _LOGGER.warning("Maya via Jarvis response did not include speech")
            return self._result_with_speech(
                user_input,
                chat_log,
                speech=_FALLBACK_SPEECH,
                conversation_id=conversation_id,
                continue_conversation=False,
            )

        response_language = (
            jarvis_data.get("response", {}).get("language") or user_input.language
        )
        returned_conversation_id = (
            jarvis_data.get("conversation_id") or conversation_id
        )

        return self._result_with_speech(
            user_input,
            chat_log,
            speech=speech,
            conversation_id=returned_conversation_id,
            continue_conversation=bool(
                jarvis_data.get("continue_conversation", False)
            ),
            language=response_language,
        )

    async def _async_build_exposed_entities_snapshot(self) -> dict[str, object]:
        """Capture the latest Assist-exposed entities for Jarvis Brain."""
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        area_registry = ar.async_get(self.hass)
        label_registry = lr.async_get(self.hass)
        assistant_settings = async_get_assistant_settings(self.hass, conversation.DOMAIN)
        candidate_entity_ids = set(entity_registry.entities)
        candidate_entity_ids.update(assistant_settings)
        candidate_entity_ids.update(state.entity_id for state in self.hass.states.async_all())
        entities: list[dict[str, object]] = []

        for entity_id in candidate_entity_ids:
            if not async_should_expose(self.hass, conversation.DOMAIN, entity_id):
                continue

            state = self.hass.states.get(entity_id)
            registry_entry = entity_registry.async_get(entity_id)
            area_name = None
            labels: list[str] = []
            if registry_entry is not None:
                area_id = registry_entry.area_id
                if area_id is None and registry_entry.device_id:
                    device_entry = device_registry.async_get(registry_entry.device_id)
                    area_id = device_entry.area_id if device_entry is not None else None

                if area_id:
                    area_entry = area_registry.async_get_area(area_id)
                    area_name = _clean_text(area_entry.name if area_entry is not None else None)

                labels = _resolve_label_names(label_registry, registry_entry.labels)

            entities.append(
                {
                    "entityId": entity_id,
                    "name": _resolve_entity_name(state, registry_entry),
                    "state": _clean_text(state.state if state is not None else None),
                    "area": area_name,
                    "labels": labels,
                }
            )

        entities.sort(
            key=lambda item: (
                str(item["area"] or "").casefold(),
                str(item["name"] or "").casefold(),
                str(item["entityId"]).casefold(),
            )
        )

        return {
            "assistant": conversation.DOMAIN,
            "capturedAtUtc": datetime.now(UTC).isoformat(),
            "entityCount": len(entities),
            "entities": entities,
        }

    def _result_with_speech(
        self,
        user_input: conversation.ConversationInput,
        chat_log: ChatLog,
        *,
        speech: str,
        conversation_id: str,
        continue_conversation: bool,
        language: str | None = None,
    ) -> conversation.ConversationResult:
        """Build a Home Assistant conversation result with spoken text."""
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(
                agent_id=user_input.agent_id,
                content=speech,
            )
        )

        response = intent.IntentResponse(language=language or user_input.language)
        response.async_set_speech(speech)

        return conversation.ConversationResult(
            conversation_id=conversation_id,
            response=response,
            continue_conversation=continue_conversation,
        )


def _resolve_entity_name(state, registry_entry) -> str | None:
    """Resolve a readable name for an exposed entity."""
    if registry_entry is not None:
        if cleaned := _clean_text(registry_entry.name):
            return cleaned
        if cleaned := _clean_text(registry_entry.original_name):
            return cleaned

    if state is None:
        return None

    return _clean_text(getattr(state, "name", None)) or _clean_text(
        state.attributes.get("friendly_name")
    )


def _resolve_label_names(label_registry, label_ids) -> list[str]:
    """Resolve label ids to distinct human-readable names."""
    names: set[str] = set()
    for label_id in label_ids:
        label_entry = label_registry.async_get_label(label_id)
        if cleaned := _clean_text(label_entry.name if label_entry is not None else None):
            names.add(cleaned)

    return sorted(names, key=str.casefold)


def _clean_text(value: object | None) -> str | None:
    """Normalize optional text values sent to Jarvis Brain."""
    if value is None:
        return None

    cleaned = str(value).strip()
    return cleaned or None

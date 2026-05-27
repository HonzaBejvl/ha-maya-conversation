"""Shared exposed-entities snapshot builder for Maya Conversation."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.homeassistant.exposed_entities import (
    async_get_assistant_settings,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)

DEFAULT_ASSISTANT = "conversation"


async def async_build_exposed_entities_snapshot(
    hass: HomeAssistant,
    assistant: str = DEFAULT_ASSISTANT,
) -> dict[str, object]:
    """Capture the explicit Assist-exposed entities for Jarvis Brain."""
    normalized_assistant = _clean_text(assistant) or DEFAULT_ASSISTANT
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    area_registry = ar.async_get(hass)
    label_registry = lr.async_get(hass)
    assistant_settings = async_get_assistant_settings(hass, normalized_assistant)
    candidate_entity_ids = {
        entity_id
        for entity_id, settings in assistant_settings.items()
        if settings.get("should_expose") is True
    }
    entities: list[dict[str, object]] = []

    for entity_id in candidate_entity_ids:
        state = hass.states.get(entity_id)
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
                area_name = _clean_text(
                    area_entry.name if area_entry is not None else None
                )

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
        "assistant": normalized_assistant,
        "capturedAtUtc": datetime.now(UTC).isoformat(),
        "entityCount": len(entities),
        "entities": entities,
    }


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

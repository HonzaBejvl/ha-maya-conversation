"""HTTP views for Maya Conversation."""

from __future__ import annotations

import logging

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .snapshot import DEFAULT_ASSISTANT, async_build_exposed_entities_snapshot

_LOGGER = logging.getLogger(__name__)


class MayaExposedEntitiesSnapshotView(HomeAssistantView):
    """Authenticated endpoint exposing Maya's prebuilt Assist snapshot."""

    requires_auth = True
    url = "/api/maya_conversation/exposed_entities_snapshot"
    name = "api:maya_conversation:exposed_entities_snapshot"

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Return the latest explicit Assist-exposed entities snapshot."""
        assistant = (request.query.get("assistant") or DEFAULT_ASSISTANT).strip()
        if assistant != DEFAULT_ASSISTANT:
            return web.json_response(
                {
                    "error": (
                        "Only assistant=conversation is supported by "
                        "maya_conversation exposed snapshot endpoint."
                    )
                },
                status=400,
            )

        try:
            snapshot = await async_build_exposed_entities_snapshot(
                self._hass, assistant=assistant
            )
        except Exception:  # pragma: no cover - best-effort runtime safety
            _LOGGER.exception("Failed to build Maya exposed entities snapshot view")
            return web.json_response(
                {"error": "Failed to build exposed entities snapshot."}, status=500
            )

        return web.json_response(snapshot)

"""Maya Conversation integration."""

from __future__ import annotations

from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .views import MayaExposedEntitiesSnapshotView

PLATFORMS: list[Platform] = [Platform.CONVERSATION]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _ensure_snapshot_view_registered(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("snapshot_view_registered"):
        return

    hass.http.register_view(MayaExposedEntitiesSnapshotView(hass))
    domain_data["snapshot_view_registered"] = True


async def async_setup(
    hass: HomeAssistant, config: Mapping[str, object]
) -> bool:
    """Set up Maya Conversation integration."""
    _ensure_snapshot_view_registered(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Maya Conversation from a config entry."""
    _ensure_snapshot_view_registered(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Maya Conversation config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

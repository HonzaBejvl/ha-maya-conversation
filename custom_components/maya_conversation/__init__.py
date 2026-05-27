"""Maya Conversation integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .views import MayaExposedEntitiesSnapshotView

PLATFORMS: list[Platform] = [Platform.CONVERSATION]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Maya Conversation from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("snapshot_view_registered"):
        hass.http.register_view(MayaExposedEntitiesSnapshotView(hass))
        domain_data["snapshot_view_registered"] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Maya Conversation config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

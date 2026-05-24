"""Config flow for the Maya Conversation integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AGENT,
    CONF_TIMEOUT,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_AGENT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    NAME,
    STT_PROVIDER,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(Exception):
    """Error to indicate the Jarvis backend could not be reached."""


class InvalidAuth(Exception):
    """Error to indicate the provided voice token was rejected."""


def _resolve_url(url: str | None) -> str:
    """Resolve and normalize the Jarvis Brain base URL."""
    cleaned = (url or "").strip().rstrip("/")
    if not cleaned:
        raise CannotConnect
    return cleaned


def _clean_agent(agent: str) -> str:
    """Normalize the Jarvis voice agent slug."""
    return agent.strip().strip("/").lower()


def _normalize_input(user_input: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Normalize config flow input and return the resolved backend URL."""
    resolved_url = _resolve_url(user_input.get(CONF_URL))
    normalized = {
        CONF_URL: resolved_url,
        CONF_AGENT: _clean_agent(user_input[CONF_AGENT]),
        CONF_TOKEN: user_input[CONF_TOKEN].strip(),
        CONF_TIMEOUT: int(user_input[CONF_TIMEOUT]),
    }
    return normalized, resolved_url


def _user_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Return the config flow form schema."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_URL,
                default=user_input.get(CONF_URL, ""),
            ): str,
            vol.Required(
                CONF_TOKEN,
                default=user_input.get(CONF_TOKEN, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD,
                )
            ),
            vol.Required(
                CONF_AGENT,
                default=user_input.get(CONF_AGENT, DEFAULT_AGENT),
            ): str,
            vol.Required(
                CONF_TIMEOUT,
                default=user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
        }
    )


async def _validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    """Validate the Jarvis endpoint and token with a read-only voice request."""
    url = _resolve_url(user_input.get(CONF_URL))
    agent = _clean_agent(user_input[CONF_AGENT])
    token = user_input[CONF_TOKEN].strip()
    timeout = int(user_input[CONF_TIMEOUT])

    if not token:
        raise InvalidAuth

    session = async_get_clientsession(hass)
    payload = {
        "text": "ping",
        "language": hass.config.language or "cs",
        "conversationId": "ha-config-flow-test",
        "deviceId": "config-flow",
        "sttProvider": STT_PROVIDER,
    }

    try:
        async with asyncio.timeout(timeout):
            response = await session.post(
                f"{url}/api/voice/{agent}/conversation",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status in (401, 403):
                raise InvalidAuth

            if response.status >= 400:
                text = await response.text()
                _LOGGER.warning(
                    "Maya Conversation validation failed with HTTP %s: %s",
                    response.status,
                    text[:300],
                )
                raise CannotConnect

            data = await response.json(content_type=None)
    except InvalidAuth:
        raise
    except (asyncio.TimeoutError, TimeoutError) as err:
        raise CannotConnect from err
    except Exception as err:
        raise CannotConnect from err

    speech = (
        data.get("response", {})
        .get("speech", {})
        .get("plain", {})
        .get("speech")
    )
    if not speech:
        raise CannotConnect


class MayaConversationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Maya Conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input, resolved_url = _normalize_input(user_input)

            await self.async_set_unique_id(
                f"{resolved_url}|{user_input[CONF_AGENT]}"
            )
            self._abort_if_unique_id_configured()

            try:
                await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during Maya Conversation setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=NAME,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
        )

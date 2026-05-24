# Maya via Jarvis for Home Assistant

`maya_conversation` is a Home Assistant custom integration that registers a
conversation agent for Assist and forwards each turn to a Jarvis Brain voice
endpoint. The Home Assistant voice pipeline stays local to HA, while Maya runs
behind that backend.

## Scope

This repository is primarily a personal adapter between my Home Assistant
Assist setup and my own agent layer.

That means:

- it is not a hosted service
- it is not a generic turnkey assistant product
- it expects a compatible Jarvis Brain-style backend on your side
- it is published mainly so the integration can be versioned cleanly and, if
  desired later, distributed through HACS

The repository layout is HACS-ready:

- `custom_components/maya_conversation`
- `hacs.json`
- standard `README.md`

## What It Does

- Adds a selectable Assist conversation agent named `Maya via Jarvis`
- Sends each Assist turn to `POST /api/voice/{agent}/conversation` on Jarvis Brain
- Returns Jarvis speech back to Home Assistant
- Passes through `conversationId`, `language`, `deviceId`, and
  `sttProvider=home-assistant`
- Captures the current Assist-exposed entities snapshot and sends it with each
  voice turn so Jarvis Brain can upsert the linked home's latest view

## Current Backend Contract

The Home Assistant side is branded as Maya, but the backend remains Jarvis:

- Backend URL: required in the integration setup flow
- Default voice agent slug: `maya`
- Auth: bearer token from Jarvis Brain voice-token issuance

## Privacy And Secrets

This repository does not contain:

- Home Assistant access tokens
- Jarvis voice tokens
- user conversation history
- exposed-entities snapshots from any real home

Those values live only in:

- your Home Assistant config entry storage
- your Jarvis Brain deployment
- runtime HTTP requests between Home Assistant and your backend

If you run this integration yourself, you are expected to provide and secure
your own backend URL and voice token.

## HACS Install

If this repository is public, add it to HACS as a custom integration
repository:

1. Open HACS.
2. Add a custom repository.
3. Repository: `https://github.com/HonzaBejvl/ha-maya-conversation`
4. Category: `Integration`
5. Install `Maya via Jarvis` and restart Home Assistant.

After restart, add the integration from `Settings -> Devices & Services`.

## Manual Install

1. Copy `custom_components/maya_conversation` into your Home Assistant config:

   ```text
   /config/custom_components/maya_conversation
   ```

2. Restart Home Assistant.
3. Go to `Settings -> Devices & Services -> Add Integration`.
4. Search for `Maya via Jarvis`.
5. Enter:
   - Jarvis Brain URL
   - Jarvis Voice Token
   - Agent slug, usually `maya`
   - Timeout in seconds
6. In Assist, select the `Maya via Jarvis` conversation agent.

## Jarvis Prerequisites

The voice token used by this integration identifies a Jarvis user/profile. That
means the selected Maya user context controls what Maya can do.

Before issuing a voice token, make sure the Maya user profile in Jarvis Brain
is linked to the correct Home Assistant home:

- `HomeAssistantHome`
- its `BaseUrl`
- its `AccessToken`

Jarvis Brain stores the HA connection on the shared home record, not directly on
the Maya profile. That linked home is also where the integration's exposed
entities snapshots are upserted on each voice turn.

## Issuing a Voice Token

Jarvis Brain exposes a per-user voice token endpoint:

```text
POST /api/users/{userId}/voice-token
```

Example request body:

```json
{
  "agent": "maya"
}
```

The response includes:

- `token`
- `expiresAtUtc`
- `userId`
- `agent`
- `endpoint`, expected to be `/api/voice/maya/conversation`

Use the returned `token` as the integration's `Jarvis Voice Token`.

## HACS Readiness

This repo is structured for HACS custom-repository use:

- one integration under `custom_components/`
- `hacs.json`
- GitHub validation workflows
- local brand assets for Home Assistant

If you use this integration, treat it as a personal adapter to your own Jarvis
agent layer rather than a general-purpose hosted assistant.

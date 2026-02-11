# Intelliclima Home Assistant integration

This repository contains a custom Home Assistant integration for Intelliclima devices.

> ⚠️ The Intelliclima cloud API is not officially documented and appears to vary between app/API versions.

## What is implemented

- Config flow with username/password authentication
- Configurable API base URL
- Endpoint fallback strategy for auth/devices/states/control requests
- Climate entities per Intelliclima device
- Basic environmental sensors (humidity and outdoor temperature when available)

## Installation

1. Copy `custom_components/intelliclima` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for **Intelliclima** and add your credentials.

## Notes

- In this execution environment, direct access to GitHub was still blocked (`CONNECT tunnel failed, response 403`), so I could not live-clone `ruizmarc/homebridge-intelliclima` from here.
- To improve compatibility despite this, the API client now supports multiple endpoint variants and multiple payload shapes for token/devices/states parsing.
- If you can share a redacted sample response from your Intelliclima account (login + devices + status), I can align the integration exactly to your installation.

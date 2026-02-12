# Intelliclima Home Assistant integration

This repository contains a custom Home Assistant integration for Intelliclima devices.

## Implemented API flow

The integration uses the Intelliclima API request model based on observed endpoints and payloads:

1. `user/login/{username}/{sha256(password)}` with a device-info JSON body
2. `casa/elenco2/{userId}` to obtain houses and device IDs (with `Tokenid`/`Token` headers)
3. `sync/cronos380` with `IDs`, `ECOs`, `includi_eco`, `includi_ledot` to fetch device details
4. `sync/cronos400` for ECOCOMFORT data (`ECOs` populated from `ecoIDs`)
5. `C800/scrivi/` for write operations (`serial`, `w_Tset_Tman`, `mode`) for `C800WiFi`

The integration also parses `model` and `config` if they are JSON-encoded strings.

## Features

- Config flow with username/password
- Configurable API base URL and API folder path
- Climate entities for C800WiFi devices
- ECOCOMFORT fan entities (state/speed from `cronos400`)
- ECOCOMFORT sensors (temperature `tamb`, humidity `rh`, VOC `voc_state`)
- C800WiFi write support for setpoint/mode

## Run in local development environment

### 1) Clone and install dependencies

```bash
git clone <YOUR_REPOSITORY_URL>
cd Intelliclima-hass-integration
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> You can also use the helper script:
>
> ```bash
> ./scripts/setup
> ```

### 2) Start Home Assistant with this custom component

```bash
source .venv/bin/activate
./scripts/develop
```

This script:
- creates `config/` if missing,
- exposes this repository `custom_components` through `PYTHONPATH`,
- starts Home Assistant in debug mode.

### 3) Open Home Assistant UI

Once Home Assistant is running, open:
- `http://localhost:8123`

Finish onboarding/login, then add the integration.

## Add the component to Home Assistant

You can add this custom component either from this repo directly (dev mode) or into an existing Home Assistant instance.

### Option A: Use this repository as your HA runtime (recommended for local testing)

1. Start HA with `./scripts/develop`.
2. In Home Assistant UI go to **Settings → Devices & Services**.
3. Click **Add Integration**.
4. Search for **Intelliclima**.
5. Enter:
   - **Username**
   - **Password**
   - **API Base URL** (default usually works)
   - **API Folder Path** (default `/server_v1_mono/api/`, change only if your account uses a different API family/path)

### Option B: Install into an existing Home Assistant instance

1. Copy folder `custom_components/intelliclima` into your HA config folder:
   - `<HA_CONFIG>/custom_components/intelliclima`
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for **Intelliclima** and configure credentials.

## Manual API testing (without Home Assistant)

You can test the Intelliclima API directly with:

```bash
python scripts/intelliclima_api_tester.py --username <USER> --password <PASS> login
python scripts/intelliclima_api_tester.py --username <USER> --password <PASS> devices
python scripts/intelliclima_api_tester.py --username <USER> --password <PASS> device --device-id <ID>
python scripts/intelliclima_api_tester.py --username <USER> --password <PASS> set --device-id <ID> --temperature 21.5 --mode heat
```

Optional flags:
- `--base-url` (default: `https://intelliclima.fantinicosmi.it`)
- `--api-folder` (default: `/server_v1_mono/api/`)
- `devices --raw` to print complete payloads

Known API folders:
- `/server_v1_mono/api/`
- `/server_v1_multi/api/`



## ECOCOMFORT fan behavior (mode + speed mapping)

The ECO devices expose **two independent dimensions** in API payloads:

- **Speed** (`speed_set`, `speed_state`)
- **Ventilation mode** (`mode_set`, `mode_state`)

### Speed mapping used by this integration

Observed native states:

| API value | Meaning |
|---|---|
| `0` | Off |
| `1` | Sleep |
| `2` | Vel1 |
| `3` | Vel2 |
| `4` | Vel3 |

Some schedule/auto payloads may report translated values `16..19`; these are normalized to native levels `1..4` for Home Assistant state rendering.

In Home Assistant:
- `is_on` is `true` when normalized speed is `> 0`
- `percentage` is computed from normalized level over max level `4`

### Ventilation mode mapping used by this integration

| API value (`mode_set`/`mode_state`) | Preset |
|---|---|
| `1` | `outdoor_intake` |
| `2` | `indoor_exhaust` |
| `3` | `alternating_45s` |
| `4` | `alternating_sensor` |
| `132` | `alternating_sensor` |

`132` is treated as a runtime state variant of sensor-driven alternating mode.

### Reverse-engineered ECO `trama` body pattern

From captured `eco/send/` requests, the body payload follows this frame layout:

```text
trama = 0A 0000 SSSS 000E2F0050 0000 MM SS CC 0D
```

Where:
- `SSSS` = 4-digit device serial (example: `0675`, `0674`)
- `MM` = mode byte (`01` outdoor intake, `02` indoor exhaust, `03` alternating 45s, `04` alternating sensor, `00` off)
- `SS` = speed byte (`01` sleep, `02` vel1, `03` vel2, `04` vel3, `10` auto, `00` off)
- `CC` = checksum byte (varies with full frame content)

You can analyze your own captured curl JSON with:

```bash
python scripts/eco_trama_pattern.py path/to/captured_curls.json
```

### Exposed diagnostic attributes

For ECO fan entities, the integration exposes additional state attributes:

- raw: `mode_set`, `mode_state`, `speed_set`, `speed_state`
- normalized: `speed_level`, `ventilation_mode`

These attributes are useful when creating automations and when comparing HA state with vendor app behavior.

### ECO control from Home Assistant UI

ECO fan entities now support write operations directly from the frontend:

- set **ventilation mode** via `preset_mode`
- set **fan speed** via percentage (mapped to native levels `0..4`)
- turn on/off with standard fan controls

Under the hood the integration builds and sends `eco/send/` payloads with this frame format:

```json
{"trama":"0A0000SSSS000E2F00500000MMSSCC0D"}
```

Where `SSSS` is serial, `MM` is mode byte, `SS` is speed byte, and `CC` is CRC-8 checksum.

Write responses are validated against the vendor echo payload (example: `{"status":"OK","serial":"00000674","trama":"0A00000674000E2F005000000410B20D"}`), so mismatched `serial`/`trama` now raise an integration error instead of silently succeeding.

## Troubleshooting

- If login fails with a DNS resolver error similar to `Channel.getaddrinfo() takes 3 positional arguments...`, update to the latest version of this integration.
  The Intelliclima integration now forces a threaded DNS resolver for its own HTTP session to avoid that aiodns incompatibility.
- If you still see the same traceback under **other integrations** (for example `homeassistant_alerts`), that is a Home Assistant environment resolver issue, not specific to Intelliclima.
  In local dev environments, reinstalling/upgrading resolver deps usually fixes it:

  ```bash
  pip install --upgrade aiodns pycares aiohttp-asyncmdnsresolver
  ```

  If it persists, remove `aiodns` so aiohttp falls back to threaded DNS:

  ```bash
  pip uninstall -y aiodns
  ```


## Enable Intelliclima debug logs

In your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.intelliclima: debug
```

Then restart Home Assistant.


### Deep API debug (cURL + raw response)

When `custom_components.intelliclima: debug` is enabled, the integration now logs:
- a cURL-equivalent command for each API request
- raw HTTP response status and body
- parsed raw payloads for login, house list, and device fetch

> ⚠️ These logs can contain sensitive values (token, serial, device/account data). Use only for troubleshooting and disable debug logs afterwards.

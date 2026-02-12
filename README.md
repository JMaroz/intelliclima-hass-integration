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

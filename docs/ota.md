# OTA (signed over-the-air updates)

Narthex applies **signed** release tarballs from a channel manifest. Portunus (or ops CLI) triggers check/apply via the device API.

## Trust model

- Ed25519 signatures over canonical payload: `{version}\n{sha256}\n{url}`
- Device holds **public** key only (`data/ota/ota_public.key` or `NARTHEX_OTA_PUBLIC_KEY`)
- Private key stays on the release builder (never on the Pi)
- `ota.require_signature: true` by default (protected config key)

## Manifest

```json
{
  "channel": "stable",
  "versions": [
    {
      "version": "0.2.1",
      "url": "https://example/narthex-0.2.1.tar.gz",
      "sha256": "…",
      "signature": "…"
    }
  ]
}
```

List newest first. `check` returns the first entry whose version ≠ current.

## Device layout

```
$data_dir/ota/
  ota_public.key
  current -> versions/<ver>   # symlink
  versions/<ver>/…            # extracted tree (must pass healthgate)
```

Healthgate accepts `VERSION` file matching version, or `pyproject.toml` / `src/narthex` markers.

## CLI (builder + device)

```bash
# Builder
narthex ota keygen --out-dir ./ota-keys
narthex ota pack --source ./release-tree --version 0.2.1 \
  --private-key ./ota-keys/ota_private.key --out-dir ./ota-dist \
  --url https://releases.example/narthex-0.2.1.tar.gz

# Device
cp ota-keys/ota_public.key $DATA/ota/
# config: ota.check_url: https://…/manifest-stable.json
narthex ota check -c /etc/narthex/config.yaml
narthex ota apply 0.2.1 -c /etc/narthex/config.yaml
narthex ota rollback -c /etc/narthex/config.yaml
```

## Device API

- `POST /device/v1/ota/check`
- `POST /device/v1/ota/apply` `{"version":"0.2.1"}`
- `GET  /device/v1/ota/status`
- `POST /device/v1/ota/rollback`

## Install convention (Pi)

Point systemd `WorkingDirectory` / venv at `$(readlink -f $DATA/ota/current)` after first bootstrap install. Apply switches the symlink; restart service to load new code (`restart` flag reserved for later supervisor hook).

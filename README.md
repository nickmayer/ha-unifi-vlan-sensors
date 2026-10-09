# UniFi Network for Home Assistant — with per-VLAN sensors

This is Home Assistant's built-in **UniFi Network** integration with one addition: **sensors for the number of connected clients and the traffic on each VLAN**, without creating a device entity for every client.

It is a *drop-in replacement* for the built-in integration: same domain (`unifi`), same config entry, same entities. Everything else behaves exactly like upstream. The change is small and meant to be proposed upstream as a pull request.

> **Built for Home Assistant 2026.10.x.** Because this replaces the built-in integration, it must match your Home Assistant version. When you update Home Assistant, update this too (see [Versions](#versions)). HACS cannot enforce an upper version bound.

## What you get

Set the new option **VLANs to create sensors for** (UniFi options → *More options*), for example `11, 12, 13, 30`. For each VLAN you get a device **VLAN 11** with:

| Entity | Meaning |
| --- | --- |
| `sensor.vlan_11_clients` | Clients currently connected on VLAN 11 |
| `sensor.vlan_11_traffic` | Their combined current traffic in Mbit/s (received + sent) |

Use `native` for clients without a VLAN tag (device `Native VLAN`, `sensor.native_vlan_clients`).

- The list is empty by default: **no new entities unless you ask for them.**
- "Connected" uses the same rule as the integration's other sensors: the client was seen within the detection time.
- Wired clients are measured on the wired counters, wireless on the wireless counters, as the existing bandwidth sensors do.
- Adding or removing a VLAN in the options creates or removes its sensors immediately.

## Install

1. HACS → ⋮ → **Custom repositories** → `https://github.com/nickmayer/ha-unifi-vlan-sensors`, type **Integration**.
2. Download **UniFi Network (with VLAN sensors)** and **restart Home Assistant**.
3. **Settings → Devices & services → UniFi Network → Configure → More options** and fill in *VLANs to create sensors for*.

Home Assistant will log that it found a custom integration `unifi`; that is expected. To go back to the built-in integration, remove this from HACS and restart.

## Versions

| Thing | Format | Example |
| --- | --- | --- |
| Release / HACS version | `<HA version>-vlan.<n>` | `2026.10.0-vlan.1` |
| Upstream snapshot (branch `upstream`) | tag `upstream/<HA version>` | `upstream/2026.10.0` |

The repository has two long-lived branches:

- **`upstream`** — an untouched copy of `homeassistant/components/unifi` from each Home Assistant release (plus the two files a custom integration needs: a `version` in the manifest and the generated `translations/en.json`). Never edited by hand. Each release is a commit tagged `upstream/<version>`.
- **`main`** — `upstream` plus our changes. `git diff upstream/2026.10.0 main -- custom_components/unifi` is exactly the patch.

### Syncing a new Home Assistant release

```bash
python scripts/sync_upstream.py --core ../ha-core --ref 2026.11.0   # imports it onto `upstream`
git merge upstream                                                   # 3-way merge; conflicts only where we touched the same code
bash scripts/run_core_tests.sh                                       # runs core's UniFi tests (WSL/Linux)
git tag -a 2026.11.0-vlan.1 -m "2026.11.0-vlan.1"
git push origin main upstream --tags                                 # the tag triggers the release workflow
```

`--core` is any checkout of `home-assistant/core`; the script fetches the tag itself and never touches its working tree.

### Proposing it upstream

`git diff upstream/<version> main -- custom_components/unifi` is the change relative to Home Assistant. Replace the path prefix `custom_components/unifi` with `homeassistant/components/unifi` to apply it to a core checkout; `tests/test_vlan_sensor.py` and `tests/core-patches/` hold the tests.

## Development

Home Assistant core only supports Linux/macOS. On Windows use WSL.

```bash
# one-time: a core checkout, a Python 3.14 venv with core's requirements and test
# requirements, and `python -m script.translations develop --all` run once in the checkout.
bash scripts/run_core_tests.sh      # copies this integration and tests/ into the checkout and runs the UniFi suite
```

The script keeps core's own manifest and regenerates translations, so the checkout always tests exactly what is in `custom_components/unifi/`.

## License

Home Assistant is licensed under the [Apache License 2.0](https://github.com/home-assistant/core/blob/dev/LICENSE.md); this repository contains a modified copy of one of its integrations and keeps that license. See `LICENSE`.

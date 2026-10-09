# UniFi Network for Home Assistant — with per-VLAN sensors

This is Home Assistant's built-in **UniFi Network** integration with one addition: **sensors for the number of connected clients and the traffic on each VLAN**, without creating a device entity for every client.

It is a *drop-in replacement* for the built-in integration: same domain (`unifi`), same config entry, same entities. Everything else behaves exactly like upstream. The change is small and meant to be proposed upstream as a pull request.

> **Built for Home Assistant 2026.10.x.** Because this replaces the built-in integration, it must match your Home Assistant version. When you update Home Assistant, update this too (see [Versions](#versions)). HACS cannot enforce an upper version bound.

## What you get

Select the new option **VLANs to create sensors for** (UniFi → *Configure* → *More options*). The list suggests the VLANs your connected clients are on, and you can also type a VLAN ID that has no clients yet (for example `11`, `12`, `13`, `30`). For each VLAN you get a device **VLAN 11** with:

| Entity | Meaning |
| --- | --- |
| `sensor.vlan_11_clients` | Clients currently connected on VLAN 11 |
| `sensor.vlan_11_traffic` | Their combined current traffic in Mbit/s (received + sent) |

Select `native` for clients without a VLAN tag (device `Native VLAN`, `sensor.native_vlan_clients`).

- The list is empty by default: **no new entities unless you ask for them.**
- "Connected" uses the same rule as the integration's other sensors: the client was seen within the detection time.
- Wired clients are measured on the wired counters, wireless on the wireless counters, as the existing bandwidth sensors do.
- Adding or removing a VLAN in the options creates or removes its sensors immediately.

## Install

1. HACS → ⋮ → **Custom repositories** → `https://github.com/nickmayer/ha-unifi-vlan-sensors`, type **Integration**.
2. Download **UniFi Network (with VLAN sensors)** and **restart Home Assistant**.
3. **Settings → Devices & services → UniFi Network → Configure → More options** and fill in *VLANs to create sensors for*.

Home Assistant will log that it found a custom integration `unifi`; that is expected. To go back to the built-in integration, remove this from HACS and restart.

### Upgrading from `2026.10.0-vlan.1`

Release 1 saved the VLAN list as comma separated text. Release 2 still reads that format, so nothing breaks; open the options once and save to convert it to the new list.

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

The change is also prepared as a branch for Home Assistant core (`unifi-vlan-sensors`, based on `dev`). This repository carries it for the version you run:

- `git diff upstream/<version> main -- custom_components/unifi` is the integration change. The only difference from the core branch is `_vlan_sensors_option` in `hub/config.py` (reads the text option of release 1), which is kept in its own commit and is not part of the proposal.
- `tests/core-patches/unifi-vlan-sensors.patch` is the test change (new tests in `test_sensor.py` and `test_config_flow.py`, plus the snapshot); `tests/test_legacy_vlan_option.py` tests the shim.
- `docs/home-assistant.io-unifi.patch` is the documentation change for the `home-assistant.io` repository.

Home Assistant's [AI policy](https://developers.home-assistant.io/docs/ai_policy) requires that a person understands and submits the pull request and writes the description and replies themselves; autonomous contributions are not accepted.

## Development

Home Assistant core only supports Linux/macOS. On Windows use WSL.

| Script | Purpose |
| --- | --- |
| `scripts/run_core_tests.sh` | Copies this integration into a core checkout at the matching release and runs core's UniFi suite plus our tests |
| `scripts/setup_core_dev.sh` | Prepares a checkout of core `dev` and the tools used by `pr_checks.sh` |
| `scripts/pr_checks.sh` | The checks a core PR needs: tests with coverage of the new lines, ruff, mypy, pylint, hassfest, codespell |
| `scripts/gen_translations.py` | Regenerates `translations/en.json` after editing `strings.json` |
| `scripts/sync_upstream.py` | Imports a new Home Assistant release onto the `upstream` branch |

`run_core_tests.sh` keeps core's own manifest and regenerates translations, so it always tests exactly what is in `custom_components/unifi/`.

## License

Home Assistant is licensed under the [Apache License 2.0](https://github.com/home-assistant/core/blob/dev/LICENSE.md); this repository contains a modified copy of one of its integrations and keeps that license. See `LICENSE`.

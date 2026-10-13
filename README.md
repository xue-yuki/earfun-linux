# EarFun Panel

Control your **EarFun Air Pro 4i** from Linux, with a GNOME top-bar extension, an animated connection popup, and a command-line interface.

EarFun Panel reads device settings and sends control commands directly over Bluetooth. A local Python service handles communication with the earbuds, while the extension displays battery levels and controls in GNOME Shell.

**Current version:** 0.3.0 · **Extension target:** GNOME Shell 50 · **Device:** Air Pro 4i / TW230

## Features

- Battery levels for the left earbud, right earbud, and charging case.
- Normal, Ambient, and ANC modes.
- ANC strength: Strong, Balanced, Wind, and Adaptive.
- Game mode, spatial audio, and multipoint controls.
- Flat, Bass, and Vocal EQ presets, plus custom 10-band EQ through the CLI.
- An animated connection popup with live battery data.
- Saved device configuration, so repeated commands do not need a Bluetooth address.
- A user-level background service with connection events, periodic refresh, and automatic restart.

The extension keeps a headphone icon in the top bar. Its percentage is the lowest known earbud battery level; the menu shows all three battery readings separately.

> The popup is triggered by a Bluetooth connection, not by opening the charging-case lid. Physical lid detection is not implemented.

## Compatibility

| Component | Requirement |
| --- | --- |
| Earbuds | EarFun Air Pro 4i, hardware model TW230 |
| Operating system | Linux with BlueZ and RFCOMM support |
| Desktop extension | GNOME Shell 50; the installer checks this version |
| Python | 3.10 or later; the service uses `/usr/bin/python3` |
| Service bindings | PyGObject with Gio and GLib |
| Service manager | systemd user services and a session D-Bus |
| Device discovery | `bluetoothctl`; `sdptool` for discovering the SPP channel |

Development and hardware testing have used CachyOS, GNOME Shell 50.5, and firmware `TW230_20251017_v1.0.5`. Other EarFun models and firmware versions are not currently confirmed compatible.

The CLI can run independently of GNOME. The desktop installer currently targets GNOME Shell 50 only.

## Installation

### 1. Get the project

Clone this repository or download and extract its source archive. Open a terminal in the project root—the directory containing `install.py` and `earfunctl.py`.

### 2. Install dependencies

On **CachyOS / Arch Linux**:

```bash
sudo pacman -S --needed python python-gobject bluez bluez-utils bluez-deprecated-tools
```

`python-gobject` provides the Python bindings. `bluez-utils` provides `bluetoothctl`, and `bluez-deprecated-tools` provides `sdptool`.

Check your environment:

```bash
gnome-shell --version
/usr/bin/python3 -c 'from gi.repository import Gio, GLib; print("Gio and GLib are available")'
python3 earfunctl.py doctor
```

`doctor` checks platform support and tool availability. It does not test your Bluetooth adapter or communicate with the earbuds.

If the system Bluetooth service is not running:

```bash
sudo systemctl enable --now bluetooth.service
```

No APK, Android device, pip installation, or Python virtual environment is required to use the project.

### 3. Pair and connect your earbuds

Use GNOME's Bluetooth settings to pair and connect the Air Pro 4i. Keep the earbuds awake during setup.

List known Bluetooth devices:

```bash
python3 earfunctl.py devices
```

Identify your earbuds by name and confirm the address with `bluetoothctl info`. A renamed device is supported.

**The commands below use `AA:BB:CC:DD:EE:FF` as an example address. Replace it with your own earbuds' address.**

```bash
bluetoothctl info AA:BB:CC:DD:EE:FF
python3 earfunctl.py --mac AA:BB:CC:DD:EE:FF discover
```

Discovery looks for the Serial Port Profile service:

```text
00001101-0000-1000-8000-00805f9b34fb
```

Use the channel returned by discovery. The examples below use channel `1`; replace it if your device reports a different channel. Do not assume a channel before checking.

Before installation, try a read-only status query:

```bash
python3 earfunctl.py --mac AA:BB:CC:DD:EE:FF --channel 1 status --full
```

### 4. Install the extension and service

Run the installer as your normal user, **without `sudo`**:

```bash
python3 install.py --mac AA:BB:CC:DD:EE:FF --channel 1
```

The installer saves the device configuration, installs the extension, and enables the user service. It also attempts to enable the extension.

**Log out and log back in** so GNOME discovers the extension and loads its current code. Then run:

```bash
gnome-extensions enable earfun@ell.local
```

### 5. Verify the installation

```bash
systemctl --user status earfun.service --no-pager
gnome-extensions info earfun@ell.local
```

Click the headphone icon in the top bar. The menu contains battery levels, device controls, EQ presets, **Refresh status**, and **Tes popup** (test popup).

While the earbuds are connected, use **Tes popup** to preview the animation with your device's current battery readings.

## Using the desktop extension

### Panel controls

Choose a sound mode or ANC level from its submenu. Game mode, spatial audio, and multipoint use switches. Feature changes are read back from the device to check whether the requested value was applied.

The service refreshes status when it observes a BlueZ connection change, every 30 seconds, and when the menu requests a refresh. A `—` reading means the value is unavailable; it does not mean the battery is empty.

### Connection popup

The popup appears once after a connection is observed and the first status read completes. It can also appear when the extension starts with already-connected earbuds.

Its animation uses a case-lid reveal followed by the two earbuds rising slightly in sequence. Battery levels then appear. The popup:

- Closes automatically after approximately five seconds.
- Can be dismissed with the close button, or Escape while it receives keyboard events.
- Provides a **Kontrol** button to open the panel menu.
- Respects GNOME's animation setting.
- Does not take keyboard focus or appear on the lock screen.

The artwork is a stylized 2D welcome animation, not a physical simulation of the case hinge. It does not represent a detected lid-open event.

## CLI usage

The installer saves your default device. From the project root, commands can then omit `--mac` and `--channel`.

To avoid simultaneous RFCOMM access, stop the background service before a CLI testing session and start it again afterward:

```bash
systemctl --user stop earfun.service
python3 earfunctl.py status --full
systemctl --user start earfun.service
```

### Common commands

| Action | Command |
| --- | --- |
| Check the environment | `python3 earfunctl.py doctor` |
| List known devices | `python3 earfunctl.py devices` |
| Discover the SPP channel | `python3 earfunctl.py --mac AA:BB:CC:DD:EE:FF discover` |
| Read firmware | `python3 earfunctl.py version` |
| Read battery levels | `python3 earfunctl.py battery` |
| Read all exposed status fields | `python3 earfunctl.py status --full` |
| Enable ANC | `python3 earfunctl.py noise anc` |
| Enable Ambient mode | `python3 earfunctl.py noise ambient` |
| Use Normal mode | `python3 earfunctl.py noise normal` |
| Set ANC strength | `python3 earfunctl.py anc-level strong` |
| Enable game mode | `python3 earfunctl.py game on` |
| Disable spatial audio | `python3 earfunctl.py spatial off` |
| Enable multipoint | `python3 earfunctl.py multipoint on` |
| Apply a preset | `python3 earfunctl.py eq --preset bass` |
| Restore flat EQ | `python3 earfunctl.py eq --preset flat` |

Feature commands accept `get` to read the current setting, such as `python3 earfunctl.py noise get`.

### Custom EQ

Supply exactly ten gains, ordered by these frequencies:

| Band | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hz | 31.5 | 63 | 125 | 250 | 500 | 1,000 | 2,000 | 4,000 | 8,000 | 16,000 |

```bash
python3 earfunctl.py eq --gains=3,3,2,1,0,0,0,0,0,0
```

Supported gains in dB:

```text
-6, -5, -4, -3.5, -3, -2.5, -2, -1.5, -1, -0.5,
 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6
```

EQ writes send one frame per band. Current EQ readback is not implemented: `transport_sent_unverified` means the frames were sent, not that device acceptance or persistence was verified. Flat and Bass have produced an audible effect in hardware testing; confirm changes by listening. Applying EQ can change overall volume.

### Diagnostics and packet inspection

```bash
# Machine-readable status
python3 earfunctl.py status --full --json

# Inspect packets without contacting the earbuds
python3 earfunctl.py noise anc --dry-run --json
python3 earfunctl.py eq --preset flat --dry-run --json

# Save a Bluetooth protocol trace
python3 earfunctl.py status --full --trace earfun-trace.jsonl

# Decode a captured response
python3 earfunctl.py decode ef1014026464cafe
```

Common flags include `--mac`, `--channel`, `--timeout`, `--json`, `--trace`, and `--dry-run`. Use `python3 earfunctl.py --help` or a command's `--help` for details.

### Change the default device

```bash
python3 earfunctl.py configure --mac AA:BB:CC:DD:EE:FF --channel 1
systemctl --user restart earfun.service
```

An explicit address overrides the saved device. If it is a different address, the saved device's channel is not inherited; discover the new device's channel or provide its confirmed channel explicitly.

## Updating and uninstalling

### Update

There is no need to uninstall an earlier version. Obtain the new source, run its installer with your confirmed device address and channel, then log out and log back in.

The installer updates the same service and extension locations. Re-enabling the extension alone does not guarantee that GNOME reloads JavaScript already cached in the session.

### Uninstall

From the project root, run without `sudo`:

```bash
python3 uninstall.py
```

This disables and removes the extension, installed application files, service unit, and service drop-ins. Your saved device configuration is preserved. Log out and back in to unload any cached extension code.

## Troubleshooting

### The menu says the service is unavailable

```bash
systemctl --user restart earfun.service
systemctl --user status earfun.service --no-pager -l
journalctl --user -u earfun.service -n 60 --no-pager
```

### `ModuleNotFoundError: gi`

Install `python-gobject` on Arch-based distributions, then check the system interpreter:

```bash
/usr/bin/python3 -c 'from gi.repository import Gio, GLib'
```

The service runs with `/usr/bin/python3`, even if your interactive shell uses another Python installation.

### The extension is missing or still shows the previous version

Log out and log back in, then enable it again:

```bash
gnome-extensions enable earfun@ell.local
gnome-extensions info earfun@ell.local
```

For extension errors:

```bash
journalctl -b -o cat /usr/bin/gnome-shell --no-pager
```

### The device is disconnected or battery readings show `—`

Confirm the earbuds are awake and connected in GNOME Bluetooth settings. Verify the configured device address and its discovered SPP channel. Pairing and automatic Bluetooth connection are not implemented by the extension.

### A CLI command times out or cannot open RFCOMM

Stop `earfun.service` while testing with the CLI. Confirm the earbuds remain connected and that another controller is not using the control channel. Retry a read-only status command with the confirmed address and channel.

### Inspect the service directly

```bash
gdbus call --session \
  --dest io.github.ell.EarFun \
  --object-path /io/github/ell/EarFun \
  --method io.github.ell.EarFun.GetState
```

## Project structure

| Path | Purpose |
| --- | --- |
| `earfunctl.py` | CLI entry point |
| `earfun_cli/` | Packet codec, RFCOMM transport, commands, and configuration |
| `service/` | Python background service and UI-independent backend |
| `extension/earfun@ell.local/` | GNOME Shell extension, popup, styles, and artwork |
| `tests/` | Python tests and JavaScript state/lifecycle tests |
| `install.py` / `uninstall.py` | Per-user installation and removal |
| [PROTOCOL.md](PROTOCOL.md) | Reverse-engineered protocol notes |
| [HARDWARE_CHECKLIST.md](HARDWARE_CHECKLIST.md) | Manual device and desktop checks |
| [VALIDATION.json](VALIDATION.json) | Validation results and their scope |

The extension communicates with the Python service over the session D-Bus. Bluetooth operations run on a worker thread outside GNOME Shell. Requests received while the service is busy are rejected instead of queued.

| D-Bus item | Value |
| --- | --- |
| Bus name / interface | `io.github.ell.EarFun` |
| Object path | `/io/github/ell/EarFun` |
| Methods | `GetState()` and `Request(command, value)` |
| Signal | `StateChanged(state)` |
| Payload format | JSON strings |

Only supported command/value combinations are accepted. The API is available to applications in the same user's session.

### Installed files

| Item | Default location |
| --- | --- |
| Application | `~/.local/share/earfun-panel/` |
| Extension | `~/.local/share/gnome-shell/extensions/earfun@ell.local/` |
| Device configuration | `~/.config/earfun/config.json` |
| User service | `~/.config/systemd/user/earfun.service` |
| Service drop-ins | `~/.config/systemd/user/earfun.service.d/` |

Application/extension paths respect `XDG_DATA_HOME`. Device configuration respects `XDG_CONFIG_HOME`; the installer passes that setting to the service. Service-unit paths currently use `~/.config/systemd/user/`.

## Development and testing

The Python CLI uses the standard library. The background service additionally needs system PyGObject. Node.js is required only for JavaScript tests, not for normal use.

Run Python tests with the system interpreter:

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

Run JavaScript tests:

```bash
node --experimental-vm-modules --test \
  tests/popup-state.test.mjs \
  tests/popup-lifecycle.test.mjs
```

Optional session-bus tests require Gio, `gdbus`, and an isolated D-Bus session:

```bash
dbus-run-session /usr/bin/python3 -m unittest discover -s tests -v
```

The latest validation of version 0.3.0 passed 59 Python tests, including all three full session-bus tests on an isolated D-Bus session, and 15 JavaScript tests. No session-bus tests were skipped. Popup lifecycle tests use St/Clutter mocks and do not establish native GNOME rendering correctness. Use the hardware checklist for real-device and desktop validation.

## Contributing

Bug reports, hardware observations, documentation improvements, and focused pull requests are welcome.

For a useful issue, include:

- Distribution, GNOME Shell version, and Python version.
- EarFun model, firmware version, and discovered SPP channel.
- Steps to reproduce, expected behavior, and actual behavior.
- Relevant service or extension logs, and a protocol trace when applicable.

Remove device addresses and other personal identifiers from shared logs.

When adding device support or changing protocol behavior, provide captured request/response evidence and tests. Keep unsupported values explicit, preserve uncertainty when readback fails, and keep Bluetooth work outside GNOME Shell's main thread. Run the applicable tests and update the protocol notes and hardware checklist with your findings.

## Current limitations

- Only Air Pro 4i / TW230 has confirmed device compatibility.
- The extension installer supports GNOME Shell 50 only.
- Case-lid detection, automatic pairing, and automatic connection are not implemented.
- EQ readback, confirmed EQ persistence, and a graphical 10-band editor are not implemented.
- Settings and EQ presets are not automatically reapplied after reconnecting.
- Artwork is currently a stylized 2D asset set, with some source-edge imperfections.
- Panel labels are currently in Indonesian.

## Roadmap

- Extension preferences and optional popup behavior.
- A graphical 10-band EQ editor and user-defined presets.
- Localization and additional tested GNOME Shell versions.
- Investigating case-lid events using actual Bluetooth captures.
- Additional EarFun models backed by documented protocol evidence.

## References

- [GNOME extension development](https://gjs.guide/extensions/development/creating.html)
- [GJS D-Bus guide](https://gjs.guide/guides/gio/dbus.html)
- [GNOME Shell 50 extension changes](https://gjs.guide/extensions/upgrading/gnome-shell-50.html)
- [Arch Linux: python-gobject](https://archlinux.org/packages/extra/x86_64/python-gobject/)
- [Arch Linux: bluez-deprecated-tools](https://archlinux.org/packages/extra/x86_64/bluez-deprecated-tools/)

## License

Original project code is available under the [MIT License](LICENSE).
Copyright (c) 2026 elamgah. The generated popup artwork is included under the same license to the extent of the creator's rights; its provenance and checksums are recorded in `extension/earfun@ell.local/assets/manifest.json`.

GNOME Shell is licensed under GPL-2.0-or-later. Distribution of the extension as a derivative work of GNOME Shell must comply with compatible GPL terms; MIT licensing of the original project code does not remove those obligations. See the [GNOME licensing guidelines](https://gjs.guide/extensions/review-guidelines/review-guidelines.html#licensing).

This community project is not affiliated with EarFun. EarFun product names and trademarks belong to their respective owners; the project license grants no trademark rights.

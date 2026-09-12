# ableton-tools

Python Control Surface scripts for Ableton Live 12 that run as background listeners — no MIDI hardware, Input and Output set to None. Source is canonical here; `install.sh` copies a script into the Live app bundle.

## AutoSlotSelector

Select a track whose name **ends** with `•` (Option-8) and the first empty clip slot on that track becomes the highlighted slot, ready for the transport Record button. The sentinel is the last character so Live's first-character conveniences keep working: `# Bass •` still displays its track number. If a grid controller is running (Push, Launchpad, Move), its session ring scrolls just enough to show that slot — top row if the slot was above the ring, bottom row if below, untouched if already visible. Tracks without the bullet are left alone. Return, master and group tracks are skipped.

### Install

```bash
./install.sh                      # default: /Applications/Ableton Live 12 Suite.app
./install.sh "/Applications/Ableton Live 12 Beta.app"
```

Restart Live. In Settings → Link, Tempo & MIDI, pick **AutoSlotSelector** in a free Control Surface slot, Input and Output **None**. Re-run `install.sh` after every Live update.

### Verify

Everything the script does is written to Live's log:

```bash
tail -f ~/Library/Preferences/Ableton/Live\ 12*/Log.txt | grep -i autoslot
```

If a previous version failed to import, Live clears the Control Surface slot: re-select **AutoSlotSelector** in Settings after reinstalling.

On load: `AutoSlotSelector: loaded, listening for track selection`. On selecting a bullet track: one line naming the slot it highlighted and the scene now selected, then one line per controller ring it scrolled. A script that failed to load shows a `RemoteScriptError` traceback in the same file instead.

### Tests

```bash
python3 -m unittest discover -s tests
```

Logic only (sentinel, first empty slot, ring math, coalescing, error logging) against a stubbed framework and song. Framework integration is checked by reading Live's installed bytecode; behaviour in Live is checked in Log.txt.

### Design notes

- **Base class is `ableton.v2.control_surface.ControlSurface`**, which takes `c_instance` as its first argument and needs no hardware specification. The `ableton.v3` `ControlSurface` takes a *specification* first; passing `c_instance` there fails inside the framework before the script exists.
- **Deferral uses `schedule_message`.** Live drives every loaded script's timer from `update_display` every ~100 ms; a task group of your own is never ticked. `update()` is not a tick, it is a rebuild hook.
- **Controller rings are found through `get_control_surfaces()`**, the Python-side registry of loaded scripts, imported from the `control_surface` submodule (the package does not re-export it). `Application.control_surfaces` in the Live Object Model returns proxy objects that carry no Python attributes.
- **Logging goes through `c_instance.log_message`**, the route every stock script uses, with the `logging` module as fallback.
- **Selected scene.** In Live the highlighted clip slot sits at the intersection of the selected track and the selected scene, so highlighting a slot in another row moves the scene selection with it. The log line reports the scene after each highlight.

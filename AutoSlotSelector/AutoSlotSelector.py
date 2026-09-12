# -*- coding: utf-8 -*-
"""AutoSlotSelector — a background Control Surface script for Ableton Live 12.

When the selected track changes to a track whose name starts with the bullet
sentinel (•, Option-8 on macOS), highlight that track's first empty clip slot.
If a grid controller (Push, Launchpad, Move) is running, scroll its session
ring just enough to bring that slot into view. Runs with Input/Output = None;
no MIDI hardware is required, and a missing controller is a silent no-op.

Built on ableton.v2 — the framework Live's own Launchpad scripts use. Every
message goes to Live's Log.txt, prefixed "AutoSlotSelector:".
"""
import logging
import traceback

from ableton.v2.control_surface import ControlSurface, get_control_surfaces

logger = logging.getLogger(__name__)

SENTINEL_PREFIX = "•"   # • — Option-8 on macOS
DEFER_TICKS = 1              # one ~100 ms tick, so the controller's own selection work settles first


class AutoSlotSelector(ControlSurface):

    def __init__(self, c_instance):
        super().__init__(c_instance)
        self._pending = False
        self.song.view.add_selected_track_listener(self._on_selected_track_changed)
        logger.info("AutoSlotSelector: loaded, listening for track selection")

    # -- listener + one-tick deferral -------------------------------------------------

    def _on_selected_track_changed(self):
        if self._pending:
            return
        self._pending = True
        # schedule_message runs the callback from the framework's timer tick,
        # which Live drives every ~100 ms for every loaded script.
        self.schedule_message(DEFER_TICKS, self._process_track_selection)

    def _process_track_selection(self):
        self._pending = False
        try:
            self._select_first_empty_slot()
        except Exception:
            logger.error("AutoSlotSelector: %s", traceback.format_exc())

    # -- the behaviour --------------------------------------------------------------

    def _select_first_empty_slot(self):
        view = self.song.view
        track = view.selected_track
        if track is None:
            return
        slots = list(track.clip_slots)
        if not slots or track.is_foldable:
            return  # return/master tracks have no slots; group tracks only have group slots
        name = track.name.strip()
        if not name.startswith(SENTINEL_PREFIX):
            return
        for index, slot in enumerate(slots):
            if not slot.has_clip:
                break
        else:
            logger.info("AutoSlotSelector: '%s' has no empty slot", name)
            return
        view.highlighted_clip_slot = slot
        logger.info("AutoSlotSelector: '%s' -> slot %d (selected scene is now %d)",
                    name, index + 1, self._selected_scene_index() + 1)
        self._nudge_session_rings(index)

    def _selected_scene_index(self):
        selected = self.song.view.selected_scene
        for i, scene in enumerate(self.song.scenes):
            if scene == selected:
                return i
        return -1

    # -- session ring, best effort: no controller script = nothing to do --------------

    def _nudge_session_rings(self, scene_index):
        # get_control_surfaces() is the Python-side registry of loaded scripts.
        # Push 2/3, the Novation scripts and every ableton.v3 script keep their
        # ring at `_session_ring`.
        for cs in get_control_surfaces():
            if cs is self:
                continue
            ring = getattr(cs, "_session_ring", None)
            if ring is None:
                continue
            try:
                self._nudge_ring(cs.__class__.__name__, ring, scene_index)
            except Exception:
                logger.error("AutoSlotSelector: ring nudge on %s failed: %s",
                             cs.__class__.__name__, traceback.format_exc())

    @staticmethod
    def _nudge_ring(owner, ring, scene_index):
        for attr in ("scene_offset", "track_offset", "num_scenes", "set_offsets"):
            if not hasattr(ring, attr):
                return
        height = ring.num_scenes
        if height <= 0:
            return
        top = ring.scene_offset
        bottom = top + height - 1
        if scene_index > bottom:
            new_top = scene_index - height + 1   # target lands on the bottom row
        elif scene_index < top:
            new_top = scene_index                # target lands on the top row
        else:
            return                               # already in view: leave the ring alone
        ring.set_offsets(ring.track_offset, new_top)
        logger.info("AutoSlotSelector: %s ring scrolled to scenes %d-%d",
                    owner, new_top + 1, new_top + height)

    def disconnect(self):
        view = self.song.view
        if view.selected_track_has_listener(self._on_selected_track_changed):
            view.remove_selected_track_listener(self._on_selected_track_changed)
        logger.info("AutoSlotSelector: disconnected")
        super().disconnect()

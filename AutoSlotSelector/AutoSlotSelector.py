# -*- coding: utf-8 -*-
from ableton.v3.base import task
from ableton.v3.control_surface import ControlSurface

SENTINEL_PREFIX = "•"
DEFAULT_NUM_SCENES = 8

class AutoSlotSelector(ControlSurface):
    def __init__(self, c_instance):
        super().__init__(c_instance)
        self._tasks = task.TaskContainer()
        self._session_ring = None
        self.song.view.add_selected_track_listener(self._on_selected_track_changed)
        self.log_message("AutoSlotSelector: Initialized and listening for track selection.")

    def _get_active_session_ring(self):
        """Finds any active hardware SessionRingComponent (Push, Launchpad, etc.).
        Returns None if no supported grid controller is currently attached.
        """
        if self._session_ring is not None:
            return self._session_ring

        for cs in self.application.control_surfaces:
            if cs and cs is not self:
                ring = (
                    getattr(cs, "_session_ring", None)
                    or getattr(cs, "session_ring", None)
                    or getattr(cs, "_session_ring_component", None)
                )
                if ring and hasattr(ring, "scene_offset") and hasattr(ring, "set_offsets"):
                    self._session_ring = ring
                    self.log_message(f"AutoSlotSelector: Attached to session ring on {cs.__class__.__name__}.")
                    return self._session_ring

        return None

    def _on_selected_track_changed(self):
        # 2-tick deferral ensures hardware scripts settle their internal view logic first
        self._tasks.add(
            task.sequence(
                task.delay(2),
                task.run(self._process_track_selection)
            )
        )

    def _process_track_selection(self):
        track = self.song.view.selected_track

        # Skip Master and Return tracks
        if not hasattr(track, 'clip_slots') or not track.clip_slots:
            return

        track_name = track.name.strip()
        if not track_name.startswith(SENTINEL_PREFIX):
            return

        self.log_message(f"AutoSlotSelector: Processing tagged track '{track_name}'.")

        # Find the first unoccupied slot
        target_index = None
        target_slot = None
        for index, slot in enumerate(track.clip_slots):
            if not slot.has_clip:
                target_index = index
                target_slot = slot
                break

        if target_slot is None:
            self.log_message(f"AutoSlotSelector: No empty slot found on '{track_name}'.")
            return

        # 1. Update Live's GUI highlighted slot (runs with or without hardware)
        self.song.view.highlighted_clip_slot = target_slot
        self.log_message(f"AutoSlotSelector: Highlighted empty slot index {target_index}.")

        # 2. Safely nudge the hardware session ring if present
        self._nudge_session_ring(target_index)

    def _nudge_session_ring(self, target_scene_index):
        ring = self._get_active_session_ring()
        if ring is None:
            # Running headless / mouse-and-keyboard only
            return

        current_offset = ring.scene_offset
        num_scenes = getattr(ring, "num_scenes", DEFAULT_NUM_SCENES)
        max_visible_scene = current_offset + num_scenes - 1

        if target_scene_index > max_visible_scene:
            new_offset = target_scene_index - num_scenes + 1
            ring.set_offsets(ring.track_offset, new_offset)
            self.log_message(f"AutoSlotSelector: Shifted ring down to scene offset {new_offset}.")
        elif target_scene_index < current_offset:
            ring.set_offsets(ring.track_offset, target_scene_index)
            self.log_message(f"AutoSlotSelector: Shifted ring up to scene offset {target_scene_index}.")
        else:
            self.log_message(f"AutoSlotSelector: Slot index {target_scene_index} already inside visible ring window [{current_offset}–{max_visible_scene}].")

    def update(self):
        super().update()
        self._tasks.update(0.0)

    def disconnect(self):
        if self.song.view.selected_track_has_listener(self._on_selected_track_changed):
            self.song.view.remove_selected_track_listener(self._on_selected_track_changed)
        self._tasks.clear()
        self._session_ring = None
        self.log_message("AutoSlotSelector: Disconnected.")
        super().disconnect()

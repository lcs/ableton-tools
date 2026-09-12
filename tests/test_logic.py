"""Logic tests for AutoSlotSelector, run outside Live with stubbed framework + song.

    python3 -m unittest discover -s tests

Framework integration (base class, schedule_message, registry) is checked against
Live's installed bytecode, not here.
"""
import os
import sys
import types
import unittest

# ---- stub the ableton.v2 framework just enough to import the script -------------
_registry = []


class _StubControlSurface:
    def __init__(self, c_instance):
        self._c_instance = c_instance
        self.scheduled = []
        _registry.append(self)

    @property
    def song(self):
        return self._c_instance.song()

    def schedule_message(self, ticks, callback, parameter=None):
        self.scheduled.append((ticks, callback))

    def disconnect(self):
        pass


pkg = types.ModuleType("ableton"); pkg.__path__ = []
v2 = types.ModuleType("ableton.v2"); v2.__path__ = []
cs_pkg = types.ModuleType("ableton.v2.control_surface"); cs_pkg.__path__ = []
cs_mod = types.ModuleType("ableton.v2.control_surface.control_surface")
cs_pkg.ControlSurface = _StubControlSurface
cs_mod.get_control_surfaces = lambda: _registry
for name, mod in [("ableton", pkg), ("ableton.v2", v2), ("ableton.v2.control_surface", cs_pkg),
                  ("ableton.v2.control_surface.control_surface", cs_mod)]:
    sys.modules[name] = mod

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from AutoSlotSelector.AutoSlotSelector import AutoSlotSelector, SENTINEL  # noqa: E402


# ---- stub song objects ------------------------------------------------------------
class Slot:
    def __init__(self, has_clip): self.has_clip = has_clip


class Track:
    def __init__(self, name, slots, foldable=False):
        self.name, self.clip_slots, self.is_foldable = name, [Slot(x) for x in slots], foldable


class View:
    def __init__(self, track, scenes):
        self.selected_track = track
        self.selected_scene = scenes[0]
        self.highlighted_clip_slot = None
        self._listeners = []
        self._scenes = scenes

    def add_selected_track_listener(self, cb): self._listeners.append(cb)
    def selected_track_has_listener(self, cb): return cb in self._listeners
    def remove_selected_track_listener(self, cb): self._listeners.remove(cb)


class Song:
    def __init__(self, track, num_scenes=16):
        self.scenes = [object() for _ in range(num_scenes)]
        self.view = View(track, self.scenes)


class CInstance:
    def __init__(self, song): self._song, self.lines = song, []
    def song(self): return self._song
    def log_message(self, text): self.lines.append(text)


class Ring:
    def __init__(self, top, height=8):
        self.scene_offset, self.track_offset, self.num_scenes = top, 3, height
        self.calls = []

    def set_offsets(self, t, s):
        self.calls.append((t, s)); self.track_offset, self.scene_offset = t, s


class Controller:
    def __init__(self, ring): self._session_ring = ring


def make(track, ring=None):
    _registry.clear()
    if ring is not None:
        _registry.append(Controller(ring))
    c = CInstance(Song(track))
    s = AutoSlotSelector(c)
    return s, c


def fire(s):
    s._on_selected_track_changed()
    ticks, cb = s.scheduled[-1]
    cb()
    return ticks


class Tests(unittest.TestCase):
    def test_bullet_track_highlights_first_empty_slot(self):
        s, c = make(Track("Bass " + SENTINEL, [True, True, False, False]))
        self.assertEqual(fire(s), 1)
        self.assertIs(c._song.view.highlighted_clip_slot, c._song.view.selected_track.clip_slots[2])
        self.assertIn("-> slot 3", c.lines[-1])

    def test_untagged_track_is_left_alone(self):
        s, c = make(Track("Bass", [True, False]))
        fire(s)
        self.assertIsNone(c._song.view.highlighted_clip_slot)

    def test_trailing_spaces_after_bullet_still_match(self):
        s, c = make(Track("Keys" + SENTINEL + "  ", [False]))
        fire(s)
        self.assertIsNotNone(c._song.view.highlighted_clip_slot)

    def test_leading_bullet_no_longer_matches(self):
        s, c = make(Track(SENTINEL + " Keys", [False]))
        fire(s)
        self.assertIsNone(c._song.view.highlighted_clip_slot)

    def test_hash_prefix_track_with_trailing_bullet_matches(self):
        s, c = make(Track("# Bass " + SENTINEL, [True, False]))
        fire(s)
        self.assertIs(c._song.view.highlighted_clip_slot, c._song.view.selected_track.clip_slots[1])

    def test_full_track_logs_and_does_nothing(self):
        s, c = make(Track("Full " + SENTINEL, [True, True]))
        fire(s)
        self.assertIsNone(c._song.view.highlighted_clip_slot)
        self.assertIn("no empty slot", c.lines[-1])

    def test_group_and_return_tracks_skipped(self):
        for t in (Track("Group " + SENTINEL, [False], foldable=True), Track("Return " + SENTINEL, [])):
            s, c = make(t); fire(s)
            self.assertIsNone(c._song.view.highlighted_clip_slot)

    def test_pending_flag_coalesces_rapid_changes(self):
        s, c = make(Track("A " + SENTINEL, [False]))
        s._on_selected_track_changed(); s._on_selected_track_changed()
        self.assertEqual(len(s.scheduled), 1)
        s.scheduled[-1][1]()
        s._on_selected_track_changed()
        self.assertEqual(len(s.scheduled), 2)

    def test_ring_scrolls_down_just_enough(self):
        ring = Ring(top=0)
        s, c = make(Track("A " + SENTINEL, [True] * 11 + [False]), ring)  # target scene index 11
        fire(s)
        self.assertEqual(ring.calls, [(3, 4)])  # scenes 5-12 visible, target on the bottom row

    def test_ring_scrolls_up_just_enough(self):
        ring = Ring(top=6)
        s, c = make(Track("A " + SENTINEL, [True, False]), ring)  # target scene index 1
        fire(s)
        self.assertEqual(ring.calls, [(3, 1)])

    def test_ring_untouched_when_target_visible(self):
        ring = Ring(top=2)
        s, c = make(Track("A " + SENTINEL, [True] * 5 + [False]), ring)  # index 5, ring 2-9
        fire(s)
        self.assertEqual(ring.calls, [])

    def test_no_controller_is_a_clean_no_op(self):
        s, c = make(Track("A " + SENTINEL, [False]))
        fire(s)
        self.assertFalse(any("ring" in l for l in c.lines))

    def test_ring_of_four_rows_uses_its_own_height(self):
        ring = Ring(top=0, height=4)
        s, c = make(Track("A " + SENTINEL, [True] * 6 + [False]), ring)  # index 6
        fire(s)
        self.assertEqual(ring.calls, [(3, 3)])  # scenes 4-7

    def test_exception_inside_handler_is_logged_not_raised(self):
        s, c = make(Track("A " + SENTINEL, [False]))
        c._song.view.selected_track = None
        s._on_selected_track_changed(); s.scheduled[-1][1]()  # None track: early return, no log line needed
        broken = Track("B " + SENTINEL, [False]); del broken.clip_slots
        c._song.view.selected_track = broken
        s._on_selected_track_changed(); s.scheduled[-1][1]()
        self.assertIn("AttributeError", c.lines[-1])

    def test_disconnect_removes_listener(self):
        s, c = make(Track("x", [False]))
        s.disconnect()
        self.assertEqual(c._song.view._listeners, [])


if __name__ == "__main__":
    unittest.main()

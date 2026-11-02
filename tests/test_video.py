from __future__ import annotations

import unittest

from homelab_vision.video import constant_rate_timestamps, event_is_represented


class VideoTests(unittest.TestCase):
    def test_constant_rate_sampling_is_bounded(self) -> None:
        self.assertEqual(constant_rate_timestamps(10, 3), (0.0, 3.0, 6.0, 9.0))

    def test_short_event_can_be_missed(self) -> None:
        frames = constant_rate_timestamps(10, 5)
        self.assertFalse(event_is_represented(frames, 2.0, 3.0))
        self.assertTrue(event_is_represented(frames, 4.5, 5.5))

    def test_invalid_event_window_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            event_is_represented((0.0,), 2.0, 1.0)


if __name__ == "__main__":
    unittest.main()

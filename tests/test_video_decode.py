import math
import unittest
from homelab_vision.video_decode import select_frames
from homelab_vision.video import constant_rate_timestamps, FrameRecord


class SelectionTests(unittest.TestCase):
    def test_variable_rate_keeps_actual_and_requested_times(self):
        frames = [dict(best_effort_timestamp_time=t, width=640, height=360)
                  for t in [10.0, 10.08, 10.23, 10.31, 10.57]]
        result = select_frames(frames, .2)
        self.assertEqual([r['frame_index'] for r in result], [0,2,4])
        self.assertEqual([r['timestamp_seconds'] for r in result], [0,.23,.57])
        self.assertEqual([r['requested_timestamp_seconds'] for r in result], [0,.2,.4])

    def test_bad_timestamps_and_limits_rejected(self):
        for times in [[0, float('nan')], [1,0], [0,121]]:
            with self.assertRaises(ValueError):
                select_frames([dict(best_effort_timestamp_time=t,width=640,height=360) for t in times],1)
        with self.assertRaises(ValueError):
            select_frames([dict(best_effort_timestamp_time=t,width=640,height=360) for t in [0,100]],.1)

    def test_nonfinite_or_unbounded_sampling_rejected(self):
        for duration, interval in [(float('inf'),1), (1,float('nan')), (120,.0001)]:
            with self.assertRaises(ValueError):
                constant_rate_timestamps(duration, interval)
        with self.assertRaises(ValueError):
            FrameRecord('a'*64,math.nan,0,'uniform','b'*64)

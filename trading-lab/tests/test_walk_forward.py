import unittest
import pandas as pd

from walk_forward import _index_at_or_after


class WalkForwardTests(unittest.TestCase):
    def test_exact_timestamp(self):
        frame = pd.DataFrame({"timestamp": pd.to_datetime([
            "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z",
            "2026-01-03T00:00:00Z"
        ], utc=True)})
        self.assertEqual(_index_at_or_after(frame, "2026-01-02T00:00:00Z"), 1)

    def test_between_timestamps(self):
        frame = pd.DataFrame({"timestamp": pd.to_datetime([
            "2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z"
        ], utc=True)})
        self.assertEqual(_index_at_or_after(frame, "2026-01-02T00:00:00Z"), 1)

    def test_after_end(self):
        frame = pd.DataFrame({"timestamp": pd.to_datetime([
            "2026-01-01T00:00:00Z"
        ], utc=True)})
        self.assertEqual(_index_at_or_after(frame, "2026-01-02T00:00:00Z"), 1)

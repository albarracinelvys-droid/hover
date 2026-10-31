"""Synthetic tests for the HOVER microphone gate.

No microphone or Whisper model is required for these tests.
"""
import unittest
import numpy as np

from hover_next.audio import SpeechSegmenter, _resample


class AudioTests(unittest.TestCase):
    def test_silence_stays_silent(self):
        gate = SpeechSegmenter(threshold=0.0008)
        outputs = [gate.process(np.full(480, 0.0003, dtype=np.float32))
                   for _ in range(80)]
        self.assertTrue(all(out is None for out in outputs))

    def test_low_volume_voice_is_detected(self):
        gate = SpeechSegmenter(threshold=0.0008)
        frames = [np.full(480, 0.003, dtype=np.float32) for _ in range(14)]
        frames += [np.zeros(480, dtype=np.float32) for _ in range(30)]
        outputs = [gate.process(frame) for frame in frames]
        segments = [audio for audio in outputs if audio is not None]
        self.assertEqual(len(segments), 1)
        self.assertGreater(len(segments[0]), 14 * 480)

    def test_separates_two_sentences(self):
        gate = SpeechSegmenter()
        signals = ([np.full(480, 0.003, dtype=np.float32)] * 12 +
                   [np.zeros(480, dtype=np.float32)] * 30) * 2
        outputs = [gate.process(frame) for frame in signals]
        self.assertEqual(len([audio for audio in outputs if audio is not None]), 2)

    def test_native_rate_resampling(self):
        audio = np.ones(1440, dtype=np.float32) * 0.25
        converted = _resample(audio, 480)
        self.assertEqual(len(converted), 480)
        self.assertAlmostEqual(float(converted.mean()), 0.25, places=5)

    def test_rejects_zero_threshold(self):
        with self.assertRaises(ValueError):
            SpeechSegmenter(threshold=0.0)


if __name__ == "__main__":
    unittest.main()

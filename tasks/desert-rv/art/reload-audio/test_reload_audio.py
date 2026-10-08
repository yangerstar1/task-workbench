"""Static and deliberately synthetic-fixture tests; never generate/audition production WAV here."""
import ast
import importlib.util
import hashlib
import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave

HERE = Path(__file__).resolve().parent
GENERATOR = HERE.parent / 'scripts/make_reload_foley.py'
spec = importlib.util.spec_from_file_location('validate_reload', HERE / 'validate_reload.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ReloadAudioTests(unittest.TestCase):
    def fixture(self, output, *, missing=None, clip=False, rate=48000, trim=False, stray=False):
        # Pure test sine with smooth ends. It is NOT the source's synthesized mechanical waveform.
        samples = [0.0] * 79200
        for frame, action, duration in validator.CUES:
            first, count = round((frame-1) / 60 * 48000), round(duration * 48000)
            if action == missing:
                continue
            for i in range(count):
                samples[first+i] = .2 * math.sin(math.pi * i / (count-1)) * math.sin(2 * math.pi * 800 * i / 48000)
        if clip:
            samples[10000] = 1.0
        if stray:
            samples[10] = .05
        if trim:
            samples = samples[:-100]
        with wave.open(str(output), 'wb') as wav:
            wav.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
            wav.writeframes(b''.join(struct.pack('<h', round(v * 32767)) for v in samples))

    def check(self, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'TEST_ONLY.wav'
            self.fixture(output, **kwargs)
            return validator.analyze(output)

    def test_generator_timing_matches_independent_contract(self):
        tree = ast.parse(GENERATOR.read_text())
        values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                  and node.targets[0].id in {'RATE', 'DURATION', 'CUES'}}
        self.assertEqual((values['RATE'], values['DURATION']), (48000, 1.65))
        self.assertEqual([(f,n,d) for f,n,d,*_ in values['CUES']], validator.CUES)
        self.assertLessEqual(max((f-1)/60+d for f,n,d,*_ in values['CUES']), 1.65)

    def test_nominal_test_fixture_passes_without_claiming_listening(self):
        report = self.check()
        self.assertTrue(report['objective_checks_passed'], report['failures'])
        self.assertFalse(report['auditioned'])
        self.assertFalse(report['perceptual_quality_approved'])
        self.assertFalse(report['unity_import_verified'])
        self.assertEqual(len(report['events']), 8)

    def test_missing_event_rejected(self):
        self.assertFalse(self.check(missing='strip_seat')['objective_checks_passed'])

    def test_clipping_rejected(self):
        report = self.check(clip=True)
        self.assertFalse(report['objective_checks_passed'])
        self.assertEqual(report['clipped_sample_count'], 1)

    def test_wrong_sample_rate_rejected(self):
        self.assertFalse(self.check(rate=44100)['objective_checks_passed'])

    def test_wrong_length_rejected(self):
        self.assertFalse(self.check(trim=True)['objective_checks_passed'])

    def test_stray_silence_content_rejected(self):
        self.assertFalse(self.check(stray=True)['objective_checks_passed'])

    def test_invalid_wav_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'invalid.wav'
            output.write_bytes(b'not a WAV')
            self.assertFalse(validator.analyze(output)['objective_checks_passed'])

    def test_provenance_rejects_wrong_hash_cues_format_and_false_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'TEST_ONLY.wav'
            self.fixture(output)
            provenance = {'duration_seconds': 1.65, 'sample_rate': 48000, 'channels': 1,
                          'format': 'PCM signed 16-bit',
                          'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                          'generator_sha256': hashlib.sha256(GENERATOR.read_bytes()).hexdigest(),
                          'cues': [{'frame': f, 'action': n, 'seconds': (f-1)/60, 'duration_seconds': d}
                                   for f,n,d in validator.CUES],
                          'auditioned': False, 'visual_sync_approved': False,
                          'source_commit': 'TEST_ONLY', 'github_run_id': 'TEST_ONLY'}
            self.assertEqual(validator.validate_provenance(output, provenance, GENERATOR, 'TEST_ONLY', 'TEST_ONLY'), [])
            self.assertTrue(validator.validate_provenance(output, provenance, GENERATOR, 'WRONG_COMMIT', 'TEST_ONLY'))
            self.assertTrue(validator.validate_provenance(output, provenance, GENERATOR, 'TEST_ONLY', 'WRONG_RUN'))
            for key, value in [('sha256', 'wrong'), ('generator_sha256', 'wrong'), ('cues', []),
                               ('sample_rate', 44100), ('auditioned', True),
                               ('visual_sync_approved', True), ('github_run_id', None)]:
                changed = dict(provenance); changed[key] = value
                self.assertTrue(validator.validate_provenance(output, changed, GENERATOR), key)

    def test_generator_requires_actions_and_refuses_overwrite(self):
        source = GENERATOR.read_text()
        self.assertIn("os.environ.get('GITHUB_ACTIONS') != 'true'", source)
        self.assertIn("args.output.exists()", source)
        self.assertNotIn("max(-.95, min(.95", source)
        self.assertIn("raise ValueError('Reload source exceeds", source)


if __name__ == '__main__':
    unittest.main()

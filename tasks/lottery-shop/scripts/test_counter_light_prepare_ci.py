#!/usr/bin/env python3
"""Cold real-entrypoint regressions. Synthetic Git/PNG inputs; never native evidence.
Default suite uses only stdlib and launches the actual prepare CLI with python -S.
--dependencies-only checks pinned image packages in the disposable CI venv.
"""
import hashlib
import inspect
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
TASK = 'tasks/lottery-shop'
FOLDER = TASK + '/scripts/counter_light_diagnostics'
WORKFLOW = '.github/workflows/lottery-visual-candidate.yml'
REQUEST = TASK + '/ci/visual-candidate-request.json'
EVIDENCE = TASK + '/evidence/visual-candidate'
PREPARED = TASK + '/artifacts/counter-light-diagnostic/prepared-context.json'
ENV_KEYS = {'GITHUB_EVENT_NAME': 'push', 'GITHUB_REPOSITORY': 'yangerstar1/task-workbench',
            'GITHUB_REPOSITORY_OWNER': 'yangerstar1', 'GITHUB_ACTOR': 'yangerstar1',
            'GITHUB_TRIGGERING_ACTOR': 'yangerstar1', 'GITHUB_REF': 'refs/heads/lottery-shop-g0-20261011'}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ColdPrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='SYNTHETIC_COLD_PREPARE_NOT_NATIVE_')
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent/'checkout'
        self.root.mkdir()
        self.home = self.parent/'empty-home'
        self.home.mkdir()
        self.env = {'PATH': os.defpath, 'HOME': str(self.home), 'LANG': 'C.UTF-8',
                    'PYTHONDONTWRITEBYTECODE': '1', 'GIT_CONFIG_NOSYSTEM': '1',
                    'GIT_CONFIG_GLOBAL': os.devnull}
        contract = json.loads((ROOT/FOLDER/'code-contract.json').read_bytes())
        paths = {row['repositoryPath'] for row in contract['files']}
        paths.update({FOLDER+'/code-contract.json', TASK+'/.gitignore', WORKFLOW})
        for name in paths:
            target = self.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, target)
        # Real restore_font API with synthetic bytes. The production font is not
        # present in this bounded fixture; this is not licensed-font validation.
        font = b'SYNTHETIC_FONT_NOT_PRODUCTION' * 40
        self.font = font
        compressed = self.root/TASK/'fonts/synthetic-font.xz'
        compressed.parent.mkdir(parents=True)
        compressed.write_bytes(lzma.compress(font))
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic Cold Prepare')
        self.git('config', 'user.email', 'synthetic-prepare@example.invalid')
        self.event = self.parent/'event.json'
        write(self.event, {'repository': {'private': False, 'fork': False}, 'deleted': False})

    def git(self, *args):
        p = subprocess.run(['git', '-C', str(self.root), *args], env=self.env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def commit_pair(self, wrong_review=False, extra_trigger_file=False):
        self.git('add', '.')
        self.git('commit', '-qm', 'Synthetic separately reviewed source')
        reviewed = self.git('rev-parse', 'HEAD')
        request = {'schemaVersion': 1, 'requestId': 'lottery-visual-20261014-26',
                   'sourceCommit': reviewed, 'purpose': 'DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS',
                   'sourceReview': {'sourceCommit': 'f'*40 if wrong_review else reviewed,
                                    'status': 'APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY',
                                    'reviewedAtUtc': '2020-01-01T00:00:00Z',
                                    'reviewId': 'visual-source-20261014-26', 'reviewer': 'independent-source-review'}}
        write(self.root/REQUEST, request)
        if extra_trigger_file:
            (self.root/TASK/'scripts/unauthorized-trigger.txt').write_text('synthetic')
        self.git('add', '.')
        self.git('commit', '-qm', 'Synthetic request-only trigger')
        source = self.git('rev-parse', 'HEAD')
        self.ident = {'sourceCommit': source, 'reviewedCandidateCommit': reviewed,
                      'runId': '123456', 'runAttempt': '1'}
        self.env.update(ENV_KEYS)
        self.env.update(GITHUB_SHA=source, GITHUB_RUN_ID='123456', GITHUB_RUN_ATTEMPT='1',
                        GITHUB_EVENT_PATH=str(self.event), GITHUB_WORKSPACE=str(self.root),
                        GITHUB_WORKFLOW_REF='yangerstar1/task-workbench/'+WORKFLOW+'@'+ENV_KEYS['GITHUB_REF'])
        return self.ident

    def python(self, *args):
        return subprocess.run([sys.executable, '-S', *args], cwd=self.parent,
                              env=self.env, capture_output=True, text=True, timeout=60)

    def prepare(self):
        # Same command/arguments as CI, deliberately unrelated cwd and no site packages.
        return self.python(str(self.root/FOLDER/'compose_evidence.py'), 'prepare', '--repo-root', str(self.root))

    def assert_rejected(self, error):
        p = self.prepare()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(error, p.stderr)
        self.assertFalse((self.root/PREPARED).exists())

    def test_actual_cold_prepare_returns_bound_identity_and_all_code_hashes(self):
        ident = self.commit_pair()
        p = self.prepare()
        self.assertEqual(p.returncode, 0, p.stderr)
        prepared = json.loads((self.root/PREPARED).read_bytes())
        original = json.loads((self.root/EVIDENCE/'source-receipt.json').read_bytes())
        before = json.loads((self.root/EVIDENCE/'source-before.json').read_bytes())
        for payload in (prepared, original, before):
            for key, value in ident.items(): self.assertEqual(payload[key], value)
        self.assertEqual(prepared['guardSourceReceiptSha256'], sha(self.root/EVIDENCE/'source-receipt.json'))
        self.assertEqual(prepared['sourceBeforeSha256'], sha(self.root/EVIDENCE/'source-before.json'))
        contract = json.loads((self.root/FOLDER/'code-contract.json').read_bytes())
        compact = json.dumps(contract, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        self.assertEqual(prepared['codeContractSha256'], hashlib.sha256(compact).hexdigest())
        records = {row['path']: row for row in before['files']}
        for row in contract['files']:
            self.assertEqual(records[row['repositoryPath']]['sha256'], row['sha256'])
        self.assertEqual(self.git('diff', '--name-only', 'HEAD'), '')
        self.assertFalse(any(self.root.rglob('__pycache__')))

    def test_actual_pinned_signatures_identity_and_imports_are_stdlib(self):
        self.commit_pair()
        code = """import inspect,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import compose_evidence as c
v,_,_=c.modules()
r=v.guard(Path(sys.argv[2]));v.snapshot(Path(sys.argv[2]),False)
print(json.dumps({'guard':str(inspect.signature(v.guard)),'snapshot':str(inspect.signature(v.snapshot)),
                 'identity':{k:r[k] for k in ('sourceCommit','reviewedCandidateCommit','runId','runAttempt')},
                 'imageLoaded':any(n=='numpy' or n=='PIL' or n.startswith('numpy.') or n.startswith('PIL.') for n in sys.modules)}))
"""
        p = self.python('-c', code, str(self.root/FOLDER), str(self.root))
        self.assertEqual(p.returncode, 0, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result, {'guard': '(root)', 'snapshot': '(root, after=False)',
                                  'identity': self.ident, 'imageLoaded': False})

    def test_second_guard_after_ignored_font_restore_outputs_remains_clean(self):
        self.commit_pair()
        code = """import hashlib,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import compose_evidence as c
v,_,_=c.modules();root=Path(sys.argv[2]);v.guard(root)
font=b'SYNTHETIC_FONT_NOT_PRODUCTION'*40
source=root/c.TASK/'fonts/synthetic-font.xz'
v.bounded.restore_font(source,root/c.TASK/'unity/Assets/Resources/ProbeChinese.otf',
    compressed_sha=hashlib.sha256(source.read_bytes()).hexdigest(),font_sha=hashlib.sha256(font).hexdigest(),font_size=len(font))
(root/c.TASK/'unity/Assets/Resources/ProbeFontLicense.txt').write_text('SYNTHETIC_LICENSE_NOT_PRODUCTION')
v.snapshot(root,False)
"""
        p = self.python('-c', code, str(self.root/FOLDER), str(self.root))
        self.assertEqual(p.returncode, 0, p.stderr)
        before = (self.root/EVIDENCE/'source-before.json').read_bytes()
        self.assertEqual(self.git('diff', '--name-only', 'HEAD', '--', TASK, WORKFLOW), '')
        p = self.prepare()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(before, (self.root/EVIDENCE/'source-before.json').read_bytes())

    def test_wrong_actor_keeps_original_context_guard(self):
        self.commit_pair(); self.env['GITHUB_ACTOR'] = 'wrong-actor'
        self.assert_rejected('CI_CONTEXT_REQUIRED')

    def test_private_event_keeps_original_source_guard(self):
        self.commit_pair(); write(self.event, {'repository': {'private': True, 'fork': False}})
        self.assert_rejected('Unexpected repository event')

    def test_wrong_workflow_is_rejected(self):
        self.commit_pair(); self.env['GITHUB_WORKFLOW_REF'] = 'wrong/workflow@ref'
        self.assert_rejected('EXPECTED_WORKFLOW_CONTEXT_REQUIRED')

    def test_wrong_source_is_rejected(self):
        self.commit_pair(); self.env['GITHUB_SHA'] = 'e'*40
        self.assert_rejected('CI_CHECKOUT_MISMATCH')

    def test_repeated_attempt_is_rejected(self):
        self.commit_pair(); self.env['GITHUB_RUN_ATTEMPT'] = '2'
        self.assert_rejected('CI_IDENTITY_INVALID')

    def test_wrong_review_is_rejected(self):
        self.commit_pair(wrong_review=True)
        self.assert_rejected('Source review does not cover this candidate')

    def test_non_request_trigger_change_is_rejected(self):
        self.commit_pair(extra_trigger_file=True)
        self.assert_rejected('Trigger commit must change only visual-candidate-request.json')

    def test_changed_tracked_source_is_rejected(self):
        self.commit_pair()
        with (self.root/TASK/'scripts/safe_project_ci.py').open('a') as f: f.write('\n# synthetic mutation\n')
        self.assert_rejected('Checkout changed before candidate guard')

    def test_precommitted_bad_contract_is_rejected(self):
        path = self.root/FOLDER/'code-contract.json'
        contract = json.loads(path.read_bytes()); contract['files'][0]['sha256'] = '0'*64; write(path, contract)
        self.commit_pair()
        self.assert_rejected('REVIEWED_HELPER_PLAN_OR_VALIDATOR_MISSING_OR_CHANGED')

    def test_changed_pinned_dependency_is_rejected(self):
        self.commit_pair()
        with (self.root/FOLDER/'pinned_dependencies/visual_candidate_ci.py').open('a') as f: f.write('\n# synthetic mutation\n')
        self.assert_rejected('PINNED_DEPENDENCY_CHANGED')

    def test_missing_image_dependencies_fail_closed_when_image_work_requested(self):
        self.commit_pair()
        code = "import sys;sys.path.insert(0,sys.argv[1]);import verify_and_measure as v;v.validate_camera({})"
        p = self.python('-c', code, str(self.root/FOLDER))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("No module named 'numpy'", p.stderr)
        self.assertFalse((self.root/PREPARED).exists())


class MeasurementDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT/FOLDER))
        import verify_and_measure
        cls.v = verify_and_measure

    def test_exact_official_versions(self):
        import numpy
        import PIL
        self.assertEqual(numpy.__version__, '2.3.5')
        self.assertEqual(PIL.__version__, '12.3.0')

    def test_actual_png_decode_hash_geometry_and_statistics(self):
        import numpy as np
        from PIL import Image
        pixels = np.random.default_rng(20261014).integers(0, 256, size=(720, 1280, 3), dtype=np.uint8)
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC_IMAGE_SMOKE_NOT_NATIVE_') as folder:
            path = Path(folder)/'synthetic.png'; Image.fromarray(pixels).save(path)
            image = self.v.png(path, sha(path), path.stat().st_size)
            np.testing.assert_array_equal(image, pixels.astype(np.float64))
            for kwargs, error in (({'digest': '0'*64}, 'PNG hash mismatch'),
                                  ({'count': 1}, 'PNG length mismatch'),
                                  ({'size': (1, 1)}, 'PNG format/geometry mismatch')):
                with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, error): self.v.png(path, **kwargs)
        simple = np.array([[[0, 10, 20], [100, 110, 120]]], dtype=np.float64)
        result = self.v.stats(simple)
        self.assertEqual(result['pixels'], 2)
        self.assertEqual(result['meanRGBCode'], [50.0, 60.0, 70.0])
        np.testing.assert_allclose(result['p95RGBCode'], [95, 105, 115], rtol=0, atol=1e-12)
        np.testing.assert_allclose(result['p99RGBCode'], [99, 109, 119], rtol=0, atol=1e-12)
        measures = self.v.measures(image, {'synthetic-delta': image+1})
        for roi in self.v.PLAN['rois']:
            delta = measures[roi]['cases']['synthetic-delta']
            self.assertEqual(delta['meanSignedRGBCodeDelta'], [1.0, 1.0, 1.0])
            self.assertEqual(delta['meanAbsoluteRGBCodeDelta'], 1.0)
            self.assertEqual(delta['maxAbsoluteRGBCodeDelta'], 1.0)

    def test_actual_matrix_validation_rejects_singular_matrix(self):
        import numpy as np
        matrix = np.eye(4).reshape(-1).tolist()
        c = {key: 1 for key in ('instanceId', 'targetId', 'expectedTargetId', 'urpInstanceId', 'volumeTriggerId', 'antiAliasing', 'cullingMask')}
        c.update(width=1280, height=720, format='ARGB32', orthographic=False, targetCreated=True, enabled=True,
                 urpStackIds=[], urpSerializedSha256='a'*64, position=dict(x=0, y=0, z=0), rotation=dict(x=0, y=0, z=0, w=1),
                 background=dict(r=0, g=0, b=0, a=1), projection=matrix, worldToCamera=matrix,
                 viewport=[0, 0, 1, 1], allowHDR=True, allowMSAA=False, sRGB=True, clearFlags='Color',
                 fov=60, aspect=1280/720, near=.1, far=100)
        self.v.validate_camera(c)
        c['projection'] = [0]*16
        with self.assertRaisesRegex(ValueError, 'Camera matrix singular'): self.v.validate_camera(c)


if __name__ == '__main__':
    dependencies = '--dependencies-only' in sys.argv
    if dependencies: sys.argv.remove('--dependencies-only')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MeasurementDependencyTests if dependencies else ColdPrepareTests)
    result = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)

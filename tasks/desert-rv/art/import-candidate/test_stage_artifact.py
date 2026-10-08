import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from stage_artifact import stage

class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / 'artifact.zip'
        with zipfile.ZipFile(self.archive, 'w') as z:
            z.writestr('model.fbx', b'not-a-real-model-test-fixture')
            z.writestr('report.json', '{}')
        self.sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.contract = {'schema': 1, 'mode':'DISCOVERY_ONLY','scope':'DEATH_DIAGNOSTIC_NOT_FULL', 'repository': 'yangerstar1/task-workbench', 'sourceCommit': 'a'*40,
                         'runUrl': 'https://github.com/yangerstar1/task-workbench/actions/runs/1',
                         'artifactName': 'fixture', 'artifactSha256': self.sha,
                         'files': [{'file': 'model.fbx', 'sha256': hashlib.sha256(b'not-a-real-model-test-fixture').hexdigest()}]}
        self.run = {'id': 1, 'repository': {'full_name': self.contract['repository']}, 'head_sha': 'a'*40,
                    'status': 'completed', 'conclusion': 'success'}
        self.artifact = {'name': 'fixture', 'expired': False, 'digest': 'sha256:' + self.sha,
                         'workflow_run': {'id': 1, 'head_sha': 'a'*40}}
    def tearDown(self):
        self.temp.cleanup()
    def call(self):
        for name, value in [('contract', self.contract), ('run', self.run), ('artifact', self.artifact)]:
            (self.root / (name+'.json')).write_text(json.dumps(value))
        return stage(self.root/'contract.json', self.root/'run.json', self.root/'artifact.json', self.archive, self.root/'out')
    def test_only_declared_payload(self):
        self.assertEqual(self.call()['status'], 'staged-not-imported-or-reviewed')
        self.assertTrue((self.root/'out/model.fbx').is_file())
        self.assertFalse((self.root/'out/report.json').exists())
    def test_discovery_needs_no_guessed_binding(self):
        result=self.call();self.assertEqual(result['mode'],'DISCOVERY_ONLY');self.assertEqual(result['scope'],'DEATH_DIAGNOSTIC_NOT_FULL')
    def test_discovery_rejects_invented_takes(self):
        self.contract['clips']=[{'take':'guessed'}]
        with self.assertRaisesRegex(ValueError,'Discovery cannot'):self.call()
    def test_discovery_rejects_explicit_empty_or_null_keys(self):
        for key in ('bindings','clips','materials'):
            for value in (None,[],{}):
                self.contract[key]=value
                with self.assertRaisesRegex(ValueError,'Discovery cannot'):self.call()
            del self.contract[key]
    def test_discovery_allows_strict_words_in_value(self):
        self.contract['note']='bindings clips materials';self.call()
    def test_partial_cannot_promote_to_strict(self):
        self.contract['mode']='STRICT_BINDING'
        with self.assertRaisesRegex(ValueError,'Partial diagnostic'):self.call()
    def test_missing_mode_rejected(self):
        del self.contract['mode']
        with self.assertRaisesRegex(ValueError,'Explicit import mode'):self.call()
    def test_unknown_scope_rejected(self):
        self.contract['scope']='APPROVED'
        with self.assertRaisesRegex(ValueError,'Explicit source scope'):self.call()
    def test_source_mismatch(self):
        self.run['head_sha']='b'*40
        with self.assertRaisesRegex(ValueError, 'Run source'): self.call()
    def test_wrong_run(self):
        self.artifact['workflow_run']['id']=2
        with self.assertRaisesRegex(ValueError, 'Artifact run'): self.call()
    def test_missing_server_digest(self):
        del self.artifact['digest']
        with self.assertRaisesRegex(ValueError, 'GitHub artifact digest'): self.call()
    def test_changed_archive(self):
        self.archive.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError, 'Archive hash'): self.call()
    def test_payload_mismatch(self):
        self.contract['files'][0]['sha256']='b'*64
        with self.assertRaisesRegex(ValueError, 'Payload hash'): self.call()
    def test_collision(self):
        self.contract['files'].append({'file':'MODEL.fbx','sha256':'b'*64})
        with self.assertRaisesRegex(ValueError, 'colliding'): self.call()
    def test_zip_traversal(self):
        with zipfile.ZipFile(self.archive,'a') as z: z.writestr('../escape',b'bad')
        self.contract['artifactSha256']=hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.artifact['digest']='sha256:'+self.contract['artifactSha256']
        with self.assertRaisesRegex(ValueError, 'Unsafe artifact path'): self.call()
    def test_no_overwrite(self):
        self.call()
        with self.assertRaisesRegex(ValueError, 'overwrite'): self.call()
    def test_failed_generation(self):
        self.run['conclusion']='failure'
        with self.assertRaisesRegex(ValueError, 'did not succeed'): self.call()

if __name__ == '__main__': unittest.main()

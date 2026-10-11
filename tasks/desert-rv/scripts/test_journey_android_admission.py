"""Real depth-two Git and reused-helper regressions; never native execution evidence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tasks/desert-rv/scripts/player'))
import journey_android as android
import verify_evidence as original


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AndroidAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='android-admission-host-fixture-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.seed = cls.folder / 'seed'
        cls.seed.mkdir()
        names = original.source_inventory() | {android.SOURCE, 'tasks/desert-rv/PUBLIC-EXPORT.json'}
        names |= {p.relative_to(ROOT).as_posix() for p in (ROOT / '.github/dispatch').glob('*.json')}
        names.discard(android.REQUEST)
        for name in sorted(names):
            target = cls.seed / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        cls.git(cls.seed, 'init', '--quiet')
        cls.git(cls.seed, 'config', 'user.name', 'Host-only identity fixture')
        cls.git(cls.seed, 'config', 'user.email', 'fixture@example.invalid')
        cls.git(cls.seed, 'add', '.')
        cls.git(cls.seed, 'commit', '--quiet', '-m', 'Synthetic parent; not native evidence')
        cls.parent = cls.git(cls.seed, 'rev-parse', 'HEAD')
        helper = cls.seed / 'tasks/desert-rv/scripts/player/journey_android.py'
        helper.write_text(helper.read_text().replace("BASE = '" + android.BASE + "'", "BASE = '" + cls.parent + "'"))
        subprocess.run([sys.executable, 'tasks/desert-rv/scripts/update_source_state.py'], cwd=cls.seed,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True, stdout=subprocess.DEVNULL)
        cls.request = dict(schema=1, requestId=android.REQUEST_ID, baseCommit=cls.parent,
                           sourceStateSha256=sha(cls.seed / android.SOURCE), selection=android.SELECTION,
                           selectionSha256=sha(cls.seed / android.SELECTION), image=android.IMAGE)
        (cls.seed / android.REQUEST).write_text(json.dumps(cls.request) + '\n')
        cls.git(cls.seed, 'add', '.')
        cls.git(cls.seed, 'commit', '--quiet', '-m', 'Synthetic Android child; not native evidence')
        cls.head = cls.git(cls.seed, 'rev-parse', 'HEAD')

    @staticmethod
    def git(root, *args):
        return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()

    def setUp(self):
        self.repo = self.folder / self._testMethodName
        subprocess.run(['git', 'clone', '--quiet', '--depth=2', self.seed.as_uri(), str(self.repo)], check=True)
        self.event = dict(before=self.parent, after=self.head, ref=android.REF, created=False, deleted=False, forced=False,
                          sender=dict(login='yangerstar1'), head_commit=dict(id=self.head),
                          repository=dict(full_name=android.REPO, private=False, fork=False, default_branch='main', owner=dict(login='yangerstar1')))
        event_path = self.repo / 'host-event.json'
        event_path.write_text(json.dumps(self.event))
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
                        RUNNER_OS='Linux', GITHUB_REPOSITORY=android.REPO, GITHUB_REPOSITORY_VISIBILITY='public',
                        GITHUB_ACTOR='yangerstar1', GITHUB_TRIGGERING_ACTOR='yangerstar1', GITHUB_EVENT_NAME='push',
                        GITHUB_REF=android.REF, GITHUB_WORKFLOW_REF=android.REPO + '/' + android.WORKFLOW + '@' + android.REF,
                        GITHUB_SHA=self.head, GITHUB_RUN_ID='987654321', GITHUB_RUN_ATTEMPT='1',
                        GITHUB_EVENT_PATH=str(event_path), GITHUB_OUTPUT=str(self.repo / 'host-output'), NATIVE_OUTCOME='success')

    def script(self, body):
        imports = "import os,json,sys,hashlib,subprocess\nfrom pathlib import Path\nsys.path[:0]=['tasks/desert-rv/scripts','tasks/desert-rv/scripts/player','tasks/desert-rv/art/journey-preparation','tasks/desert-rv/scripts/rendered']\nimport journey_android as a, journey_tracer_source_diagnostic as d, journey_keyboard_look_native as k, journey_cabin_entry_native as c, journey_tracer_dispatch as linux\n"
        result = subprocess.run([sys.executable, '-B', '-c', imports + body], cwd=self.repo, env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(result.returncode, 0, result.stdout[-7000:])
        return result.stdout

    def initialize(self):
        self.script("""
assert a.dispatch()['requestId'] == a.REQUEST_ID
assert subprocess.check_output(['git','rev-list','--count','HEAD']).strip() == b'2'
assert subprocess.check_output(['git','rev-parse','--is-shallow-repository']).strip() == b'true'
assert subprocess.run(['git','cat-file','-e',linux.BASE+'^{commit}'],stderr=subprocess.DEVNULL).returncode != 0
subprocess.run([sys.executable,'tasks/desert-rv/scripts/backup/restore_unity_font.py'],check=True)
import pipeline
pipeline.init(a.SELECTION, a.sha(a.ROOT/a.SELECTION))
""")

    def test_depth_two_real_source_gate_copy_owner_cabin_and_preserve(self):
        self.initialize()
        self.script("""
assert d.run(os.environ) == 0, d.REPORT.read_text()
report=json.loads(d.REPORT.read_bytes())
assert report['baselineAuthenticated'] and report['sourceUnchanged']
assert all(row['status']=='PASS' for row in report['checks'].values())
assert k.create_copy(os.environ) == 0
owner=k.load_owner(os.environ)
assert all(owner[key]==value for key,value in k.owner_identity(os.environ).items())
assert k.inspect_copy(os.environ) == 0
assert k.run_source(os.environ) == 0
# Synthetic, allowlisted host fixtures exercise consumption only; no native pass is claimed.
import xml.etree.ElementTree as ET
import test_journey_cabin_entry_native as cabin_fixture
root=ET.Element('test-run',result='Passed',total='4',passed='4',failed='0',skipped='0',inconclusive='0')
for name in k.EXPECTED: ET.SubElement(root,'test-case',fullname=name,result='Passed')
k.ARTIFACTS.mkdir(parents=True); ET.ElementTree(root).write(k.ARTIFACTS/'host-results.xml')
assert k.run(os.environ) == 0
c.RAW_REPORT.parent.mkdir(parents=True);c.RAW_REPORT.write_text(json.dumps(cabin_fixture.fixture(True)))
c.ARTIFACTS.mkdir(parents=True);(c.ARTIFACTS/'host-results.xml').write_bytes(cabin_fixture.xml('Passed'))
assert c.run(os.environ) == 0
report=json.loads(c.REPORT.read_bytes())
assert c.validate_report(report, os.environ)
assert report['requestId']==a.REQUEST_ID and report['requestSha256']==a.sha(a.ROOT/a.REQUEST)
assert report['checks']['identity']=='PASS' and report['diagnosticComplete']
assert not c.validate_report(report)  # Absent context retains the old Linux report contract.
assert not c.validate_report(dict(report,requestId=linux.REQUEST_ID), os.environ)
assert k.preserve(os.environ) == 0
assert {p.name for p in k.PREPARATION_REPORTS.iterdir()} == {'native-report.json','source-report.json','isolation-report.json'}
assert k.cleanup_copy(os.environ) == 0
assert not k.COPY.exists()
""")

    def test_head_baseline_survives_working_source_request_drift_without_admission(self):
        self.initialize()
        self.script("""
source,expected,pinned=d.pinned_baseline(os.environ)
original_request=(a.ROOT/a.REQUEST).read_bytes()
for name in (a.SOURCE,a.REQUEST):
    path=a.ROOT/name;before=path.read_bytes();path.write_bytes(before+b' ')
    assert d.pinned_baseline(os.environ)[2] == pinned
    assert d.check_original_gates(os.environ,source)['dispatchIdentity']['status']=='FAIL'
    assert d.run(os.environ) == 2
    report=json.loads(d.REPORT.read_bytes())
    assert report['baselineAuthenticated'] and report['status']=='SOURCE_CHANGED'
    assert any(row['path']==name for row in report['records'])
    d.REPORT.unlink();path.write_bytes(before)
assert (a.ROOT/a.REQUEST).read_bytes()==original_request
assert d.run(os.environ)==0, d.REPORT.read_text()
""")

    def test_exact_android_context_rejects_changed_identity_and_request_fields(self):
        self.script("""
assert d.admission(os.environ) is a
for key,bad in [('GITHUB_REPOSITORY','other/repo'),('GITHUB_REPOSITORY_VISIBILITY','private'),('RUNNER_ENVIRONMENT','self-hosted'),('RUNNER_OS','Windows'),('GITHUB_ACTOR','other'),('GITHUB_TRIGGERING_ACTOR','other'),('GITHUB_EVENT_NAME','workflow_dispatch'),('GITHUB_REF','refs/heads/main'),('GITHUB_REF','refs/heads/journey-android-other'),('GITHUB_WORKFLOW_REF',linux.REPOSITORY+'/'+linux.WORKFLOW+'@'+linux.REF),('GITHUB_RUN_ATTEMPT','2'),('GITHUB_SHA','f'*40)]:
    try: d.pinned_baseline(dict(os.environ,**{key:bad}))
    except Exception: pass
    else: raise AssertionError('admitted changed '+key)
request=(a.ROOT/a.REQUEST).read_bytes();value=json.loads(request)
for key,bad in [('schema',True),('requestId',linux.REQUEST_ID),('baseCommit',linux.BASE),('sourceStateSha256','e'*64),('selectionSha256','f'*64),('image','other'),('extra',1)]:
    changed=json.dumps(dict(value,**{key:bad})).encode()
    try: a.validate(os.environ,json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes()),os.environ['GITHUB_SHA'],[a.BASE],changed,changed,False,[a.REQUEST],value['sourceStateSha256'],value['selectionSha256'])
    except Exception: pass
    else: raise AssertionError('admitted changed request '+key)
for present,changed in [(True,[a.REQUEST]),(False,[])]:
    try: a.validate(os.environ,json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes()),os.environ['GITHUB_SHA'],[a.BASE],request,request,present,changed,value['sourceStateSha256'],value['selectionSha256'])
    except Exception: pass
    else: raise AssertionError('admitted replay')
""")

    def test_extra_git_parent_and_committed_wrong_nonce_are_rejected(self):
        self.script("""
subprocess.run(['git','config','user.name','Host fixture'],check=True)
subprocess.run(['git','config','user.email','fixture@example.invalid'],check=True)
request_path=a.ROOT/a.REQUEST
value=json.loads(request_path.read_bytes());value['requestId']='wrong-one-use-nonce'
request_path.write_text(json.dumps(value))
subprocess.run(['git','add',a.REQUEST],check=True)
subprocess.run(['git','commit','--quiet','--amend','--no-edit'],check=True)
head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()
os.environ['GITHUB_SHA']=head
path=Path(os.environ['GITHUB_EVENT_PATH']);event=json.loads(path.read_bytes());event['after']=head;event['head_commit']['id']=head;path.write_text(json.dumps(event))
for gate in (lambda:a.dispatch(),lambda:d.pinned_baseline(os.environ)):
    try: gate()
    except ValueError as error: assert str(error)=='ANDROID_REQUEST'
    else: raise AssertionError('committed wrong nonce admitted')
value['requestId']=a.REQUEST_ID;request_path.write_text(json.dumps(value))
subprocess.run(['git','add',a.REQUEST],check=True);subprocess.run(['git','commit','--quiet','--amend','--no-edit'],check=True)
parent=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()
subprocess.run(['git','commit','--quiet','--allow-empty','-m','Unexpected extra descendant'],check=True)
head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip();os.environ['GITHUB_SHA']=head
event.update(before=parent,after=head);event['head_commit']['id']=head;path.write_text(json.dumps(event))
for gate in (lambda:a.dispatch(),lambda:d.pinned_baseline(os.environ)):
    try: gate()
    except ValueError as error: assert str(error)=='ANDROID_PARENT'
    else: raise AssertionError('extra Git parent admitted')
""")

    def test_legacy_report_and_unknown_refs_do_not_inherit_ambient_android(self):
        self.script("""
identity=dict(GITHUB_SHA=os.environ['GITHUB_SHA'],GITHUB_RUN_ID=os.environ['GITHUB_RUN_ID'],GITHUB_RUN_ATTEMPT='1')
assert d.admission(identity) is linux
assert d.admission(dict(identity,GITHUB_REF=linux.REF)) is linux
assert d.admission(dict(identity,GITHUB_REF='refs/heads/arbitrary')) is linux
report=c.blank(identity)
assert report['requestId']==linux.REQUEST_ID and c.validate_report(report)
assert not c.validate_report(report,os.environ)
# Existing Linux pure identity contract remains closed under the same Android ambient environment.
import test_journey_tracer_dispatch as old
head='a'*40;env=old.fixture_env(head);request=dict(schema=1,requestId=linux.REQUEST_ID,baseCommit=linux.BASE,sourceStateSha256='b'*64,selection=linux.SELECTION,selectionSha256='c'*64,shortEvidence=linux.SHORT)
raw=json.dumps(request).encode()
assert linux.validate(env,old.fixture_event(head,linux.BASE),head,[linux.BASE],raw,raw,False,list(linux.CHANGED_FILES),'b'*64,'c'*64)==request
""")


if __name__ == '__main__':
    unittest.main()

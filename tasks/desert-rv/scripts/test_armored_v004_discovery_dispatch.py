"""Synthetic offline contracts in real temporary Git repositories; never native evidence."""
import copy, importlib.util, io, json, os, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
import armored_v004_discovery_dispatch as d
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'art/import-candidate'))

def encoded(obj): return (json.dumps(obj,indent=2)+'\n').encode()
def contract():
    return dict(schema=1,mode='DISCOVERY_ONLY',scope='FULL_CANDIDATE',id=d.CONTRACT_ID,
        kind='armored',repository=d.REPOSITORY,sourceCommit='e'*40,
        runUrl='https://github.com/'+d.REPOSITORY+'/actions/runs/123',artifactId=456,
        artifactName='armored-v004-r1-technical-source-123-1',artifactSha256='a'*64,
        files=[dict(file=name,sha256='b'*64) for name in sorted(d.INPUT_FILES)])
def environment(head):
    return dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=d.REPOSITORY,
        GITHUB_REPOSITORY_VISIBILITY='public',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',
        GITHUB_ACTOR=d.OWNER,GITHUB_TRIGGERING_ACTOR=d.OWNER,GITHUB_REF='refs/heads/main',
        GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@refs/heads/main',
        GITHUB_SHA=head,GITHUB_WORKFLOW_SHA=head,GITHUB_RUN_ID='789',GITHUB_RUN_ATTEMPT='1')
def event(base,head):
    return dict(before=base,after=head,ref='refs/heads/main',created=False,deleted=False,forced=False,
        repository=dict(full_name=d.REPOSITORY,private=False,fork=False,default_branch='main',visibility='public',owner=dict(login=d.OWNER)),
        head_commit=dict(id=head),sender=dict(login=d.OWNER))

class RealGitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.git('init','-q');self.git('config','user.email','offline-fixture@example.invalid');self.git('config','user.name','Offline fixture')
        self.write('fixture-baseline.txt',b'EXPLICIT SYNTHETIC FIXTURE. NO NATIVE PROOF.\n')
        self.write(d.SOURCE_STATE,b'EXPLICIT SYNTHETIC BEFORE STATE')
        prior={}
        for path in d.PAYLOAD_PATHS:
            if path.endswith(('prepare_runner.sh','verify_evidence.py')):
                raw=b'EXPLICIT SYNTHETIC BEFORE SOURCE';self.write(path,raw);prior[path]=d.sha(raw)
            else:prior[path]=None
        self.commit('fixture baseline');self.base=self.git('rev-parse','HEAD')
        self.c=contract();self.craw=encoded(self.c)
        self.patches=patch.multiple(d,BASE=self.base,PRODUCER_COMMIT=self.c['sourceCommit'],CONTRACT_SHA=d.sha(self.craw));self.patches.start();self.addCleanup(self.patches.stop)
        for path in d.PAYLOAD_PATHS:self.write(path,self.craw if path==d.CONTRACT else ('EXPLICIT SYNTHETIC AFTER '+path).encode())
        self.state=b'EXPLICIT SYNTHETIC SOURCE STATE';self.write(d.SOURCE_STATE,self.state)
        self.manifest=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=self.base,files=[dict(path=p,sha256=d.sha((self.root/p).read_bytes()),priorSha256=prior[p],size=(self.root/p).stat().st_size,mode='100644') for p in sorted(d.PAYLOAD_PATHS)])
        self.mraw=encoded(self.manifest);self.write(d.MANIFEST,self.mraw)
        self.request=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=self.base,contractSha256=d.CONTRACT_SHA,filesManifestSha256=d.sha(self.mraw),sourceStateSha256=d.sha(self.state))
        self.rraw=encoded(self.request);self.write(d.REQUEST,self.rraw)
        self.commit('fixture exact request');self.head=self.git('rev-parse','HEAD');self.env=environment(self.head);self.event=event(self.base,self.head)
        self.event_path=self.root/'fixture-event.json';self.flush_event();self.env['GITHUB_EVENT_PATH']=str(self.event_path)
    def git(self,*args):return subprocess.check_output(['git',*args],cwd=self.root,stderr=subprocess.DEVNULL,text=True).strip()
    def commit(self,message):self.git('add','-A');self.git('commit','-qm',message)
    def write(self,name,raw):p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    def flush_event(self):self.event_path.write_bytes(encoded(self.event))
    def verify(self):return d.verify(self.root,self.env)
    def reject(self,code):
        with self.assertRaisesRegex((ValueError,subprocess.CalledProcessError),code):self.verify()
    def pure(self,**kw):
        args=dict(env=self.env,event=self.event,head=self.head,parents=[self.base],request_raw=self.rraw,
            tracked_request=self.rraw,request_in_parent=False,changed=list(d.PAYLOAD_PATHS|{d.REQUEST,d.MANIFEST,d.SOURCE_STATE}),manifest_raw=self.mraw,state_raw=self.state,contract_raw=self.craw)
        args.update(kw);return d.validate(**args)
    def test_real_git_positive(self):self.assertEqual(self.c,self.verify())
    def test_unfinalized_parent_rejected(self):
        with patch.object(d,'BASE','UNRESOLVED_FINAL_PARENT_COMMIT'):self.reject('UNFINALIZED_PARENT')
    def test_unfinalized_producer_contract_rejected(self):
        for name in ('PRODUCER_COMMIT','CONTRACT_SHA'):
            with self.subTest(name=name),patch.object(d,name,'UNRESOLVED'):
                with self.assertRaisesRegex(ValueError,'UNFINALIZED_PRODUCER_CONTRACT'):d.parse_contract(self.craw)
    def test_real_environment_matrix(self):
        cases={'GITHUB_ACTIONS':'false','GITHUB_REPOSITORY':'other/repo','GITHUB_REPOSITORY_VISIBILITY':'private',
            'RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Windows','GITHUB_ACTOR':'other','GITHUB_TRIGGERING_ACTOR':'other',
            'GITHUB_REF':'refs/heads/other','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_WORKFLOW_REF':d.REPOSITORY+'/.github/workflows/desert-rv-candidate-art-import.yml@refs/heads/main',
            'GITHUB_SHA':'f'*40,'GITHUB_WORKFLOW_SHA':'f'*40,'GITHUB_RUN_ID':'0','GITHUB_RUN_ATTEMPT':'2'}
        for key,value in cases.items():
            with self.subTest(key=key),patch.dict(self.env,{key:value}),self.assertRaises(ValueError):self.verify()
    def test_event_identity_matrix(self):
        mutations=[('before','f'*40),('after','f'*40),('ref','refs/heads/other'),('created',True),('deleted',True),('forced',True)]
        for key,value in mutations:
            with self.subTest(key=key):
                ev=copy.deepcopy(self.event);ev[key]=value
                with self.assertRaises(ValueError):self.pure(event=ev)
    def test_private_fork_default_owner_sender_and_head(self):
        for section,key,value in [('repository','private',True),('repository','fork',True),('repository','default_branch','other'),('repository','owner',{'login':'other'}),('sender','login','other'),('head_commit','id','f'*40)]:
            ev=copy.deepcopy(self.event);ev[section][key]=value
            with self.subTest(section=section,key=key),self.assertRaises(ValueError):self.pure(event=ev)
    def test_merge_or_wrong_parent(self):
        for parents in ([],[self.base,'e'*40],['f'*40]):
            with self.subTest(parents=parents),self.assertRaisesRegex(ValueError,'PARENT'):self.pure(parents=parents)
    def test_request_cannot_exist_in_parent(self):
        with self.assertRaisesRegex(ValueError,'REQUEST_GIT'):self.pure(request_in_parent=True)
    def test_request_worktree_tamper(self):self.write(d.REQUEST,self.rraw+b' ');self.reject('TRACKED_CONTROL')
    def test_manifest_worktree_tamper(self):self.write(d.MANIFEST,self.mraw+b' ');self.reject('TRACKED_CONTROL')
    def test_contract_worktree_tamper(self):self.write(d.CONTRACT,self.craw+b' ');self.reject('TRACKED_CONTROL')
    def test_source_state_worktree_tamper(self):self.write(d.SOURCE_STATE,self.state+b' ');self.reject('TRACKED_CONTROL')
    def test_source_payload_tamper(self):self.write('tasks/desert-rv/scripts/prepare_runner.sh',b'TAMPER');self.reject('PAYLOAD_BYTES')
    def test_symlink_control_rejected(self):
        path=self.root/d.CONTRACT;path.unlink();path.symlink_to(self.event_path);self.reject('INPUT_FILE')
    def test_executable_control_rejected(self):
        self.git('update-index','--chmod=+x',d.REQUEST);self.git('commit','--amend','--no-edit','-q')
        self.head=self.git('rev-parse','HEAD');self.env.update(GITHUB_SHA=self.head,GITHUB_WORKFLOW_SHA=self.head);self.event=event(self.base,self.head);self.flush_event();self.reject('GIT_MODE')
    def test_extra_tracked_file_rejected(self):
        self.write('unrelated.txt',b'NO');self.git('add','unrelated.txt');self.git('commit','--amend','--no-edit','-q')
        self.head=self.git('rev-parse','HEAD');self.env.update(GITHUB_SHA=self.head,GITHUB_WORKFLOW_SHA=self.head);self.event=event(self.base,self.head);self.flush_event();self.reject('CHANGED_SET')
    def test_prior_bytes_rejected(self):
        m=copy.deepcopy(self.manifest);m['files'][0]['priorSha256']='c'*64
        self.write(d.MANIFEST,encoded(m));r=copy.deepcopy(self.request);r['filesManifestSha256']=d.sha(encoded(m));self.write(d.REQUEST,encoded(r))
        self.git('add',d.MANIFEST,d.REQUEST);self.git('commit','--amend','--no-edit','-q');self.head=self.git('rev-parse','HEAD')
        self.env.update(GITHUB_SHA=self.head,GITHUB_WORKFLOW_SHA=self.head);self.event=event(self.base,self.head);self.flush_event();self.reject('PRIOR_BYTES')
    def test_json_duplicate_and_nonfinite(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'[]\x00'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):d.decode(raw)
    def test_contract_scope_and_old_prefix_rejected(self):
        for key,value in [('scope','PARTIAL_DIAGNOSTIC_NOT_FULL'),('mode','STRICT_BINDING'),('kind','pouncer'),('artifactId',True),('artifactName','armored-technical-123-1'),('sourceCommit','f'*40),('neutralBounds',{})]:
            c=copy.deepcopy(self.c);c[key]=value;raw=encoded(c)
            with self.subTest(key=key),patch.object(d,'CONTRACT_SHA',d.sha(raw)),self.assertRaises(ValueError):d.parse_contract(raw)
        c=copy.deepcopy(self.c);c['files'][0]['file']='technical/'+c['files'][0]['file'];raw=encoded(c)
        with patch.object(d,'CONTRACT_SHA',d.sha(raw)),self.assertRaises(ValueError):d.parse_contract(raw)
    def test_no_metadata_environment_is_spoofed(self):
        workflow=(Path(__file__).resolve().parents[3]/d.WORKFLOW).read_text()
        self.assertNotIn('workflow_dispatch:',workflow)
        self.assertNotIn('GITHUB_EVENT_NAME:',workflow)
        self.assertNotIn('GITHUB_SHA:',workflow)
        self.assertIn('fetch-depth: 2',workflow)
        self.assertIn('GITHUB_REPOSITORY_VISIBILITY: ${{ github.event.repository.visibility }}',workflow)
        self.assertIn('customParameters: -assemblyNames DesertRV.CandidateArtTests -force-glcore -job-worker-count 2',workflow)
        self.assertNotIn('-testFilter',workflow)
        self.assertIn("steps.exact_native.outcome == 'success'",workflow)
        self.assertIn('verify_output.py --native "$NATIVE_RESULT" --protected "$PROTECTED_RESULT"',workflow)
    def workflow_env(self,text=None,step_id='request'):
        import yaml
        workflow=text or (Path(__file__).resolve().parents[3]/d.WORKFLOW).read_text()
        document=yaml.load(workflow,Loader=yaml.BaseLoader);job=document['jobs']['import']
        context={'github':{'repository':d.REPOSITORY,'event':self.event},'steps':{'request':{'outputs':{'contract':d.CONTRACT,'contract_sha256':d.CONTRACT_SHA}}}}
        env={k:v for k,v in self.env.items() if k!='GITHUB_REPOSITORY_VISIBILITY'}
        step=next(s for s in job['steps'] if s.get('id')==step_id)
        def expand(value):
            if not value.startswith('${{ '):return value
            obj=context
            for piece in value[4:-3].split('.'):
                obj=obj.get(piece,'') if isinstance(obj,dict) else ''
            return str(obj)
        for scope in (document,job,step):
            for key,value in (scope.get('env') or {}).items():env[key]=expand(value)
        return env
    def test_actual_yaml_context_and_git_positive(self):
        env=self.workflow_env();self.assertEqual('public',env['GITHUB_REPOSITORY_VISIBILITY'])
        self.assertEqual('push',env['GITHUB_EVENT_NAME']);self.assertEqual(self.c,d.verify(self.root,env))
    def test_missing_or_wrong_visibility_context_fails_real_helper(self):
        workflow=(Path(__file__).resolve().parents[3]/d.WORKFLOW).read_text()
        for text in (workflow.replace('      GITHUB_REPOSITORY_VISIBILITY: ${{ github.event.repository.visibility }}\n',''),workflow.replace('github.event.repository.visibility','github.repository.visibility')):
            with self.subTest(text=text[-50:]),self.assertRaisesRegex(ValueError,'REPOSITORY'):d.verify(self.root,self.workflow_env(text))
    def make_input(self):
        from PIL import Image
        # Real ZIP/PNG serialization with synthetic FBX/metadata bytes, never Blender or Unity evidence.
        png=io.BytesIO();Image.new('RGB',(1024,1024),(80,60,40)).save(png,format='PNG')
        files={name:(png.getvalue() if name.endswith('.png') else b'EXPLICIT SYNTHETIC FBX; NOT UNITY INPUT') for name in d.INPUT_FILES}
        art=b'EXPLICIT SYNTHETIC ART SOURCE MANIFEST';execution=b'EXPLICIT SYNTHETIC EXECUTION MANIFEST'
        self.addCleanup(patch.stopall)
        patch.object(d,'ART_MANIFEST_SHA',d.sha(art)).start();patch.object(d,'EXECUTION_MANIFEST_SHA',d.sha(execution)).start()
        declaration=dict(scope='FULL_CANDIDATE',status='FULL_SOURCE_ASSETS_NOT_UNITY_APPROVAL',errors=[],artSourceCommit=d.ART_SOURCE_COMMIT,executionCommit=d.PRODUCER_COMMIT,runId='123',sourceManifestSha256=d.ART_MANIFEST_SHA,executionManifestSha256=d.EXECUTION_MANIFEST_SHA,visualApproved=False,unityVerified=False)
        directory=self.root/'tasks/desert-rv/unity/CandidateImportInput';directory.mkdir(parents=True)
        with zipfile.ZipFile(directory/'artifact.zip','w') as archive:
            for name,raw in {**files,'source-manifest.json':art,'execution-manifest.json':execution,'producer-contract.json':encoded(declaration)}.items():archive.writestr(name,raw)
        self.c['artifactSha256']=d.sha((directory/'artifact.zip').read_bytes())
        self.c['files']=[dict(file=name,sha256=d.sha(raw)) for name,raw in sorted(files.items())]
        self.craw=encoded(self.c);patch.object(d,'CONTRACT_SHA',d.sha(self.craw)).start();self.write(d.CONTRACT,self.craw)
        for item in self.manifest['files']:
            if item['path']==d.CONTRACT:item.update(sha256=d.sha(self.craw),size=len(self.craw))
        self.mraw=encoded(self.manifest);self.write(d.MANIFEST,self.mraw)
        self.request.update(contractSha256=d.CONTRACT_SHA,filesManifestSha256=d.sha(self.mraw));self.rraw=encoded(self.request);self.write(d.REQUEST,self.rraw)
        self.git('add',d.CONTRACT,d.MANIFEST,d.REQUEST);self.git('commit','--amend','--no-edit','-q');self.head=self.git('rev-parse','HEAD')
        self.env.update(GITHUB_SHA=self.head,GITHUB_WORKFLOW_SHA=self.head);self.event=event(self.base,self.head);self.flush_event()
        run=dict(id=123,repository=dict(full_name=d.REPOSITORY,private=False,fork=False),head_sha=d.PRODUCER_COMMIT,status='completed',conclusion='success',event='push',path=d.PRODUCER_WORKFLOW,head_branch='main',run_attempt=1,actor=dict(login=d.OWNER),triggering_actor=dict(login=d.OWNER))
        artifact=dict(id=456,name=self.c['artifactName'],expired=False,workflow_run=dict(id=123,head_sha=d.PRODUCER_COMMIT),digest='sha256:'+self.c['artifactSha256'])
        for name,raw in [('contract.json',self.craw),('run.json',encoded(run)),('artifact.json',encoded(artifact))]:(directory/name).write_bytes(raw)
        (directory/'payload').mkdir()
        for name,raw in files.items():(directory/'payload'/name).write_bytes(raw)
        return directory,run,artifact
    def test_actual_zip_stager_and_full_declaration(self):
        self.make_input();self.assertEqual(self.c,d.verify_input(self.root,self.env))
    def test_actual_upstream_event_and_rerun_rejected(self):
        directory,run,_=self.make_input()
        for key,value in [('event','workflow_dispatch'),('run_attempt',2),('path','.github/workflows/old.yml'),('head_sha','f'*40),('conclusion','failure')]:
            bad=copy.deepcopy(run);bad[key]=value;(directory/'run.json').write_bytes(encoded(bad))
            with self.subTest(key=key),self.assertRaises(ValueError):d.verify_input(self.root,self.env)
    def test_payload_mutation_rejected(self):
        directory,_,_=self.make_input();(directory/'payload/bulwark-basecolor.png').write_bytes(b'TAMPER')
        with self.assertRaisesRegex(ValueError,'STAGED_PAYLOAD'):d.verify_input(self.root,self.env)

class NarrowRoutingTests(unittest.TestCase):
    def test_runner_routes_are_exclusive_before_any_license_or_cleanup(self):
        source=(Path(__file__).parent/'prepare_runner.sh').read_text()
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);(p/'prepare_runner.sh').write_text(source)
            for name in ('environment_v4_r2_dispatch','environment_v4_dispatch','armored_v004_discovery_dispatch','journey_rebuild_dispatch'):
                (p/(name+'.py')).write_text('raise SystemExit("EXACT_ROUTE_'+name+'")\n')
            for workflow,wanted in [(d.WORKFLOW,'armored_v004_discovery_dispatch'),('.github/workflows/desert-rv-environment-v4-r2.yml','environment_v4_r2_dispatch'),('.github/workflows/desert-rv-environment-v4.yml','environment_v4_dispatch'),('.github/workflows/desert-rv-journey-rebuild.yml','journey_rebuild_dispatch'),('.github/workflows/other.yml','journey_rebuild_dispatch')]:
                env=dict(os.environ,**environment('d'*40));env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/'+workflow+'@refs/heads/main'
                result=subprocess.run(['bash',str(p/'prepare_runner.sh')],env=env,text=True,capture_output=True)
                self.assertNotEqual(result.returncode,0);self.assertIn('EXACT_ROUTE_'+wanted,result.stderr)
    def test_source_guard_uses_exact_new_route(self):
        import verify_evidence as v
        env=environment('d'*40)
        with patch.dict(os.environ,env),patch.object(d,'verify',side_effect=ValueError('NEW_ROUTE_ONLY')):
            with self.assertRaisesRegex(ValueError,'NEW_ROUTE_ONLY'):v.guard()
    def test_original_source_guard_routes_remain(self):
        import types,verify_evidence as v
        for workflow,name in [('.github/workflows/desert-rv-environment-v4-r2.yml','environment_v4_r2_dispatch'),('.github/workflows/desert-rv-environment-v4.yml','environment_v4_dispatch'),('.github/workflows/desert-rv-journey-rebuild.yml','journey_rebuild_dispatch')]:
            env=environment('d'*40);env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/'+workflow+'@refs/heads/main'
            def stop(*_):raise ValueError('ORIGINAL_ROUTE')
            with patch.dict(os.environ,env),patch.dict('sys.modules',{name:types.SimpleNamespace(verify=stop)}),self.assertRaisesRegex(ValueError,'ORIGINAL_ROUTE'):v.guard()

if __name__=='__main__':unittest.main(verbosity=2)

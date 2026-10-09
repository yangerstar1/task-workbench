"""Filesystem exporter/counterexample fixtures, never evidence of native Unity acceptance."""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'import-candidate'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/rendered'))
import generated_export as g
import prepared_source as p
import test_prepared_source as fixtures

COMMIT='a'*40;RUN='https://github.com/yangerstar1/task-workbench/actions/runs/123'
class GeneratedExportTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.PreparedSourceTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.env=mock.patch.dict(os.environ,GITHUB_SHA=COMMIT,GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1');self.env.start();self.addCleanup(self.env.stop)
        self.fx=self.fixture.make_native_journey_fixture();self.generated=dict(self.fixture.added)
        self.fx['parametersSha256']='f'*64
        self.fixture.write('Packages/packages-lock.json',json.dumps({'dependencies':{'com.unity.render-pipelines.universal':{'version':'17.3.0','source':'builtin'}}}).encode())
        self.fixture.files['tasks/desert-rv/unity/Packages/packages-lock.json']=p.PROJECT/'Packages/packages-lock.json'
        self.source={name[len('tasks/desert-rv/unity/'):]:g.sha(path) for name,path in self.fixture.files.items()}
        self.fixture.source={'files':[dict(path=n,sha256=g.sha(f),size=f.stat().st_size) for n,f in self.fixture.files.items()],'restoredFiles':[]}
        (p.TASK/'SOURCE-STATE.json').write_text(json.dumps(self.fixture.source));self.identity=p.original.identity()
        self.fixture.dirs['Packages']=sorted(p.walk(p.PROJECT/'Packages')[1])
        self.state={'completed':[],'assetFiles':{}}
        for kind in g.KINDS:
            folder=p.TASK/'journey-preparation-export'/kind;folder.mkdir(parents=True);records=[]
            for name in ('CandidateArtImports.meta','CandidateArtImports/'+kind+'.meta','CandidateArtImports/'+kind+'/Candidate.prefab','CandidateArtImports/'+kind+'/Candidate.prefab.meta'):
                data=b'shared-root' if name=='CandidateArtImports.meta' else ('synthetic-'+name).encode()
                original=self.fixture.write('Assets/DesertRV/'+name,data);dest=folder/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
                records.append(g.record(dest,name));self.state['assetFiles']['Assets/DesertRV/'+name]=g.sha(original)
            receipt=dict(status='STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED',approved=False,kind=kind,importCommit=COMMIT,importRunUrl=RUN,files=records,nativeXmlSha256='c'*64,nativeCases=26)
            (folder/'receipt.json').write_text(json.dumps(receipt));self.state['completed'].append(dict(kind=kind,exportReceiptSha256=g.sha(folder/'receipt.json')))
        # Synthetic native rows reproduce the selected declarations; these bytes are never a Unity result.
        plan=json.loads(Path(__file__).with_name('three-strict-candidates.json').read_text());plan['spawnRootHeightSource']=g.GROUND_SOURCE
        selection=p.TASK/'art/journey-preparation/fixture.json';selection.parent.mkdir(parents=True,exist_ok=True);selection.write_text(json.dumps(plan))
        self.state.update(plan=copy.deepcopy(plan),selection=str(selection.relative_to(p.ROOT)),selectionSha256=g.sha(selection))
        ready=dict(sourceCommit=COMMIT,selectionSha256=self.state['selectionSha256'],spawnRootHeightSource=g.GROUND_SOURCE,integration=copy.deepcopy(plan['integration']))
        ready_path=self.fixture.write('JourneyEvidence/JourneyPreparation/ready-input.json',json.dumps(ready).encode());self.state['readyInputSha256']=g.sha(ready_path)
        self.grounding=dict(schema=1,status='ACTUAL_NATIVE_ROOT_GROUNDING_UNREVIEWED',sourceCommit=COMMIT,source=g.GROUND_SOURCE,
            selectionSha256=self.state['selectionSha256'],readyInputSha256=self.state['readyInputSha256'],approved=False,rows=[])
        for region in plan['integration']['regions']:
            for row in region['guards']+region['roadBeasts']+[enemy for wave in region['waves'] for enemy in wave['enemies']]:
                point=dict(row['position'],y=-.04)
                self.grounding['rows'].append(dict(id=row['id'],kind=row['kind'],region=region['region'],scene=g.REGION_SCENES[region['region']],
                    floor='Route foundation',layer=0,declaredPosition=dict(row['position']),resolvedPosition=dict(point),hitPoint=dict(point),hitNormal=dict(x=0,y=1,z=0),yaw=row['yaw']))
        ground_path=self.fixture.write(g.GROUND_PATH,json.dumps(self.grounding).encode())
        self.native=dict(schema=3,status='ACTUAL_NATIVE_JOURNEY_ASSETS_UNREVIEWED',sourceCommit=COMMIT,unityVersion=g.UNITY,importRunUrl=RUN,approved=False,
            spawnGrounding=dict(path=g.GROUND_PATH,sha256=g.sha(ground_path)),
            files=[dict(path=n,sha256=h) for n,h in self.generated.items()],dependencies=[])
        for name in sorted(set(self.generated)|set(self.state['assetFiles'])|{'Assets/Original.cs','Assets/Original.cs.meta'}):
            if name.endswith('.meta') and not (p.PROJECT/name[:-5]).is_file():continue
            self.native['dependencies'].append(dict(g.record(p.PROJECT/name,name),kind='asset',packageName='',packageVersion=''))
        for name in ('Packages/com.unity.render-pipelines.universal/Shaders/Particles/ParticlesUnlit.shader','Packages/com.unity.render-pipelines.universal/Shaders/Particles/ParticlesUnlit.shader.meta'):
            self.native['dependencies'].append(dict(path=name,sha256='d'*64,bytes=123,kind='package',packageName='com.unity.render-pipelines.universal',packageVersion='17.3.0'))
        self.native['dependencies'].append(dict(path='Resources/unity_builtin_extra',sha256='',bytes=0,kind='builtin',packageName='',packageVersion=''))
        self.scope=dict(label='EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT',sourceCommit=COMMIT,files=[dict(path=p.JOURNEY+'/JourneyBootstrap.unity',sha256=self.generated[p.JOURNEY+'/JourneyBootstrap.unity'],dependencyHash='1'*32,kind='scene')])
        outputs=[dict(path=p.JOURNEY+'/'+n,sha256=self.generated[p.JOURNEY+'/'+n],dependencyHash='1'*32,dependencySha256='2'*64) for n in ('JourneyBootstrap.unity','FirstStation.unity','Scrapyard.unity','NightBeacon.unity','JourneyContent.asset')]
        self.integration=dict(status='STRICT_CANDIDATES_BOUND_UNREVIEWED',sourceCommit=COMMIT,candidateOnly=True,protectedSourcesUnchanged=True,rolledBack=False,failures=[],visualReviewed=False,gameplayReviewed=False,audioAuditioned=False,outputs=outputs)
        self.flush()
        def verify():
            p.verify_original(self.identity)
            added={**self.state['assetFiles'],**p.journey_files(self.fx)}
            p.verify_asset_union(self.fixture.source,self.fixture.dirs,added)
            paths=[p.PROJECT/'JourneyEvidence/JourneyPreparation/authored-assets.json',p.PROJECT/'JourneyEvidence/journey-diagnostic-scope.json',p.PROJECT/g.GROUND_PATH]
            return dict(addedAssets=added,dataPins=[dict(path=str(path.relative_to(p.ROOT)),sha256=g.sha(path)) for path in paths])
        self.prepared=SimpleNamespace(verify=verify,journey_files=p.journey_files,STATE=p.STATE,PROOF=p.PROOF,PROJECT=p.PROJECT,TASK=p.TASK)
    def flush(self):
        self.fixture.write(g.GROUND_PATH,json.dumps(self.grounding).encode())
        for path,data in [('JourneyEvidence/JourneyPreparation/state.json',self.state),('JourneyEvidence/JourneyPreparation/authored-assets.json',self.native),('JourneyEvidence/JourneyPreparation/prepared-source.json',{'fixture':'not-native'}),('JourneyEvidence/journey-candidate-fx.json',self.fx),('JourneyEvidence/journey-candidate-integration.json',self.integration),('JourneyEvidence/journey-diagnostic-scope.json',self.scope)]:self.fixture.write(path,json.dumps(data).encode())
    def export(self):return g.export_generated(self.prepared,'b'*64)
    def closure(self):return g.native_closure(self.native,self.generated,self.source,self.state['assetFiles'],p.PROJECT,COMMIT,RUN)
    def reject(self,code):
        self.flush()
        with self.assertRaisesRegex(Exception,code):self.export()
        self.assertFalse((p.TASK/'journey-preparation-export/generated').exists())
    def test_exact_native_fixture_is_persisted_without_private_package_bytes(self):
        result=self.export();folder=p.TASK/'journey-preparation-export/generated';receipt=g.read(folder/'receipt.json')
        self.assertEqual(result['sha256'],g.sha(folder/'receipt.json'));g.verify_staged_inventory(folder,receipt['files'],result['sha256'])
        self.assertEqual({r['path'] for r in receipt['files']},set(self.generated)|{'native-authored-assets.json','diagnostic-scope-evidence.json',g.GROUND_EXPORT});self.assertFalse(receipt['approved']);self.assertFalse(receipt['scopeReusable'])
        self.assertEqual({r['owner'] for r in receipt['dependencies']},{'source','strict','generated','official-package','unity-builtin'})
        self.assertFalse(any('Package' in str(f.relative_to(folder)) for f in folder.rglob('*')))
        for row in receipt['files']:
            if row['path'].startswith('Assets/'):self.assertEqual((folder/row['path']).read_bytes(),(p.PROJECT/row['path']).read_bytes())
        self.assertEqual(g.sha(folder/receipt['nativeManifestPath']),receipt['nativeManifestSha256'])
        self.assertEqual(g.sha(folder/receipt['diagnosticScopeEvidencePath']),receipt['diagnosticScopeSha256'])
        self.assertEqual(g.sha(folder/receipt['spawnGroundingPath']),receipt['spawnGroundingSha256'])
    def test_fresh_consumer_can_reconstruct_assets_and_meta_from_exact_three_bundles(self):
        self.export();public=p.TASK/'journey-preparation-export'
        with tempfile.TemporaryDirectory() as temporary:
            consumer=Path(temporary);files={}
            for kind in g.KINDS:
                folder=public/kind
                for row in g.read(folder/'receipt.json')['files']:
                    path='Assets/DesertRV/'+row['path'];data=(folder/row['path']).read_bytes()
                    self.assertTrue(path not in files or files[path]==data);files[path]=data
            for row in g.read(public/'generated/receipt.json')['files']:
                if row['path'].startswith('Assets/'):files[row['path']]=(public/'generated'/row['path']).read_bytes()
            for name,data in files.items():target=consumer/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            self.assertEqual({name:g.sha(consumer/name) for name in files},{**self.state['assetFiles'],**self.generated})
    def test_original_source_mutation_is_rejected(self):self.fixture.write('Assets/Original.cs',b'mutated');self.reject('ORIGINAL_CHANGED')
    def test_generated_meta_mutation_after_native_is_rejected(self):self.fixture.write(p.JOURNEY+'/FirstStation.unity.meta',b'mutated');self.reject('NATIVE_ASSET_SNAPSHOT_CHANGED')
    def test_generated_scene_meta_missing_is_rejected(self):(p.PROJECT/(p.JOURNEY+'/FirstStation.unity.meta')).unlink();self.reject('ADDITION_INVENTORY')
    def test_unlisted_generated_script_is_rejected(self):self.fixture.write(p.JOURNEY+'/Injected.cs');self.reject('ADDITION_INVENTORY')
    def test_unknown_dependency_is_rejected(self):
        self.native['dependencies'].append(dict(path='Assets/Unknown.asset',sha256='a'*64,bytes=1,kind='asset',packageName='',packageVersion=''));self.reject('UNKNOWN_OR_AMBIGUOUS')
    def test_native_float_schema_is_rejected(self):self.native['schema']=3.0;self.reject('NATIVE_ASSET_SNAPSHOT_CHANGED')
    def test_native_replaced_foundation_layout_is_omitted_without_changing_original(self):
        name=p.JOURNEY+'/Layout-123456.mat'
        for path in (name,name+'.meta'):
            self.fixture.add(path);self.generated[path]=g.sha(p.PROJECT/path);self.native['files'].append(dict(path=path,sha256=self.generated[path]))
        self.flush();self.export();folder=p.TASK/'journey-preparation-export/generated';receipt=g.read(folder/'receipt.json')
        self.assertEqual({r['path'] for r in receipt['omittedUnreferencedLayout']},{name,name+'.meta'})
        self.assertTrue((p.PROJECT/name).is_file());self.assertFalse((folder/name).exists())
        self.assertIn(name,{r['path'] for r in g.read(folder/receipt['nativeManifestPath'])['files']})
    def test_unreferenced_fx_is_rejected(self):
        self.native['dependencies']=[r for r in self.native['dependencies'] if not r['path'].endswith('MuzzleFlash.prefab')];self.reject('ROOT_DEPENDENCY_MISSING')
    def test_package_missing_meta_is_rejected(self):
        self.native['dependencies']=[r for r in self.native['dependencies'] if not (r['kind']=='package' and r['path'].endswith('.meta'))];self.reject('DEPENDENCY_META_MISSING')
    def test_native_unknown_field_is_rejected(self):self.native['rawLog']='private runner text';self.reject('NATIVE_IDENTITY')
    def test_native_approval_true_is_rejected(self):self.native['approved']=True;self.reject('NATIVE_IDENTITY')
    def test_native_old_run_is_rejected(self):self.native['importRunUrl']=RUN+'4';self.reject('NATIVE_IDENTITY')
    def test_native_old_commit_is_rejected(self):self.native['sourceCommit']='0'*40;self.reject('NATIVE_ASSET_SNAPSHOT_CHANGED')
    def test_dependency_absolute_path_is_rejected(self):self.native['dependencies'][0]['path']='/runner/private/file';self.reject('DEPENDENCY_PATH')
    def test_dependency_traversal_is_rejected(self):self.native['dependencies'][0]['path']='Assets/../private';self.reject('DEPENDENCY_PATH')
    def test_duplicate_dependency_is_rejected(self):self.native['dependencies'].append(copy.deepcopy(self.native['dependencies'][0]));self.reject('DEPENDENCY_PATH')
    def test_native_dependency_hash_mutation_is_rejected(self):self.native['dependencies'][0]['sha256']='0'*64;self.reject('DEPENDENCY_PIN_CHANGED')
    def test_native_dependency_size_mutation_is_rejected(self):self.native['dependencies'][0]['bytes']+=1;self.reject('DEPENDENCY_BYTES_CHANGED')
    def test_missing_root_dependency_is_rejected(self):self.native['dependencies']=[r for r in self.native['dependencies'] if r['path']!=p.JOURNEY+'/FirstStation.unity'];self.reject('ROOT_DEPENDENCY_MISSING')
    def test_missing_dependency_meta_is_rejected(self):self.native['dependencies']=[r for r in self.native['dependencies'] if r['path']!=p.JOURNEY+'/FirstStation.unity.meta'];self.reject('DEPENDENCY_META_MISSING')
    def test_unknown_builtin_is_rejected(self):self.native['dependencies'][-1]['path']='Library/private';self.reject('BUILTIN_IDENTITY')
    def test_package_version_drift_is_rejected(self):self.native['dependencies'][-2]['packageVersion']='99';self.reject('PACKAGE_VERSION')
    def test_package_unknown_name_is_rejected(self):self.native['dependencies'][-2]['packageName']='com.unity.unknown';self.reject('PACKAGE_IDENTITY')
    def test_package_private_physical_path_is_rejected(self):self.native['dependencies'][-2]['path']='CandidatePackageSnapshot/private';self.reject('PACKAGE_PATH')
    def test_source_symlink_is_rejected(self):
        path=p.PROJECT/'Assets/Original.cs';data=path.read_bytes();path.unlink();target=p.PROJECT/'Library/external';target.parent.mkdir();target.write_bytes(data);path.symlink_to(target);self.reject('SYMLINK|UNSAFE|linked evidence')
    def test_strict_receipt_hash_tamper_is_rejected(self):
        path=p.TASK/'journey-preparation-export/armored/receipt.json';path.write_text(path.read_text()+' ');self.reject('STRICT_RECEIPT_CHANGED')
    def test_strict_receipt_other_run_even_with_new_hash_is_rejected(self):
        path=p.TASK/'journey-preparation-export/armored/receipt.json';value=g.read(path);value['importRunUrl']=RUN+'4';path.write_text(json.dumps(value));self.state['completed'][0]['exportReceiptSha256']=g.sha(path);self.reject('STRICT_IDENTITY')
    def test_native_json_must_match_actual_sealed_proof_pin(self):
        original=self.prepared.verify
        def changed_pin():
            proof=original();proof['dataPins'][0]['sha256']='0'*64;return proof
        self.prepared.verify=changed_pin;self.reject('SEALED_JSON_CHANGED')
    def test_raw_native_evidence_copy_must_keep_exact_prevalidated_bytes(self):
        original=g.shutil.copyfile
        def corrupt(source,dest):
            result=original(source,dest)
            if Path(dest).name=='native-authored-assets.json':Path(dest).write_text('{"unexpected":"changed copy"}')
            return result
        with mock.patch.object(g.shutil,'copyfile',side_effect=corrupt):self.reject('EVIDENCE_COPY_CHANGED')
    def test_partial_copy_failure_never_publishes_generated_folder(self):
        original=g.shutil.copyfile;calls=[]
        def fail(source,dest):
            calls.append(dest)
            if len(calls)==3:raise OSError('fixture copy failure')
            return original(source,dest)
        with mock.patch.object(g.shutil,'copyfile',side_effect=fail):self.reject('fixture copy failure')
        self.assertFalse(list(p.STATE.parent.glob('generated-safe-*')))
    def test_post_copy_original_mutation_never_publishes_generated_folder(self):
        original=g.shutil.copyfile;changed=[]
        def mutate(source,dest):
            result=original(source,dest)
            if not changed:self.fixture.write('Assets/Original.cs',b'mutation during copy');changed.append(True)
            return result
        with mock.patch.object(g.shutil,'copyfile',side_effect=mutate):self.reject('ORIGINAL_CHANGED')
    def test_second_export_cannot_overwrite_existing_generated_bundle(self):
        self.export();before=g.sha(p.TASK/'journey-preparation-export/generated/receipt.json')
        with self.assertRaisesRegex(Exception,'DESTINATION_EXISTS'):self.export()
        self.assertEqual(before,g.sha(p.TASK/'journey-preparation-export/generated/receipt.json'))
    def test_scope_unknown_field_is_rejected(self):self.scope['rawLog']='private';self.reject('SCOPE_IDENTITY')
    def test_scope_unknown_pin_kind_is_rejected(self):self.scope['files'][0]['kind']='grant-build';self.reject('SCOPE_PIN')
    def test_unknown_empty_directory_is_rejected(self):(p.PROJECT/p.JOURNEY/'empty').mkdir();self.reject('DIRECTORY_UNION')
    def reject_grounding(self,code):
        # Re-pin synthetic bytes to exercise semantics beyond the separate immutable-byte gate.
        path=self.fixture.write(g.GROUND_PATH,json.dumps(self.grounding).encode())
        self.native['spawnGrounding']['sha256']=g.sha(path);self.reject(code)
    def test_grounding_missing_file_is_rejected(self):
        (p.PROJECT/g.GROUND_PATH).unlink()
        with self.assertRaises(Exception):self.export()
        self.assertFalse((p.TASK/'journey-preparation-export/generated').exists())
    def test_grounding_bytes_must_match_native_pin(self):
        path=p.PROJECT/g.GROUND_PATH;path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(Exception,'GROUNDING_NATIVE_HASH'):self.export()
    def test_grounding_native_pin_path_cannot_escape(self):self.native['spawnGrounding']['path']='../secret';self.reject('GROUNDING_NATIVE_PIN')
    def test_grounding_unknown_source_is_rejected(self):self.grounding['source']='manual-offset';self.reject_grounding('GROUNDING_IDENTITY')
    def test_grounding_approval_is_rejected(self):self.grounding['approved']=True;self.reject_grounding('GROUNDING_IDENTITY')
    def test_grounding_unknown_field_is_rejected(self):self.grounding['rawLog']='private';self.reject_grounding('GROUNDING_IDENTITY')
    def test_grounding_wrong_selection_hash_is_rejected(self):self.grounding['selectionSha256']='0'*64;self.reject_grounding('GROUNDING_SELECTION_PIN')
    def test_grounding_wrong_ready_hash_is_rejected(self):self.grounding['readyInputSha256']='0'*64;self.reject_grounding('GROUNDING_READY_PIN')
    def test_grounding_missing_row_is_rejected(self):self.grounding['rows'].pop();self.reject_grounding('GROUNDING_ROW_COUNT')
    def test_grounding_duplicate_row_is_rejected(self):self.grounding['rows'][1]=copy.deepcopy(self.grounding['rows'][0]);self.reject_grounding('GROUNDING_ROW_ID')
    def test_grounding_unknown_actor_is_rejected(self):self.grounding['rows'][0]['id']='unknown';self.reject_grounding('GROUNDING_ROW_ID')
    def test_grounding_wrong_scene_is_rejected(self):self.grounding['rows'][0]['scene']=g.REGION_SCENES[2];self.reject_grounding('GROUNDING_ROW_IDENTITY')
    def test_grounding_wrong_kind_is_rejected(self):self.grounding['rows'][0]['kind']='armored';self.reject_grounding('GROUNDING_ROW_IDENTITY')
    def test_grounding_arbitrary_floor_path_is_rejected(self):self.grounding['rows'][0]['floor']='/runner/private';self.reject_grounding('GROUNDING_FLOOR')
    def test_grounding_nonzero_layer_is_rejected(self):self.grounding['rows'][0]['layer']=1;self.reject_grounding('GROUNDING_FLOOR')
    def test_grounding_shallow_normal_is_rejected(self):self.grounding['rows'][0]['hitNormal']['y']=.89;self.reject_grounding('GROUNDING_NORMAL')
    def test_grounding_nonfinite_position_is_rejected(self):self.grounding['rows'][0]['hitPoint']['y']=float('inf');self.reject_grounding('NONFINITE_JSON')
    def test_grounding_boolean_position_is_rejected(self):self.grounding['rows'][0]['declaredPosition']['y']=False;self.reject_grounding('GROUNDING_FINITE')
    def test_grounding_changed_declared_position_is_rejected(self):self.grounding['rows'][0]['declaredPosition']['x']+=1;self.reject_grounding('GROUNDING_DECLARED_POSITION')
    def test_grounding_changed_yaw_is_rejected(self):self.grounding['rows'][0]['yaw']+=1;self.reject_grounding('GROUNDING_DECLARED_POSITION')
    def test_grounding_resolved_xz_cannot_move_spawn(self):self.grounding['rows'][0]['resolvedPosition']['x']+=.001;self.reject_grounding('GROUNDING_RESOLVED_POSITION')
    def test_grounding_resolved_y_must_equal_actual_hit(self):self.grounding['rows'][0]['resolvedPosition']['y']+=.001;self.reject_grounding('GROUNDING_RESOLVED_POSITION')
    def test_grounding_hit_xz_must_remain_on_declared_ray(self):self.grounding['rows'][0]['hitPoint']['x']+=.001;self.reject_grounding('GROUNDING_RESOLVED_POSITION')
    def test_grounding_hit_xz_accepts_native_ray_precision(self):
        self.grounding['rows'][0]['hitPoint']['x']+=.00001
        path=self.fixture.write(g.GROUND_PATH,json.dumps(self.grounding).encode());self.native['spawnGrounding']['sha256']=g.sha(path);self.flush();self.export()
    def test_grounding_state_rows_cannot_replace_original_selection(self):
        self.state['plan']['integration']['regions'][0]['guards'][0]['position']['x']+=1;self.reject('GROUNDING_DECLARATION_CHANGED')
    def test_grounding_copy_cannot_replace_prevalidated_raw_bytes(self):
        original=g.shutil.copyfile
        def corrupt(source,dest):
            result=original(source,dest)
            if Path(dest).name==g.GROUND_EXPORT:Path(dest).write_text('{"rawLog":"must not publish"}')
            return result
        with mock.patch.object(g.shutil,'copyfile',side_effect=corrupt):self.reject('EVIDENCE_COPY_CHANGED')
    def test_prepared_proof_has_exact_nine_pins_including_native_grounding(self):
        self.state.update(initialIdentity=self.identity,initialSourceDirectories=self.fixture.dirs);self.integration['protectedFiles']=[];self.flush();p.PROOF.unlink()
        with mock.patch.object(p,'verified_package_snapshot',return_value=None):
            p.seal();proof=p.verify();self.assertEqual(len(proof['dataPins']),9)
            name=str((p.PROJECT/g.GROUND_PATH).relative_to(p.ROOT));self.assertIn(name,{r['path'] for r in proof['dataPins']})
            proof['dataPins']=[r for r in proof['dataPins'] if r['path']!=name];p.PROOF.write_text(json.dumps(proof))
            with self.assertRaisesRegex(Exception,'EXACT_DATA_PINS'):p.verify()
if __name__=='__main__':unittest.main(verbosity=2)

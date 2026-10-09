"""Runs with standard Python only. Does not import bpy, execute Blender, or validate appearance."""
from collections import Counter
import cavity_geometry
import ast, hashlib, json, math, unittest, tempfile
from artifact_io import fresh_output
from pathlib import Path
import motion
HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'parameters.json').read_text())
class SourceTests(unittest.TestCase):
    def test_python_syntax(self):
        for p in HERE.glob('*.py'): ast.parse(p.read_text(),filename=p.name)
    def test_clip_contract(self):
        self.assertEqual(set(P['clips']),{'Idle','Walk','Windup','Attack','Recover','Hit','Death'})
        self.assertFalse(P['root_motion'])
    def test_reachability_and_ground_targets(self):
        samples=0
        for clip,duration in P['clips'].items():
            for i in range(round(duration*240)+1):
                p=motion.sample(clip,i/240)
                for k in motion.LEGS:
                    h=motion.add(motion.HIP[k],(0,0,p['z'])); f=p['feet'][k]; n=motion.knee(h,f,k,minimum_z=p.get('knee_clearance'))
                    self.assertAlmostEqual(motion.length(motion.sub(h,n)),motion.UPPER,places=8)
                    self.assertAlmostEqual(motion.length(motion.sub(f,n)),motion.LOWER,places=8)
                    self.assertGreaterEqual(f[2],motion.FOOT[k][2]-1e-9)
                    if p['contact'][k]: self.assertAlmostEqual(f[2],motion.FOOT[k][2],places=8)
                    samples+=1
        self.assertGreater(samples,7000)
    def test_clip_boundaries(self):
        for a,b in [('Windup','Attack'),('Attack','Recover'),('Recover','Idle'),('Hit','Idle')]:
            x=motion.sample(a,P['clips'][a]); y=motion.sample(b,0)
            for key in ('z','ram'): self.assertAlmostEqual(x[key],y[key],places=8)
            if (a,b) not in [('Attack','Recover'),('Recover','Idle')]: self.assertAlmostEqual(x['gate'],y['gate'],places=8)
            for k in motion.LEGS:
                for i in range(3): self.assertAlmostEqual(x['feet'][k][i],y['feet'][k][i],places=8)
    def test_loops(self):
        for clip in ('Idle','Walk','Attack'):
            a=motion.sample(clip,0); b=motion.sample(clip,P['clips'][clip])
            self.assertAlmostEqual(a['z'],b['z'])
            for k in motion.LEGS:
                for i in range(3): self.assertAlmostEqual(a['feet'][k][i],b['feet'][k][i])
    def test_world_stance_velocity(self):
        for clip,end in [('Walk',P['clips']['Walk']),('Attack',P['clips']['Attack'])]:
            for i in range(1,round(end*240)):
                ta=(i-1)/240; tb=i/240; a=motion.sample(clip,ta); b=motion.sample(clip,tb)
                for k in motion.LEGS:
                    if a['contact'][k] and b['contact'][k]:
                        ya=a['feet'][k][1]-motion.travel(clip,ta); yb=b['feet'][k][1]-motion.travel(clip,tb)
                        self.assertAlmostEqual(ya,yb,places=8)
    def test_windup_planted_compression(self):
        a=motion.sample('Windup',.6); b=motion.sample('Windup',P['clips']['Windup'])
        self.assertLess(b['z'],a['z']); self.assertEqual(a['feet'],b['feet'])
    def test_interrupt_position_continuity(self):
        for phase in (.07,.42,.91):
            a=motion.sample('Attack',phase); b=motion.interrupted(phase,0)
            self.assertEqual(a['feet'],b['feet']); self.assertEqual(a['z'],b['z'])
            for i in range(145):
                p=motion.interrupted(phase,i/240)
                for k,f in p['feet'].items():
                    self.assertEqual(f[:2],a['feet'][k][:2]); motion.knee(motion.add(motion.HIP[k],(0,0,p['z'])),f,k)
    def test_weakpoint_window_and_death_hold(self):
        self.assertEqual(motion.sample('Windup',1)['gate'],0)
        self.assertGreater(motion.sample('Recover',.8)['gate'],1)
        self.assertEqual(motion.sample('Recover',2)['gate'],P['gate_open_radians'])
        for i in range(481):
            self.assertEqual(motion.sample('Attack',i/400)['gate'],0)
            self.assertEqual(motion.sample('Recover',i/240)['gate'],P['gate_open_radians'])
        self.assertEqual(motion.sample('Death',1),motion.sample('Death',1.8))
    def test_no_external_asset_or_execution_calls(self):
        for name in ('generate.py','animate.py','motion.py'):
            source=(HERE/name).read_text()
            for prohibited in ('subprocess.','os.system(','urllib.','requests.','bpy.ops.wm.open_mainfile'):
                self.assertNotIn(prohibited,source)
    def test_runtime_parameter_contract(self):
        c=P['runtime_contract']
        for k in ('walk_speed_mps','charge_speed_mps','weakpoint_seconds','root_motion'): self.assertEqual(P[k],c[k])
        self.assertEqual(P['clips']['Windup'],c['windup_seconds'])
        self.assertEqual(P['clips']['Attack'],c['charge_timeout_seconds'])
        self.assertEqual(P['clips']['Recover'],c['weakpoint_seconds'])
        self.assertEqual(P['clips']['Hit'],c['hit_seconds'])
        self.assertEqual(P['charge_speed_mps'],10)
        self.assertEqual(P['walk_speed_mps'],2.1)
    def test_death_ram_vertices_clear_floor(self):
        # Same sections consumed by generate.py, every ring vertex over whole Death.
        for frame in range(round(P['clips']['Death']*240)+1):
            pose=motion.sample('Death',frame/240); angle=pose['ram']
            for x,y,z,w,h in motion.RAM_SECTIONS:
                for j in range(16):
                    vz=z+h*math.sin(math.tau*j/16)
                    world_z=.66+pose['z']+math.sin(angle)*(y+.79)+math.cos(angle)*(vz-.66)
                    self.assertGreaterEqual(world_z,-P['floor_penetration_limit_m'])
        # Explicit regression: rejected old settle exceeded the unchanged 4mm limit.
        old=.66-.30+math.sin(.18)*(-.70)+math.cos(.18)*(-.25)
        self.assertLess(old,-P['floor_penetration_limit_m'])
    def test_nonempty_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); fresh_output(base/'fresh')
            stale=base/'stale'; stale.mkdir(); (stale/'old.fbx').write_text('old')
            with self.assertRaises(ValueError): fresh_output(stale)
            with self.assertRaises(ValueError): fresh_output(stale/'old.fbx')
            self.assertEqual((stale/'old.fbx').read_text(),'old')
    def test_fps_evidence_contract(self):
        from evidence_layout import fps_files
        f=P['fps_evidence']; self.assertEqual(f['eye_height_m'],1.65); self.assertEqual(f['distances_m'],[2,4,6])
        self.assertEqual(f['gameplay_rule'],'whole_body_vulnerable_during_recover_no_directional_hit_cone')
        self.assertEqual(len(fps_files(P)),47); self.assertEqual(len(set(fps_files(P))),47)
        self.assertEqual(f['recover_seconds'],[0,1,1.95]); self.assertGreater(P['gate_open_radians'],math.pi/2)
        text=(HERE/'generate.py').read_text(); self.assertNotIn('math.sin(x',text)
        self.assertNotIn("bone('gate.'",text)
    def test_shared_cavity_topology(self):
        for verts,faces in (cavity_geometry.bowl_wall(),cavity_geometry.bowl_floor(),cavity_geometry.core_disk(),cavity_geometry.cover(1),cavity_geometry.cover(-1)):
            edges=Counter(tuple(sorted((a,b))) for face in faces for a,b in zip(face,face[1:]+face[:1]))
            self.assertTrue(all(count==2 for count in edges.values()),edges)
            self.assertTrue(all(0<=i<len(verts) for face in faces for i in face))
        wall,_=cavity_geometry.bowl_wall(); floor,_=cavity_geometry.bowl_floor()
        # The full outer bottom ring shares the floor top, closing front/side/rear underside.
        for a,b in zip(wall[96:128],floor[:32]):self.assertEqual(a,b)
        self.assertLessEqual(max(v[2] for v in cavity_geometry.cover(1)[0]),1.05)
    def test_presentation_ownership_contract(self):
        c=P['presentation_contract']; self.assertEqual(c['material_slot'],0); self.assertEqual(len(c['plate_pivots']),2)
        self.assertEqual(c['animation_owner'],'runtime_only_unkeyed_branch')
        source=(HERE/'generate.py').read_text(); begin=source.index('def set_presentation'); end=source.index('set_presentation(False)',begin)
        self.assertNotIn('keyframe_insert',source[begin:end]); self.assertNotIn("bone('gate.",source)
        self.assertIn('require_full_body=False',(HERE/'fps_evidence.py').read_text())
        self.assertIn('core target outside safe viewport',(HERE/'fps_evidence.py').read_text())
        self.assertIn('bake_anim=False',(HERE/'animate.py').read_text())
    def test_observed_greave_regression(self):
        import floor_probe
        report=json.loads((HERE/'floor-regression-observed.json').read_text())
        self.assertEqual(len(report['failures']),99)
        for r in report['failures']:
            name,frame=r['label'].rsplit(':',1); t=(int(frame)-1)/60
            if name.startswith('SYNTHETIC'):
                phase=float(name.rsplit('_',1)[1]);lead=min(.35,phase)
                pose=motion.sample('Attack',phase-lead+t) if t<lead else motion.interrupted(phase,t-lead)
            else:pose=motion.sample(name,t)
            old=floor_probe.diagnose(pose,guard=False); current=floor_probe.diagnose(pose)
            self.assertLess(abs(old['min_z']-r['observed']),1e-6)
            self.assertGreater(current['min_z'],0)
            self.assertEqual(current['ankle'],pose['feet'][current['bone'].split('.',1)[1]])
    def test_historical_unchanged_clip_equivalence(self):
        evidence=json.loads((HERE/'historical-clip-equivalence.json').read_text())
        for clip,expected in evidence['clips'].items():
            data=[]
            for i in range(expected['samples']):
                p=motion.sample(clip,i/240);self.assertIsNone(p.pop('knee_clearance'))
                p['knees']={k:motion.knee(motion.add(motion.HIP[k],(0,0,p['z'])),p['feet'][k],k) for k in motion.LEGS};data.append(p)
            digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            self.assertEqual(digest,expected['original_sha256']);self.assertEqual(digest,expected['current_sha256'])
    def test_source_manifest(self):
        manifest=json.loads((HERE/'source-manifest.json').read_text())
        for name,digest in manifest['sha256'].items(): self.assertEqual(hashlib.sha256((HERE/name).read_bytes()).hexdigest(),digest)
if __name__=='__main__': unittest.main(verbosity=2)

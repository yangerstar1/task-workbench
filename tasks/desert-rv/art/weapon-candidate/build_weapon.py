"""Original DesertRV weapon/hand candidate. Run only in the authorized Actions runner.
Blender 4.2.3; no downloaded art; units metres; +Y muzzle, +Z up, +X right.
"""
import bpy, math, json, pathlib, sys, hashlib
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
OUT=pathlib.Path(sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'output'); OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=24
scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.fps=60
scene.world.color=(.18,.18,.18); scene.view_settings.view_transform='AgX'
assets=[]; gun=[]; hands=[]; bone_defs={}
def mat(name,c,metal=0,rough=.45):
 m=bpy.data.materials.new(name); m.diffuse_color=(*c,1); m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
 return m
cream=mat('Powdercoat_Ivory',(.72,.64,.43),.35,.38); red=mat('Oxide_Red',(.38,.065,.028),.28,.38); dark=mat('Graphite_Parkerized',(.043,.05,.05),.65,.33); steel=mat('Brushed_Steel',(.32,.37,.39),.85,.27); rubber=mat('Glove_Graphite',(.036,.043,.047),0,.82); orange=mat('Cuff_Safety_Orange',(.68,.16,.018),0,.62); seam=mat('Glove_Seam',(.14,.15,.13),0,.77)
def finish(o,name,m,group=gun,bevel=0):
 o.name=name; o.data.materials.append(m)
 if bevel:
  mod=o.modifiers.new('Manufactured_Edge_Radius','BEVEL'); mod.width=bevel; mod.segments=3
  bpy.context.view_layer.objects.active=o; bpy.ops.object.modifier_apply(modifier=mod.name)
 for p in o.data.polygons:p.use_smooth=True
 assets.append(o); group.append(o); return o
def cube(name,loc,scale,m,bevel=.004,group=gun):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); return finish(o,name,m,group,bevel)
def cyl(name,a,b,r,m,vertices=32,group=gun):
 a,b=Vector(a),Vector(b); d=b-a; bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=d.length,location=(a+b)/2); o=bpy.context.object; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return finish(o,name,m,group,.001)
def profile(name,points,width,m):
 # Hand-authored YZ outline extruded along X, with real tapered housing silhouette.
 vs=[(x,y,z) for x in [-width/2,width/2] for y,z in points]; n=len(points)
 fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 mesh=bpy.data.meshes.new(name); mesh.from_pydata(vs,[],fs); mesh.update(); o=bpy.data.objects.new(name,mesh); scene.collection.objects.link(o); return finish(o,name,m,bevel=.008)
profile('Forged_Main_Housing',[(-.21,.02),(-.22,.105),(-.16,.145),(.055,.145),(.105,.105),(.12,.025),(.075,-.018),(-.145,-.02)],.102,cream)
profile('Red_Driver_Cowl',[(.03,.045),(.025,.13),(.07,.16),(.15,.15),(.175,.105),(.17,.04)],.094,red)
profile('Angled_Grip',[(-.16,.025),(-.09,.015),(-.12,-.18),(-.185,-.19),(-.20,-.16)],.057,dark)
profile('Grip_Overmould',[(-.165,-.02),(-.13,-.028),(-.15,-.16),(-.178,-.165)],.061,rubber)
profile('Long_Nail_Magazine',[(-.16,-.205),(-.155,-.155),(.265,-.11),(.272,-.155)],.042,dark)
mag_objs=[gun[-1]]
for x in [-.027,.027]:
 mag_objs.append(cyl('Magazine_Continuous_Guide_Rail',(x,-.155,-.169),(x,.253,-.124),.004,steel,20))
for i in range(27):
 y=-.136+i*.0138; z=-.175+(y+.155)*.107
 mag_objs.append(cyl('Visible_Collated_Nail_%02d'%i,(.023,y,z),(.023,y,z+.028),.0017,steel,8))
follower=cube('Magazine_Follower',(.0,-.155,-.178),(.065,.025,.045),red); mag_objs.append(follower)
cyl('Driver_Piston', (0,.12,.072),(0,.29,.072),.029,steel)
cyl('Nose_Safety_Sleeve',(0,.258,.072),(0,.32,.072),.036,dark)
cyl('Contact_Safety_Tip',(0,.316,.072),(0,.35,.072),.018,steel)
cube('Nail_Feed_Channel',(0,.266,-.038),(.032,.032,.165),dark)
for x in [-.0525,.0525]:
 for y,z in [(-.155,.085),(-.025,.08),(.085,.095)]:
  cyl('Recessed_Torx_Fastener',(x,y,z),(x+math.copysign(.003,x),y,z),.006,dark,12)
 for j in range(6):cube('Cooling_Slot',(x,-.11+j*.022,.115),(.002,.012,.005),dark,.001)
for z in [-.055,-.075,-.095,-.115,-.135]:cube('Grip_Tread',(0,-.184,z),(.062,.006,.004),seam,.001)
# Open trigger guard, not a solid slab.
for a,b in [((0,-.11,.005),(0,-.045,-.013)),((0,-.045,-.013),(0,-.05,-.075)),((0,-.05,-.075),(0,-.128,-.09))]:cyl('Trigger_Guard',a,b,.0045,dark,16)
trigger=cyl('Trigger',(0,-.092,-.01),(0,-.097,-.045),.006,red)
cyl('Rear_Pneumatic_Inlet',(0,-.215,.072),(0,-.244,.072),.017,dark)
# Two continuous glove surfaces created from overlapping anatomical volumes,
# voxel-unioned before skinning. No individual disconnected finger capsules in export.
def ellipsoid(loc,size):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,location=loc); o=bpy.context.object; o.scale=size; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); return o
def distance_seg(p,a,b):
 v=b-a; t=max(0,min(1,(p-a).dot(v)/max(v.length_squared,1e-12))); return (p-a-t*v).length
finger_paths={}
def glove(side,center):
 c=Vector(center); bits=[]
 def e(offset,size):bits.append(ellipsoid(c+Vector(offset),size))
 # Palm sits right/left of the tool, fingers wrap around the grip or fore-end.
 s=1 if side=='R' else -1
 e((s*.04,0,-.005),(.031,.045,.054)); e((s*.036,-.032,-.06),(.027,.038,.04)); e((s*.035,-.07,-.092),(.027,.048,.032))
 for idx,y in enumerate([-.028,-.008,.013,.032]):
  z=.014-idx*.006
  path=[c+Vector((s*.047,y,z)),c+Vector((s*.039,y+.004,z-.032)),c+Vector((s*.002,y+.008,z-.052)),c+Vector((-s*.027,y+.004,z-.037))]
  if idx==0 and side=='R':path=[c+Vector((s*.042,.031,.03)),c+Vector((s*.036,.057,.012)),c+Vector((s*.008,.060,-.009)),c+Vector((-.004,.052,-.004))]
  finger_paths[(side,idx)]=path
  for a,b in zip(path,path[1:]):
   for j in range(5):bits.append(ellipsoid(a.lerp(b,j/4),(.0125,.011,.0125)))
 path=[c+Vector((s*.035,-.025,.032)),c+Vector((s*.017,-.040,.052)),c+Vector((-s*.009,-.034,.037))]; finger_paths[(side,4)]=path
 for a,b in zip(path,path[1:]):
  for j in range(6):bits.append(ellipsoid(a.lerp(b,j/5),(.016,.014,.016)))
 bpy.ops.object.select_all(action='DESELECT')
 for o in bits:o.select_set(True)
 bpy.context.view_layer.objects.active=bits[0]; bpy.ops.object.join(); o=bits[0]; o.name='Glove_'+side+'_Continuous'
 rem=o.modifiers.new('Continuous_Anatomy_Union','REMESH'); rem.mode='VOXEL'; rem.voxel_size=.003; bpy.ops.object.modifier_apply(modifier=rem.name)
 sm=o.modifiers.new('Leather_Form_Relaxation','SMOOTH'); sm.factor=.65; sm.iterations=3; bpy.ops.object.modifier_apply(modifier=sm.name)
 o.data.calc_loop_triangles(); count=len(o.data.loop_triangles)
 dec=o.modifiers.new('Export_Topology_Budget','DECIMATE'); dec.ratio=min(1,6500/count); bpy.ops.object.modifier_apply(modifier=dec.name)
 finish(o,o.name,rubber,hands)
 cuff=cyl('Cuff_'+side,c+Vector((s*.035,-.065,-.09)),c+Vector((s*.035,-.11,-.12)),.035,orange,32,hands)
 # Raised stitched knuckle panels follow palm, distinct from the continuous base glove.
 for idx in range(4):
  pad=cube('Knuckle_Pad_'+side+'_'+str(idx),c+Vector((s*.066,-.024+idx*.019,.006-idx*.006)),(.012,.015,.027),seam,.006,hands)
 return o
right=glove('R',(0,-.151,-.065)); left=glove('L',(0,.13,-.023))
# Explicit hierarchy: root > arms > hands > fingers; gun, magazine and safety mechanism bones.
bpy.ops.object.armature_add(); rig=bpy.context.object; rig.name='DesertRV_WeaponHands_Rig'; bpy.ops.object.mode_set(mode='EDIT'); rig.data.edit_bones.remove(rig.data.edit_bones[0])
def bone(name,a,b,parent=None):
 e=rig.data.edit_bones.new(name); e.head=a; e.tail=b
 if parent:e.parent=rig.data.edit_bones[parent]
 bone_defs[name]=(Vector(a),Vector(b)); return e
bone('root',(0,0,-.35),(0,0,-.25)); bone('weapon',(0,-.15,.03),(0,.12,.03),'root'); bone('magazine',(0,-.1,-.18),(0,.15,-.15),'weapon'); bone('trigger',(0,-.092,-.01),(0,-.097,-.045),'weapon'); bone('follower',(0,-.155,-.178),(0,-.125,-.175),'magazine')
for side,c in [('R',Vector((0,-.151,-.065))),('L',Vector((0,.13,-.023)))]:
 s=1 if side=='R' else -1; bone('arm.'+side,c+Vector((s*.035,-.11,-.12)),c,'root'); bone('hand.'+side,c,c+Vector((0,.045,0)),'arm.'+side)
 for idx in range(5):
  p=finger_paths[(side,idx)]
  for j,(a,b) in enumerate(zip(p,p[1:])):bone('finger%d.%d.%s'%(idx,j,side),a,b,'hand.'+side if j==0 else 'finger%d.%d.%s'%(idx,j-1,side))
bpy.ops.object.mode_set(mode='OBJECT')
def skin(o,weights):
 for name in weights:o.vertex_groups.new(name=name)
 for v in o.data.vertices:
  p=o.matrix_world@v.co
  if len(weights)==1:o.vertex_groups[weights[0]].add([v.index],1,'REPLACE'); continue
  scores=sorted([(distance_seg(p,*bone_defs[n]),n) for n in weights])[:4]; vals=[1/max(d,.005)**4 for d,n in scores]; total=sum(vals)
  for (_,n),w in zip(scores,vals):o.vertex_groups[n].add([v.index],w/total,'REPLACE')
 mod=o.modifiers.new('Skin','ARMATURE'); mod.object=rig; o.parent=rig
for o in gun:skin(o,['follower' if o==follower else 'magazine' if o in mag_objs else 'trigger' if o==trigger else 'weapon'])
for o in hands:
 side='R' if '_R' in o.name else 'L'; names=['hand.'+side,'arm.'+side]+[n for n in bone_defs if n.startswith('finger') and n.endswith(side)] if o in [right,left] else ['hand.'+side]; skin(o,names)
# Stable bone-relative authoring anchors. Contact verification is sampled and reported,
# never interpreted as a mesh-intersection or art-quality pass.
anchors={}
for name,pos,parent in [('Grip',(0,-.15,-.07),'weapon'),('Trigger',(0,-.095,-.03),'weapon'),('Magazine',(0,.13,-.023),'magazine')]:
 ob=bpy.data.objects.new(name,None); scene.collection.objects.link(ob); ob.empty_display_type='SPHERE'; ob.empty_display_size=.006; ob.location=pos; skinparent=rig.data.bones[parent].matrix_local
 ob.parent=rig; ob.parent_type='BONE'; ob.parent_bone=parent; ob.matrix_world.translation=Vector(pos); anchors[name]=ob
# Bone local locations are converted from requested world-space deltas.
def key(name,frame,delta=(0,0,0),rot=(0,0,0)):
 p=rig.pose.bones[name]; basis=rig.data.bones[name].matrix_local.to_3x3(); p.location=basis.inverted()@Vector(delta); p.rotation_mode='XYZ'; p.rotation_euler=rot; p.keyframe_insert('location',frame=frame); p.keyframe_insert('rotation_euler',frame=frame)
clips={}
for clip,end in [('Idle',121),('Fire',14.2),('Reload',100)]:
 action=bpy.data.actions.new(clip); rig.animation_data_create(); rig.animation_data.action=action
 for n in bone_defs:key(n,1); key(n,end)
 if clip=='Idle':
  for f,z in [(1,0),(31,.0015),(61,0),(91,-.0015),(121,0)]:key('root',f,(0,0,z))
 if clip=='Fire':
  for f,d in [(1,0),(3,-.022),(7,-.007),(14.2,0)]:key('root',f,(0,d,0))
  key('trigger',3,rot=(.12,0,0)); key('trigger',8); key('finger0.1.R',3,rot=(.1,0,0)); key('finger0.1.R',8)
 if clip=='Reload':
  # Left hand and magazine share translation until seated; right hand maintains grip.
  for f,d in [(1,(0,0,0)),(12,(0,0,0)),(28,(-.05,-.08,-.16)),(43,(-.07,-.10,-.19)),(60,(-.05,-.08,-.16)),(77,(0,0,0)),(100,(0,0,0))]:
   key('magazine',f,d); key('arm.L',f,d)
  # Release and reach to charging follower after insertion, then return.
  for f,d in [(78,(0,0,0)),(86,(0,-.285,-.155)),(92,(0,-.320,-.155)),(100,(0,0,0))]:key('arm.L',f,d)
  for f,d in [(78,(0,0,0)),(86,(0,0,0)),(92,(0,-.035,-.0037)),(100,(0,0,0))]:key('follower',f,d)
 for fc in action.fcurves:
  for kp in fc.keyframe_points:kp.interpolation='LINEAR' if clip=='Reload' else 'BEZIER'
 track=rig.animation_data.nla_tracks.new(); track.name=clip; strip=track.strips.new(clip,1,action); track.mute=True; clips[clip]={'frames':[1,end],'seconds':(end-1)/60,'gameplay_events':[]}
rig.animation_data.action=bpy.data.actions['Idle']; scene.frame_set(1)
# Export before adding presentation geometry.
for ob in bpy.context.selected_objects:ob.select_set(False)
for ob in assets+[rig]+list(anchors.values()):ob.select_set(True)
bpy.context.view_layer.objects.active=rig
for tr in rig.animation_data.nla_tracks:tr.mute=False
rig.animation_data.action=None
bpy.ops.export_scene.gltf(filepath=str(OUT/'weapon_hands.glb'),use_selection=True,export_format='GLB',export_animation_mode='NLA_TRACKS',export_nla_strips=True,export_skins=True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'weapon_hands.fbx'),use_selection=True,add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=True,axis_forward='-Z',axis_up='Y')
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=bpy.data.actions['Idle']; scene.frame_set(1)
validation={'candidate_only':True,'approved':False,'blender':bpy.app.version_string,'coordinate_system':'+Y muzzle, +Z up, +X right; export converts axes','clips':clips,'mesh_groups':{},'weight_errors':[],'limitations':['Human visual acceptance required. Continuous glove voxel topology is a first candidate, not final hand retopology.','Reload includes remove/reinsert same magazine, then follower reach; no off-screen replacement magazine simulation.','Follower contact and mesh penetration have not been certified. Candidate must not enter production scene.'],'quality_gate':'PENDING_RENDER_REVIEW'}
for label,objs,budget in [('weapon',gun,[8000,12000]),('hands',hands,[10000,16000])]:
 tris=0
 for o in objs:
  o.data.calc_loop_triangles(); tris+=len(o.data.loop_triangles)
  for v in o.data.vertices:
   ws=[g.weight for g in v.groups if g.weight>1e-6]
   if len(ws)>4 or abs(sum(ws)-1)>1e-5:validation['weight_errors'].append([o.name,v.index,len(ws),sum(ws)])
 validation['mesh_groups'][label]={'triangles':tris,'initial_budget':budget,'in_budget':budget[0]<=tris<=budget[1]}
(OUT/'clip-manifest.json').write_text(json.dumps(clips,indent=2))
# Studio lighting and scene: presentation objects excluded from exchange exports.
def look(o,target):o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
for name,pos,power,size in [('Key',(1,-1.5,2),180,2),('Fill',(-1,-.5,.7),100,1.5),('Rim',(0,1.5,1.2),200,1)]:
 bpy.ops.object.light_add(type='AREA',location=pos); ob=bpy.context.object; ob.name=name; ob.data.energy=power; ob.data.shape='DISK'; ob.data.size=size; look(ob,(0,0,0))
bpy.ops.object.camera_add(); camera=bpy.context.object; scene.camera=camera; camera.data.type='ORTHO'; camera.data.ortho_scale=.8
scene.render.resolution_x=960; scene.render.resolution_y=720
for i in range(8):
 a=i*math.tau/8; camera.location=(math.cos(a)*1.2,math.sin(a)*1.2,.4); look(camera,(0,.04,-.035)); scene.render.filepath=str(OUT/('studio_%02d.png'%i)); bpy.ops.render.render(write_still=True)
# Orthographic side animation evidence, complete cycles at 60fps, PNG for ffmpeg.
camera.location=(1.1,.1,.12); look(camera,(0,.04,-.035)); scene.render.resolution_x=640; scene.render.resolution_y=480; scene.cycles.samples=8
for clip in clips:
 rig.animation_data.action=bpy.data.actions[clip]; folder=OUT/('frames_'+clip); folder.mkdir(exist_ok=True)
 for f in range(1,math.ceil(clips[clip]['frames'][1])+1):
  scene.frame_set(f); scene.render.filepath=str(folder/('%04d.png'%f)); bpy.ops.render.render(write_still=True)
rig.animation_data.action=bpy.data.actions['Idle']; scene.frame_set(1); scene.cycles.samples=24
# Fit real rendered model into lower-right safe rectangle. Bounds include all hand meshes.
validation['viewmodels']={}
for w,h in [(1280,720),(1600,720)]:
 scene.render.resolution_x=w; scene.render.resolution_y=h; camera.data.type='ORTHO'; camera.data.ortho_scale=2.6; camera.location=(0,-1.8,.3); look(camera,(0,1.8,.3))
 def bounds():
  ps=[world_to_camera_view(scene,camera,o.matrix_world@Vector(v)) for o in assets for v in o.bound_box]; return [min(p.x for p in ps),min(p.y for p in ps),max(p.x for p in ps),max(p.y for p in ps)]
 for _ in range(4):
  bpy.context.view_layer.update(); b=bounds(); camera.data.ortho_scale*=max((b[2]-b[0])/.29,(b[3]-b[1])/.32); bpy.context.view_layer.update(); b=bounds()
  camera.location.x+=((b[0]+b[2])/2-.81)*camera.data.ortho_scale
  camera.location.z+=((b[1]+b[3])/2-.19)*camera.data.ortho_scale*h/w
 bpy.context.view_layer.update(); b=bounds(); validation['viewmodels'][f'{w}x{h}']={'normalized_bounds':b,'width_fraction':b[2]-b[0],'height_fraction':b[3]-b[1],'target_fit':.25<=b[2]-b[0]<=.32 and .25<=b[3]-b[1]<=.35,'center_clear':not(b[0]<=.5<=b[2] and b[1]<=.5<=b[3]),'ui_buttons':'Requires actual game HUD overlay review; none assumed.'}
 scene.render.filepath=str(OUT/f'viewmodel_{w}x{h}.png'); bpy.ops.render.render(write_still=True)
(OUT/'validation.json').write_text(json.dumps(validation,indent=2)); bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'weapon_hands.blend'))
(OUT/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='SHA256SUMS')+'\n')
if validation['weight_errors']:raise RuntimeError('Skin weight validation failed')

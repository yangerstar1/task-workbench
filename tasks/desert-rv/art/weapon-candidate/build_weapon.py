"""Original DesertRV weapon/hand candidate. Run only in the authorized Actions runner.
Blender 4.2.3; no downloaded art; units metres; +Y muzzle, +Z up, +X right.
"""
import bpy, math, json, pathlib, sys, hashlib
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from asset_validation import strip_carrier_animation_channels, delivered_file
from pixel_evidence import alpha_bounds, is_core_asset, core_fully_visible, core_fit_score, core_target_fit
OUT=pathlib.Path(sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'output'); OUT.mkdir(parents=True,exist_ok=True)
bpy.context.preferences.filepaths.save_version=0
CONTACT_ONLY='--contact-only' in sys.argv
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=24
scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGBA'; scene.render.fps=60
scene.world.color=(.18,.18,.18); scene.view_settings.view_transform='AgX'
assets=[]; gun=[]; hands=[]; bone_defs={}
def mat(name,c,metal=0,rough=.45):
 m=bpy.data.materials.new(name); m.diffuse_color=(*c,1); m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
 return m
cream=mat('Powdercoat_Ivory',(.72,.64,.43),.18,.67); red=mat('Oxide_Red',(.38,.065,.028),.18,.61); dark=mat('Graphite_Parkerized',(.043,.05,.05),.6,.47); steel=mat('Brushed_Steel',(.32,.37,.39),.85,.27); rubber=mat('Glove_Graphite',(.036,.043,.047),0,.82); orange=mat('Cuff_Safety_Orange',(.68,.16,.018),0,.62); seam=mat('Glove_Seam',(.14,.15,.13),0,.77)
def finish(o,name,m,group=gun,bevel=0,bevel_segments=2):
 o.name=name; o.data.materials.append(m)
 if bevel:
  mod=o.modifiers.new('Manufactured_Edge_Radius','BEVEL'); mod.width=bevel; mod.segments=bevel_segments
  bpy.context.view_layer.objects.active=o; bpy.ops.object.modifier_apply(modifier=mod.name)
 for p in o.data.polygons:p.use_smooth=len(p.vertices)<=4
 assets.append(o); group.append(o); return o
def cube(name,loc,scale,m,bevel=.004,group=gun):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); return finish(o,name,m,group,bevel)
def cyl(name,a,b,r,m,vertices=24,group=gun):
 a,b=Vector(a),Vector(b); d=b-a; bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=d.length,location=(a+b)/2); o=bpy.context.object; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return finish(o,name,m,group,.0008 if r>.008 else 0,bevel_segments=1)
def profile(name,points,width,m):
 # Hand-authored YZ outline extruded along X, with real tapered housing silhouette.
 vs=[(x,y,z) for x in [-width/2,width/2] for y,z in points]; n=len(points)
 fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 mesh=bpy.data.meshes.new(name); mesh.from_pydata(vs,[],fs); mesh.update(); o=bpy.data.objects.new(name,mesh); scene.collection.objects.link(o); return finish(o,name,m,bevel=.008)
profile('Forged_Main_Housing',[(-.21,.02),(-.22,.105),(-.16,.145),(.055,.145),(.105,.105),(.12,.025),(.075,-.018),(-.145,-.02)],.102,cream)
profile('Red_Driver_Cowl',[(.03,.045),(.025,.13),(.07,.16),(.15,.15),(.175,.105),(.17,.04)],.094,red)
profile('Angled_Grip',[(-.16,.025),(-.09,.015),(-.12,-.18),(-.185,-.19),(-.20,-.16)],.057,dark)
profile('Grip_Overmould',[(-.165,-.02),(-.13,-.028),(-.15,-.16),(-.178,-.165)],.061,rubber)
# Fixed, open-top magazine: split side rails and lower spine leave a real loading slot.
mag_objs=[]; nail_objs=[]; strip_objs=[]
for x in [-.025,.025]:
 rail=profile('Magazine_Sidewall', [(-.17,-.20),(-.16,-.171),(.265,-.125),(.272,-.155)],.007,dark); rail.location.x=x; mag_objs.append(rail)
 mag_objs.append(cyl('Magazine_Continuous_Guide_Rail',(x,-.16,-.171),(x,.253,-.126),.003,steel,20))
mag_objs.append(profile('Magazine_Lower_Spine',[(-.16,-.197),(.265,-.151),(.265,-.160),(-.16,-.206)],.038,dark))
# Duplicate seated strip is a visual reload prop. Rest-loaded strip and incoming
# strip swap at the action boundary without game ammunition changes.
NAIL_CAPACITY=12; NAIL_PITCH=Vector((0,-.030,-.00321)); FIRST_NAIL=Vector((0,.223,-.135))
for destination,prefix in [(nail_objs,'LoadedNail'),(strip_objs,'IncomingNail')]:
 for i in range(NAIL_CAPACITY):
  v=FIRST_NAIL+NAIL_PITCH*i; y,z=v.y,v.z
  shaft=cyl(prefix+'_%02d'%i,(0,y,z),(0,y,z+.028),.0017,steel,8)
  head=cyl(prefix+'_Head_%02d'%i,(0,y,z+.028),(0,y,z+.03),.0035,steel,12)
  bond=cyl(prefix+'_Bond_%02d'%i,(0,y-.015,z+.027-.001605),(0,y+.015,z+.027+.001605),.0025,red,8)
  bpy.ops.object.select_all(action='DESELECT')
  for part in [shaft,head,bond]:part.select_set(True)
  for part in [head,bond]:assets.remove(part); gun.remove(part)
  bpy.context.view_layer.objects.active=shaft; bpy.ops.object.join(); shaft.name=prefix+'_%02d'%i
  destination.append(shaft)
follower=cube('Magazine_Follower',(.0,-.155,-.178),(.061,.022,.04),red); mag_objs.append(follower)
cyl('Driver_Piston', (0,.12,.072),(0,.29,.072),.029,steel)
cyl('Nose_Safety_Sleeve',(0,.258,.072),(0,.32,.072),.036,dark)
safety_tip=cyl('Contact_Safety_Tip',(0,.316,.072),(0,.35,.072),.018,steel)
cube('Nail_Feed_Channel',(0,.266,-.038),(.032,.032,.165),dark)
for x in [-.0525,.0525]:
 for y,z in [(-.155,.085),(-.025,.08),(.085,.095)]:
  cyl('Recessed_Torx_Fastener',(x,y,z),(x+math.copysign(.003,x),y,z),.006,dark,12)
 for j in range(6):cube('Cooling_Slot',(x,-.11+j*.022,.115),(.002,.012,.005),dark,.001)
for z in [-.055,-.075,-.095,-.115,-.135]:cube('Grip_Tread',(0,-.184,z),(.062,.006,.004),seam,.001)
for side in [-1,1]:
 panel=profile('Side_Service_Gasket',[(-.176,.032),(-.184,.092),(-.143,.121),(.035,.121),(.072,.087),(.071,.035)],.003,dark); panel.location.x=side*.052
 panel=profile('Side_Service_Cover',[(-.169,.038),(-.176,.089),(-.140,.114),(.030,.114),(.063,.084),(.063,.041)],.004,cream); panel.location.x=side*.054
 # Functional lower seam follows the pressure body split rather than decorative blocks.
 cyl('Housing_Parting_Seam',(side*.05,-.167,.018),(side*.05,.06,.018),.0014,dark,12)
# Contoured rubber foregrip provides the left hand a real load-bearing surface.
profile('Underbarrel_Grasp_Surface',[(.085,.026),(.165,.021),(.166,-.058),(.092,-.064)],.053,rubber)
# Spring visible between two safety sleeve shoulders.
for j in range(7):
 y=.273+j*.005
 bpy.ops.mesh.primitive_torus_add(major_radius=.030,minor_radius=.0015,major_segments=24,minor_segments=6,location=(0,y,.072),rotation=(math.pi/2,0,0)); finish(bpy.context.object,'Safety_Return_Spring',steel)
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
 # Palm broad plane is YZ, fingers stack down the vertical tool grip.
 # Narrower individual phalanges and 5mm gaps prevent the R1 fused bead row.
 s=1 if side=='R' else -1
 e((s*.043,-.007,-.018),(.018,.027,.046))
 e((s*.040,-.027,-.062),(.019,.023,.030))
 e((s*.038,-.055,-.087),(.021,.028,.026))
 for idx,z in enumerate([.015,-.006,-.027,-.047]):
  reach=.042 if side=='R' and idx==0 else .025
  path=[c+Vector((s*.046,.007,z)),c+Vector((s*.039,reach,z-.001)),c+Vector((s*.008,reach+.009,z-.004)),c+Vector((-s*.024,reach-.005,z-.006))]
  finger_paths[(side,idx)]=path
  radii=[.009,.0084,.0074]
  for k,(a,b) in enumerate(zip(path,path[1:])):
   for j in range(5):
    r=radii[k]*(1-.10*j/4); bits.append(ellipsoid(a.lerp(b,j/4),(r,r*.92,r*.96)))
 # Distinct thumb emerges above the palm across a visible web-space.
 path=[c+Vector((s*.045,-.022,.018)),c+Vector((s*.035,-.035,.045)),c+Vector((-s*.002,-.020,.039))]
 finger_paths[(side,4)]=path
 for k,(a,b) in enumerate(zip(path,path[1:])):
  for j in range(6):bits.append(ellipsoid(a.lerp(b,j/5),(.0115-k*.001,.0105,.0108)))
 bpy.ops.object.select_all(action='DESELECT')
 for o in bits:o.select_set(True)
 bpy.context.view_layer.objects.active=bits[0]; bpy.ops.object.join(); o=bits[0]; o.name='Glove_'+side+'_Continuous'
 rem=o.modifiers.new('Continuous_Anatomy_Union','REMESH'); rem.mode='VOXEL'; rem.voxel_size=.0018; bpy.ops.object.modifier_apply(modifier=rem.name)
 sm=o.modifiers.new('Leather_Form_Relaxation','SMOOTH'); sm.factor=.32; sm.iterations=2; bpy.ops.object.modifier_apply(modifier=sm.name)
 o.data.calc_loop_triangles(); count=len(o.data.loop_triangles)
 dec=o.modifiers.new('Export_Topology_Budget','DECIMATE'); dec.ratio=min(1,5200/count); bpy.ops.object.modifier_apply(modifier=dec.name)
 finish(o,o.name,rubber,hands)
 cuff=cyl('Cuff_'+side,c+Vector((s*.035,-.065,-.09)),c+Vector((s*.035,-.11,-.12)),.035,rubber,32,hands)
 cyl('Cuff_Orange_Band_'+side,c+Vector((s*.035,-.075,-.097)),c+Vector((s*.035,-.088,-.105)),.036,orange,32,hands)
 cube('Handback_Orange_Guard_'+side,c+Vector((s*.068,-.004,-.01)),(.004,.039,.038),orange,.0017,hands)
 # Low, broad integrated padding follows the four stacked proximal phalanges.
 for idx,z in enumerate([.015,-.006,-.027,-.047]):
  cube('Knuckle_Leather_'+side+'_'+str(idx),c+Vector((s*.059,.007,z)),(.004,.019,.013),rubber,.0018,hands)
  cyl('Finger_Seam_'+side+'_'+str(idx),c+Vector((s*.058,-.001,z-.005)),c+Vector((s*.058,.015,z-.005)),.0008,seam,8,hands)
 # Tapered, continuous sleeve reaching back/down far beyond the game viewport.
 start=c+Vector((s*.035,-.080,-.105)); end=c+Vector((-.22,-.46,-.72))
 direction=(end-start).normalized(); axis=direction.cross(Vector((1,0,0))).normalized(); cross=direction.cross(axis).normalized()
 vs=[]; fs=[]; rings=9; sides=24
 for row in range(rings):
  t=row/(rings-1); center=start.lerp(end,t); radius=.033+.019*t
  for j in range(sides):
   a=j*math.tau/sides; v=center+axis*math.cos(a)*radius+cross*math.sin(a)*radius*.86; vs.append(v)
 for row in range(rings-1):
  for j in range(sides):fs.append((row*sides+j,row*sides+(j+1)%sides,(row+1)*sides+(j+1)%sides,(row+1)*sides+j))
 mesh=bpy.data.meshes.new('Sleeve_'+side); mesh.from_pydata(vs,[],fs); mesh.update(); arm=bpy.data.objects.new('Forearm_'+side,mesh); scene.collection.objects.link(arm); finish(arm,arm.name,rubber,hands)
 return o
right=glove('R',(0,-.151,-.065)); left=glove('L',(0,.13,-.023))
# Explicit hierarchy: root > arms > hands > fingers; gun, magazine and safety mechanism bones.
bpy.ops.object.armature_add(); rig=bpy.context.object; rig.name='DesertRV_WeaponHands_Rig'; bpy.ops.object.mode_set(mode='EDIT'); rig.data.edit_bones.remove(rig.data.edit_bones[0])
def bone(name,a,b,parent=None):
 e=rig.data.edit_bones.new(name); e.head=a; e.tail=b
 if parent:e.parent=rig.data.edit_bones[parent]
 bone_defs[name]=(Vector(a),Vector(b)); return e
bone('root',(0,0,-.35),(0,0,-.25)); bone('IncomingOffset',(0,0,0),(0,.1,0),'root'); bone('LeftReloadOffset',(0,0,0),(0,.1,0),'root'); bone('weapon',(0,-.15,.03),(0,.12,.03),'root'); bone('magazine',(0,-.1,-.18),(0,.15,-.15),'weapon'); bone('trigger',(0,-.092,-.01),(0,-.097,-.045),'weapon'); bone('follower',(0,-.155,-.178),(0,-.125,-.175),'magazine'); bone('loaded_nails',(0,.13,-.14),(0,.16,-.137),'magazine'); bone('reload_strip',(0,.13,-.14),(0,.16,-.137),'IncomingOffset'); bone('safety_tip',(0,.32,.072),(0,.35,.072),'weapon'); bone('Muzzle',(0,.35,.072),(0,.385,.072),'weapon')
for side,c in [('R',Vector((0,-.151,-.065))),('L',Vector((0,.13,-.023)))]:
 s=1 if side=='R' else -1; bone('arm.'+side,c+Vector((s*.035,-.11,-.12)),c,'LeftReloadOffset' if side=='L' else 'root'); bone('hand.'+side,c,c+Vector((0,.045,0)),'arm.'+side)
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
for o in gun:skin(o,['safety_tip' if o==safety_tip else 'loaded_nails' if o in nail_objs else 'reload_strip' if o in strip_objs else 'follower' if o==follower else 'magazine' if o in mag_objs else 'trigger' if o==trigger else 'weapon'])
for o in hands:
 side='R' if '_R' in o.name else 'L'; names=['hand.'+side,'arm.'+side]+[n for n in bone_defs if n.startswith('finger') and n.endswith(side)] if o in [right,left] else ['hand.'+side,'root'] if o.name.startswith('Forearm_') else ['hand.'+side]; skin(o,names)
 if o.name.startswith('Forearm_'):
  c=bone_defs['hand.'+side][0]; sign=1 if side=='R' else -1; start=c+Vector((sign*.035,-.080,-.105)); end=c+Vector((-.22,-.46,-.72)); span=end-start
  for v in o.data.vertices:
   t=max(0,min(1,((o.matrix_world@v.co)-start).dot(span)/span.length_squared)); t=t*t*(3-2*t)
   o.vertex_groups['hand.'+side].add([v.index],1-t,'REPLACE'); o.vertex_groups['root'].add([v.index],t,'REPLACE')
# Anatomical skin partition: the continuous palm/wrist follows hand only.
# Localized finger chains blend at their own roots; arm.L/R never influences
# the glove, avoiding the R5 arm-stationary/hand-rotated split deformation.
for side,obj in [('R',right),('L',left)]:
 c=bone_defs['hand.'+side][0]; obj.vertex_groups.clear()
 for name in ['hand.'+side]+[n for n in bone_defs if n.startswith('finger') and n.endswith(side)]:obj.vertex_groups.new(name=name)
 for vertex in obj.data.vertices:
  p=obj.matrix_world@vertex.co; rel=p-c
  if rel.z>.020 and rel.y<.013:
   digit=4; amount=max(0,min(1,(rel.z-.016)/.018))
  elif rel.y>.006:
   digit=min(range(4),key=lambda k:min(distance_seg(p,a,b) for a,b in zip(finger_paths[(side,k)],finger_paths[(side,k)][1:])))
   amount=max(0,min(1,(rel.y-.006)/.016))
  else:digit=None;amount=0
  obj.vertex_groups['hand.'+side].add([vertex.index],1-amount,'REPLACE')
  if amount:
   names=[n for n in bone_defs if n.startswith('finger%d.'%digit) and n.endswith(side)]
   nearest=sorted((distance_seg(p,*bone_defs[n]),n) for n in names)[:2]; values=[1/max(d,.004)**2 for d,n in nearest]; total=sum(values)
   for (_,name),value in zip(nearest,values):obj.vertex_groups[name].add([vertex.index],amount*value/total,'REPLACE')
# Pinch IK changes the fingers' pose for strip carry and follower operation.
# Targets are explicit opposing surfaces; constraints are sampled by exporters.
ik_controls=[]; contact_targets={}
for phase,parent,center in [('strip','reload_strip',(0,.223,-.106)),('follower','follower',(0,-.155,-.166))]:
 for digit,offset in [(0,(.004,0,0)),(1,(.004,.018,-.002)),(4,(-.004,0,0))]:
  pos=Vector(center)+Vector(offset); target=bpy.data.objects.new('IK_'+phase+'_'+str(digit),None); scene.collection.objects.link(target)
  target.parent=rig; target.parent_type='BONE'; target.parent_bone=parent; bpy.context.view_layer.update(); target.matrix_world.translation=pos
  name='finger%d.%d.L'%(digit,1 if digit==4 else 2)
  con=rig.pose.bones[name].constraints.new('IK'); con.name='Pinch_'+phase; con.target=target; con.chain_count=2 if digit==4 else 3; con.use_rotation=False; con.influence=0
  ik_controls.append((phase,con)); contact_targets[(phase,digit)]=(name,target)
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
 for n in bone_defs:
  if n not in ['IncomingOffset','LeftReloadOffset','Muzzle']:key(n,1); key(n,end)
 for phase,con in ik_controls:
  con.influence=0; con.keyframe_insert('influence',frame=1); con.keyframe_insert('influence',frame=end)
 if clip=='Idle':
  for f,z in [(1,0),(31,.0015),(61,0),(91,-.0015),(121,0)]:key('root',f,(0,0,z))
 if clip=='Fire':
  for f,d in [(1,0),(3,-.032),(7,-.009),(14.2,0)]:key('root',f,(0,d,0))
  key('safety_tip',3,(0,-.012,0)); key('safety_tip',7); key('trigger',3,rot=(.12,0,0)); key('trigger',8); key('finger0.1.R',3,rot=(.1,0,0)); key('finger0.1.R',8)
 if clip=='Reload':
  # Count-driven reload: magazine stays attached. A genuinely new collated nail strip
  # travels from below the camera, through the open loading channel, into place.
  strip_path=[(1,(-.12,-.10,-.24)),(35,(-.12,-.10,-.24)),(48,(-.10,0,.075)),(60,(0,0,.045)),(68,(0,0,0)),(100,(0,0,0))]
  for f,d in strip_path:key('reload_strip',f,d)
  hand_path=[(1,(0,0,0)),(12,(.015,-.310,-.155)),(23,(.015,-.365,-.161)),
   (35,(-.120,-.032,-.302)),(48,(-.100,.068,.013)),(60,(0,.068,-.017)),(68,(0,.068,-.062)),
   (73,(-.06,0,.015)),(82,(.015,-.365,-.161)),(91,(.015,-.310,-.155)),(100,(0,0,0))]
  for f,d in hand_path:key('arm.L',f,d)
  # Pronate the palm over the slot: palm/non-pinching fingers stay above rails.
  for f,a in [(1,0),(23,0),(35,math.pi),(68,math.pi),(78,0),(100,0)]:key('hand.L',f,rot=(a,0,0))
  for phase,con in ik_controls:
   keys=[(1,0),(30,0),(35,1),(68,1),(73,0),(100,0)] if phase=='strip' else [(1,0),(8,0),(12,1),(23,1),(28,0),(77,0),(82,1),(91,1),(96,0),(100,0)]
   for frame,value in keys:con.influence=value; con.keyframe_insert('influence',frame=frame)
  for f,d in [(1,(0,0,0)),(12,(0,0,0)),(23,(0,-.055,-.006)),(82,(0,-.055,-.006)),(91,(0,0,0)),(100,(0,0,0))]:key('follower',f,d)
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
bpy.ops.export_scene.gltf(filepath=str(OUT/'weapon_hands.glb'),use_selection=True,export_format='GLB',export_animation_mode='NLA_TRACKS',export_nla_strips=True,export_skins=True,export_def_bones=False)
carrier_cleanup=strip_carrier_animation_channels(OUT/'weapon_hands.glb')
(OUT/'carrier-channel-cleanup.json').write_text(json.dumps(carrier_cleanup,indent=2))
# Blender 4.2.3 forces constant NLA channels via force_keep=True even when
# bake_anim_use_all_bones=False. Disable only that forced retention during this
# export; actual sampled motion remains, and package validation inspects links.
from io_scene_fbx import export_fbx_bin
original_fbx_animation_sampler=export_fbx_bin.fbx_animations_do
def export_motion_without_forced_constants(*args,**kwargs):
 kwargs['force_keep']=False
 return original_fbx_animation_sampler(*args,**kwargs)
export_fbx_bin.fbx_animations_do=export_motion_without_forced_constants
try:
 bpy.ops.export_scene.fbx(filepath=str(OUT/'weapon_hands.fbx'),use_selection=True,object_types={'ARMATURE','MESH','EMPTY'},use_armature_deform_only=False,add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=True,bake_anim_use_all_bones=False,bake_anim_simplify_factor=1.0,axis_forward='-Z',axis_up='Y')
finally:export_fbx_bin.fbx_animations_do=original_fbx_animation_sampler

for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=bpy.data.actions['Idle']; scene.frame_set(1)
validation={'candidate_only':True,'approved':False,'blender':bpy.app.version_string,'coordinate_system':'+Y muzzle, +Z up, +X right; export converts axes','clips':clips,'mesh_groups':{},'weight_errors':[],'limitations':['Human visual acceptance required. Continuous glove voxel topology is a first candidate, not final hand retopology.','Reload visual preview is loadedBefore=3, added=5. Runtime must drive 12 individual nail renderers and synchronized offset bones from the authoritative count snapshot.','Follower contact and mesh penetration have not been certified. Candidate must not enter production scene.'],'quality_gate':'PENDING_RENDER_REVIEW'}
for label,objs,budget in [('weapon',gun,[8000,12000]),('hands',hands,[10000,16000])]:
 tris=0
 for o in objs:
  o.data.calc_loop_triangles(); tris+=len(o.data.loop_triangles)
  for v in o.data.vertices:
   ws=[g.weight for g in v.groups if g.weight>1e-6]
   if len(ws)>4 or abs(sum(ws)-1)>1e-5:validation['weight_errors'].append([o.name,v.index,len(ws),sum(ws)])
 validation['mesh_groups'][label]={'triangles':tris,'per_mesh_triangles':{o.name:len(o.data.loop_triangles) for o in objs},'initial_budget':budget,'in_budget':budget[0]<=tris<=budget[1]}
# Sample shared-grip authoring references throughout each contact phase.
# These measure kinematic alignment, NOT triangle penetration or anatomical quality.
contact_report=[]
rig.animation_data.action=bpy.data.actions['Reload']
for phase,frames,target,ref in [('pull_follower',range(12,24),'follower',(.015,-.18,-.178)),('carry_and_seat_strip',range(35,69),'reload_strip',(0,.198,-.085)),('release_follower',range(82,92),'follower',(.015,-.18,-.178))]:
 errors=[]; fingertip_errors=[]
 for frame in frames:
  scene.frame_set(frame); bpy.context.view_layer.update()
  palm=rig.matrix_world @ rig.pose.bones['hand.L'].head
  target_matrix=rig.matrix_world @ rig.pose.bones[target].matrix @ rig.data.bones[target].matrix_local.inverted()
  errors.append((palm-target_matrix@Vector(ref)).length)
  kind='strip' if target=='reload_strip' else 'follower'
  for digit in [0,1,4]:
   name,ob=contact_targets[(kind,digit)]; fingertip_errors.append(((rig.matrix_world@rig.pose.bones[name].tail)-ob.matrix_world.translation).length)
 contact_report.append({'phase':phase,'frames':[frames.start,frames.stop-1],'max_authoring_reference_error_m':max(errors),'max_fingertip_IK_error_m':max(fingertip_errors),'surface_collision_tested':False})
validation['reload_mechanism']={'type':'fixed_open_top_magazine_fresh_collated_strip','magazine_detaches':False,'new_nails_count':12,'gameplay_events':[],'reference_contact_samples':contact_report}
rig.animation_data.action=bpy.data.actions['Idle']; scene.frame_set(1)
validation['incoming_skin_contract']={'same_rig':all(o.parent==rig and sum(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)==1 for o in strip_objs),'positive_weight_bones':sorted({o.vertex_groups[g.group].name for o in strip_objs for v in o.data.vertices for g in v.groups if g.weight>0}),'required_carrier_ancestor':'IncomingOffset','carrier_parent_of_reload_strip':rig.data.bones['reload_strip'].parent.name,'renderer_reparented':False}
validation['muzzle']={'node':'Muzzle','parent':rig.data.bones['Muzzle'].parent.name,'head_xyz':list(rig.data.bones['Muzzle'].head_local),'tail_xyz':list(rig.data.bones['Muzzle'].tail_local),'source_forward_axis':'+Y','bone_local_forward_axis':'+Y'}
(OUT/'clip-manifest.json').write_text(json.dumps(clips,indent=2))
# Unity bridge contract: count/offset application occurs after Animator evaluation.
# No authored animation curves target the two offset bones or visibility carriers.
contract={'muzzle':{'node':'Muzzle','parent_bone':'weapon','source_head_xyz':[0,.35,.072],'source_tail_xyz':[0,.385,.072],'source_forward_axis':'+Y','bone_local_forward_axis':[0,1,0],'unity_note':'Use actual imported Muzzle position; local +Y is the bone forward axis. Do not assume Transform.forward.'},'incoming_binding':{'mode':'skinned','same_rig_required':True,'positive_weight_bones_must_descend_from':'IncomingOffset','renderer_transform_may_be_at_rig_root':True,'never_reparent_skinned_mesh':True},'capacity':12,'loaded_nodes':['LoadedNail_%02d'%i for i in range(12)],'incoming_nodes':['IncomingNail_%02d'%i for i in range(12)],'incoming_offset':'IncomingOffset','left_reload_offset':'LeftReloadOffset','source_pitch_xyz':list(NAIL_PITCH),'source_axes':'+Y muzzle, +Z up','derive_imported_pitch':'Use transformed source vector or verify imported adjacent nail origins; do not assume Unity axes.','count_snapshot':['ReloadPresented.Epoch','ReloadPresented.Sequence','LoadedBefore','PlannedAdded'],'loaded_visible':'prefix[0,LoadedBefore) until authoritative completion; then prefix[0,actualLoaded)','incoming_visible':'prefix[0,PlannedAdded), frames 35..100; hidden on cancel/complete','offset':'LoadedBefore * source_pitch; IncomingOffset throughout reload; LeftReloadOffset blends 30..35, holds35..68, fades68..73','animation_events':[],'commit':'Game commits once at 1.65s; physical seating frame68 does not allow early fire','preview':{'loaded_before':3,'planned_added':5}}
(OUT/'weapon-presentation-contract.json').write_text(json.dumps(contract,indent=2))
def preview_pose(clip,frame,loaded_before=3,planned_added=5):
 scene.frame_set(frame)
 before,added=(loaded_before,planned_added) if clip=='Reload' else (12,0)
 if not(0<=before<=12 and 0<=added<=12-before):raise ValueError('Invalid cosmetic reload count snapshot')
 for i,o in enumerate(nail_objs):o.hide_render=i>=before
 for i,o in enumerate(strip_objs):o.hide_render=not(clip=='Reload' and frame>=35 and i<added)
 weight=max(0,min(1,(frame-30)/5,(73-frame)/5)) if clip=='Reload' else 0
 rig.pose.bones['IncomingOffset'].location=NAIL_PITCH*before if clip=='Reload' else Vector((0,0,0))
 rig.pose.bones['LeftReloadOffset'].location=NAIL_PITCH*before*weight
 bpy.context.view_layer.update()
preview_pose('Idle',1)
# Studio lighting and scene: presentation objects excluded from exchange exports.
def look(o,target):o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
for name,pos,power,size in [('Key',(1,-1.5,2),180,2),('Fill',(-1,-.5,.7),100,1.5),('Rim',(0,1.5,1.2),200,1)]:
 bpy.ops.object.light_add(type='AREA',location=pos); ob=bpy.context.object; ob.name=name; ob.data.energy=power; ob.data.shape='DISK'; ob.data.size=size; look(ob,(0,0,0))
bpy.ops.object.camera_add(); camera=bpy.context.object; scene.camera=camera; camera.data.type='ORTHO'; camera.data.ortho_scale=1.15
scene.render.resolution_x=960; scene.render.resolution_y=720
for i in range(0 if CONTACT_ONLY else 8):
 a=i*math.tau/8; camera.location=(math.cos(a)*1.2,math.sin(a)*1.2,.4); look(camera,(0,.04,-.15)); scene.render.filepath=str(OUT/('studio_%02d.png'%i)); bpy.ops.render.render(write_still=True)
# Orthographic side animation evidence, complete cycles at 60fps, PNG for ffmpeg.
camera.location=(-1.1,.1,.12); look(camera,(0,.04,-.15)); scene.render.resolution_x=640; scene.render.resolution_y=480; scene.cycles.samples=8
for clip in ([] if CONTACT_ONLY else clips):
 rig.animation_data.action=bpy.data.actions[clip]; folder=OUT/('frames_'+clip); folder.mkdir(exist_ok=True)
 for f in range(1,math.ceil(clips[clip]['frames'][1])+1):
  preview_pose(clip,f); scene.render.filepath=str(folder/('%04d.png'%f)); bpy.ops.render.render(write_still=True)
# Two-sided static contact witnesses: approach, acquired strip, guide, seated, release.
rig.animation_data.action=bpy.data.actions['Reload']; camera.data.ortho_scale=.85
for frame in [30,35,*range(55,69),91]:
 preview_pose('Reload',frame)
 for side in [-1,1]:
  camera.location=(side*1.1,-.12,.13); look(camera,(0,.02,-.18)); scene.render.filepath=str(OUT/f'reload_contact_{frame:03d}_{side:+d}.png'); bpy.ops.render.render(write_still=True)
# Countable empty / partial / nearly-full magazine boundary evidence.
for frame in [55,60,64,68]:
 preview_pose('Reload',frame,11,1)
 for side in [-1,1]:
  camera.location=(side*1.1,-.12,.13); look(camera,(0,.02,-.18)); scene.render.filepath=str(OUT/f'nearly_full_contact_{frame:03d}_{side:+d}.png'); bpy.ops.render.render(write_still=True)
validation['count_evidence']=[]
for before,added in [(0,12),(3,5),(11,1)]:
 for frame in [1,60,100]:
  preview_pose('Reload',frame,before,added); camera.location=(-1.1,-.12,.13); look(camera,(0,.02,-.18))
  name=f'reload_count_{before:02d}_plus_{added:02d}_frame_{frame:03d}.png'; scene.render.filepath=str(OUT/name); bpy.ops.render.render(write_still=True)
  validation['count_evidence'].append({'image':name,'loaded_before':before,'planned_added':added,'frame':frame,'visible_loaded':sum(not o.hide_render for o in nail_objs),'visible_incoming':sum(not o.hide_render for o in strip_objs)})
# Actual triangle-surface overlap samples, distinct from fingertip IK residuals.
# Test only fixed magazine rails/spine and the other glove; collated nails are
# intentional fingertip contact and are not included in this obstruction test.
def evaluated_bvh(obj):
 deps=bpy.context.evaluated_depsgraph_get(); ev=obj.evaluated_get(deps); mesh=ev.to_mesh()
 try:return BVHTree.FromPolygons([ev.matrix_world@v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons],all_triangles=False,epsilon=0)
 finally:ev.to_mesh_clear()
def surface_evidence(hand,obj):
 ht=evaluated_bvh(hand); ot=evaluated_bvh(obj); pairs=ht.overlap(ot)
 result={'object':obj.name,'triangle_pairs':len(pairs),'sample_triangle_pairs':[list(p) for p in pairs[:8]],'max_inside_vertex_depth_m':None,'inside_vertex_regions':{}}
 if not pairs:return result
 ev=hand.evaluated_get(bpy.context.evaluated_depsgraph_get()); mesh=ev.to_mesh(); depths=[]; regions={}; direction=Vector((.371,.529,.763)).normalized()
 try:
  for v in mesh.vertices:
   point=ev.matrix_world@v.co; nearest,normal,index,distance=ot.find_nearest(point)
   if nearest is None or distance>.035:continue
   cursor=point.copy(); hits=0
   for _ in range(32):
    hit,_,_,_=ot.ray_cast(cursor,direction,2)
    if hit is None:break
    hits+=1;cursor=hit+direction*.000001
   if hits%2:
    depths.append(distance)
    groups=hand.data.vertices[v.index].groups; region=hand.vertex_groups[max(groups,key=lambda g:g.weight).group].name if groups else 'unweighted'
    regions[region]=regions.get(region,0)+1
 finally:ev.to_mesh_clear()
 result['max_inside_vertex_depth_m']=max(depths) if depths else None;result['inside_vertex_regions']=regions
 return result
validation['loading_surface_samples']=[]
for before,added in [(0,12),(3,5),(11,1)]:
 for frame in range(55,69):
  preview_pose('Reload',frame,before,added); hand_tree=evaluated_bvh(left)
  blocked=[surface_evidence(left,obj) for obj in [*filter(lambda o:o!=follower,mag_objs),right]]
  validation['loading_surface_samples'].append({'loaded_before':before,'added':added,'frame':frame,'intersections':[b for b in blocked if b['triangle_pairs']>0]})
if CONTACT_ONLY:
 diagnostic={'scope':'reload-contact-diagnostic','full_asset_validation':False,'approved':False,'sample_count':len(validation['loading_surface_samples']),'failed_samples':sum(bool(s['intersections']) for s in validation['loading_surface_samples'])}
 (OUT/'contact-diagnostic.json').write_text(json.dumps(diagnostic,indent=2));(OUT/'validation.json').write_text(json.dumps(validation,indent=2))
 (OUT/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(OUT.iterdir()) if delivered_file(p))+'\n')
 raise SystemExit(1 if diagnostic['failed_samples'] else 0)
rig.animation_data.action=bpy.data.actions['Idle']; preview_pose('Idle',1); scene.cycles.samples=24
# Preserve useful partial evidence before potentially failing image readback.
(OUT/'validation.json').write_text(json.dumps(validation,indent=2)); bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'weapon_hands.blend'))
# Natural viewmodel: fixed perspective camera looking +Y, no camera roll/yaw.
# Tool itself is held obliquely toward the reticle; sleeves continue below frame.
validation['viewmodels']={}; scene.render.film_transparent=True
camera.data.type='PERSP'; camera.data.lens=37.75; camera.data.sensor_width=36
camera.location=(0,0,0); look(camera,(0,1,0))
def projected_bounds(core_only=False):
 bpy.context.view_layer.update(); deps=bpy.context.evaluated_depsgraph_get()
 pts=[world_to_camera_view(scene,camera,o.evaluated_get(deps).matrix_world@Vector(v)) for o in assets if not(core_only and not is_core_asset(o.name)) for v in o.evaluated_get(deps).bound_box]
 return [min(p.x for p in pts),min(p.y for p in pts),max(p.x for p in pts),max(p.y for p in pts)]
# One immutable pose selected from static projection of the actual #3 GLB.
# Both aspects share model/camera transform and horizontal FOV. Only off-axis
# vertical lens shift compensates for aspect ratio to preserve the lower safe zone.
# No per-size search and no inf/invalid fallback selection.
rig.location=(.76484,2.44693,-.44683)
rig.rotation_euler=tuple(math.radians(a) for a in (-10,-30,55))
camera.data.sensor_fit='HORIZONTAL'
base_aspect=16/9; target_center_y=.192; reference_center_y=.18264
for w,h in [(1280,720),(1600,720)]:
 scene.render.resolution_x=w; scene.render.resolution_y=h
 aspect=w/h; camera.data.shift_y=(reference_center_y-.5)/base_aspect*(37.75/34.5)-(target_center_y-.5)/aspect
 b=projected_bounds(core_only=True)
 scene.render.filepath=str(OUT/f'viewmodel_{w}x{h}.png'); bpy.ops.render.render(write_still=True)
 # Exact alpha-pixel footprint from the actual render, not only projected boxes.
 # Headless Render Result may expose no pixel buffer after write_still.
 # Load the persisted evidence PNG and validate dimensions/alpha explicitly.
 evidence=bpy.data.images.load(scene.render.filepath,check_existing=False)
 try:
  if tuple(evidence.size)!=(w,h):raise RuntimeError(f'Evidence PNG dimensions {tuple(evidence.size)} != {(w,h)}')
  pixel_bounds=alpha_bounds(evidence.pixels[:],w,h,evidence.channels)
 finally:bpy.data.images.remove(evidence)
 full_alpha_bounds=pixel_bounds
 # Render a true core-only mask: exclude only long forearms, never gloves/cuffs.
 sleeves=[o for o in assets if not is_core_asset(o.name)]; visibility=[o.hide_render for o in sleeves]
 for o in sleeves:o.hide_render=True
 scene.render.filepath=str(OUT/f'viewmodel_core_{w}x{h}.png');bpy.ops.render.render(write_still=True)
 evidence=bpy.data.images.load(scene.render.filepath,check_existing=False)
 try:pixel_bounds=alpha_bounds(evidence.pixels[:],w,h,evidence.channels)
 finally:bpy.data.images.remove(evidence)
 for o,hidden in zip(sleeves,visibility):o.hide_render=hidden
 width=pixel_bounds[2]-pixel_bounds[0]; height=pixel_bounds[3]-pixel_bounds[1]
 validation['viewmodels'][f'{w}x{h}']={'normalized_bounds':pixel_bounds,'core_alpha_bounds':pixel_bounds,'full_alpha_bounds':full_alpha_bounds,'footprint_metric':'core-only rendered alpha, long forearms excluded','unclipped_core_bounds':b,'core_fully_visible':core_fully_visible(b),'width_fraction':width,'height_fraction':height,'target_fit':core_target_fit(pixel_bounds,b),'camera':'fixed +Y perspective 37.75mm, no rotation trick','rig_location':list(rig.location),'rig_euler':list(rig.rotation_euler),'camera_shift_y':camera.data.shift_y,'stable_pose_id':'R4_shared_pose_-10_-30_55','center_clear':not(pixel_bounds[0]<=.5<=pixel_bounds[2] and pixel_bounds[1]<=.5<=pixel_bounds[3]),'sleeves_reach_lower_edge':full_alpha_bounds[1]<=1/h,'ui_buttons':'Requires actual game HUD overlay review.'}
rig.location=(0,0,0); rig.rotation_euler=(0,0,0)
(OUT/'validation.json').write_text(json.dumps(validation,indent=2)); bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'weapon_hands.blend'))
(OUT/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(OUT.iterdir()) if delivered_file(p))+'\n')
if validation['weight_errors']:raise RuntimeError('Skin weight validation failed')

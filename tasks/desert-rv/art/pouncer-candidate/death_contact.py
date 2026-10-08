"""Author Death joint contacts before baking. Never clamp output vertices or images.
All geometry and non-Death actions remain untouched. Unsolved contact fails validation.
"""
from mathutils import Vector, Matrix, Quaternion
import bpy
import math
from death_support import TrunkSupport

class DeathContactSolver:
    def __init__(self,body,details,rig,leg_chains,duration,rest_pose):
        self.body,self.details,self.rig,self.legs=body,details,rig,leg_chains
        self.duration=duration
        self.rest_pose=rest_pose;self.relax=0
        self.support=TrunkSupport(body)
        self.torso=sorted(set(i for ids in self.support.regions.values() for i in ids))
        self.head=[v.index for v in body.data.vertices if v.co.y<-.72]
        names={g.index:g.name for g in body.vertex_groups}
        self.limb={};self.foot={}
        for key in leg_chains:
            pre,side=key.split('.')
            matched=lambda v:sum(g.weight for g in v.groups if names[g.group].startswith(pre+'_') and names[g.group].endswith('.'+side))>.70
            self.limb[key]=[v.index for v in body.data.vertices if matched(v)]  # includes proximal hip cap at bind z=.60
            self.foot[key]=[v.index for v in body.data.vertices if v.co.z<.12 and matched(v)]
        self.rows=[]
    def align_paws(self):
        # Explicit local basis from the FINAL evaluated parent avoids stale-parent matrix setters.
        bpy.context.view_layer.update()
        for key in self.legs:
            pre,side=key.split('.'); pb=self.rig.pose.bones[pre+'_paw.'+side]
            intent=self.rest_pose[key]
            side_rotation=Matrix.Rotation(intent['paw_roll']*self.relax,4,'Y') @ Matrix.Rotation(intent['paw_yaw']*self.relax,4,'Z')
            desired=side_rotation @ pb.bone.matrix_local.to_3x3().to_4x4();desired.translation=pb.head.copy()
            pb.matrix_basis=pb.bone.matrix_local.inverted() @ pb.parent.bone.matrix_local @ pb.parent.matrix.inverted() @ desired
        bpy.context.view_layer.update()
    def measure(self):
        deps=bpy.context.evaluated_depsgraph_get();ev=self.body.evaluated_get(deps);mesh=ev.to_mesh();coords=[ev.matrix_world@v.co for v in mesh.vertices];z=[v.z for v in coords];ev.to_mesh_clear()
        foot={k:min(z[i] for i in ids) for k,ids in self.foot.items()};limb={k:min(z[i] for i in ids) for k,ids in self.limb.items()};minimum=min(z);head_min=min(z[i] for i in self.head)
        for obj in self.details:
            ev=obj.evaluated_get(deps);mesh=ev.to_mesh();low=min((ev.matrix_world@v.co).z for v in mesh.vertices);ev.to_mesh_clear();minimum=min(minimum,low)
            bind=obj.get('bind_bone','')
            if bind in ('head','jaw'):head_min=min(head_min,low)
            for key in self.legs:
                pre,side=key.split('.')
                if bind==pre+'_paw.'+side:foot[key]=min(foot[key],low);limb[key]=min(limb[key],low)
        return {'torso_z':min(z[i] for i in self.torso),'support_patches':self.support.inspect(coords),'minimum_z':minimum,'head_min_z':head_min,'feet':foot,'limbs':limb}
    def region_minimum(self,key):
        ev=self.body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
        result=min((ev.matrix_world@mesh.vertices[i].co).z for i in self.limb[key]);ev.to_mesh_clear();return result
    def yield_joint(self,key,depth):
        # Coordinate-search the actual offending muscle surface, rather than assuming
        # that raising a pole always raises a proximal cap behind the hip pivot.
        pre,side=key.split('.');pole=self.rig.pose.bones[pre+'_pole.'+side]
        target=self.rig.pose.bones[pre+'_target.'+side];ik=self.rig.pose.bones[pre+'_lower.'+side].constraints['AuthoringFootLock']
        initial=pole.location.copy();initial_target=target.location.copy();initial_angle=ik.pole_angle;best=(initial.copy(),initial_target.copy(),initial_angle);best_z=self.region_minimum(key)
        step=max(.015,min(.07,2*depth))
        # Let the bulky proximal muscle rotate clear; a pole alone cannot change reach direction.
        candidates=[('pole',axis,sign) for axis in range(3) for sign in (-1,1)]+[('target',axis,sign) for axis in (0,1) for sign in (-1,1)]+[('angle',0,sign) for sign in (-1,1)]
        for kind,axis,sign in candidates:
            cp=initial.copy();ct=initial_target.copy();angle=initial_angle
            if kind=='pole':cp[axis]+=sign*step
            elif kind=='target':ct[axis]+=sign*step
            else:angle+=sign*(.08 if depth>.008 else .04)
            if abs(angle-self.pole_baselines[key])>1.0:continue
            if (cp-self.references[key][0]).length>.35 or (ct-self.references[key][1]).length>.18:continue
            pole.location=cp;target.location=ct;ik.pole_angle=angle;self.align_paws();z=self.region_minimum(key)
            if z>best_z+.00005:best_z=z;best=(cp.copy(),ct.copy(),angle)
        pole.location=best[0];target.location=best[1];ik.pole_angle=best[2];self.align_paws()
    def head_minimum(self):
        deps=bpy.context.evaluated_depsgraph_get();ev=self.body.evaluated_get(deps);mesh=ev.to_mesh()
        low=min((ev.matrix_world@mesh.vertices[i].co).z for i in self.head);ev.to_mesh_clear()
        for obj in self.details:
            if obj.get('bind_bone') not in ('head','jaw'):continue
            ev=obj.evaluated_get(deps);mesh=ev.to_mesh();low=min(low,min((ev.matrix_world@v.co).z for v in mesh.vertices));ev.to_mesh_clear()
        return low
    def relax_head(self,depth):
        # Measure both signs in evaluated geometry. The former hardcoded negative Z
        # response was experimentally shown to push this rolled neck DOWN.
        start={n:self.rig.pose.bones[n].rotation_euler.to_quaternion() for n in ('neck','head')}
        best_z=self.head_minimum();best=None;step=max(.01,min(.06,depth/.80))
        for name in ('neck','head'):
            pb=self.rig.pose.bones[name]
            for axis in (Vector((1,0,0)),Vector((0,0,1))):
                for sign in (-1,1):
                    q=start[name] @ Quaternion(axis,sign*step)
                    if q.rotation_difference(self.angular_references[name]).angle>.50:continue
                    pb.rotation_euler=q.to_euler('XYZ');bpy.context.view_layer.update();low=self.head_minimum()
                    if low>best_z+.00005:best_z=low;best=(name,q.copy())
                    pb.rotation_euler=start[name].to_euler('XYZ');bpy.context.view_layer.update()
        if best:self.rig.pose.bones[best[0]].rotation_euler=best[1].to_euler('XYZ')
        bpy.context.view_layer.update()
    def broaden_shoulder(self):
        patch=self.support.inspect()['shoulder']
        if patch['vertices_within_30mm']>=3:return
        pb=self.rig.pose.bones['chest'];start=pb.rotation_euler.to_quaternion();best=start.copy()
        best_width=patch['witnesses'][2]['world_xyz_m'][2]-patch['minimum_z']
        for axis in (Vector((1,0,0)),Vector((0,0,1))):
            for sign in (-1,1):
                q=start @ Quaternion(axis,sign*.008)
                if q.rotation_difference(self.angular_references['chest']).angle>.060:continue
                pb.rotation_euler=q.to_euler('XYZ');self.align_paws();candidate=self.support.inspect()['shoulder']
                width=candidate['witnesses'][2]['world_xyz_m'][2]-candidate['minimum_z']
                if width<best_width-.00005:best_width=width;best=q.copy()
        pb.rotation_euler=best.to_euler('XYZ');self.align_paws()
    def yield_girdle_roll(self,targets):
        # A below-floor joint origin cannot be fixed by wrist/pole rotation alone.
        # Test small rigid side-roll changes while restoring the mean two-patch support.
        pb=self.rig.pose.bones['visual_body'];loc=pb.location.copy();rot=pb.rotation_euler.copy()
        initial=self.measure();best_score=min(initial['limbs'].values());best=(loc.copy(),rot.copy())
        for delta in (-.020,.020):
            candidate=rot.copy();candidate.y+=delta
            if not self.initial_roll-.28<=candidate.y<=self.initial_roll+.04:continue
            pb.location=loc;pb.rotation_euler=candidate;self.align_paws();m=self.measure()
            pb.location.z+=sum(targets[k]-m['support_patches'][k]['minimum_z'] for k in targets)/len(targets)
            self.align_paws();m=self.measure();score=min(m['limbs'].values())
            if score>best_score+.0002:best_score=score;best=(pb.location.copy(),candidate.copy())
        pb.location=best[0];pb.rotation_euler=best[1];self.align_paws()
    def solve(self,u):
        if not hasattr(self,'pole_baselines'):
            self.pole_baselines={key:self.rig.pose.bones[key.split('.')[0]+'_lower.'+key.split('.')[1]].constraints['AuthoringFootLock'].pole_angle for key in self.legs}
        for key,angle in self.pole_baselines.items():
            self.rig.pose.bones[key.split('.')[0]+'_lower.'+key.split('.')[1]].constraints['AuthoringFootLock'].pole_angle=angle
        t=max(0,min(1,(u-.18)/.52));self.relax=t*t*(3-2*t)
        self.angular_references={n:self.rig.pose.bones[n].rotation_euler.to_quaternion() for n in ('neck','head','chest')}
        self.initial_roll=self.rig.pose.bones['visual_body'].rotation_euler.y
        self.references={}
        for key in self.legs:
            pre,side=key.split('.');self.references[key]=(self.rig.pose.bones[pre+'_pole.'+side].location.copy(),self.rig.pose.bones[pre+'_target.'+side].location.copy())
        self.align_paws();initial=self.measure()
        settle=max(0,min(1,(u-.20)/.40));settle=settle*settle*(3-2*settle)
        targets={k:r['minimum_z']*(1-settle)+.001*settle for k,r in initial['support_patches'].items()}
        visual=self.rig.pose.bones['visual_body'];initial_pitch=visual.rotation_euler.x;steps=[]
        for iteration in range(32):
            self.align_paws();m=self.measure()
            errors={k:m['support_patches'][k]['minimum_z']-targets[k] for k in targets}
            patch_ok=all(p['vertices_within_30mm']>=max(3,math.ceil(p['vertices']*.02)) and p['q05_z']<=.040 for p in m['support_patches'].values())
            if max(abs(e) for e in errors.values())<.001 and m['minimum_z']>=-.0008 and patch_ok:break
            if settle>0:
                a=m['support_patches']['shoulder'];b=m['support_patches']['pelvis']
                ya=a['lowest_world_xyz_m'][1];yb=b['lowest_world_xyz_m'][1]
                pitch_gain=math.cos(visual.rotation_euler.y)*(ya-yb)
                dp=-(errors['shoulder']-errors['pelvis'])/pitch_gain if abs(pitch_gain)>.15 else 0
                dp=max(-.05,min(.05,dp))
                dz=-.5*(errors['shoulder']+errors['pelvis'])-.5*(ya+yb)*math.cos(visual.rotation_euler.y)*dp
                visual.location.z+=.45*dz;visual.rotation_euler.x=max(initial_pitch-.18,min(initial_pitch+.18,visual.rotation_euler.x+.45*dp))
            bpy.context.view_layer.update();self.align_paws();m=self.measure()
            for key in self.legs:
                pre,side=key.split('.');target_bone=self.rig.pose.bones[pre+'_target.'+side]
                if m['feet'][key]<.0005:target_bone.location.z+=.75*(.0005-m['feet'][key])
                if m['limbs'][key]<-.0005 and m['feet'][key]>=-.0005:self.yield_joint(key,-m['limbs'][key])
            m=self.measure()
            if settle>.70 and min(m['limbs'].values())<-.008:self.yield_girdle_roll(targets)
            if settle>.95 and not patch_ok:self.broaden_shoulder()
            m=self.measure()
            if m['head_min_z']<-.0005:self.relax_head(-m['head_min_z'])
            bpy.context.view_layer.update()
            steps.append({'iteration':iteration,'support_errors':errors,'minimum_z':m['minimum_z']})
        self.align_paws();final=self.measure()
        self.rows.append({'time_fraction':u,'time_seconds':u*self.duration,'relax_fraction':self.relax,'initial':initial,'support_targets_z':targets,'final':final,'iterations':len(steps),'steps':steps})
        return final

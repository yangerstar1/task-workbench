"""Author Death joint contacts before baking. Never clamp output vertices or images.
All geometry and non-Death actions remain untouched. Unsolved contact fails validation.
"""
from mathutils import Vector
import bpy

class DeathContactSolver:
    def __init__(self,body,details,rig,leg_chains,duration):
        self.body,self.details,self.rig,self.legs=body,details,rig,leg_chains
        self.duration=duration
        self.torso=[v.index for v in body.data.vertices if -.65<v.co.y<.77 and v.co.z>.50]
        names={g.index:g.name for g in body.vertex_groups}
        self.limb={};self.foot={}
        for key in leg_chains:
            pre,side=key.split('.')
            matched=lambda v:sum(g.weight for g in v.groups if names[g.group].startswith(pre+'_') and names[g.group].endswith('.'+side))>.70
            self.limb[key]=[v.index for v in body.data.vertices if v.co.z<.50 and matched(v)]
            self.foot[key]=[v.index for v in body.data.vertices if v.co.z<.12 and matched(v)]
        self.rows=[]
    def align_paws(self):
        # Explicit local basis from the FINAL evaluated parent avoids stale-parent matrix setters.
        bpy.context.view_layer.update()
        for key in self.legs:
            pre,side=key.split('.'); pb=self.rig.pose.bones[pre+'_paw.'+side]
            desired=pb.bone.matrix_local.to_3x3().to_4x4();desired.translation=pb.head.copy()
            pb.matrix_basis=pb.bone.matrix_local.inverted() @ pb.parent.bone.matrix_local @ pb.parent.matrix.inverted() @ desired
        bpy.context.view_layer.update()
    def measure(self):
        deps=bpy.context.evaluated_depsgraph_get();ev=self.body.evaluated_get(deps);mesh=ev.to_mesh();z=[(ev.matrix_world@v.co).z for v in mesh.vertices];ev.to_mesh_clear()
        foot={k:min(z[i] for i in ids) for k,ids in self.foot.items()};limb={k:min(z[i] for i in ids) for k,ids in self.limb.items()};minimum=min(z)
        for obj in self.details:
            ev=obj.evaluated_get(deps);mesh=ev.to_mesh();low=min((ev.matrix_world@v.co).z for v in mesh.vertices);ev.to_mesh_clear();minimum=min(minimum,low)
            bind=obj.get('bind_bone','')
            for key in self.legs:
                pre,side=key.split('.')
                if bind==pre+'_paw.'+side:foot[key]=min(foot[key],low);limb[key]=min(limb[key],low)
        return {'torso_z':min(z[i] for i in self.torso),'minimum_z':minimum,'feet':foot,'limbs':limb}
    def solve(self,u):
        self.align_paws();initial=self.measure()
        settle=max(0,min(1,(u-.20)/.40));settle=settle*settle*(3-2*settle)
        target=initial['torso_z']*(1-settle)+.001*settle
        visual=self.rig.pose.bones['visual_body'];steps=[]
        for iteration in range(24):
            self.align_paws();m=self.measure()
            torso_error=m['torso_z']-target
            if abs(torso_error)<.0008 and m['minimum_z']>=-.0008:break
            if settle>0:visual.location.z-=.60*torso_error
            # Resolve the specific foot/joint, never lift every foot because one claw dipped.
            for key in self.legs:
                pre,side=key.split('.');target_bone=self.rig.pose.bones[pre+'_target.'+side];pole=self.rig.pose.bones[pre+'_pole.'+side]
                if m['feet'][key]<.0005:target_bone.location.z+=.75*(.0005-m['feet'][key])
                if m['limbs'][key]<-.0005 and m['feet'][key]>=-.0005:
                    pole.location.z+=.80*(-m['limbs'][key]+.001)
            bpy.context.view_layer.update()
            steps.append({'iteration':iteration,'torso_error':torso_error,'minimum_z':m['minimum_z']})
        # This orientation/evaluation is LAST. Nothing changes targets/poles after this point.
        self.align_paws();final=self.measure()
        self.rows.append({'time_fraction':u,'time_seconds':u*self.duration,'initial':initial,'torso_target_z':target,'final':final,'iterations':len(steps),'steps':steps})
        return final

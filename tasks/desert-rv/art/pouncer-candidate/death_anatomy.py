"""Physical proximal shoulder/hip regions: space + influence + bone-segment fraction.
Weights are evidence of deformation, not a rule that real muscle ceases to exist.
"""
import bpy

class AnatomicalSupport:
    def __init__(self,body,rig):
        self.body=body;self.regions={'shoulder':[],'pelvis':[]};self.evidence={}
        names={g.index:g.name for g in body.vertex_groups};trunk={'pelvis','spine','chest','neck'}
        for v in body.data.vertices:
            x,y,z=v.co;weights={names[g.group]:g.weight for g in v.groups};tw=sum(w for n,w in weights.items() if n in trunk)
            for region,bone_name,inside in [('shoulder','fore_upper.L',x>.12 and z>.52 and -.62<y<-.14),('pelvis','hind_upper.L',x>.12 and z>.48 and .32<y<.80)]:
                if not inside:continue
                bone=rig.data.bones[bone_name];d=bone.tail_local-bone.head_local;p=v.co-bone.head_local;t=p.dot(d)/d.length_squared
                if -.50<=t<=.45 and p.length<=.34 and weights.get(bone_name,0)+tw>=.65:
                    self.regions[region].append(v.index);self.evidence[v.index]={'bind_xyz_m':list(v.co),'bone_segment':bone_name,'segment_fraction':t,'distance_from_joint_m':p.length,'weights':weights,'trunk_weight':tw}
        if any(len(ids)<8 for ids in self.regions.values()):raise RuntimeError('Anatomical region missing; refuse head/distal-limb fallback')
        self.face=[v.index for v in body.data.vertices if v.co.y<-.90 and v.co.z>.47]
    def inspect(self,coords):
        result={}
        for name,ids in self.regions.items():
            order=sorted(ids,key=lambda i:coords[i].z);n=len(order)
            result[name]={'vertices':n,'minimum_z':coords[order[0]].z,'q05_z':coords[order[round((n-1)*.05)]].z,'q10_z':coords[order[round((n-1)*.10)]].z,'vertices_within_30mm':sum(coords[i].z<=.03 for i in ids),'witnesses':[{'vertex':i,'world_xyz_m':list(coords[i]),**self.evidence[i]} for i in order[:6]]}
        result['face']={'minimum_z':min(coords[i].z for i in self.face),'vertices_within_35mm':sum(coords[i].z<=.035 for i in self.face)}
        return result

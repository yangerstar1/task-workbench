"""Anatomically separated, trunk-dominant shoulder and pelvis support witnesses."""
def support_region(x,y,z,trunk_weight):
    if x<=.06 or z<=.38 or trunk_weight<.60:return None
    if -.57<y<-.08:return 'shoulder'
    if .32<y<.77:return 'pelvis'
    return None

class TrunkSupport:
    def __init__(self,body):
        self.body=body; self.names={g.index:g.name for g in body.vertex_groups}
        trunk={'pelvis','spine','chest','neck'}
        self.weights={v.index:sum(g.weight for g in v.groups if self.names[g.group] in trunk) for v in body.data.vertices}
        self.regions={name:[v.index for v in body.data.vertices if support_region(*v.co,self.weights[v.index])==name] for name in ('shoulder','pelvis')}
        if any(len(ids)<8 for ids in self.regions.values()):raise RuntimeError('Insufficient genuine trunk support patch; do not substitute a leg or head vertex')
    def inspect(self,coords=None):
        import bpy
        if coords is None:
            ev=self.body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();coords=[ev.matrix_world@v.co for v in me.vertices];ev.to_mesh_clear()
        result={}
        for name,ids in self.regions.items():
            ordered=sorted(ids,key=lambda i:coords[i].z); n=len(ordered)
            witnesses=[]
            for i in ordered[:6]:
                v=self.body.data.vertices[i]
                witnesses.append({'vertex':i,'world_xyz_m':list(coords[i]),'bind_xyz_m':list(v.co),'trunk_weight':self.weights[i],'weights':{self.names[g.group]:g.weight for g in v.groups}})
            result[name]={'vertices':n,'minimum_z':coords[ordered[0]].z,'q05_z':coords[ordered[min(n-1,round((n-1)*.05))]].z,'q10_z':coords[ordered[min(n-1,round((n-1)*.10))]].z,'vertices_within_30mm':sum(coords[i].z<=.03 for i in ids),'lowest_world_xyz_m':list(coords[ordered[0]]),'witnesses':witnesses}
        return result

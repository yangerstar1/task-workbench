"""Evaluated Blender graph contract, not a Unity import acceptance claim."""
def validate_binding_contract():
    descendants=[assembly]+list(assembly.children_recursive)
    forbidden_names={o.name for o in descendants}
    failures=[]
    if combined in descendants:failures.append('Body renderer must remain outside presentation branch')
    if len(core.data.materials)!=1 or core.modifiers:failures.append('Core must be a single-slot rigid independent renderer')
    for side,pivot in pivots.items():
        plate=plate_objects[side]
        if pivot.parent!=assembly or plate.parent!=pivot or plate.modifiers:failures.append('Plate hierarchy/rigid mesh mismatch '+side)
    for obj in descendants:
        if obj.animation_data and (obj.animation_data.action or obj.animation_data.nla_tracks or obj.animation_data.drivers):failures.append('Animated presentation object '+obj.name)
    for act in bpy.data.actions:
        for fc in act.fcurves:
            if any(name in fc.data_path for name in forbidden_names) or 'gate.' in fc.data_path:failures.append('Presentation channel in action '+act.name)
    contract={'status':'failed' if failures else 'source_graph_checked_import_unverified','failures':failures,'body_renderer':'Bulwark_Body','weak_point_root':'WeakPointAssembly','carrier_bone':'body','core_renderer':'Core_Renderer','material_slot':0,'core_submeshes':1,'core_materials':1,'plate_pivots':['ArmorPlate_L_Pivot','ArmorPlate_R_Pivot'],'plate_renderers':['ArmorPlate_L_Renderer','ArmorPlate_R_Renderer'],'closed_local_euler_unity_intent':[[0,0,0],[0,0,0]],'open_local_euler_unity_intent':[[0,0,-140],[0,0,140]],'blender_open_local_euler':[[0,140,0],[0,-140,0]],'controller':'BeastWeakPointPresentation exclusively reads actor.WeakPointExposed','keyed_presentation_nodes':False,'core_open_material':{'name':'Core_Open','base_color_linear':[.85,.255,.025,1],'emission_color_linear':[.12,.025,.002,1],'emission_enabled':True},'fbx_model_animations':False,'fbx_animations_separate':'bulwark-animations.fbx','unity_import_verified':False,'requires':'Verify actual imported axes, slot, renderer ownership and absence of any constant/generated animation channels under the presentation branch before binding.'}
    (OUT/'binding-contract.json').write_text(json.dumps(contract,indent=2))
    if failures:raise RuntimeError('Presentation binding contract failed')
validate_binding_contract()

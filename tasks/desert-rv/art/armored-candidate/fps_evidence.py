"""Executed in Blender static phase. Fixed-height, fixed-FOV paired evidence.
No camera auto-fit, arrows, emissive overlays or substitute hitboxes.
The orange bay signals whole-body recovery vulnerability, not a direction-only target.
"""
F=P['fps_evidence']; eye=F['eye_height_m']; fps_rows=[]
cam.data.type='PERSP'; cam.data.lens_unit='FOV'
# Blender angle is horizontal with horizontal sensor fit. Convert actual vertical FOV.
cam.data.sensor_fit='HORIZONTAL'; aspect=scene.render.resolution_x/scene.render.resolution_y
cam.data.angle=2*math.atan(math.tan(math.radians(F['vertical_fov_degrees'])/2)*aspect)
viewpoints=[(a,d) for a in F['rear_angles_degrees'] for d in F['distances_m']]+[(a,F['side_boundary_distance_m']) for a in F['side_boundary_angles_degrees']]
states=[('closed','Idle',0)]+[(f'recover-{t:.2f}','Recover',t) for t in F['recover_seconds']]
for angle,distance in viewpoints:
    a=math.radians(angle)
    # Identical physical viewpoint and aim point for every state in this pair/group.
    cam.location=(distance*math.sin(a),-distance*math.cos(a),eye)
    cam.rotation_euler=(Vector((0,.75,.85))-cam.location).to_track_quat('-Z','Y').to_euler()
    for state,clip,t in states:
        apply_pose(motion.sample(clip,t)); bpy.context.view_layer.update()
        label=f'fps-{angle:03d}-{distance}m-{state}'; row=validate_frame(label)
        # Ray-grid in the projection of the actual tagged tissue geometry. The
        # nearest evaluated surface must be tagged tissue, so doors/body occlude it.
        deps=bpy.context.evaluated_depsgraph_get(); obj=combined.evaluated_get(deps); me=obj.to_mesh()
        tag=me.attributes.get('weakpoint_face')
        if tag is None:raise RuntimeError('Weakpoint face evidence attribute lost on join/evaluation')
        points=[obj.matrix_world@me.vertices[i].co for poly in me.polygons if tag.data[poly.index].value for i in poly.vertices]
        projected=[world_to_camera_view(scene,cam,v) for v in points]
        xmin=max(0,min(v.x for v in projected)); xmax=min(1,max(v.x for v in projected)); ymin=max(0,min(v.y for v in projected)); ymax=min(1,max(v.y for v in projected))
        frame=cam.data.view_frame(scene=scene); local_min=Vector((min(v.x for v in frame),min(v.y for v in frame),frame[0].z)); local_max=Vector((max(v.x for v in frame),max(v.y for v in frame),frame[0].z))
        visible=[]; grid_x=32; grid_y=24
        for iy in range(grid_y):
            for ix in range(grid_x):
                u=xmin+(xmax-xmin)*(ix+.5)/grid_x; v=ymin+(ymax-ymin)*(iy+.5)/grid_y
                local=Vector((local_min.x+(local_max.x-local_min.x)*u,local_min.y+(local_max.y-local_min.y)*v,local_min.z))
                direction=(cam.matrix_world.to_3x3()@local).normalized()
                hit,loc,normal,index,hit_obj,_=scene.ray_cast(deps,cam.location,direction,distance=20)
                if hit and hit_obj.original==combined and index>=0 and tag.data[index].value:visible.append((u,v))
        obj.to_mesh_clear()
        if state=='closed' and len(visible)>F['maximum_closed_visible_samples']:row['errors'].append('closed armor leaks visible tissue')
        if state!='closed' and len(visible)<F['minimum_open_visible_samples']:row['errors'].append('open bay insufficient visible ray samples')
        width=scene.render.resolution_x; height=scene.render.resolution_y
        row.update({'state':state,'recovery_time_seconds':t if clip=='Recover' else None,'eye_height_m':eye,'horizontal_distance_to_actor_m':distance,'angle_degrees_from_front':angle,'vertical_fov_degrees':F['vertical_fov_degrees'],'visible_tissue_samples':len(visible),'sample_grid':[grid_x,grid_y],'projected_tissue_bbox_px':[(xmax-xmin)*width,(ymax-ymin)*height],'estimated_visible_tissue_area_px':len(visible)/(grid_x*grid_y)*(xmax-xmin)*width*(ymax-ymin)*height,'gameplay':'Recover gives whole-body vulnerability; tissue is state feedback, not separate hitbox','visual_approved':False})
        if visible:
            row['visible_tissue_bbox_px']=[(max(v[0] for v in visible)-min(v[0] for v in visible))*width,(max(v[1] for v in visible)-min(v[1] for v in visible))*height]
        if state!='closed':
            if row['estimated_visible_tissue_area_px']<F['minimum_open_visible_area_px']:row['errors'].append('open bay projected area too small')
            if row.get('visible_tissue_bbox_px',[0,0])[1]<F['minimum_open_visible_height_px']:row['errors'].append('open bay visible height too small')
        fps_rows.append(row); checks.append(row); still(review/(label+'.png'))
(OUT/'fps-visibility.json').write_text(json.dumps({'camera':'physical perspective, fixed pose across open/closed','samples':fps_rows,'note':'Ray visibility and projected area are technical diagnostics. Actual 2-second recognition and playability require image/video/Unity review.'},indent=2))

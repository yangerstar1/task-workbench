"""Shared deterministic screenshot contract; no Blender import."""
def fps_files(parameters):
    f=parameters['fps_evidence']
    viewpoints=[(a,d) for a in f['rear_angles_degrees'] for d in f['distances_m']]+[(a,f['side_boundary_distance_m']) for a in f['side_boundary_angles_degrees']]
    states=['closed']+[f'recover-{t:.2f}' for t in f['recover_seconds']]
    return [f'review/fps-{a:03d}-{d}m-{state}.png' for a,d in viewpoints for state in states]+[f'review/fps-{a:03d}-4m-closed.png' for a in f['closed_front_angles_degrees']]

"""Validate bounded original R3 observation bytes; completion is not a gameplay pass."""
import hashlib
import json
import math
import re

PRODUCER = '9dd81678b649ac7a13eb7e47354afeaf62acf323'
INPUT = 'JourneyEvidence/R3ContinuousContact/consumer-input.json'
TEST_SOURCE = 'Assets/DesertRV/Tests/PlayMode/JourneyR3ContinuousContactTests.cs'
SOURCE_PATHS = (
    'Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity',
    'Assets/DesertRV/Scenes/Journey/NightBeacon.unity',
    *(f'Assets/DesertRV/Runtime/{n}.cs' for n in ('JourneyMotor', 'BeastActor', 'JourneyDirector', 'JourneySession', 'MobileInputAdapter', 'JourneyActions', 'JourneyActions.Geometry')),
    TEST_SOURCE,
)
PLANS = (
    ('static-control', False, 0., 1/30, [('stationary',30,0,0),('reverse',60,-1,0),('forward',90,1,0),('forward-left',30,1,-1),('reverse-right',30,-1,1)]),
    ('natural-approach-30hz', True, 0., 1/30, [('stationary-approach',240,0,0),('reverse',102,-1,0),('forward',96,1,0),('reverse-again',102,-1,0),('reverse-left',36,-1,-1),('forward-left',39,1,-1),('reverse-right',51,-1,1),('forward-held',132,1,0)]),
    ('natural-approach-5hz-heading20', True, 20., .2, [('stationary-approach',80,0,0),('reverse',17,-1,0),('forward',16,1,0),('reverse-again',17,-1,0),('reverse-left',6,-1,-1),('forward-left',7,1,-1),('reverse-right',9,-1,1),('forward-held',22,1,0)]),
)


def mark_rejection(error, location, value):
    # Only schema-owned field names/array indexes reach location. Values stay hashed.
    if not hasattr(error, 'report_location'):
        error.report_location = location
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=True).encode()
        error.value_sha256 = hashlib.sha256(raw).hexdigest()
    return error


def require(ok, code, location=None, value=None):
    if not ok:
        error = ValueError('R3_CONTINUOUS_' + code)
        raise mark_rejection(error, location, value) if location else error


def number(x):
    return type(x) in (float, int) and math.isfinite(x)


def finite_tree(value, depth=0, location='$'):
    try:
        require(depth <= 24, 'DEPTH')
        if type(value) is dict:
            for key, item in value.items():
                require(type(key) is str and len(key) <= 128, 'KEY')
                child = key if key in KNOWN_FIELD_NAMES else '<unknown>'
                finite_tree(item, depth + 1, location + '.' + child)
        elif type(value) is list:
            require(len(value) <= 4096, 'ARRAY_BOUND')
            for index, item in enumerate(value):
                finite_tree(item, depth + 1, location + '[' + str(index) + ']')
        elif type(value) in (int, float):
            require(math.isfinite(value), 'NONFINITE')
        else:
            require(value is None or type(value) in (str, bool), 'TYPE')
            if type(value) is str:
                require(len(value) <= 4096, 'STRING_BOUND')
    except ValueError as error:
        raise mark_rejection(error, location, value)


def close(a, b):
    return number(a) and abs(a - b) <= 1e-5


def vector(value):
    require(type(value) is dict and set(value) == {'x','y','z'} and all(number(x) for x in value.values()), 'VECTOR')


# Exact report DTO keys/types. Unknown fields are never exported.
SCHEMA = {'Pin': {'path': 's', 'sha256': 's'}, 'DependencyCheck': {'passed': 'b', 'expectedCount': 'i', 'actualCount': 'i', 'inputSha256': 's', 'mismatches': 's[]'}, 'ColliderIdentity': {'id': 'i', 'instanceId': 'i', 'scene': 's', 'path': 's', 'type': 's', 'role': 's', 'trigger': 'b', 'min': 'v', 'max': 'v'}, 'Hit': {'present': 'b', 'self': 'b', 'walker': 'b', 'upward': 'b', 'beast': 'b', 'dead': 'b', 'collider': 'i', 'distance': 'n', 'point': 'v', 'normal': 'v'}, 'Query': {'rawCount': 'i', 'fullCount': 'i', 'performed': 'b', 'saturated': 'b', 'rawIds': 'i[]', 'fullIds': 'i[]', 'nearestRaw': 'Hit', 'nearestFull': 'Hit', 'direction': 'v', 'distance': 'n'}, 'AIQuery': {'route': 's', 'recorded': 'b', 'clearAttackLine': 'b', 'attackLineHit': 'Hit', 'queryBottom': 'v', 'queryTop': 'v', 'forward': 'Query', 'tangent': 'Query'}, 'Beast': {'id': 'i', 'health': 'i', 'phase': 's', 'active': 'b', 'enabled': 'b', 'dead': 'b', 'killedByRam': 'b', 'proxyOverlap': 'b', 'axisInside': 'b', 'penetration': 'b', 'actualAIHitBufferColliderIds': 'i[]', 'position': 'v', 'bottom': 'v', 'top': 'v', 'physicsMin': 'v', 'physicsMax': 'v', 'penetrationDirection': 'v', 'yaw': 'n', 'radius': 'n', 'phaseTime': 'n', 'attackClock': 'n', 'axisDistance': 'n', 'penetrationDepth': 'n', 'aiQuery': 'AIQuery'}, 'ArcTarget': {'beast': 'i', 'centerDistance': 'n', 'surfaceDistance': 'n', 'inRange': 'b', 'clearLine': 'b', 'firstLOSBlocker': 'Hit'}, 'ArcObservation': {'sourceReady': 'b', 'sourceDistanceFinite': 'b', 'sourceBlocker': 'i', 'pulseId': 'i', 'sourceQuery': 's', 'sourceSquareDistanceRaw': 's', 'sourceSquareDistance': 'n', 'cooldown': 'n', 'origin': 'v', 'targets': 'ArcTarget[]'}, 'ArcEvent': {'frame': 'i', 'target': 'i', 'epoch': 'i', 'sequence': 'i', 'pulse': 'i', 'origin': 'v', 'end': 'v'}, 'Contact': {'frame': 'i', 'speed': 'n', 'actualVehicleYaw': 'n', 'actualVehiclePosition': 'v', 'hit': 'Hit'}, 'MotorObservation': {'position': 'v', 'forward': 'v', 'yaw': 'n', 'speed': 'n', 'targetSpeed': 'n', 'predictedSpeed': 'n', 'intendedDistance': 'n', 'throttle': 'n', 'steering': 'n', 'attemptedYaw': 'n', 'castHeadingYaw': 'n', 'powerConnected': 'b', 'rotationAttempted': 'b', 'rotationBlocked': 'b', 'rotationRawCount': 'i', 'rotationFullCount': 'i', 'rotationNearest': 'i', 'rotationRawIds': 'i[]', 'rotationFullIds': 'i[]', 'translation': 'Query'}, 'Frame': {'frame': 'i', 'sequenceFrame': 'i', 'vehicleHealthBeforeAI': 'i', 'vehicleHealthBeforeMotor': 'i', 'vehicleHealthAfter': 'i', 'playerHealth': 'i', 'dt': 'n', 'aiDelta': 'n', 'unscaledDelta': 'n', 'fixedDelta': 'n', 'captureDelta': 'n', 'timeScale': 'n', 'gameTime': 'n', 'realTime': 'n', 'yawAfter': 'n', 'speedAfter': 'n', 'status': 's', 'control': 's', 'step': 's', 'beforeAI': 'v', 'after': 'v', 'beastsBeforeAI': 'Beast[]', 'beastsBeforeMotor': 'Beast[]', 'beastsAfter': 'Beast[]', 'actualMotor32BufferColliderIds': 'i[]', 'actualRotation32BufferColliderIds': 'i[]', 'motor': 'MotorObservation', 'arcBeforeDirector': 'ArcObservation', 'arcAfterDirector': 'ArcObservation', 'motorObstacleContact': 'Contact[]', 'arcPresented': 'ArcEvent[]'}, 'Step': {'name': 's', 'frames': 'i', 'throttle': 'n', 'steering': 'n'}, 'Sequence': {'name': 's', 'fixture': 's', 'upgrades': 's', 'liveEnemies': 'b', 'completed': 'b', 'yawOffset': 'n', 'requestedCaptureDelta': 'n', 'initialYaw': 'n', 'sourceSpawn': 'v', 'initialVehicle': 'v', 'authoredEnemies': 'Beast[]', 'initialVehicleHealth': 'i', 'initialPlayerHealth': 'i', 'plan': 'Step[]', 'frames': 'Frame[]'}, 'Report': {'schemaVersion': 'i', 'frameBound': 'i', 'status': 's', 'failureCode': 's', 'unityVersion': 's', 'producerCommit': 's', 'consumerCommit': 's', 'producerRunId': 's', 'scope': 's', 'timestep': 's', 'inputRoute': 's', 'queryRoute': 's', 'nearestSemantics': 's', 'physicsAutoSyncTransforms': 'b', 'replayDetached': 'b', 'sceneUnloaded': 'b', 'sourceFilesUnchanged': 'b', 'timeRestored': 'b', 'originalCaptureDelta': 'n', 'originalTimeScale': 'n', 'originalFixedDelta': 'n', 'dependencyCheck': 'DependencyCheck', 'sourceFiles': 'Pin[]', 'colliders': 'ColliderIdentity[]', 'sequences': 'Sequence[]'}}
KNOWN_FIELD_NAMES = frozenset(key for fields in SCHEMA.values() for key in fields) | {'x', 'y', 'z'}
EXACT_TEXT = {'scope': 'controlled R3 fixture, real yielding PlayMode frames and unchanged production Update; not an exact replay or human play', 'timestep': 'Time.captureDeltaTime=1/30 or 0.2 and timeScale=1; fixedDeltaTime preserved; controlled game-time cadence, not measured rendering FPS; Beast Update clamps delta to 0.1 while Director uses full delta', 'inputRoute': 'test-owned replay fingers -> ordinary JourneySession.Update/Input.Sample -> Director.Update/Motor.Tick/Actions.Tick; no OS key events', 'queryRoute': 'read-only snapshots: AI queries before actor Updates (cross-actor ordering may differ); Motor queries after AI/before Director are predictions without mutating self-collider poses; repeat NonAlloc selection/order may differ; Arc geometry is sampled before and after Director, while actual ObstacleContact and ArcPresented callbacks; raw production buffer IDs are read-only and may contain stale entries outside unknown valid prefixes; no per-frame Physics.SyncTransforms', 'nearestSemantics': 'Motor nearest filters self/walker/upward only, before initial-overlap escape and ram logic. AI nearest filters own hierarchy/upward. Rotation nearest uses bounds distance, since overlap has no contact distance.', 'fixture': 'fresh R3 setup; Ram+Arc installed via state APIs; Driving/unplugged; first wave activated at saved natural roots; RV x=1.7/z=24 and relative heading are approximate fixture values, not measured desktop coordinates; no later beast placement or damage calls'}
# Path tokens extracted from exact prepared Bootstrap/R3, prefab name overrides, strict prefabs and source-closure prefabs.
COLLIDER_NODE_NAMES = frozenset(['Antenna feed receiver', 'Antenna rim', 'ArcPresentation', 'Arrow head L', 'Arrow head R', 'Arrow shaft', 'Available choice', 'Beacon base service light', 'Beacon blue lantern', 'Beacon diagonal brace', 'Beacon directional signal reflector', 'Beacon emissive lens', 'Beacon equipment worklight', 'Beacon foundation', 'Beacon ground power cable', 'Beacon lantern housing', 'Beacon lattice leg', 'Beacon power cabinet', 'Beacon relay accumulator', 'Beacon safe zone', 'Beacon service lamp housing', 'Beacon solar collector 0', 'Beacon solar collector 1', 'Beacon solar collector 2', 'Beacon warm lamp diffuser', 'Boulder scatter 0-0', 'Boulder scatter 0-1', 'Boulder scatter 0-2', 'Boulder scatter 12-0', 'Boulder scatter 12-1', 'Boulder scatter 12-2', 'Boulder scatter 15-0', 'Boulder scatter 15-1', 'Boulder scatter 15-2', 'Boulder scatter 18-0', 'Boulder scatter 18-1', 'Boulder scatter 18-2', 'Boulder scatter 3-0', 'Boulder scatter 3-1', 'Boulder scatter 3-2', 'Boulder scatter 6-0', 'Boulder scatter 6-1', 'Boulder scatter 6-2', 'Boulder scatter 9-0', 'Boulder scatter 9-1', 'Boulder scatter 9-2', 'Cabin fitted details', 'Cabin installation point', 'Cabin interior reflection', 'Cabin precision hardware', 'Cabin window bounce -1', 'Cabin window bounce 1', 'Cabinet lower ventilation slot', 'Cabinet pull handle', 'Cabinet warm light', 'Cache padlock body', 'Cache padlock shackle', 'Cache padlock shackle top', 'Candidate', 'CandidateShotMuzzleAxis', 'Canopy roof rib', 'Chinese engraved label', 'Choice text', 'Closed cache crossed seal', 'DISTANT-Mesa-0', 'DISTANT-Mesa-1', 'DISTANT-Mesa-2', 'DISTANT-Mesa-3', 'Dusty painted metal face', 'Evacuation painted chevron', 'Exit volume', 'Exposed paint chip', 'Exposure response', 'Far road continuation', 'Finished cabin surfaces', 'Fitted arc', 'Fitted ram', 'GEO-agave_leaf(Clone)', 'GEO-agave_leaf.001(Clone)', 'GEO-agave_leaf.002(Clone)', 'GEO-agave_leaf.003(Clone)', 'GEO-agave_leaf.004(Clone)', 'GEO-agave_leaf.005(Clone)', 'GEO-agave_leaf.006(Clone)', 'GEO-agave_leaf.007(Clone)', 'GEO-agave_leaf.008(Clone)', 'GEO-agave_leaf.009(Clone)', 'GEO-agave_leaf.010(Clone)', 'GEO-aisle_service_mat', 'GEO-axle', 'GEO-axle.001', 'GEO-beltline_trim', 'GEO-beltline_trim_front', 'GEO-beltline_trim_rear', 'GEO-bench_drawer', 'GEO-bench_drawer.001', 'GEO-bench_drawer.002', 'GEO-bench_vise_base', 'GEO-bench_vise_body', 'GEO-body_panel_rivet', 'GEO-body_panel_rivet.001', 'GEO-body_panel_rivet.002', 'GEO-body_panel_rivet.003', 'GEO-body_panel_rivet.004', 'GEO-body_panel_rivet.005', 'GEO-body_panel_rivet.006', 'GEO-body_panel_rivet.007', 'GEO-body_panel_rivet.008', 'GEO-body_panel_rivet.009', 'GEO-body_panel_rivet.010', 'GEO-body_panel_rivet.011', 'GEO-body_panel_rivet.012', 'GEO-body_panel_rivet.013', 'GEO-body_panel_rivet.014', 'GEO-body_panel_rivet.015', 'GEO-cab_dashboard', 'GEO-cab_seat_back', 'GEO-cab_seat_back.001', 'GEO-cab_seat_base', 'GEO-cab_seat_base.001', 'GEO-cab_seat_cushion', 'GEO-cab_seat_cushion.001', 'GEO-cabin_detail_hardware', 'GEO-cabinet_inset_seam', 'GEO-cabinet_inset_seam.001', 'GEO-cabinet_inset_seam.002', 'GEO-cabinet_inset_seam.003', 'GEO-cabinet_inset_seam.004', 'GEO-cabinet_inset_seam.005', 'GEO-cabinet_inset_seam.006', 'GEO-cabinet_inset_seam.007', 'GEO-cabinet_inset_seam.008', 'GEO-cabinet_inset_seam.009', 'GEO-cabinet_inset_seam.010', 'GEO-cabinet_inset_seam.011', 'GEO-cabinet_inset_seam.012', 'GEO-cabinet_inset_seam.013', 'GEO-cabinet_inset_seam.014', 'GEO-cabinet_inset_seam.015', 'GEO-cabinet_inset_seam.016', 'GEO-cabinet_inset_seam.017', 'GEO-cabinet_inset_seam.018', 'GEO-cabinet_inset_seam.019', 'GEO-cabinet_inset_seam.020', 'GEO-cabinet_inset_seam.021', 'GEO-cabinet_inset_seam.022', 'GEO-cabinet_inset_seam.023', 'GEO-ceiling_liner', 'GEO-chassis', 'GEO-clearance_lamp', 'GEO-clearance_lamp.001', 'GEO-clearance_lamp.002', 'GEO-clearance_lamp.003', 'GEO-coach_body_shell', 'GEO-coiled_test_lead', 'GEO-console_mount_foot', 'GEO-console_mount_foot.001', 'GEO-console_support', 'GEO-console_support.001', 'GEO-crate_label', 'GEO-crate_label.001', 'GEO-crate_label.002', 'GEO-crate_latch', 'GEO-crate_latch.001', 'GEO-crate_latch.002', 'GEO-crate_latch.003', 'GEO-crate_latch.004', 'GEO-crate_latch.005', 'GEO-crate_legend', 'GEO-crate_legend.001', 'GEO-crate_legend.002', 'GEO-crate_lid', 'GEO-crate_lid.001', 'GEO-crate_lid.002', 'GEO-dashboard_cream_fascia', 'GEO-dashboard_gauge', 'GEO-dashboard_gauge.001', 'GEO-dashboard_gauge.002', 'GEO-door_weatherseal', 'GEO-drawer_pull', 'GEO-drawer_pull.001', 'GEO-drawer_pull.002', 'GEO-entry_door', 'GEO-entry_door_beltline', 'GEO-entry_door_window', 'GEO-entry_handle', 'GEO-entry_handle_recess', 'GEO-entry_hinge', 'GEO-entry_hinge.001', 'GEO-entry_step', 'GEO-entry_step_lower', 'GEO-exterior_service_hatch', 'GEO-floor_board', 'GEO-floor_board.001', 'GEO-floor_board.002', 'GEO-floor_board.003', 'GEO-floor_board.004', 'GEO-floor_board.005', 'GEO-floor_board.006', 'GEO-floor_board.007', 'GEO-floor_board.008', 'GEO-folding_step_support', 'GEO-folding_step_support.001', 'GEO-front_bumper', 'GEO-front_grille_recess', 'GEO-front_mount_bracket_left', 'GEO-front_mount_bracket_right', 'GEO-garage_toolbox(Clone)', 'GEO-gauge_needle', 'GEO-gauge_needle.001', 'GEO-grille_louvre', 'GEO-grille_louvre.001', 'GEO-grille_louvre.002', 'GEO-grille_louvre.003', 'GEO-hatch_latch', 'GEO-hatch_latch.001', 'GEO-headlamp_bezel', 'GEO-headlamp_bezel.001', 'GEO-headlamp_lens', 'GEO-headlamp_lens.001', 'GEO-interior_floor', 'GEO-interior_wall_liner', 'GEO-interior_wall_liner.001', 'GEO-ladder_rung', 'GEO-ladder_rung.001', 'GEO-ladder_rung.002', 'GEO-ladder_rung.003', 'GEO-ladder_rung.004', 'GEO-ladder_rung.005', 'GEO-ladder_rung.006', 'GEO-loose_stone.018(Clone)', 'GEO-loose_stone.022(Clone)', 'GEO-lower_body_moulding', 'GEO-lower_body_moulding.001', 'GEO-lower_body_moulding.002', 'GEO-lower_body_moulding.003', 'GEO-lower_body_moulding.004', 'GEO-lower_body_moulding.005', 'GEO-luggage_strap', 'GEO-luggage_strap.001', 'GEO-maintenance_toolbox', 'GEO-mirror_glass', 'GEO-mirror_glass.001', 'GEO-mirror_housing', 'GEO-mirror_housing.001', 'GEO-mirror_stem', 'GEO-mirror_stem.001', 'GEO-mud_flap', 'GEO-mud_flap.001', 'GEO-mud_flap.002', 'GEO-mud_flap.003', 'GEO-notes_clip', 'GEO-notes_clip.001', 'GEO-overhead_cabinet_door', 'GEO-overhead_cabinet_door.001', 'GEO-overhead_cabinet_door.002', 'GEO-overhead_cabinet_door.003', 'GEO-overhead_cabinet_door.004', 'GEO-overhead_cabinet_door.005', 'GEO-overhead_pull', 'GEO-overhead_pull.001', 'GEO-overhead_pull.002', 'GEO-overhead_pull.003', 'GEO-overhead_pull.004', 'GEO-overhead_pull.005', 'GEO-overhead_supply_cabinet', 'GEO-overhead_supply_cabinet.001', 'GEO-panel_fastener', 'GEO-panel_fastener.001', 'GEO-panel_fastener.002', 'GEO-panel_fastener.003', 'GEO-power_toggle', 'GEO-power_toggle.001', 'GEO-power_toggle.002', 'GEO-power_toggle.003', 'GEO-rack_crossbar', 'GEO-rack_crossbar.001', 'GEO-rack_crossbar.002', 'GEO-rack_crossbar.003', 'GEO-rack_foot', 'GEO-rack_foot.001', 'GEO-rack_foot.002', 'GEO-rack_foot.003', 'GEO-rack_top_rail', 'GEO-rack_top_rail.001', 'GEO-rack_upright', 'GEO-rack_upright.001', 'GEO-rack_upright.002', 'GEO-rack_upright.003', 'GEO-rear_bumper', 'GEO-rear_ladder_rail', 'GEO-rear_ladder_rail.001', 'GEO-rear_lamp', 'GEO-rear_lamp.001', 'GEO-rear_repair_bench', 'GEO-rear_repair_top', 'GEO-rear_window_glass', 'GEO-rear_window_seal', 'GEO-rear_work_mat', 'GEO-rear_workbench_foot', 'GEO-rear_workbench_foot.001', 'GEO-road_tyre', 'GEO-road_tyre.001', 'GEO-road_tyre.002', 'GEO-road_tyre.003', 'GEO-roof_skylight_frame', 'GEO-roof_skylight_lid', 'GEO-roof_storage_case', 'GEO-runner_edge', 'GEO-runner_edge.001', 'GEO-runner_woven_rib', 'GEO-runner_woven_rib.001', 'GEO-runner_woven_rib.002', 'GEO-runner_woven_rib.003', 'GEO-runner_woven_rib.004', 'GEO-runner_woven_rib.005', 'GEO-runner_woven_rib.006', 'GEO-runner_woven_rib.007', 'GEO-runner_woven_rib.008', 'GEO-runner_woven_rib.009', 'GEO-runner_woven_rib.010', 'GEO-runner_woven_rib.011', 'GEO-runner_woven_rib.012', 'GEO-runner_woven_rib.013', 'GEO-runner_woven_rib.014', 'GEO-runner_woven_rib.015', 'GEO-runner_woven_rib.016', 'GEO-runner_woven_rib.017', 'GEO-runner_woven_rib.018', 'GEO-runner_woven_rib.019', 'GEO-runner_woven_rib.020', 'GEO-runner_woven_rib.021', 'GEO-runner_woven_rib.022', 'GEO-runner_woven_rib.023', 'GEO-runner_woven_rib.024', 'GEO-saguaro_arm.004(Clone)', 'GEO-saguaro_arm.005(Clone)', 'GEO-saguaro_trunk.002(Clone)', 'GEO-service_panel_title', 'GEO-service_power_panel', 'GEO-service_round_gauge', 'GEO-service_round_gauge.001', 'GEO-socket_on_mat', 'GEO-socket_on_mat.001', 'GEO-socket_on_mat.002', 'GEO-socket_on_mat.003', 'GEO-socket_on_mat.004', 'GEO-socket_rim', 'GEO-socket_rim.001', 'GEO-socket_rim.002', 'GEO-socket_rim.003', 'GEO-socket_rim.004', 'GEO-solar_cell_division', 'GEO-solar_cell_division.001', 'GEO-solar_cell_division.002', 'GEO-solar_cell_division.003', 'GEO-solar_cell_division.004', 'GEO-solar_panel', 'GEO-solar_panel_frame', 'GEO-spare_hub', 'GEO-spare_mount_plate', 'GEO-spare_parts_crate', 'GEO-spare_parts_crate.001', 'GEO-spare_parts_crate.002', 'GEO-spare_rim', 'GEO-spare_tyre', 'GEO-steering_column', 'GEO-steering_spoke', 'GEO-steering_spoke.001', 'GEO-steering_spoke.002', 'GEO-steering_wheel', 'GEO-step_grip', 'GEO-step_grip.001', 'GEO-step_grip.002', 'GEO-step_grip.003', 'GEO-supply_cabinet', 'GEO-supply_door', 'GEO-supply_door.001', 'GEO-supply_door.002', 'GEO-supply_hinge', 'GEO-supply_hinge.001', 'GEO-supply_hinge.002', 'GEO-supply_hinge.003', 'GEO-supply_hinge.004', 'GEO-supply_hinge.005', 'GEO-supply_latch', 'GEO-supply_latch.001', 'GEO-supply_latch.002', 'GEO-supply_top', 'GEO-toolbox_clasp(Clone)', 'GEO-toolbox_clasp.001(Clone)', 'GEO-toolbox_handle', 'GEO-toolbox_handle(Clone)', 'GEO-toolbox_lid', 'GEO-toolbox_lid(Clone)', 'GEO-tread_sipe', 'GEO-tread_sipe.001', 'GEO-tread_sipe.002', 'GEO-tread_sipe.003', 'GEO-tread_sipe.004', 'GEO-tread_sipe.005', 'GEO-tread_sipe.006', 'GEO-tread_sipe.007', 'GEO-tread_sipe.008', 'GEO-tread_sipe.009', 'GEO-tread_sipe.010', 'GEO-tread_sipe.011', 'GEO-tread_sipe.012', 'GEO-tread_sipe.013', 'GEO-tread_sipe.014', 'GEO-tread_sipe.015', 'GEO-tread_sipe.016', 'GEO-tread_sipe.017', 'GEO-tread_sipe.018', 'GEO-tread_sipe.019', 'GEO-tread_sipe.020', 'GEO-tread_sipe.021', 'GEO-tread_sipe.022', 'GEO-tread_sipe.023', 'GEO-tread_sipe.024', 'GEO-tread_sipe.025', 'GEO-tread_sipe.026', 'GEO-tread_sipe.027', 'GEO-tread_sipe.028', 'GEO-tread_sipe.029', 'GEO-tread_sipe.030', 'GEO-tread_sipe.031', 'GEO-tread_sipe.032', 'GEO-tread_sipe.033', 'GEO-tread_sipe.034', 'GEO-tread_sipe.035', 'GEO-tread_sipe.036', 'GEO-tread_sipe.037', 'GEO-tread_sipe.038', 'GEO-tread_sipe.039', 'GEO-tread_sipe.040', 'GEO-tread_sipe.041', 'GEO-tread_sipe.042', 'GEO-tread_sipe.043', 'GEO-tread_sipe.044', 'GEO-tread_sipe.045', 'GEO-tread_sipe.046', 'GEO-tread_sipe.047', 'GEO-tread_sipe.048', 'GEO-tread_sipe.049', 'GEO-tread_sipe.050', 'GEO-tread_sipe.051', 'GEO-tread_sipe.052', 'GEO-tread_sipe.053', 'GEO-tread_sipe.054', 'GEO-tread_sipe.055', 'GEO-tread_sipe.056', 'GEO-tread_sipe.057', 'GEO-tread_sipe.058', 'GEO-tread_sipe.059', 'GEO-tread_sipe.060', 'GEO-tread_sipe.061', 'GEO-tread_sipe.062', 'GEO-tread_sipe.063', 'GEO-tread_sipe.064', 'GEO-tread_sipe.065', 'GEO-tread_sipe.066', 'GEO-tread_sipe.067', 'GEO-tread_sipe.068', 'GEO-tread_sipe.069', 'GEO-tread_sipe.070', 'GEO-tread_sipe.071', 'GEO-tread_sipe.072', 'GEO-tread_sipe.073', 'GEO-tread_sipe.074', 'GEO-tread_sipe.075', 'GEO-tread_sipe.076', 'GEO-tread_sipe.077', 'GEO-tread_sipe.078', 'GEO-tread_sipe.079', 'GEO-tread_sipe.080', 'GEO-tread_sipe.081', 'GEO-tread_sipe.082', 'GEO-tread_sipe.083', 'GEO-tread_sipe.084', 'GEO-tread_sipe.085', 'GEO-tread_sipe.086', 'GEO-tread_sipe.087', 'GEO-tread_sipe.088', 'GEO-tread_sipe.089', 'GEO-tread_sipe.090', 'GEO-tread_sipe.091', 'GEO-tread_sipe.092', 'GEO-tread_sipe.093', 'GEO-tread_sipe.094', 'GEO-tread_sipe.095', 'GEO-tread_sipe.096', 'GEO-tread_sipe.097', 'GEO-tread_sipe.098', 'GEO-tread_sipe.099', 'GEO-tread_sipe.100', 'GEO-tread_sipe.101', 'GEO-tread_sipe.102', 'GEO-tread_sipe.103', 'GEO-tread_sipe.104', 'GEO-tread_sipe.105', 'GEO-tread_sipe.106', 'GEO-tread_sipe.107', 'GEO-tread_sipe.108', 'GEO-tread_sipe.109', 'GEO-tread_sipe.110', 'GEO-tread_sipe.111', 'GEO-tread_sipe.112', 'GEO-tread_sipe.113', 'GEO-tread_sipe.114', 'GEO-tread_sipe.115', 'GEO-tread_sipe.116', 'GEO-tread_sipe.117', 'GEO-tread_sipe.118', 'GEO-tread_sipe.119', 'GEO-tread_sipe.120', 'GEO-tread_sipe.121', 'GEO-tread_sipe.122', 'GEO-tread_sipe.123', 'GEO-tread_sipe.124', 'GEO-tread_sipe.125', 'GEO-tread_sipe.126', 'GEO-tread_sipe.127', 'GEO-tread_sipe.128', 'GEO-tread_sipe.129', 'GEO-tread_sipe.130', 'GEO-tread_sipe.131', 'GEO-tread_sipe.132', 'GEO-tread_sipe.133', 'GEO-tread_sipe.134', 'GEO-tread_sipe.135', 'GEO-tread_sipe.136', 'GEO-tread_sipe.137', 'GEO-tread_sipe.138', 'GEO-tread_sipe.139', 'GEO-tread_sipe.140', 'GEO-tread_sipe.141', 'GEO-tread_sipe.142', 'GEO-tread_sipe.143', 'GEO-tread_sipe.144', 'GEO-tread_sipe.145', 'GEO-tread_sipe.146', 'GEO-tread_sipe.147', 'GEO-tread_sipe.148', 'GEO-tread_sipe.149', 'GEO-tread_sipe.150', 'GEO-tread_sipe.151', 'GEO-tread_sipe.152', 'GEO-tread_sipe.153', 'GEO-tread_sipe.154', 'GEO-tread_sipe.155', 'GEO-tread_sipe.156', 'GEO-tread_sipe.157', 'GEO-tread_sipe.158', 'GEO-tread_sipe.159', 'GEO-tread_sipe.160', 'GEO-tread_sipe.161', 'GEO-tread_sipe.162', 'GEO-tread_sipe.163', 'GEO-tread_sipe.164', 'GEO-tread_sipe.165', 'GEO-tread_sipe.166', 'GEO-tread_sipe.167', 'GEO-tread_sipe.168', 'GEO-tread_sipe.169', 'GEO-tread_sipe.170', 'GEO-tread_sipe.171', 'GEO-tread_sipe.172', 'GEO-tread_sipe.173', 'GEO-tread_sipe.174', 'GEO-tread_sipe.175', 'GEO-tread_sipe.176', 'GEO-tread_sipe.177', 'GEO-tread_sipe.178', 'GEO-tread_sipe.179', 'GEO-tread_sipe.180', 'GEO-tread_sipe.181', 'GEO-tread_sipe.182', 'GEO-tread_sipe.183', 'GEO-tread_sipe.184', 'GEO-tread_sipe.185', 'GEO-tread_sipe.186', 'GEO-tread_sipe.187', 'GEO-tread_sipe.188', 'GEO-tread_sipe.189', 'GEO-tread_sipe.190', 'GEO-tread_sipe.191', 'GEO-turn_indicator', 'GEO-turn_indicator.001', 'GEO-under_cabinet_light', 'GEO-under_cabinet_light.001', 'GEO-under_cabinet_light.002', 'GEO-under_cabinet_light.003', 'GEO-upper_wall_rail', 'GEO-upper_wall_rail.001', 'GEO-vise_jaw', 'GEO-vise_jaw.001', 'GEO-vise_lever', 'GEO-vise_screw', 'GEO-weathered_mesa.002(Clone)', 'GEO-weathered_mesa.003(Clone)', 'GEO-weathered_mesa.004(Clone)', 'GEO-weathered_mesa.005(Clone)', 'GEO-wheel_arch_rolled_lip', 'GEO-wheel_arch_rolled_lip.001', 'GEO-wheel_arch_rolled_lip.002', 'GEO-wheel_arch_rolled_lip.003', 'GEO-wheel_hub', 'GEO-wheel_hub.001', 'GEO-wheel_hub.002', 'GEO-wheel_hub.003', 'GEO-wheel_lug', 'GEO-wheel_lug.001', 'GEO-wheel_lug.002', 'GEO-wheel_lug.003', 'GEO-wheel_lug.004', 'GEO-wheel_lug.005', 'GEO-wheel_lug.006', 'GEO-wheel_lug.007', 'GEO-wheel_lug.008', 'GEO-wheel_lug.009', 'GEO-wheel_lug.010', 'GEO-wheel_lug.011', 'GEO-wheel_lug.012', 'GEO-wheel_lug.013', 'GEO-wheel_lug.014', 'GEO-wheel_lug.015', 'GEO-wheel_lug.016', 'GEO-wheel_lug.017', 'GEO-wheel_lug.018', 'GEO-wheel_lug.019', 'GEO-wheel_lug.020', 'GEO-wheel_lug.021', 'GEO-wheel_lug.022', 'GEO-wheel_lug.023', 'GEO-wheel_steel_rim', 'GEO-wheel_steel_rim.001', 'GEO-wheel_steel_rim.002', 'GEO-wheel_steel_rim.003', 'GEO-wheel_vent', 'GEO-wheel_vent.001', 'GEO-wheel_vent.002', 'GEO-wheel_vent.003', 'GEO-wheel_vent.004', 'GEO-wheel_vent.005', 'GEO-wheel_vent.006', 'GEO-wheel_vent.007', 'GEO-wheel_vent.008', 'GEO-wheel_vent.009', 'GEO-wheel_vent.010', 'GEO-wheel_vent.011', 'GEO-wheel_vent.012', 'GEO-wheel_vent.013', 'GEO-wheel_vent.014', 'GEO-wheel_vent.015', 'GEO-wheel_vent.016', 'GEO-wheel_vent.017', 'GEO-wheel_vent.018', 'GEO-wheel_vent.019', 'GEO-wheel_vent.020', 'GEO-wheel_vent.021', 'GEO-wheel_vent.022', 'GEO-wheel_vent.023', 'GEO-window_aluminium_divider', 'GEO-window_aluminium_divider.001', 'GEO-window_aluminium_divider.002', 'GEO-window_aluminium_divider.003', 'GEO-window_aluminium_divider.004', 'GEO-window_aluminium_divider.005', 'GEO-window_glass', 'GEO-window_glass.001', 'GEO-window_glass.002', 'GEO-window_glass.003', 'GEO-window_glass.004', 'GEO-window_glass.005', 'GEO-window_rubber', 'GEO-window_rubber.001', 'GEO-window_rubber.002', 'GEO-window_rubber.003', 'GEO-window_rubber.004', 'GEO-window_rubber.005', 'GEO-windscreen', 'GEO-windscreen_centre_mullion', 'GEO-windscreen_seal', 'GEO-wiper_arm', 'GEO-wiper_arm.001', 'GEO-wiper_blade', 'GEO-wiper_blade.001', 'GEO-work_notes_board', 'GEO-work_notes_lines', 'GEO-work_notes_lines.001', 'GEO-work_notes_lines.002', 'GEO-work_notes_lines.003', 'GEO-work_notes_lines.004', 'GEO-work_notes_lines.005', 'GEO-workbench_frame', 'GEO-workbench_top', 'Gauge needle', 'Journey HUD', 'Journey walker', 'JourneyBootstrap', 'MODULE_roof_cargo', 'MOUNT_front_ram', 'MOUNT_roof_equipment', 'Middle boulder 0', 'Middle boulder 12', 'Middle boulder 15', 'Middle boulder 18', 'Middle boulder 3', 'Middle boulder 6', 'Middle boulder 9', 'MuzzleFlash', 'Nail head', 'Nail shaft', 'Open-jaw spanner pictogram', 'Optional cache - region-3', 'Optional supply choice - region 3', 'Optional supply choice completed', 'Optional supply directions', 'Plate rivet', 'Power analogue gauge', 'Power cabinet face', 'Power interaction', 'Power socket conduit', 'Power status indicator 0', 'Power status indicator 1', 'Power status indicator 2', 'Preflight Camera', 'RIG-entry_door_pivot', 'RIG-wheel_left_front', 'RIG-wheel_left_rear', 'RIG-wheel_right_front', 'RIG-wheel_right_rear', 'RV Body Study', 'Region 3 environment', 'Regional sunlight', 'Relay cooling vent', 'Relay service panel', 'Relay shelter rear wall', 'Road behind arrival', 'Road paint 0', 'Road paint 1', 'Road paint 10', 'Road paint 11', 'Road paint 12', 'Road paint 13', 'Road paint 14', 'Road paint 15', 'Road paint 2', 'Road paint 3', 'Road paint 4', 'Road paint 5', 'Road paint 6', 'Road paint 7', 'Road paint 8', 'Road paint 9', 'Road shoulder patch 0', 'Road shoulder patch 1', 'Road shoulder patch 10', 'Road shoulder patch 11', 'Road shoulder patch 12', 'Road shoulder patch 13', 'Road shoulder patch 14', 'Road shoulder patch 15', 'Road shoulder patch 2', 'Road shoulder patch 3', 'Road shoulder patch 4', 'Road shoulder patch 5', 'Road shoulder patch 6', 'Road shoulder patch 7', 'Road shoulder patch 8', 'Road shoulder patch 9', 'Road surface', 'Roadside sand lobe 0', 'Roadside sand lobe 1', 'Roadside sand lobe 10', 'Roadside sand lobe 11', 'Roadside sand lobe 12', 'Roadside sand lobe 13', 'Roadside sand lobe 14', 'Roadside sand lobe 15', 'Roadside sand lobe 16', 'Roadside sand lobe 17', 'Roadside sand lobe 18', 'Roadside sand lobe 19', 'Roadside sand lobe 2', 'Roadside sand lobe 3', 'Roadside sand lobe 4', 'Roadside sand lobe 5', 'Roadside sand lobe 6', 'Roadside sand lobe 7', 'Roadside sand lobe 8', 'Roadside sand lobe 9', 'Route direction arrow', 'Route foundation', 'Safe-route bollard 0', 'Safe-route bollard 1', 'Safe-route bollard 2', 'Safe-route bollard 3', 'Safe-route bollard 4', 'Safe-route bollard 5', 'Safe-route lamp 0', 'Safe-route lamp 1', 'Safe-route lamp 2', 'Safe-route lamp 3', 'Safe-route lamp 4', 'Safe-route lamp 5', 'Safe-zone arch lintel', 'Safe-zone arch post', 'Safe-zone arrival light', 'Sealed choice', 'Service canopy post', 'Service corrugated roof', 'Shoulder agave 0', 'Shoulder agave 1', 'Shoulder agave 10', 'Shoulder agave 11', 'Shoulder agave 12', 'Shoulder agave 13', 'Shoulder agave 14', 'Shoulder agave 15', 'Shoulder agave 16', 'Shoulder agave 17', 'Shoulder agave 18', 'Shoulder agave 19', 'Shoulder agave 2', 'Shoulder agave 3', 'Shoulder agave 4', 'Shoulder agave 5', 'Shoulder agave 6', 'Shoulder agave 7', 'Shoulder agave 8', 'Shoulder agave 9', 'Shoulder cactus 0', 'Shoulder cactus 12', 'Shoulder cactus 16', 'Shoulder cactus 4', 'Shoulder cactus 8', 'Signal feed support', 'Signal feeder conduit', 'Solar cell divider', 'Spanner handle', 'Spanner jaw base', 'Spanner open jaw', 'Spent supply marker', 'Supply interaction - region-3', 'Supply visual - region-3', 'Three-nail pictogram', 'Timber light worn edge', 'Vehicle exit', 'Vehicle spawn', 'Warm cabin reflected light', 'Weathered timber post', 'Worn metal rim', 'bulwark-candidate', 'optional', 'pouncer-candidate', 'region-3', 'relay-kit', 'tower-ammo', 'wave-1-pouncer-1', 'wave-1-pouncer-2', 'wave-2-armored', 'weapon_hands'])


def closed_schema(value, kind, field='', location='$'):
    try:
        _closed_schema(value, kind, field, location)
    except ValueError as error:
        raise mark_rejection(error, location, value)


def _closed_schema(value, kind, field, location):
    if kind.endswith('[]'):
        require(value is None or type(value) is list, 'CLOSED_ARRAY')
        for index, item in enumerate(value or []): closed_schema(item, kind[:-2], field, location + '[' + str(index) + ']')
    elif kind in SCHEMA:
        if value is None: return  # Unity inline absent objects can also be null.
        require(type(value) is dict, 'CLOSED_KEYS_' + kind.upper())
        unknown = set(value) - set(SCHEMA[kind])
        require(not unknown, 'CLOSED_KEYS_' + kind.upper(), location + '.<unknown>', {k:value[k] for k in unknown})
        missing = set(SCHEMA[kind]) - set(value)
        require(not missing, 'CLOSED_KEYS_' + kind.upper(), location + '.' + min(missing) if missing else location, None)
        for key, subtype in SCHEMA[kind].items():
            closed_schema(value[key], subtype, kind + '.' + key, location + '.' + key)
    elif kind == 'v': vector(value)
    elif kind == 'b': require(type(value) is bool, 'CLOSED_BOOL')
    elif kind == 'i': require(type(value) is int, 'CLOSED_INT')
    elif kind == 'n': require(number(value), 'CLOSED_NUMBER')
    else:
        require(type(value) is str, 'CLOSED_STRING')
        key = field.split('.')[-1]
        if key in EXACT_TEXT: require(value == EXACT_TEXT[key], 'EXACT_TEXT')
        elif field == 'Pin.path': require(value == INPUT or value == INPUT.replace('.json','.sha256') or value in SOURCE_PATHS or value.endswith('.meta') and value[:-5] in SOURCE_PATHS, 'PIN_PATH')
        elif key in {'sha256','inputSha256'}: require(re.fullmatch('[0-9a-f]{64}',value) is not None, 'DIGEST')
        elif key in {'producerCommit','consumerCommit'}: require(re.fullmatch('[0-9a-f]{40}',value) is not None, 'COMMIT_TEXT')
        elif key == 'producerRunId': require(value=='38070456519','RUN_TEXT')
        elif key == 'unityVersion': require(value=='6000.3.19f1','VERSION_TEXT')
        elif key == 'failureCode': require(value=='' or re.fullmatch(r'OBSERVER_(NullReferenceException|MissingMethodException|MissingFieldException|TypeLoadException|TargetInvocationException|AssertionException|ArgumentException|InvalidOperationException|IndexOutOfRangeException|KeyNotFoundException)',value) is not None,'FAILURE_TEXT')
        elif key == 'mismatches': require(False,'MISMATCH_TEXT')
        elif field == 'ColliderIdentity.scene': require(value in ('','DontDestroyOnLoad','Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity','Assets/DesertRV/Scenes/Journey/NightBeacon.unity'),'SCENE_TEXT')
        elif field == 'ColliderIdentity.path': require(0<len(value)<=2048 and len(value.split('/'))<=32 and all(part in COLLIDER_NODE_NAMES for part in value.split('/')),'COLLIDER_PATH')
        elif field == 'ColliderIdentity.type': require(value in {'BoxCollider','MeshCollider','CapsuleCollider','SphereCollider','CharacterController'},'COLLIDER_TYPE')
        elif field == 'ColliderIdentity.role': require(value in {'retained-rv','walker','beast','world'},'ROLE_TEXT')
        elif key == 'phase': require(value in {'Idle','Stalk','Windup','Attack','Recover','Hit','Dead'},'PHASE_TEXT')
        elif key == 'route': require(value in {'','no-move-in-this-phase','home-forward-then-tangent-if-blocked','windup-eligible-no-move','stalk-forward-then-tangent-if-blocked','attack-forward'},'AI_ROUTE_TEXT')
        elif key == 'sourceQuery': require(re.fullmatch(r'(clear|missing-binding|nonconvex-triangles|nonconvex-aabb-distance-lower-bound|native-supported-closest-point|unsupported-solid-collider)(-invalid-geometry)?',value) is not None,'ARC_QUERY_TEXT')
        elif key == 'sourceSquareDistanceRaw': require(re.fullmatch(r'(NaN|Infinity|-Infinity|-?[0-9]+(?:\.[0-9]+)?(?:[Ee][+-]?[0-9]+)?)',value) is not None,'ARC_RAW_TEXT')
        elif field == 'Report.status': require(value in {'completed','fixture-incomplete'},'STATUS_TEXT')
        elif field == 'Frame.status': require(value in {'Menu','Loading','Playing','Paused','Failed','Completed'},'STATUS_TEXT')
        elif key == 'control': require(value in {'Driving','OnFoot'},'CONTROL_TEXT')
        elif key == 'upgrades': require(value=='Ram, Arc','UPGRADES_TEXT')
        elif field == 'Sequence.name': require(value in {p[0] for p in PLANS},'SEQUENCE_TEXT')
        elif key in {'name','step'}: require(value in {row[0] for p in PLANS for row in p[4]},'STEP_TEXT')
        else: require(False,'UNEXPECTED_STRING_FIELD')

MAX_REDACTED_BYTES = 24 * 1024 * 1024
MAX_OMISSIONS = 128


def redact_native_report(raw, rejection_code, native_failure):
    """Safety-only projection of rejected native bytes; never a validated trace."""
    require(type(raw) is bytes and len(raw) <= MAX_REDACTED_BYTES, 'REDACTED_RAW_BOUND')
    require(type(native_failure) is bool and type(rejection_code) is str and
            re.fullmatch(r'(?:R3_CONTINUOUS|R3_NATURAL_CONTACT)_[A-Z0-9_]{1,96}', rejection_code), 'REDACTED_CONTEXT')
    omissions = []; count = 0
    # Reserve wrapper/omission overhead; every data child starts as a charged null.
    budget = MAX_REDACTED_BYTES - 256 * 1024 - 4
    def encode(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=True).encode()
    def omit(value, location, code, missing=False):
        nonlocal count
        count += 1
        if len(omissions) < MAX_OMISSIONS:
            packed = encode(value)
            kind = 'missing' if missing else {type(None):'null', bool:'boolean', int:'number', float:'number', str:'string', list:'array', dict:'object'}[type(value)]
            omissions.append(dict(location=location, code=code, type=kind, jsonBytes=len(packed),
                length=len(value) if type(value) in (str,list,dict) else 0, sha256=hashlib.sha256(packed).hexdigest()))
        return None
    def charge(extra):
        nonlocal budget
        if extra > budget: return False
        budget -= extra; return True
    def project(value, kind, field, location, depth=0):
        if depth > 24: return omit(value,location,'R3_CONTINUOUS_DEPTH')
        if kind.endswith('[]'):
            if value is None: return None
            if type(value) is not list: return omit(value,location,'R3_CONTINUOUS_CLOSED_ARRAY')
            if len(value)>4096: return omit(value,location,'R3_CONTINUOUS_ARRAY_BOUND')
            if not charge(2 + max(0,len(value)-1) + 4*len(value) - 4):
                return omit(value,location,'R3_CONTINUOUS_REDACTED_JSON_BUDGET')
            return [project(v,kind[:-2],field,location+'['+str(i)+']',depth+1) for i,v in enumerate(value)]
        if kind in SCHEMA or kind == 'v':
            if value is None and kind in SCHEMA: return None
            fields = SCHEMA[kind] if kind in SCHEMA else dict(x='n',y='n',z='n')
            code = 'R3_CONTINUOUS_CLOSED_KEYS_'+kind.upper() if kind in SCHEMA else 'R3_CONTINUOUS_VECTOR'
            if type(value) is not dict: return omit(value,location,code)
            overhead = 2 + max(0,len(fields)-1) + sum(len(encode(k))+1+4 for k in fields) - 4
            if not charge(overhead): return omit(value,location,'R3_CONTINUOUS_REDACTED_JSON_BUDGET')
            for key in value:
                if key not in fields: omit(value[key],location+'.<unknown>',code)
            return {key:project(value[key],sub,kind+'.'+key,location+'.'+key,depth+1) if key in value else
                    omit(None,location+'.'+key,code,missing=True) for key,sub in fields.items()}
        try:
            finite_tree(value)
            closed_schema(value,kind,field)
        except (ValueError,OverflowError) as error:
            code = str(error) if type(error) is ValueError else 'R3_CONTINUOUS_NONFINITE'
            return omit(value,location,code)
        packed = encode(value)
        if not charge(len(packed)-4): return omit(value,location,'R3_CONTINUOUS_REDACTED_JSON_BUDGET')
        return value
    def unique(pairs):
        value = {}
        for key,item in pairs:
            require(key not in value,'REDACTED_DUPLICATE_JSON'); value[key]=item
        return value
    try:
        # JSON nonfinite constants can only become hashed omissions in this path.
        native = json.loads(raw,object_pairs_hook=unique)
    except (ValueError,UnicodeError,RecursionError):
        data = None; count=1
        omissions.append(dict(location='$',code='R3_CONTINUOUS_REDACTED_JSON_PARSE',type='invalid-json',
            jsonBytes=len(raw),length=0,sha256=hashlib.sha256(raw).hexdigest()))
    else: data=project(native,'Report','','$')
    value=dict(schema=1,mode='FAILED_REDACTED',semanticsValidated=False,diagnosticComplete=False,
        gameplayAccepted=False,nativeFailure=native_failure,rawReportExported=False,
        sourceRaw=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)),strictValidationCode=rejection_code,
        omissionCount=count,omissionsDropped=count-len(omissions),omissions=omissions,data=data)
    result=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
    require(len(result)<=MAX_REDACTED_BYTES,'REDACTED_OUTPUT_BOUND')
    return result


def verify_native_report(native, expectation, input_sha, pins):
    finite_tree(native)
    closed_schema(native, 'Report')
    require(type(native) is dict and native.get('schemaVersion') == 1, 'SCHEMA')
    complete = native['status'] == 'completed'
    require(not complete or native['failureCode'] == '', 'COMPLETED_WITH_FAILURE', '$.failureCode', native['failureCode'])
    require(native.get('producerCommit') == PRODUCER == expectation['producerCommit'] and
            native.get('consumerCommit') == expectation['consumerCommit'] and
            native.get('producerRunId') == expectation['producerRunId'] == '38070456519', 'IDENTITY')
    require(native.get('unityVersion') == '6000.3.19f1', 'UNITY')
    require(native.get('frameBound') == 2000 and native.get('physicsAutoSyncTransforms') is False, 'PHYSICS_POLICY')
    for flag in ('replayDetached','sceneUnloaded','sourceFilesUnchanged','timeRestored'):
        require(not complete or native.get(flag) is True, 'CLEANUP_' + flag.upper(), '$.' + flag, native.get(flag))
    check = native.get('dependencyCheck', {})
    require(check.get('passed') is True and check.get('expectedCount') == check.get('actualCount') == 796 and
            check.get('inputSha256') == input_sha and check.get('mismatches') == [], 'DEPENDENCIES', '$.dependencyCheck', check)
    require(len(expectation['dependencies']) == 796 and expectation.get('dependencyChanges') == [], 'EXPECTED_CLOSURE')
    required = {INPUT, INPUT.replace('.json','.sha256')} | {x for path in SOURCE_PATHS for x in (path,path+'.meta')}
    sources = native.get('sourceFiles')
    require(type(sources) is list and len(sources) == len(required), 'SOURCE_COUNT', '$.sourceFiles', sources)
    actual = {}
    for row in sources:
        require(type(row) is dict and set(row) == {'path','sha256'} and row['path'] not in actual, 'SOURCE_ROW')
        actual[row['path']] = row['sha256']
    require(set(actual) == required, 'SOURCE_SET')
    for path, digest in actual.items():
        require(path in pins and digest == (pins[path]['sha256'] if type(pins[path]) is dict else pins[path]), 'SOURCE_PIN')
    identities = native.get('colliders')
    require(type(identities) is list and len(identities) <= 4096, 'COLLIDERS')
    collider_ids = {0}
    for c in identities:
        require(type(c.get('id')) is int and c['id'] > 0 and c['id'] not in collider_ids, 'COLLIDER_ID')
        collider_ids.add(c['id'])
        require(type(c.get('path')) is str and c['path'] and c.get('type') in {'BoxCollider','MeshCollider','CapsuleCollider','SphereCollider','CharacterController'}, 'COLLIDER_TYPE_PATH')
        require(c.get('role') in {'retained-rv','walker','beast','world'}, 'COLLIDER_ROLE')
        vector(c['min']); vector(c['max'])
    def ids(rows, max_count=4096):
        require(type(rows) is list and len(rows) <= max_count and all(type(i) is int and i in collider_ids for i in rows), 'COLLIDER_REFERENCE')
    def hit(h):
        if h is None or h.get("present") is False:
            return
        require(type(h) is dict and h.get('collider') in collider_ids and h['collider'] != 0 and number(h.get('distance')) and h['distance'] >= 0, 'HIT')
        vector(h['point']); vector(h['normal'])
    def query(q, capacity):
        if q is None or q.get("performed") is False:
            return
        require(type(q) is dict and type(q.get('rawCount')) is int and 0 <= q['rawCount'] <= capacity and
                type(q.get('fullCount')) is int and 0 <= q['fullCount'] <= 4096 and q.get('saturated') is (q['rawCount'] == capacity), 'QUERY_COUNT')
        ids(q['rawIds'], capacity); ids(q['fullIds'])
        require(len(q['rawIds']) == q['rawCount'] and len(q['fullIds']) == q['fullCount'], 'QUERY_IDS')
        hit(q['nearestRaw']); hit(q['nearestFull']); vector(q['direction']); require(number(q['distance']) and q['distance'] > 0, 'QUERY_DISTANCE')
    sequences = native.get('sequences')
    require(type(sequences) is list and (len(sequences) == 3 if complete else 0 <= len(sequences) <= 3), 'SEQUENCES', '$.sequences', sequences)
    last_frame = -1; summary = []
    for sequence_index, (seq, (name, live, yaw, dt, plan)) in enumerate(zip(sequences, PLANS)):
        require(seq.get('completed') is True or not complete and sequence_index == len(sequences) - 1, 'PARTIAL_SEQUENCE_ORDER')
        require(seq.get('name') == name and seq.get('liveEnemies') is live and
                close(seq.get('yawOffset'),yaw) and close(seq.get('requestedCaptureDelta'),dt), 'SEQUENCE_IDENTITY')
        require(seq.get('initialVehicleHealth') == 300 and seq.get('initialPlayerHealth') == 100 and
                'Ram' in seq.get('upgrades','') and 'Arc' in seq.get('upgrades',''), 'FIXTURE_STATE')
        vector(seq['sourceSpawn']); vector(seq['initialVehicle'])
        require(close(seq['initialVehicle']['x'],1.7) and close(seq['initialVehicle']['z'],24) and
                close(seq['initialVehicle']['y'],seq['sourceSpawn']['y']), 'FIXTURE_POSITION')
        require(seq.get('plan') == [dict(name=n,frames=f,throttle=t,steering=s) for n,f,t,s in plan], 'PLAN')
        actor_ids = [b['id'] for b in seq['authoredEnemies']]
        require(len(set(actor_ids)) == 2, 'ACTORS')
        for beast, expected in zip(seq['authoredEnemies'], ((-7,33),(7,39))):
            require(close(beast['position']['x'],expected[0]) and close(beast['position']['z'],expected[1]) and beast['active'] is live and beast['health'] == 65, 'AUTHORED_SPAWN')
        frames = seq.get('frames'); wanted = [(n,t,s) for n,count,t,s in plan for _ in range(count)]
        require(type(frames) is list and (len(frames) == len(wanted) if seq['completed'] else 0 <= len(frames) <= len(wanted)), 'FRAME_COUNT')
        minimum_health = 300; contacts = pulses = overlaps = deep = saturated = 0; phases = set(); arc_blockers = set()
        previous_game = previous_real = None
        for index, (f,(step,throttle,steering)) in enumerate(zip(frames,wanted)):
            require(type(f['frame']) is int and f['frame'] > last_frame and f['sequenceFrame'] == index and f['step'] == step, 'FRAME_ORDER')
            if index:
                require(f['frame'] == last_frame + 1 and close(f['gameTime']-previous_game,dt) and f['realTime'] >= previous_real, 'CONTINUITY')
            last_frame=f['frame']; previous_game=f['gameTime']; previous_real=f['realTime']
            require(close(f['dt'],dt) and close(f['captureDelta'],dt) and close(f['aiDelta'],min(dt,.1)) and close(f['timeScale'],1), 'FRAME_DELTA')
            require(close(f['fixedDelta'],native['originalFixedDelta']) and number(f['unscaledDelta']) and f['unscaledDelta'] >= 0, 'FIXED_DELTA')
            for hp in ('vehicleHealthBeforeAI','vehicleHealthBeforeMotor','vehicleHealthAfter'):
                require(type(f[hp]) is int and 0 <= f[hp] <= 300, 'VEHICLE_HEALTH')
            require(f['vehicleHealthBeforeAI'] >= f['vehicleHealthBeforeMotor'] >= f['vehicleHealthAfter'], 'HEALTH_ORDER')
            minimum_health=min(minimum_health,f['vehicleHealthAfter'])
            vector(f['beforeAI']); vector(f['after'])
            m=f['motor']; query(m.get('translation'),32)
            ids(m['rotationRawIds'],32); ids(m['rotationFullIds'])
            require(m['rotationRawCount']==len(m['rotationRawIds']) and m['rotationFullCount']==len(m['rotationFullIds']) and m['rotationNearest'] in collider_ids, 'ROTATION')
            if f['status']=='Playing':
                require(close(m['throttle'],throttle) and close(m['steering'],steering) and m['powerConnected'] is False and f['control']=='Driving', 'ORDINARY_INPUT')
            ids(f['actualMotor32BufferColliderIds'],32); ids(f['actualRotation32BufferColliderIds'],32)
            require(len(f['actualMotor32BufferColliderIds'])==len(f['actualRotation32BufferColliderIds'])==32, 'ACTUAL_BUFFER')
            for phase in ('beastsBeforeAI','beastsBeforeMotor','beastsAfter'):
                require([b['id'] for b in f[phase]] == actor_ids, 'BEAST_IDENTITY')
                for b in f[phase]:
                    require(type(b['health']) is int and 0<=b['health']<=65 and b['phase'] in {'Idle','Stalk','Windup','Attack','Recover','Hit','Dead'} and b['active'] is live and b['enabled'] is True, 'BEAST_STATE')
                    require(b['dead'] is (b['phase']=='Dead') and (not b['dead'] or b['health']==0), 'BEAST_DEATH')
                    for v in ('position','bottom','top','physicsMin','physicsMax'): vector(b[v])
                    require(close(b['radius'],.36) and number(b['axisDistance']) and b['axisDistance']>=0 and b['penetrationDepth']>=0 and (b['penetration'] or b['penetrationDepth']==0), 'BEAST_GEOMETRY')
                    ids(b['actualAIHitBufferColliderIds'],16); require(len(b['actualAIHitBufferColliderIds'])==16, 'AI_ACTUAL_BUFFER')
                    if b.get('aiQuery') and b['aiQuery'].get('recorded'):
                        q=b['aiQuery']; query(q.get('forward'),16);query(q.get('tangent'),16);hit(q.get('attackLineHit'))
                    phases.add(b['phase'])
            overlaps += int(any(b['proxyOverlap'] for b in f['beastsBeforeMotor']))
            deep += int(any(b['active'] and not b['dead'] and b['axisInside'] for b in f['beastsBeforeMotor']))
            saturated += int(bool(m.get('translation') and m['translation'].get('performed') and m['translation']['saturated']))
            for timing in ('arcBeforeDirector','arcAfterDirector'):
                arc=f[timing];require(arc['sourceBlocker'] in collider_ids and len(arc['targets'])==2,'ARC')
                for target in arc['targets']:
                    require(target['beast'] in actor_ids,'ARC_TARGET');hit(target['firstLOSBlocker'])
                    if target['inRange'] and not target['clearLine'] and target['firstLOSBlocker'] and target['firstLOSBlocker'].get('present'): arc_blockers.add(target['firstLOSBlocker']['collider'])
            for contact in f['motorObstacleContact']:
                require(contact['frame']==f['frame'] and number(contact['speed']),'CONTACT_FRAME');hit(contact['hit']);contacts+=1
            for event in f['arcPresented']:
                require(event['frame']==f['frame'] and event['target'] in actor_ids and event['sequence']>0 and event['pulse']>0,'ARC_EVENT');pulses+=1
        summary.append(dict(name=name,completed=seq['completed'],frames=len(frames),expectedFrames=len(wanted),delta=dt,minimumVehicleHealth=minimum_health,
                            obstacleContacts=contacts,arcPresented=pulses,proxyOverlapFrames=overlaps,
                            liveAxisInsideFrames=deep,motorSaturatedFrames=saturated,phases=sorted(phases),arcBlockers=sorted(arc_blockers)))
    require(not complete or sum(x['frames'] for x in summary)==1212, 'TOTAL_FRAMES')
    return dict(diagnosticComplete=complete,gameplayAccepted=False,
        status='COMPLETED_OBSERVATION_NOT_ACCEPTANCE' if complete else 'FAILED_PARTIAL_OBSERVATION_NOT_ACCEPTANCE',
        nativeReportStatus=native['status'], failureCode=native['failureCode'],
        scope='Controlled natural-AI observation, not exact desktop replay or a lock-free regression verdict' if complete else
            'Failed/incomplete native execution; only the validated recorded sequence/frame prefix is available; no full-case result or gameplay acceptance',
        observedFrames=sum(x['frames'] for x in summary), expectedFrames=1212,
        cleanup={flag:native[flag] for flag in ('replayDetached','sceneUnloaded','sourceFilesUnchanged','timeRestored')}, sequences=summary)

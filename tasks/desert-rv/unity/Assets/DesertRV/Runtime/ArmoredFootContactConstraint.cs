using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV
{
    // Candidate only. Same entry point for LateUpdate and explicit STRICT evaluation.
    // Floor nonpenetration only: no world-XZ anchors, locomotion retiming or slip acceptance.
    [DefaultExecutionOrder(1500)]
    [DisallowMultipleComponent]
    public sealed class ArmoredFootContactConstraint : MonoBehaviour
    {
        [Serializable] public sealed class Leg
        {
            public string id; // fore.L, fore.R, hind.L, hind.R
            public Transform upper, lower, foot;
            [NonSerialized] internal List<Vector3> sole = new List<Vector3>();
            [NonSerialized] internal List<int> sourceVertices = new List<int>();
            [NonSerialized] internal float upperLength, lowerLength;
            [NonSerialized] internal Vector3 poleInActor;
        }
        [Serializable] public sealed class LegReport
        {
            public string id, reason, sourceState, destinationState;
            public bool corrected, valid, sourceAirborne, destinationAirborne;
            public int lowestSourceVertex,groundSceneHandle;
            public float preMinDistance, postMinDistance, attemptedPostMinDistance, correctionMeters, targetClearance;
            public Vector3 preFootWorld, postFootWorld, groundPoint, groundNormal;
        }
        [Serializable] public sealed class Report
        {
            public bool valid, paused, fullMeshValidated, slipValidated, swingArcValidated;
            public int frame,actorSceneHandle,physicsSceneHash;
            public string reason;
            public float transitionNormalizedTime, currentNormalizedTime, nextNormalizedTime, currentLength, nextLength, animatorSpeed;
            public List<LegReport> legs = new List<LegReport>();
        }
        public BeastActor actor;
        public Animator animator;
        public SkinnedMeshRenderer bodyRenderer;
        public Leg[] legs = new Leg[4];
        public LayerMask groundMask; // Explicitly configured actual ground; zero is a binding failure.
        public float maxCorrectionMeters = .20f;
        public Report lastReport;
        public Report lastCorrectionReport; // Retains the raw pre-correction witness on harmless repeated calls.
        public bool HasFailure { get; private set; }
        const float FloorTolerance = .004f, LengthTolerance = .0001f, SolveEpsilon = .000001f;
        bool calibrated;
        readonly RaycastHit[] groundHits = new RaycastHit[32];

        void OnEnable() { calibrated = false; HasFailure = false; }
        void OnDisable() { calibrated = false; }
        public void ResetContactState() { calibrated = false; HasFailure = false; lastReport = lastCorrectionReport = null; }
        void LateUpdate()
        {
            if (!actor || !animator || animator.speed <= 0) return;
            if (!ApplyFootContact(out var report)) Debug.LogError("ARMORED_FOOT_CONTACT_FAILED " + JsonUtility.ToJson(report), this);
        }
        public bool ValidateBindings(out string reason) => Calibrate(out reason);
        bool Calibrate(out string reason)
        {
            reason = null;
            if (!actor || gameObject != actor.gameObject || !actor.armored || !animator || !animator.runtimeAnimatorController || !bodyRenderer || groundMask.value == 0 ||
                !bodyRenderer.transform.IsChildOf(actor.transform) || legs == null || legs.Length != 4 ||
                !TwoBoneArmSolver.Finite(maxCorrectionMeters) || maxCorrectionMeters <= 0 || maxCorrectionMeters > .20f)
            { reason = "Explicit armored actor, Animator, body renderer, four legs, ground mask and bounded correction required."; return false; }
            var mesh = bodyRenderer.sharedMesh;
            if (!mesh || !mesh.isReadable || mesh.blendShapeCount != 0)
            { reason = "Calibration requires actual readable rigid-foot mesh without unaccounted blend shapes."; return false; }
            var vertices = mesh.vertices; var bindposes = mesh.bindposes; var bones = bodyRenderer.bones;
            // Borrowed read-only native mesh streams, not the legacy truncated four-weight view.
            var counts = mesh.GetBonesPerVertex(); var weights = mesh.GetAllBoneWeights();
            if (counts.Length != vertices.Length) { reason = "Complete source influence counts required."; return false; }
            var starts = new int[vertices.Length]; int cursor=0;
            for(int i=0;i<vertices.Length;i++)
            {
                starts[i]=cursor;
                if(cursor+counts[i]>weights.Length){reason="Truncated full influence stream.";return false;}
                float sum=0;
                for(int k=0;k<counts[i];k++)
                {
                    var weight=weights[cursor++];
                    if(weight.boneIndex<0||weight.boneIndex>=bones.Length||!TwoBoneArmSolver.Finite(weight.weight)||weight.weight<0)
                    {reason="Invalid full influence entry.";return false;}
                    sum+=weight.weight;
                }
                if(counts[i]>0 && Mathf.Abs(sum-1)>.00001f){reason="Full influence weights are not normalized.";return false;}
            }
            if(cursor!=weights.Length){reason="Unexpected trailing full influences.";return false;}
            var seen = new HashSet<Transform>(); var ids = new HashSet<string>();
            foreach (var leg in legs)
            {
                if (leg == null || !KnownLeg(leg.id) || !ids.Add(leg.id) || !leg.upper || !leg.lower || !leg.foot ||
                    leg.lower.parent != leg.upper || leg.foot.parent != leg.lower || !leg.upper.IsChildOf(actor.transform) ||
                    !seen.Add(leg.upper) || !seen.Add(leg.lower) || !seen.Add(leg.foot))
                { reason = "Distinct direct upper/lower/foot chains and canonical leg IDs required."; return false; }
                int index = Array.IndexOf(bones, leg.foot);
                if (index < 0 || index >= bindposes.Length) { reason = "Foot missing actual skin bind pose."; return false; }
                if(leg.sole==null)leg.sole=new List<Vector3>();if(leg.sourceVertices==null)leg.sourceVertices=new List<int>();
                leg.sole.Clear(); leg.sourceVertices.Clear();
                for (int i = 0; i < vertices.Length; i++)
                {
                    bool referencesFoot=false;
                    for(int k=0;k<counts[i];k++)
                        if(weights[starts[i]+k].boneIndex==index && weights[starts[i]+k].weight>0)referencesFoot=true;
                    if(!referencesFoot)continue;
                    if(counts[i]!=1 || weights[starts[i]].boneIndex!=index || Mathf.Abs(weights[starts[i]].weight-1)>.00001f)
                    {reason="Foot has multiple full-stream influences; rigid sole calibration rejected.";return false;}
                    Vector3 point = bindposes[index].MultiplyPoint3x4(vertices[i]);
                    if (!TwoBoneArmSolver.Finite(point)) { reason = "Nonfinite foot source geometry."; return false; }
                    leg.sole.Add(point); leg.sourceVertices.Add(i);
                }
                if (leg.sole.Count < 4) { reason = "Missing actual finite sole geometry."; return false; }
                leg.upperLength = Vector3.Distance(leg.upper.position, leg.lower.position);
                leg.lowerLength = Vector3.Distance(leg.lower.position, leg.foot.position);
                leg.poleInActor = actor.transform.InverseTransformDirection(leg.lower.position - leg.upper.position);
                if (!TwoBoneArmSolver.Finite(leg.upperLength) || !TwoBoneArmSolver.Finite(leg.lowerLength) ||
                    leg.upperLength <= SolveEpsilon || leg.lowerLength <= SolveEpsilon)
                { reason = "Invalid physical segment lengths."; return false; }
            }
            calibrated = true; return true;
        }
        static bool KnownLeg(string id) => id == "fore.L" || id == "fore.R" || id == "hind.L" || id == "hind.R";
        static string StateName(AnimatorStateInfo state)
        {
            foreach (string name in new[] { "Idle", "Walk", "Windup", "Attack", "Recover", "Hit", "Death" })
                if (state.shortNameHash == Animator.StringToHash(name)) return name;
            return "Unknown";
        }
        // Labels come from authored foot schedules. No inferred transition weight or fake lift.
        static bool Airborne(string state, float normalized, string leg)
        {
            bool diagonalA = leg == "fore.L" || leg == "hind.R";
            if (state == "Walk" || state == "Attack")
            {
                float duration = state == "Walk" ? .6f : 1.2f;
                float cycle = state == "Walk" ? .6f : .15f;
                return Mathf.Repeat(normalized * duration / cycle + (diagonalA ? 0 : .5f), 1) > .5f;
            }
            if (state == "Windup")
            { float time = Mathf.Clamp01(normalized) * 1.1f, start = diagonalA ? 0 : .25f; return time > start && time < start + .30f; }
            if (state == "Recover")
            { float time = Mathf.Clamp01(normalized) * 2, start = diagonalA ? .20f : .85f; return time > start && time < start + .55f; }
            return false; // Idle/Hit/Death have no new authored swing; incoming blend label is retained separately.
        }
        bool Ground(Leg leg, out RaycastHit ground, out string reason)
        {
            ground = default; reason = null;
            var scene=actor.gameObject.scene;
            if(!scene.IsValid()||!scene.isLoaded){reason="Actor scene is invalid or unloaded.";return false;}
            var physicsScene=scene.GetPhysicsScene();
            if(!physicsScene.IsValid()){reason="Actor has no valid owning PhysicsScene.";return false;}
            int count = physicsScene.Raycast(leg.foot.position + Vector3.up * .5f, Vector3.down,
                groundHits, 1.5f, groundMask, QueryTriggerInteraction.Ignore);
            if (count == groundHits.Length) { reason = "Ground probe buffer saturated; ambiguous support."; return false; }
            float distance = float.PositiveInfinity; bool found = false;
            for (int i = 0; i < count; i++)
            {
                var hit = groundHits[i];
                if (!hit.collider || hit.collider.gameObject.scene!=scene || hit.transform.IsChildOf(actor.transform) || Vector3.Dot(hit.normal, Vector3.up) < .7f) continue;
                if (hit.distance < distance) { ground = hit; distance = hit.distance; found = true; }
            }
            if (!found) reason = "No supported actual ground hit; no guessed Y=0 plane.";
            return found;
        }
        static float MinDistance(Leg leg, Vector3 point, Vector3 normal, out int index)
        {
            float min = float.PositiveInfinity; index = -1;
            for (int i = 0; i < leg.sole.Count; i++)
            {
                float d = Vector3.Dot(leg.foot.TransformPoint(leg.sole[i]) - point, normal);
                if (d < min) { min = d; index = leg.sourceVertices[i]; }
            }
            return min;
        }
        public bool ApplyFootContact(out Report report)
        {
            if (animator && animator.speed <= 0)
            {
                report = new Report { paused=true, frame=Time.frameCount, reason="Paused: no transform writes or ground solve; not a new validation sample." };
                return false;
            }
            report = new Report { frame=Time.frameCount }; lastReport = report;
            if (!calibrated && !Calibrate(out report.reason)) { HasFailure = true; return false; }
            var owningScene=actor.gameObject.scene;
            if(!owningScene.IsValid()||!owningScene.isLoaded||!owningScene.GetPhysicsScene().IsValid())
            {report.reason="No valid loaded actor PhysicsScene.";HasFailure=true;return false;}
            report.actorSceneHandle=owningScene.handle;report.physicsSceneHash=owningScene.GetPhysicsScene().GetHashCode();
            var current = animator.GetCurrentAnimatorStateInfo(0); bool transition = animator.IsInTransition(0);
            var next = transition ? animator.GetNextAnimatorStateInfo(0) : current;
            string source = StateName(current), destination = StateName(next);
            report.currentNormalizedTime=current.normalizedTime;report.nextNormalizedTime=next.normalizedTime;
            report.currentLength=current.length;report.nextLength=next.length;report.animatorSpeed=animator.speed;
            report.transitionNormalizedTime = transition ? animator.GetAnimatorTransitionInfo(0).normalizedTime : 0;
            if (source == "Unknown" || destination == "Unknown") { report.reason = "Unknown actual Animator state."; HasFailure = true; return false; }
            Physics.SyncTransforms(); // One sync per shared runtime/STRICT evaluation, before owning-scene queries.
            Vector3 rootPosition = actor.transform.position, rootScale = actor.transform.localScale;
            Quaternion rootRotation = actor.transform.rotation; bool all = true;
            foreach (var leg in legs)
            {
                var row = new LegReport { id = leg.id, sourceState = source, destinationState = destination,
                    sourceAirborne = Airborne(source, current.normalizedTime, leg.id), destinationAirborne = Airborne(destination, next.normalizedTime, leg.id),
                    preFootWorld = leg.foot.position }; report.legs.Add(row);
                if (!Ground(leg, out var ground, out row.reason)) { all = false; continue; }
                row.groundPoint = ground.point; row.groundNormal = ground.normal;row.groundSceneHandle=ground.collider.gameObject.scene.handle;
                row.preMinDistance = MinDistance(leg, ground.point, ground.normal, out row.lowestSourceVertex);
                row.postMinDistance = row.attemptedPostMinDistance = row.preMinDistance;
                if (!TwoBoneArmSolver.Finite(row.preMinDistance)) { row.reason = "Nonfinite actual sole distance."; all = false; continue; }
                if (row.preMinDistance >= -FloorTolerance) { row.valid = true; row.postFootWorld = leg.foot.position; continue; }
                // Only violating feet are corrected. Valid swing clearance is never reduced or raised.
                float margin = row.sourceAirborne || row.destinationAirborne ? .001f : .005f;
                row.targetClearance=margin;row.correctionMeters = margin - row.preMinDistance;
                if (row.correctionMeters > maxCorrectionMeters) { row.reason = "Correction exceeds bounded candidate range; no clamp/false pass."; all = false; continue; }
                Vector3 hip = leg.upper.position, knee = leg.lower.position, foot = leg.foot.position;
                Vector3 upperLocal = leg.upper.localPosition, lowerLocal = leg.lower.localPosition, footLocal = leg.foot.localPosition;
                Vector3 upperScale = leg.upper.localScale, lowerScale = leg.lower.localScale, footScale = leg.foot.localScale;
                Quaternion upperRotation = leg.upper.rotation, lowerRotation = leg.lower.rotation, footRotation = leg.foot.rotation;
                if (Mathf.Abs(Vector3.Distance(hip,knee)-leg.upperLength)>LengthTolerance || Mathf.Abs(Vector3.Distance(knee,foot)-leg.lowerLength)>LengthTolerance)
                { row.reason = "Animated leg length differs from calibration."; all = false; continue; }
                Vector3 target = foot + ground.normal * row.correctionMeters;
                Vector3 pole = actor.transform.TransformDirection(leg.poleInActor);
                if (!TwoBoneArmSolver.TryElbow(hip,knee,target,leg.upperLength,leg.lowerLength,pole,SolveEpsilon,out var solvedKnee,out var normal,out row.reason))
                { all = false; continue; }
                if (!TwoBoneArmSolver.TrySwing(knee-hip,solvedKnee-hip,normal,SolveEpsilon,out var upperSwing))
                { row.reason = "Upper-leg swing solve failed."; all = false; continue; }
                leg.upper.rotation = upperSwing * upperRotation;
                bool lowerOk = TwoBoneArmSolver.TrySwing(leg.foot.position-leg.lower.position,target-leg.lower.position,normal,SolveEpsilon,out var lowerSwing);
                if (lowerOk) leg.lower.rotation = lowerSwing * leg.lower.rotation;
                leg.foot.rotation = footRotation; // Preserve actual world sole orientation; never translate the foot bone.
                row.attemptedPostMinDistance = MinDistance(leg,ground.point,ground.normal,out _);
                bool invariant = (leg.upper.position-hip).magnitude<=LengthTolerance && (leg.foot.position-target).magnitude<=LengthTolerance &&
                    Mathf.Abs(Vector3.Distance(leg.upper.position,leg.lower.position)-leg.upperLength)<=LengthTolerance &&
                    Mathf.Abs(Vector3.Distance(leg.lower.position,leg.foot.position)-leg.lowerLength)<=LengthTolerance &&
                    leg.upper.localPosition==upperLocal && leg.lower.localPosition==lowerLocal && leg.foot.localPosition==footLocal &&
                    leg.upper.localScale==upperScale && leg.lower.localScale==lowerScale && leg.foot.localScale==footScale;
                row.valid = lowerOk && invariant && TwoBoneArmSolver.Finite(row.attemptedPostMinDistance) && row.attemptedPostMinDistance >= -FloorTolerance && Mathf.Abs(row.attemptedPostMinDistance-margin)<=LengthTolerance*2 && Quaternion.Angle(leg.foot.rotation,footRotation)<=.01f;
                if (!row.valid)
                {
                    row.reason = "Post-solve sole/length/endpoint/immutable-transform invariant failed; rotations restored.";
                    leg.upper.rotation=upperRotation; leg.lower.rotation=lowerRotation; leg.foot.rotation=footRotation; all=false;
                }
                row.corrected=row.valid;row.postFootWorld=leg.foot.position;
                row.postMinDistance=MinDistance(leg,ground.point,ground.normal,out _);
            }
            if (actor.transform.position!=rootPosition || actor.transform.rotation!=rootRotation || actor.transform.localScale!=rootScale)
            { report.reason="Actor root changed during contact solve.";all=false; }
            if (HasFailure && all) { report.reason="A prior failure remains latched until explicit contact-state reset."; all=false; }
            report.valid=all;
            if(report.legs.Exists(x=>x.corrected))lastCorrectionReport=report;
            // This module does not certify upper-leg armor, the entire mesh, swing trajectory or foot slip.
            report.fullMeshValidated=report.slipValidated=report.swingArcValidated=false;
            if (!all) HasFailure=true;
            return all;
        }
    }
}

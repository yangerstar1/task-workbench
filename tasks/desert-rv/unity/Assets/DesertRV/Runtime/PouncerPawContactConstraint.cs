using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV
{
    // Candidate normal-only floor constraint, shared verbatim by LateUpdate and STRICT.
    // No world-XZ anchor, animation retiming, root offset, geometry edit or slip certification.
    [DefaultExecutionOrder(1500), DisallowMultipleComponent]
    public sealed class PouncerPawContactConstraint : MonoBehaviour
    {
        [Serializable] public sealed class Leg
        {
            public string id;
            public Transform upper, lower, paw;
            [NonSerialized] internal readonly List<SolePoint> sole = new List<SolePoint>();
            [NonSerialized] internal int excludedMixedVertices;
            [NonSerialized] internal float upperLength, lowerLength;
            [NonSerialized] internal Vector3 poleInActor;
            [NonSerialized] internal Transform[] descendants;
            [NonSerialized] internal Vector3[] descendantPositions, descendantScales;
            [NonSerialized] internal Quaternion[] descendantRotations;
        }
        internal sealed class SolePoint
        {
            internal string rendererPath;
            internal int vertex;
            internal Influence[] influences;
        }
        internal struct Influence { internal int bone; internal float weight; internal Vector3 point; }
        sealed class SkinCache { internal SkinnedMeshRenderer renderer; internal Mesh mesh; internal Transform[] bones; }
        [Serializable] public sealed class LegReport
        {
            public string id, reason, sourceState, destinationState, lowestRendererPath;
            public bool corrected, valid;
            public int lowestSourceVertex, selectedVertices, excludedMixedVertices, groundSceneHandle;
            public float preMinDistance, postMinDistance, attemptedPostMinDistance, correctionMeters, targetClearance;
            public Vector3 prePawWorld, postPawWorld, groundPoint, groundNormal;
        }
        [Serializable] public sealed class Report
        {
            public bool valid, paused, fullMeshValidated, slipValidated, swingArcValidated;
            public int frame, actorSceneHandle, physicsSceneHash;
            public string reason;
            public float transitionNormalizedTime, currentNormalizedTime, nextNormalizedTime, currentLength, nextLength, animatorSpeed;
            public List<LegReport> legs = new List<LegReport>();
        }
        public BeastActor actor;
        public Animator animator;
        public SkinnedMeshRenderer[] sourceRenderers;
        public Leg[] legs = new Leg[4];
        public LayerMask groundMask;
        public float maxCorrectionMeters = .10f;
        public Report lastReport, lastCorrectionReport;
        public bool HasFailure { get; private set; }
        const float FloorTolerance=.004f, Clearance=.001f, LengthTolerance=.0001f, Epsilon=.000001f;
        static readonly string[] StateNames={"Idle","Walk","Windup","Attack","Recover","Hit","Death"};
        bool calibrated;
        readonly List<SkinCache> skins = new List<SkinCache>();
        readonly List<Transform> neededBones = new List<Transform>();
        Matrix4x4[] boneMatrices;
        readonly RaycastHit[] groundHits = new RaycastHit[32];
        readonly Quaternion[] upperBefore=new Quaternion[4], lowerBefore=new Quaternion[4], pawBefore=new Quaternion[4];
        void OnEnable() { calibrated=false; }
        void OnDisable() { calibrated=false; }
        public void ResetContactState() { calibrated=false;HasFailure=false;lastReport=lastCorrectionReport=null; }
        void LateUpdate()
        {
            if(!animator || animator.speed<=0 || Time.timeScale<=0 || HasFailure)return;
            if(!ApplyPawContact(out var report))Debug.LogError("POUNCER_PAW_CONTACT_FAILED "+JsonUtility.ToJson(report),this);
        }
        public bool ValidateBindings(out string reason) => Calibrate(out reason);
        static bool KnownLeg(string id) => id=="fore.L" || id=="fore.R" || id=="hind.L" || id=="hind.R";
        static bool Under(Transform node,Transform root) => node && (node==root || node.IsChildOf(root));
        string PathOf(Transform node)
        {
            string path=node.name;
            while(node.parent && node.parent!=actor.transform) { node=node.parent;path=node.name+"/"+path; }
            return path;
        }
        bool Calibrate(out string reason)
        {
            reason=null; calibrated=false;skins.Clear();neededBones.Clear();
            if(!actor || actor.gameObject!=gameObject || actor.armored || !animator || actor.animator!=animator || !Under(animator.transform,actor.transform) ||
                groundMask.value==0 || sourceRenderers==null || sourceRenderers.Length==0 || legs==null || legs.Length!=4 ||
                !TwoBoneArmSolver.Finite(maxCorrectionMeters) || maxCorrectionMeters<=0 || maxCorrectionMeters>.10f)
            {reason="Explicit Pouncer actor, Animator, complete skin inventory, four legs, ground layer and bounded correction required.";return false;}
            var actual=actor.GetComponentsInChildren<SkinnedMeshRenderer>(true);
            var inventory=new HashSet<SkinnedMeshRenderer>(sourceRenderers);
            if(inventory.Count!=sourceRenderers.Length || inventory.Contains(null) || !inventory.SetEquals(actual))
            {reason="Explicit renderer inventory must exactly cover every actor skin, including claws.";return false;}
            var ids=new HashSet<string>();var nodes=new HashSet<Transform>();
            foreach(var leg in legs)
            {
                if(leg==null || !KnownLeg(leg.id) || !ids.Add(leg.id) || !leg.upper || !leg.lower || !leg.paw ||
                    leg.lower.parent!=leg.upper || leg.paw.parent!=leg.lower || !Under(leg.upper,actor.transform) ||
                    !nodes.Add(leg.upper) || !nodes.Add(leg.lower) || !nodes.Add(leg.paw))
                {reason="Four distinct direct upper/lower/paw chains with canonical IDs required.";return false;}
                leg.sole.Clear();leg.excludedMixedVertices=0;
                leg.upperLength=Vector3.Distance(leg.upper.position,leg.lower.position);
                leg.lowerLength=Vector3.Distance(leg.lower.position,leg.paw.position);
                leg.poleInActor=actor.transform.InverseTransformDirection(leg.lower.position-leg.upper.position);
                if(!TwoBoneArmSolver.Finite(leg.upperLength) || !TwoBoneArmSolver.Finite(leg.lowerLength) || leg.upperLength<=Epsilon || leg.lowerLength<=Epsilon)
                {reason="Invalid physical leg lengths.";return false;}
                leg.descendants=leg.paw.GetComponentsInChildren<Transform>(true);
                leg.descendantPositions=new Vector3[leg.descendants.Length];leg.descendantScales=new Vector3[leg.descendants.Length];
                leg.descendantRotations=new Quaternion[leg.descendants.Length];
            }
            // Bone collections are disjoint; no leg can move another leg's calibrated geometry.
            foreach(var a in legs)foreach(var b in legs)if(a!=b && (Under(a.upper,b.upper) || Under(b.upper,a.upper)))
            {reason="Leg chains must not be nested.";return false;}
            var boneLookup=new Dictionary<Transform,int>();
            foreach(var renderer in sourceRenderers)
            {
                var mesh=renderer.sharedMesh;
                if(!mesh || !mesh.isReadable || mesh.blendShapeCount!=0 || renderer.quality!=SkinQuality.Auto || QualitySettings.skinWeights!=SkinWeights.Unlimited)
                {reason="Readable unblended skins with complete Unlimited skinning required.";return false;}
                var vertices=mesh.vertices;var bindposes=mesh.bindposes;var bones=renderer.bones;
                // Read-only borrowed native mesh streams. Copy only selected influences into the cache.
                var counts=mesh.GetBonesPerVertex();var weights=mesh.GetAllBoneWeights();
                if(counts.Length!=vertices.Length || bindposes.Length!=bones.Length){reason="Incomplete skin source/bind-pose inventory.";return false;}
                for(int b=0;b<bones.Length;b++)if(!bones[b] || !Under(bones[b],actor.transform))
                {reason="Skin references a missing or foreign actor bone.";return false;}
                int cursor=0;string rendererPath=PathOf(renderer.transform);
                for(int v=0;v<vertices.Length;v++)
                {
                    int count=counts[v];if(count==0 || cursor+count>weights.Length || !TwoBoneArmSolver.Finite(vertices[v]))
                    {reason="Missing, truncated or nonfinite source vertex influences.";return false;}
                    float sum=0;int owner=-1;bool mixed=false;var touches=new bool[4];
                    for(int k=0;k<count;k++)
                    {
                        var w=weights[cursor+k];
                        if(w.boneIndex<0 || w.boneIndex>=bones.Length || !TwoBoneArmSolver.Finite(w.weight) || w.weight<0)
                        {reason="Invalid full-stream source weight.";return false;}
                        sum+=w.weight;if(w.weight==0)continue;
                        int paw=-1;for(int p=0;p<4;p++)if(Under(bones[w.boneIndex],legs[p].paw)){paw=p;touches[p]=true;break;}
                        if(paw<0)mixed=true;else if(owner<0)owner=paw;else if(owner!=paw)mixed=true;
                    }
                    if(Mathf.Abs(sum-1)>.00001f){reason="Full source weights must be normalized.";return false;}
                    if(mixed) {for(int p=0;p<4;p++)if(touches[p])legs[p].excludedMixedVertices++;}
                    if(owner>=0 && !mixed)
                    {
                        var influences=new List<Influence>();
                        for(int k=0;k<count;k++)
                        {
                            var w=weights[cursor+k];if(w.weight==0)continue;
                            var bone=bones[w.boneIndex];
                            if(!boneLookup.TryGetValue(bone,out int index)){index=neededBones.Count;neededBones.Add(bone);boneLookup.Add(bone,index);}
                            var point=bindposes[w.boneIndex].MultiplyPoint3x4(vertices[v]);
                            if(!TwoBoneArmSolver.Finite(point)){reason="Nonfinite bind-space source geometry.";return false;}
                            influences.Add(new Influence{bone=index,weight=w.weight,point=point});
                        }
                        legs[owner].sole.Add(new SolePoint{rendererPath=rendererPath,vertex=v,influences=influences.ToArray()});
                    }
                    cursor+=count;
                }
                if(cursor!=weights.Length){reason="Unexpected trailing full influences.";return false;}
                skins.Add(new SkinCache{renderer=renderer,mesh=mesh,bones=bones});
            }
            foreach(var leg in legs)if(leg.sole.Count<4){reason="Missing complete paw-subtree sole geometry.";return false;}
            boneMatrices=new Matrix4x4[neededBones.Count];calibrated=true;return true;
        }
        bool CacheStillValid(out string reason)
        {
            reason=null;
            foreach(var s in skins)if(!s.renderer || !s.mesh || s.renderer.sharedMesh!=s.mesh || s.renderer.quality!=SkinQuality.Auto || s.mesh.blendShapeCount!=0)
            {reason="Calibrated skin identity/quality changed; explicit reset required.";return false;}
            if(QualitySettings.skinWeights!=SkinWeights.Unlimited){reason="Complete skinning quality changed.";return false;}
            foreach(var bone in neededBones)if(!bone){reason="A calibrated paw bone was removed.";return false;}
            return true;
        }
        void RefreshMatrices() {for(int i=0;i<neededBones.Count;i++)boneMatrices[i]=neededBones[i].localToWorldMatrix;}
        float Minimum(Leg leg,Vector3 ground,Vector3 normal,out SolePoint lowest)
        {
            float min=float.PositiveInfinity;lowest=null;
            foreach(var point in leg.sole)
            {
                Vector3 world=Vector3.zero;
                foreach(var weight in point.influences)world+=boneMatrices[weight.bone].MultiplyPoint3x4(weight.point)*weight.weight;
                if(!TwoBoneArmSolver.Finite(world))return float.NaN;
                float d=Vector3.Dot(world-ground,normal);if(d<min){min=d;lowest=point;}
            }
            return min;
        }
        bool Ground(Leg leg,out RaycastHit ground,out string reason)
        {
            ground=default;reason=null;var scene=actor.gameObject.scene;
            if(!scene.IsValid() || !scene.isLoaded || !scene.GetPhysicsScene().IsValid()){reason="No valid actor PhysicsScene.";return false;}
            int count=scene.GetPhysicsScene().Raycast(leg.paw.position+Vector3.up*.5f,Vector3.down,groundHits,1.5f,groundMask,QueryTriggerInteraction.Ignore);
            if(count==groundHits.Length){reason="Ground buffer saturated; ambiguous support.";return false;}
            float nearest=float.PositiveInfinity;bool found=false;
            for(int i=0;i<count;i++)
            {
                var hit=groundHits[i];
                if(!hit.collider || hit.collider.gameObject.scene!=scene || Under(hit.transform,actor.transform) || Vector3.Dot(hit.normal,Vector3.up)<.7f)continue;
                if(hit.distance<nearest){ground=hit;nearest=hit.distance;found=true;}
            }
            if(!found)reason="No supported actual ground in actor scene; no guessed plane.";
            return found;
        }
        static string StateName(AnimatorStateInfo state)
        {
            foreach(string name in StateNames)if(state.shortNameHash==Animator.StringToHash(name))return name;
            return "Unknown";
        }
        void SnapshotDescendants(Leg leg)
        {
            for(int i=0;i<leg.descendants.Length;i++)
            {var d=leg.descendants[i];leg.descendantPositions[i]=d.localPosition;leg.descendantScales[i]=d.localScale;leg.descendantRotations[i]=d.localRotation;}
        }
        bool DescendantsUnchanged(Leg leg)
        {
            for(int i=0;i<leg.descendants.Length;i++)
            {var d=leg.descendants[i];if(d.localPosition!=leg.descendantPositions[i] || d.localScale!=leg.descendantScales[i] || d!=leg.paw && d.localRotation!=leg.descendantRotations[i])return false;}
            return true;
        }
        public bool ApplyPawContact(out Report report)
        {
            if(animator && (animator.speed<=0 || Time.timeScale<=0))
            {report=new Report{paused=true,frame=Time.frameCount,reason="Paused: no transform writes and no new validation sample."};return false;}
            report=new Report{frame=Time.frameCount};lastReport=report;
            if(HasFailure){report.reason="A prior failure remains latched until explicit ResetContactState; no transform writes.";return false;}
            if((!calibrated && !Calibrate(out report.reason)) || !CacheStillValid(out report.reason)){HasFailure=true;return false;}
            var scene=actor.gameObject.scene;
            if(!scene.IsValid() || !scene.isLoaded || !scene.GetPhysicsScene().IsValid()){report.reason="No valid loaded actor PhysicsScene.";HasFailure=true;return false;}
            report.actorSceneHandle=scene.handle;report.physicsSceneHash=scene.GetPhysicsScene().GetHashCode();
            var current=animator.GetCurrentAnimatorStateInfo(0);bool transition=animator.IsInTransition(0);var next=transition?animator.GetNextAnimatorStateInfo(0):current;
            string source=StateName(current),destination=StateName(next);
            report.currentNormalizedTime=current.normalizedTime;report.nextNormalizedTime=next.normalizedTime;
            report.currentLength=current.length;report.nextLength=next.length;report.animatorSpeed=animator.speed;
            report.transitionNormalizedTime=transition?animator.GetAnimatorTransitionInfo(0).normalizedTime:0;
            if(source=="Unknown" || destination=="Unknown"){report.reason="Unknown actual Animator state.";HasFailure=true;return false;}
            Physics.SyncTransforms();RefreshMatrices();
            Vector3 rootPosition=actor.transform.position,rootScale=actor.transform.localScale;Quaternion rootRotation=actor.transform.rotation;
            for(int i=0;i<4;i++){upperBefore[i]=legs[i].upper.localRotation;lowerBefore[i]=legs[i].lower.localRotation;pawBefore[i]=legs[i].paw.localRotation;}
            bool all=true,anyWrite=false;
            foreach(var leg in legs)
            {
                var row=new LegReport{id=leg.id,sourceState=source,destinationState=destination,prePawWorld=leg.paw.position,
                    postPawWorld=leg.paw.position,selectedVertices=leg.sole.Count,excludedMixedVertices=leg.excludedMixedVertices,lowestSourceVertex=-1};report.legs.Add(row);
                if(!Ground(leg,out var ground,out row.reason)){all=false;continue;}
                row.groundPoint=ground.point;row.groundNormal=ground.normal;row.groundSceneHandle=ground.collider.gameObject.scene.handle;
                row.preMinDistance=Minimum(leg,ground.point,ground.normal,out var lowest);
                row.lowestSourceVertex=lowest==null?-1:lowest.vertex;row.lowestRendererPath=lowest==null?null:lowest.rendererPath;
                row.postMinDistance=row.attemptedPostMinDistance=row.preMinDistance;
                if(!TwoBoneArmSolver.Finite(row.preMinDistance)){row.reason="Nonfinite actual paw LBS geometry.";all=false;continue;}
                if(row.preMinDistance>=-FloorTolerance){row.valid=true;continue;}
                row.targetClearance=Clearance;row.correctionMeters=Clearance-row.preMinDistance;
                if(row.correctionMeters>maxCorrectionMeters){row.reason="Correction exceeds bounded range; no clamp.";all=false;continue;}
                Vector3 hip=leg.upper.position,knee=leg.lower.position,paw=leg.paw.position;
                Vector3 upperLocal=leg.upper.localPosition,lowerLocal=leg.lower.localPosition,upperScale=leg.upper.localScale,lowerScale=leg.lower.localScale;
                Quaternion upperRotation=leg.upper.rotation,pawRotation=leg.paw.rotation;SnapshotDescendants(leg);
                if(Mathf.Abs(Vector3.Distance(hip,knee)-leg.upperLength)>LengthTolerance || Mathf.Abs(Vector3.Distance(knee,paw)-leg.lowerLength)>LengthTolerance)
                {row.reason="Animated segment length differs from calibration.";all=false;continue;}
                var target=paw+ground.normal*row.correctionMeters;
                if(!TwoBoneArmSolver.TryElbow(hip,knee,target,leg.upperLength,leg.lowerLength,actor.transform.TransformDirection(leg.poleInActor),Epsilon,out var solvedKnee,out var normal,out row.reason))
                {all=false;continue;}
                if(!TwoBoneArmSolver.TrySwing(knee-hip,solvedKnee-hip,normal,Epsilon,out var upperSwing)){row.reason="Upper-leg swing failed.";all=false;continue;}
                anyWrite=true;leg.upper.rotation=upperSwing*upperRotation;
                bool lowerOk=TwoBoneArmSolver.TrySwing(leg.paw.position-leg.lower.position,target-leg.lower.position,normal,Epsilon,out var lowerSwing);
                if(lowerOk)leg.lower.rotation=lowerSwing*leg.lower.rotation;
                leg.paw.rotation=pawRotation; // The animated digits keep their local TRS and world orientation.
                RefreshMatrices();row.attemptedPostMinDistance=Minimum(leg,ground.point,ground.normal,out _);
                bool immutable=leg.upper.localPosition==upperLocal && leg.lower.localPosition==lowerLocal && leg.upper.localScale==upperScale && leg.lower.localScale==lowerScale && DescendantsUnchanged(leg);
                row.valid=lowerOk && immutable && Vector3.Distance(leg.upper.position,hip)<=LengthTolerance && Vector3.Distance(leg.paw.position,target)<=LengthTolerance &&
                    Mathf.Abs(Vector3.Distance(leg.upper.position,leg.lower.position)-leg.upperLength)<=LengthTolerance && Mathf.Abs(Vector3.Distance(leg.lower.position,leg.paw.position)-leg.lowerLength)<=LengthTolerance &&
                    Quaternion.Angle(leg.paw.rotation,pawRotation)<=.01f && TwoBoneArmSolver.Finite(row.attemptedPostMinDistance) && Mathf.Abs(row.attemptedPostMinDistance-Clearance)<=LengthTolerance*2;
                if(!row.valid){row.reason="Post-solve geometry/length/endpoint/immutable-transform invariant failed; all attempted rotations restored.";all=false;}
                row.corrected=row.valid;row.postPawWorld=leg.paw.position;row.postMinDistance=row.attemptedPostMinDistance;
            }
            if(actor.transform.position!=rootPosition || actor.transform.rotation!=rootRotation || actor.transform.localScale!=rootScale){report.reason="Actor root changed during solve.";all=false;}
            if(!all)
            {
                // Transactional rollback includes successful earlier legs; do not leave a partially corrected pose.
                if(anyWrite)for(int i=0;i<4;i++){legs[i].upper.localRotation=upperBefore[i];legs[i].lower.localRotation=lowerBefore[i];legs[i].paw.localRotation=pawBefore[i];}
                RefreshMatrices();
                for(int i=0;i<4;i++)
                {var row=report.legs[i];row.corrected=false;row.valid=false;row.postPawWorld=legs[i].paw.position;
                    if(row.lowestSourceVertex>=0)row.postMinDistance=Minimum(legs[i],row.groundPoint,row.groundNormal,out _);}
                report.reason=report.reason??"Paw contact failed; transaction rolled back and failure latched.";HasFailure=true;
            }
            report.valid=all;if(all && report.legs.Exists(row=>row.corrected))lastCorrectionReport=report;
            // Complete mesh, swing arc and tangential slip are validated separately, never by this module.
            report.fullMeshValidated=report.slipValidated=report.swingArcValidated=false;
            return all;
        }
    }
}

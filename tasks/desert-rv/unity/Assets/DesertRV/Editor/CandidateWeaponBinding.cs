using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;
using static DesertRV.Editor.JourneyCandidateArtImport;

namespace DesertRV.Editor
{
    // Measured candidate binding only. Never creates gameplay actions, accepts art or enables a presenter.
    public static class CandidateWeaponBinding
    {
        [Serializable] public sealed class ArmPaths { public string upperArm,forearm,wristTip,wristTarget; }
        [Serializable] public sealed class Spec
        {
            public string rigRoot,neutralState,discoveryReportSha256;
            public float neutralTimeSeconds,sourceToRigScale,leftUpperSource,leftForeSource,rightUpperSource,rightForeSource;
            public float positionToleranceRig,numericToleranceRig;
            public ArmPaths left,right;
            public Vector3 sourceMuzzleForwardLocal,sourceMuzzleUpLocal;
        }
        [Serializable] public sealed class MaterialReadback
        {
            public string sourceName,materialPath,shader,actualName,materialGuid;
            public long materialLocalId;
            public Color expectedColor,actualColor;
            public float expectedMetallic,actualMetallic,expectedSmoothness,actualSmoothness,actualCull;
        }
        [Serializable] public sealed class ArmReadback
        {
            public string upperArm,forearm,wristTip,wristTarget,neutralPoseEvidence;
            public bool calibrated;
            public float upperLengthRig,foreLengthRig,sourceUpperLength,sourceForeLength,sourceToRigScale;
            public Vector3 upperAxisLocal,foreAxisLocal,poleRigLocal,shoulderLocal,elbowLocal,tipLocal,upperScale,foreScale;
            public Quaternion upperBindRotation,foreBindRotation;
        }
        [Serializable] public sealed class Readback
        {
            public string neutralState,neutralPoseEvidence,sourceSha256,rigRoot;
            public float neutralTimeSeconds,rigWorldScale,positionToleranceWorld,numericToleranceWorld;
            public ArmReadback left,right;
            public List<MaterialReadback> materials=new List<MaterialReadback>();
            public bool sceneCalibrated=false,visualApproved=false;
        }
        public static Readback Bind(Spec spec,WeaponPresentation presenter,GameObject visual,string modelPath,
            IEnumerable<AnimationClip> clips,IEnumerable<MaterialSpec> materialSpecs,string materialFolder,MuzzleObservation muzzle)
        {
            Check(spec!=null&&spec.left!=null&&spec.right!=null,"Explicit measured arm and muzzle source-axis contract required.");
            Check(Regex.IsMatch(spec.discoveryReportSha256??"","^[a-f0-9]{64}$"),"Pin the real Unity discovery report.");
            var neutral=clips.Where(c=>c.name==spec.neutralState).ToArray();
            Check(neutral.Length==1&&spec.neutralState=="Idle"&&Finite(spec.neutralTimeSeconds)&&spec.neutralTimeSeconds>=0&&spec.neutralTimeSeconds<=neutral[0].length,"Explicit actual neutral Idle clip and time required.");
            var source=AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);Check(source,"Actual FBX source is missing.");
            var expectedMaterials=materialSpecs.ToArray();
            var materialSnapshot=CaptureMaterialIdentity(visual,materialFolder,expectedMaterials.Length);
            var reach=presenter.gameObject.AddComponent<WeaponArmReach>();reach.animator=presenter.animator;
            reach.rigRoot=At(visual.transform,spec.rigRoot);reach.left=Arm(spec.left);reach.right=Arm(spec.right);
            Check(reach.left.wristTarget.IsChildOf(presenter.leftHand)&&reach.right.wristTarget.IsChildOf(presenter.rightHand),"Measured wrist targets must stay hand-owned.");
            // Sample the real imported clip on its correct model-root-relative hierarchy.
            // No guessed bind rotations or lengths are serialized by the offline preparation.
            neutral[0].SampleAnimation(presenter.animator.gameObject,spec.neutralTimeSeconds);
            ValidateMaterialIdentityUnchanged(visual,materialSnapshot);
            string evidence="Unity6000.3.19f1: "+modelPath+" sha256="+Sha(modelPath)+" neutral="+spec.neutralState+" seconds="+
                spec.neutralTimeSeconds.ToString("R",System.Globalization.CultureInfo.InvariantCulture)+" discovery="+spec.discoveryReportSha256;
            Check(WeaponArmCalibration.CaptureCurrentNeutral(reach,source,evidence,spec.sourceToRigScale,
                spec.leftUpperSource,spec.leftForeSource,spec.rightUpperSource,spec.rightForeSource,
                spec.positionToleranceRig,spec.numericToleranceRig,out string reason),"Actual imported neutral arm calibration failed: "+reason);
            Check(WeaponArmReach.UniformPositive(reach.rigRoot,out float scale),"Calibrated rig must retain its actual uniform positive scale.");
            presenter.armReach=reach;
            // Original Muzzle remains untouched. The adapter's +Z follows observed source bone +Y.
            // This is source-axis construction, NOT gameplay camera/reticle calibration or a flash.
            Check(Vector3.Distance(spec.sourceMuzzleForwardLocal,Vector3.up)<.000001f&&Vector3.Distance(spec.sourceMuzzleUpLocal,Vector3.forward)<.000001f,"This pinned source requires explicit +Y muzzle and +Z up axes.");
            Transform original=presenter.muzzle;
            var adapter=CreateSourceAxisAdapter(original,spec.sourceMuzzleForwardLocal,spec.sourceMuzzleUpLocal);
            presenter.muzzle=adapter;
            muzzle.forwardAdapterPath=AnimationUtility.CalculateTransformPath(adapter,visual.transform);
            muzzle.forwardAdapterWorld=adapter.forward;muzzle.sourceAxisDerived=true;muzzle.calibratedForScene=false;
            var readback=new Readback{neutralState=spec.neutralState,neutralTimeSeconds=spec.neutralTimeSeconds,neutralPoseEvidence=evidence,
                sourceSha256=reach.sourceSha256,rigRoot=spec.rigRoot,rigWorldScale=scale,positionToleranceWorld=spec.positionToleranceRig*scale,
                numericToleranceWorld=spec.numericToleranceRig*scale,left=ReadArm(reach.left,visual.transform),right=ReadArm(reach.right,visual.transform)};
            for(int i=0;i<expectedMaterials.Length;i++)
            {
                var expected=expectedMaterials[i];string expectedPath=MaterialPath(materialFolder,i);
                var material=AssetDatabase.LoadAssetAtPath<Material>(expectedPath);
                string identity=MaterialIdentity(material,out string guid,out long localId);
                Check(identity==materialSnapshot.expectedIdentities[i],"Persistent candidate material identity changed: "+expected.sourceName);
                var color=material.GetColor("_BaseColor");
                float metallic=material.GetFloat("_Metallic"),smoothness=material.GetFloat("_Smoothness"),cull=material.GetFloat("_Cull");
                Check(ColorNear(color,expected.baseColor)&&Mathf.Abs(metallic-expected.metallic)<.00001f&&Mathf.Abs(smoothness-expected.smoothness)<.00001f&&
                    Mathf.Abs(cull-(expected.doubleSided?0:2))<.00001f,"Actual material readback differs from the reviewed source mapping: "+expected.sourceName);
                readback.materials.Add(new MaterialReadback{sourceName=expected.sourceName,materialPath=AssetDatabase.GetAssetPath(material),shader=material.shader.name,actualName=material.name,materialGuid=guid,materialLocalId=localId,
                    expectedColor=expected.baseColor,actualColor=color,expectedMetallic=expected.metallic,actualMetallic=metallic,expectedSmoothness=expected.smoothness,actualSmoothness=smoothness,actualCull=cull});
            }
            return readback;
            ArmReachBinding Arm(ArmPaths paths)=>new ArmReachBinding{upperArm=At(visual.transform,paths.upperArm),forearm=At(visual.transform,paths.forearm),wristTip=At(visual.transform,paths.wristTip),wristTarget=At(visual.transform,paths.wristTarget)};
        }
        public sealed class MaterialSnapshot
        {
            public Renderer[] renderers;
            public string[][] slotIdentities;
            public string[] expectedPaths,expectedIdentities;
        }
        // Names are observation metadata, not identity. The creator's exact output path,
        // persistent object, GUID/localID, source mapping and every slot remain required.
        public static MaterialSnapshot CaptureMaterialIdentity(GameObject visual,string materialFolder,int count)
        {
            Check(visual&&count>0&&count<=32,"Bounded actual material set required.");
            var snapshot=new MaterialSnapshot{renderers=visual.GetComponentsInChildren<Renderer>(true),expectedPaths=new string[count],expectedIdentities=new string[count]};
            Check(snapshot.renderers.Length>0,"Material identity check requires actual renderers.");
            for(int i=0;i<count;i++)
            {
                string path=MaterialPath(materialFolder,i);var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                snapshot.expectedPaths[i]=path;snapshot.expectedIdentities[i]=MaterialIdentity(material,out string guid,out long localId);
                Check(AssetDatabase.GetAssetPath(material)==path,"Loaded material path differs from exact created path.");
                LogMaterial("before-neutral",path,material.name,guid,localId);
            }
            Check(snapshot.expectedIdentities.Distinct().Count()==count,"Declared material identities must be distinct.");
            snapshot.slotIdentities=new string[snapshot.renderers.Length][];var used=new HashSet<string>();
            for(int r=0;r<snapshot.renderers.Length;r++)
            {
                var slots=snapshot.renderers[r].sharedMaterials;Check(slots.Length>0,"Actual renderer has no material slots.");
                snapshot.slotIdentities[r]=slots.Select(m=>MaterialIdentity(m,out _,out _)).ToArray();
                foreach(string id in snapshot.slotIdentities[r]){Check(snapshot.expectedIdentities.Contains(id),"Renderer uses material outside the exact created set.");used.Add(id);}
            }
            Check(used.SetEquals(snapshot.expectedIdentities),"Created material set does not match the exact used slots.");
            return snapshot;
        }
        public static void ValidateMaterialIdentityUnchanged(GameObject visual,MaterialSnapshot snapshot)
        {
            Check(visual&&snapshot!=null&&visual.GetComponentsInChildren<Renderer>(true).SequenceEqual(snapshot.renderers),"Renderer set changed during neutral sampling.");
            // Emit actual post-sample names even when a slot will fail the identity check.
            foreach(var observed in snapshot.renderers.SelectMany(r=>r.sharedMaterials).Distinct().Take(32))
            {
                string guid=null;long localId=0;
                if(observed)AssetDatabase.TryGetGUIDAndLocalFileIdentifier(observed,out guid,out localId);
                LogMaterial("after-neutral-observed",observed?AssetDatabase.GetAssetPath(observed):"<null>",observed?observed.name:"<null>",guid??"<unresolved>",localId);
            }
            for(int r=0;r<snapshot.renderers.Length;r++)
            {
                var slots=snapshot.renderers[r].sharedMaterials;Check(slots.Length==snapshot.slotIdentities[r].Length,"Material slot count changed during neutral sampling.");
                for(int slot=0;slot<slots.Length;slot++)
                    Check(MaterialIdentity(slots[slot],out _,out _)==snapshot.slotIdentities[r][slot],"Material slot identity changed during neutral sampling: "+
                        AnimationUtility.CalculateTransformPath(snapshot.renderers[r].transform,visual.transform)+" slot="+slot);
            }
            for(int i=0;i<snapshot.expectedPaths.Length;i++)
            {
                var material=AssetDatabase.LoadAssetAtPath<Material>(snapshot.expectedPaths[i]);
                Check(MaterialIdentity(material,out string guid,out long localId)==snapshot.expectedIdentities[i],"Declared asset identity changed during neutral sampling.");
                LogMaterial("after-neutral",snapshot.expectedPaths[i],material.name,guid,localId);
            }
        }
        static string MaterialPath(string folder,int index)
        {SafeRelative(folder);return folder+"/Material_"+index.ToString("D2")+".mat";}
        static string MaterialIdentity(Material material,out string guid,out long localId)
        {
            guid=null;localId=0;Check(material&&EditorUtility.IsPersistent(material),"Material must be a real persistent asset, not a same-name instance.");
            string path=AssetDatabase.GetAssetPath(material);
            Check(!string.IsNullOrEmpty(path)&&AssetDatabase.LoadAssetAtPath<Material>(path)==material&&
                AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material,out guid,out localId)&&Regex.IsMatch(guid??"","^[a-f0-9]{32}$")&&localId!=0,
                "Material object/path/GUID/localID must identify the actual main material asset.");
            return path+"|"+guid+"|"+localId.ToString(System.Globalization.CultureInfo.InvariantCulture);
        }
        static void LogMaterial(string phase,string path,string name,string guid,long localId)
            =>Debug.Log("CANDIDATE_WEAPON_MATERIAL phase="+phase+" path="+path+" actualName="+name+" guid="+guid+" localId="+localId);
        static ArmReadback ReadArm(ArmReachBinding arm,Transform modelRoot)=>new ArmReadback
        {
            upperArm=AnimationUtility.CalculateTransformPath(arm.upperArm,modelRoot),forearm=AnimationUtility.CalculateTransformPath(arm.forearm,modelRoot),
            wristTip=AnimationUtility.CalculateTransformPath(arm.wristTip,modelRoot),wristTarget=AnimationUtility.CalculateTransformPath(arm.wristTarget,modelRoot),
            neutralPoseEvidence=arm.neutralPoseEvidence,calibrated=arm.calibrated,upperLengthRig=arm.upperLengthRig,foreLengthRig=arm.foreLengthRig,
            sourceUpperLength=arm.sourceUpperLength,sourceForeLength=arm.sourceForeLength,sourceToRigScale=arm.sourceToRigScale,
            upperAxisLocal=arm.upperAxisLocal,foreAxisLocal=arm.foreAxisLocal,poleRigLocal=arm.poleRigLocal,shoulderLocal=arm.shoulderLocal,
            elbowLocal=arm.elbowLocal,tipLocal=arm.tipLocal,upperScale=arm.upperScale,foreScale=arm.foreScale,
            upperBindRotation=arm.upperBindRotation,foreBindRotation=arm.foreBindRotation
        };
        public static Transform CreateSourceAxisAdapter(Transform source,Vector3 forward,Vector3 up)
        {
            Check(source&&Finite(forward.x)&&Finite(forward.y)&&Finite(forward.z)&&Finite(up.x)&&Finite(up.y)&&Finite(up.z)&&
                Mathf.Abs(forward.magnitude-1)<.00001f&&Mathf.Abs(up.magnitude-1)<.00001f&&Mathf.Abs(Vector3.Dot(forward,up))<.00001f,"Finite orthonormal explicit muzzle axes required.");
            Check(!source.Cast<Transform>().Any(c=>c.name=="CandidateShotMuzzleAxis"),"Never replace an existing muzzle adapter.");
            var adapter=new GameObject("CandidateShotMuzzleAxis").transform;adapter.SetParent(source,false);
            adapter.localPosition=Vector3.zero;adapter.localRotation=Quaternion.LookRotation(forward,up);adapter.localScale=Vector3.one;
            Check(Vector3.Dot(adapter.forward.normalized,source.TransformDirection(forward).normalized)>.99999f,"Actual adapter forward differs from the source bone axis.");
            return adapter;
        }
        static Transform At(Transform root,string path)
        {
            Check(path!=null,"Explicit actual model-relative path required.");if(path=="")return root;SafeRelative(path);
            foreach(string segment in path.Split('/')) {var found=root.Cast<Transform>().Where(t=>t.name==segment).ToArray();Check(found.Length==1,"Missing/ambiguous measured hierarchy path: "+path);root=found[0];}return root;
        }
        static bool ColorNear(Color a,Color b)=>Mathf.Abs(a.r-b.r)<.00001f&&Mathf.Abs(a.g-b.g)<.00001f&&Mathf.Abs(a.b-b.b)<.00001f&&Mathf.Abs(a.a-b.a)<.00001f;
        static bool Finite(float value)=>!float.IsNaN(value)&&!float.IsInfinity(value);
    }
}

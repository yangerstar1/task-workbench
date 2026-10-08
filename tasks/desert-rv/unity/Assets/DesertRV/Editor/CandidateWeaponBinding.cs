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
            public string sourceName,materialPath,shader;
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
            IEnumerable<AnimationClip> clips,IEnumerable<MaterialSpec> materialSpecs,MuzzleObservation muzzle)
        {
            Check(spec!=null&&spec.left!=null&&spec.right!=null,"Explicit measured arm and muzzle source-axis contract required.");
            Check(Regex.IsMatch(spec.discoveryReportSha256??"","^[a-f0-9]{64}$"),"Pin the real Unity discovery report.");
            var neutral=clips.Where(c=>c.name==spec.neutralState).ToArray();
            Check(neutral.Length==1&&spec.neutralState=="Idle"&&Finite(spec.neutralTimeSeconds)&&spec.neutralTimeSeconds>=0&&spec.neutralTimeSeconds<=neutral[0].length,"Explicit actual neutral Idle clip and time required.");
            var source=AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);Check(source,"Actual FBX source is missing.");
            var reach=presenter.gameObject.AddComponent<WeaponArmReach>();reach.animator=presenter.animator;
            reach.rigRoot=At(visual.transform,spec.rigRoot);reach.left=Arm(spec.left);reach.right=Arm(spec.right);
            Check(reach.left.wristTarget.IsChildOf(presenter.leftHand)&&reach.right.wristTarget.IsChildOf(presenter.rightHand),"Measured wrist targets must stay hand-owned.");
            // Sample the real imported clip on its correct model-root-relative hierarchy.
            // No guessed bind rotations or lengths are serialized by the offline preparation.
            neutral[0].SampleAnimation(presenter.animator.gameObject,spec.neutralTimeSeconds);
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
            var actualMaterials=visual.GetComponentsInChildren<Renderer>(true).SelectMany(r=>r.sharedMaterials).Distinct().ToArray();
            foreach(var expected in materialSpecs)
            {
                var matches=actualMaterials.Where(m=>m&&m.name==expected.sourceName+"_Candidate").ToArray();
                Check(matches.Length==1,"Missing/ambiguous actual candidate material: "+expected.sourceName);
                var material=matches[0];var color=material.GetColor("_BaseColor");
                float metallic=material.GetFloat("_Metallic"),smoothness=material.GetFloat("_Smoothness"),cull=material.GetFloat("_Cull");
                Check(ColorNear(color,expected.baseColor)&&Mathf.Abs(metallic-expected.metallic)<.00001f&&Mathf.Abs(smoothness-expected.smoothness)<.00001f&&
                    Mathf.Abs(cull-(expected.doubleSided?0:2))<.00001f,"Actual material readback differs from the reviewed source mapping: "+expected.sourceName);
                readback.materials.Add(new MaterialReadback{sourceName=expected.sourceName,materialPath=AssetDatabase.GetAssetPath(material),shader=material.shader.name,
                    expectedColor=expected.baseColor,actualColor=color,expectedMetallic=expected.metallic,actualMetallic=metallic,expectedSmoothness=expected.smoothness,actualSmoothness=smoothness,actualCull=cull});
            }
            return readback;
            ArmReachBinding Arm(ArmPaths paths)=>new ArmReachBinding{upperArm=At(visual.transform,paths.upperArm),forearm=At(visual.transform,paths.forearm),wristTip=At(visual.transform,paths.wristTip),wristTarget=At(visual.transform,paths.wristTarget)};
        }
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

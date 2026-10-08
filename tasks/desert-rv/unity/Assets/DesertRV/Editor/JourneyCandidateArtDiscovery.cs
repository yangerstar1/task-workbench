using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using static DesertRV.Editor.JourneyCandidateArtImport;

namespace DesertRV.Editor
{
    // Discovery imports bytes, never creates gameplay prefabs/controllers or invents bindings.
    public static class JourneyCandidateArtDiscovery
    {
        [Serializable] public sealed class Node
        {
            public string path, name; public Vector3 localPosition, localScale, worldPosition, basisX, basisY, basisZ; public Quaternion localRotation;
        }
        [Serializable] public sealed class MeshRecord
        {
            public string rendererPath, rendererType, rootBone; public string[] materials, materialAssetPaths, bones;
            public int vertices, subMeshes, bindPoseCount, boneWeightCount; public Matrix4x4[] bindPoses;
            public Bounds localBounds, worldBounds; public bool readable;
        }
        [Serializable] public sealed class Take { public string name,takeName; public float firstFrame,lastFrame; public bool loop; }
        [Serializable] public sealed class Curve { public string path, property, type; }
        [Serializable] public sealed class Clip
        {
            public string name; public float seconds,frameRate; public bool looping,rootCurves,motionCurves;
            public Curve[] floatCurves,objectCurves; public int events;
        }
        [Serializable] public sealed class Model
        {
            public string file,dependencyHash,dependencySha256; public string[] dependencies;
            public List<Node> hierarchy=new List<Node>(); public List<MeshRecord> renderers=new List<MeshRecord>();
            public Take[] defaultTakes; public Clip[] importedClips;
        }
        [Serializable] public sealed class DiscoveryReport
        {
            public string mode="DISCOVERY_ONLY", status="failed-discovery",scope,contractSha256,runUrl,sourceCommit,artifactName,artifactSha256;
            public bool approved=false, bindingCalibrated=false;
            public string limitation="Raw imported structure only. No final material mapping, weakpoint axis calibration, motion/visual acceptance or gameplay verification. Muzzle basis is observed, not certified barrel direction.";
            public List<Model> models=new List<Model>(); public List<string> failures=new List<string>();
        }
        public static void Discover()
        {
            string folder=Path.GetFullPath("CandidateImportInput"); string contractFile=Path.Combine(folder,"contract.json");
            var report=new DiscoveryReport(); Directory.CreateDirectory("JourneyEvidence/CandidateArtDiscovery");
            try
            {
                Check(Application.unityVersion=="6000.3.19f1","Exact Unity version required.");
                var c=JsonUtility.FromJson<Contract>(File.ReadAllText(contractFile)); ValidateSourceContract(c);
                Check(c.mode=="DISCOVERY_ONLY","Discovery entry requires explicit DISCOVERY_ONLY contract.");
                Check(c.scope=="DEATH_DIAGNOSTIC_NOT_FULL" || c.scope=="FULL_CANDIDATE" || c.scope=="PARTIAL_DIAGNOSTIC_NOT_FULL","Explicit bounded source scope required.");
                Check(c.bindings==null && (c.clips==null || c.clips.Length==0) && (c.materials==null || c.materials.Length==0),"Discovery must not contain inferred strict bindings/takes/material mappings.");
                report.scope=c.scope;report.runUrl=c.runUrl;report.sourceCommit=c.sourceCommit;report.artifactName=c.artifactName;report.artifactSha256=c.artifactSha256;report.contractSha256=Sha(contractFile);
                Check(Sha(Path.Combine(folder,"artifact.zip"))==c.artifactSha256,"Artifact archive mismatch.");
                string destination="Assets/DesertRV/CandidateArtDiscovery/"+c.id;
                Check(!Directory.Exists(destination) && !File.Exists(destination+".meta"),"Discovery ID already exists; no overwrite.");
                foreach(var f in c.files)Check(Sha(Source(Path.Combine(folder,"payload"),f.file))==f.sha256,"Payload mismatch: "+f.file);
                foreach(var f in c.files) { string target=destination+"/Source/"+f.file; Directory.CreateDirectory(Path.GetDirectoryName(target));File.Copy(Source(Path.Combine(folder,"payload"),f.file),target,false); }
                File.Copy(contractFile,destination+"/discovery-contract.json",false);
                AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                foreach(var f in c.files.Where(f=>f.file.EndsWith(".fbx",StringComparison.OrdinalIgnoreCase)))
                {
                    string path=destination+"/Source/"+f.file; var importer=AssetImporter.GetAtPath(path) as ModelImporter;Check(importer,"Actual FBX importer missing.");
                    importer.isReadable=true;importer.optimizeGameObjects=false;importer.importAnimation=true;importer.animationType=ModelImporterAnimationType.Generic;
                    importer.animationCompression=ModelImporterAnimationCompression.Off;importer.importCameras=false;importer.importLights=false;
                    // Do NOT rename takes, select frames, change root baking, or remap source materials.
                    importer.SaveAndReimport();
                    var model=AssetDatabase.LoadAssetAtPath<GameObject>(path);Check(model,"Actual imported model missing.");
                    var record=new Model{file=f.file};
                    foreach(var t in model.GetComponentsInChildren<Transform>(true))
                        record.hierarchy.Add(new Node{path=AnimationUtility.CalculateTransformPath(t,model.transform),name=t.name,localPosition=t.localPosition,localRotation=t.localRotation,localScale=t.localScale,worldPosition=t.position,basisX=t.TransformDirection(Vector3.right),basisY=t.TransformDirection(Vector3.up),basisZ=t.TransformDirection(Vector3.forward)});
                    foreach(var renderer in model.GetComponentsInChildren<Renderer>(true))
                    {
                        var skin=renderer as SkinnedMeshRenderer;var filter=renderer.GetComponent<MeshFilter>();var mesh=skin?skin.sharedMesh:filter?filter.sharedMesh:null;
                        Check(mesh,"Unsupported/non-mesh model renderer.");
                        var r=new MeshRecord{rendererPath=AnimationUtility.CalculateTransformPath(renderer.transform,model.transform),rendererType=renderer.GetType().Name,vertices=mesh.vertexCount,subMeshes=mesh.subMeshCount,localBounds=mesh.bounds,worldBounds=renderer.bounds,readable=mesh.isReadable,
                            materials=renderer.sharedMaterials.Select(m=>m?m.name:"<null>").ToArray(),materialAssetPaths=renderer.sharedMaterials.Select(m=>m?AssetDatabase.GetAssetPath(m):"").ToArray(),bindPoses=mesh.bindposes,bindPoseCount=mesh.bindposes.Length};
                        if(skin) {r.rootBone=skin.rootBone?AnimationUtility.CalculateTransformPath(skin.rootBone,model.transform):"<null>";r.bones=skin.bones.Select(b=>b?AnimationUtility.CalculateTransformPath(b,model.transform):"<null>").ToArray();r.boneWeightCount=mesh.GetAllBoneWeights().Length;}
                        record.renderers.Add(r);
                    }
                    record.defaultTakes=importer.defaultClipAnimations.Select(t=>new Take{name=t.name,takeName=t.takeName,firstFrame=t.firstFrame,lastFrame=t.lastFrame,loop=t.loopTime}).ToArray();
                    record.importedClips=AssetDatabase.LoadAllAssetsAtPath(path).OfType<AnimationClip>().Select(clip=>new Clip{name=clip.name,seconds=clip.length,frameRate=clip.frameRate,looping=clip.isLooping,rootCurves=clip.hasRootCurves,motionCurves=clip.hasMotionCurves,events=AnimationUtility.GetAnimationEvents(clip).Length,
                        floatCurves=AnimationUtility.GetCurveBindings(clip).Select(b=>new Curve{path=b.path,property=b.propertyName,type=b.type.FullName}).ToArray(),objectCurves=AnimationUtility.GetObjectReferenceCurveBindings(clip).Select(b=>new Curve{path=b.path,property=b.propertyName,type=b.type.FullName}).ToArray()}).ToArray();
                    record.dependencies=AssetDatabase.GetDependencies(path,true);record.dependencyHash=AssetDatabase.GetAssetDependencyHash(path).ToString();record.dependencySha256=JourneyContentChecks.DependencySha256(path);report.models.Add(record);
                }
                AssetDatabase.SaveAssets();report.status="discovered-unreviewed-not-bound";
            }
            catch(Exception e){report.failures.Add(e.ToString());throw;}
            finally {File.WriteAllText("JourneyEvidence/CandidateArtDiscovery/discovery-report.json",JsonUtility.ToJson(report,true));}
        }
    }
}

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
            public MaterialObservation[] materialObservations;
        }
        [Serializable] public sealed class MaterialPropertyObservation
        {
            public string name,type,textureName,texturePath,textureFileSha256,textureGuid;
            public long textureLocalId;
            public float scalar; public Color color; public Vector4 vector;
            public Vector2 textureScale,textureOffset;
        }
        [Serializable] public sealed class MaterialObservation
        {
            public string name,path,shaderName,shaderPath; public string[] keywords;
            public List<MaterialPropertyObservation> properties=new List<MaterialPropertyObservation>();
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
        // Scan actual top-level JSON property names. Escapes and nested/string values
        // are consumed structurally; value text is never mistaken for a key.
        public static bool ContainsStrictRootFields(string json)
        {
            int depth=0; bool keyExpected=false;
            for(int i=0;i<json.Length;i++)
            {
                char ch=json[i];
                if(ch=='"')
                {
                    var token=new System.Text.StringBuilder(); bool closed=false;
                    while(++i<json.Length)
                    {
                        ch=json[i];
                        if(ch=='"'){closed=true;break;}
                        if(ch=='\\')
                        {
                            if(++i>=json.Length)throw new FormatException("Invalid JSON escape.");
                            ch=json[i];
                            if(ch=='u')
                            {
                                if(i+4>=json.Length)throw new FormatException("Invalid Unicode escape.");
                                token.Append((char)Convert.ToInt32(json.Substring(i+1,4),16));i+=4;continue;
                            }
                            switch(ch)
                            {
                                case '"':case '\\':case '/':token.Append(ch);break;
                                case 'b':token.Append('\b');break;case 'f':token.Append('\f');break;
                                case 'n':token.Append('\n');break;case 'r':token.Append('\r');break;case 't':token.Append('\t');break;
                                default:throw new FormatException("Invalid JSON escape.");
                            }
                        }
                        else token.Append(ch);
                    }
                    if(!closed)throw new FormatException("Unclosed JSON string.");
                    if(depth==1 && keyExpected)
                    {
                        int next=i+1;while(next<json.Length && char.IsWhiteSpace(json[next]))next++;
                        if(next>=json.Length || json[next]!=':')throw new FormatException("JSON property colon required.");
                        string key=token.ToString();if(key=="bindings" || key=="clips" || key=="materials" || key=="weapon")return true;
                        keyExpected=false;
                    }
                    continue;
                }
                if(ch=='{' || ch=='['){depth++;if(depth==1)keyExpected=true;}
                else if(ch=='}' || ch==']'){depth--;if(depth<0)throw new FormatException("Invalid JSON nesting.");}
                else if(ch==',' && depth==1)keyExpected=true;
            }
            if(depth!=0)throw new FormatException("Unclosed JSON container.");
            return false;
        }
        public static void Discover()
        {
            string folder=Path.GetFullPath("CandidateImportInput"); string contractFile=Path.Combine(folder,"contract.json");
            var report=new DiscoveryReport(); Directory.CreateDirectory("JourneyEvidence/CandidateArtDiscovery");
            try
            {
                Check(Application.unityVersion=="6000.3.19f1","Exact Unity version required.");
                string contractJson=File.ReadAllText(contractFile);
                var c=JsonUtility.FromJson<Contract>(contractJson); ValidateSourceContract(c);
                Check(c.mode=="DISCOVERY_ONLY","Discovery entry requires explicit DISCOVERY_ONLY contract.");
                Check(c.scope=="DEATH_DIAGNOSTIC_NOT_FULL" || c.scope=="FULL_CANDIDATE" || c.scope=="PARTIAL_DIAGNOSTIC_NOT_FULL","Explicit bounded source scope required.");
                // JsonUtility can materialize absent serializable fields as default objects.
                // Reject strict keys in the reviewed raw JSON, not serializer-created defaults.
                Check(!ContainsStrictRootFields(contractJson),"Discovery must not contain strict bindings/takes/material mapping keys.");
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
                            materialObservations=renderer.sharedMaterials.Select(ObserveMaterial).ToArray(),
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
        // Read the actual imported material; no shader changes, copied colors or texture remapping.
        static MaterialObservation ObserveMaterial(Material material)
        {
            if(!material)return new MaterialObservation{name="<null>"};
            var shader=material.shader;
            var observation=new MaterialObservation{name=material.name,path=AssetDatabase.GetAssetPath(material),shaderName=shader?shader.name:"<null>",shaderPath=shader?AssetDatabase.GetAssetPath(shader):"",keywords=material.shaderKeywords};
            if(!shader)return observation;
            for(int i=0;i<shader.GetPropertyCount();i++)
            {
                string name=shader.GetPropertyName(i);var type=shader.GetPropertyType(i);
                var p=new MaterialPropertyObservation{name=name,type=type.ToString()};
                switch(type)
                {
                    case UnityEngine.Rendering.ShaderPropertyType.Color:p.color=material.GetColor(name);break;
                    case UnityEngine.Rendering.ShaderPropertyType.Vector:p.vector=material.GetVector(name);break;
                    case UnityEngine.Rendering.ShaderPropertyType.Float:
                    case UnityEngine.Rendering.ShaderPropertyType.Range:p.scalar=material.GetFloat(name);break;
                    case UnityEngine.Rendering.ShaderPropertyType.Int:p.scalar=material.GetInteger(name);break;
                    case UnityEngine.Rendering.ShaderPropertyType.Texture:
                        var texture=material.GetTexture(name);p.textureScale=material.GetTextureScale(name);p.textureOffset=material.GetTextureOffset(name);
                        if(texture)
                        {
                            p.textureName=texture.name;p.texturePath=AssetDatabase.GetAssetPath(texture);
                            if(AssetDatabase.TryGetGUIDAndLocalFileIdentifier(texture,out string guid,out long localId)){p.textureGuid=guid;p.textureLocalId=localId;}
                            if(!string.IsNullOrEmpty(p.texturePath) && File.Exists(p.texturePath))p.textureFileSha256=Sha(p.texturePath);
                        }
                        break;
                }
                observation.properties.Add(p);
            }
            return observation;
        }
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace DesertRV.Editor
{
    // Explicit candidate-only import. Never edits scenes, manifest, review flags or build gates.
    public static class JourneyCandidateArtImport
    {
        const string Root = "Assets/DesertRV/CandidateArtImports";
        [Serializable] public sealed class InputFile { public string file, sha256; }
        [Serializable] public sealed class ClipSpec { public string state, file, take, poseExpectation; public float seconds; public bool loop; }
        [Serializable] public sealed class MaterialSpec
        {
            public string sourceName, baseColorFile, normalFile, metallicSmoothnessFile, occlusionFile, ormFile;
            public Color baseColor = Color.white; public float metallic, smoothness;
            // Only Unity packed metallic R/smoothness A is accepted, never raw ORM.
        }
        [Serializable] public sealed class RendererNeutralBaseline { public string path; public Vector3 worldCenter,worldExtents; }
        [Serializable] public sealed class RootNeutralBaseline { public Vector3 position,scale;public Quaternion rotation;public RendererNeutralBaseline[] renderers; }
        [Serializable] public sealed class Bindings
        {
            public string animatorPath, body, leftHand, rightHand, muzzle, incomingOffset, leftReloadOffset;
            public RootNeutralBaseline neutralBaseline;
            public string[] loadedNails, incomingNails;
            public string weakPointRoot, core; public string[] plates, plateRenderers;
            public Vector3[] openEuler; public Color openEmission, openBaseColor;
            public Vector3 colliderCenter; public float colliderRadius, colliderHeight;
        }
        [Serializable] public sealed class Contract
        {
            public int schema; public string mode, scope; public string id, kind, repository, runUrl, sourceCommit, artifactName, artifactSha256;
            public string modelFile; public InputFile[] files; public ClipSpec[] clips; public MaterialSpec[] materials; public Bindings bindings;
        }
        [Serializable] public sealed class ClipReadback { public string state, file, take, poseExpectation; public float seconds, frameRate; public int floatBindings, objectBindings; public bool loop; }
        [Serializable] public sealed class MuzzleObservation
        {
            public bool calibratedForScene = false;
            public string sourceBoneLocalForwardAxis = "+Y";
            public Vector3 sourceHead = new Vector3(0,.35f,.072f), sourceTail = new Vector3(0,.385f,.072f);
            public Vector3 importedWorldPosition, importedBasisX, importedBasisY, importedBasisZ;
            public string gate = "BLOCKED: verify actual exported head/tail or imported basis against barrel geometry before creating forward-aligned ShotMuzzle/flash adapter. No flash is bound; WeaponPresentation.ValidateBindings must fail until completed.";
        }
        [Serializable] public sealed class RootCurveReadback { public string state,property; public int keys; public float minimum,maximum; public bool constant,tangentsSafe; }
        [Serializable] public sealed class Report
        {
            public string mode="STRICT_BINDING",scope,kind;
            public string status = "failed-candidate-import", contractSha256, prefab, dependencyHash, dependencySha256;
            public string runUrl, sourceCommit, artifactName, artifactSha256;
            public bool candidateOnly = true, visualReviewed = false, gameplayReviewed = false;
            public MuzzleObservation muzzle;
            public string[] importedAnimatorPaths,dependencies;
            public List<CandidateOrmConversion.Record> derivedTextures=new List<CandidateOrmConversion.Record>();
            public List<RootCurveReadback> rootCurves=new List<RootCurveReadback>();
            public List<ClipReadback> clips = new List<ClipReadback>(); public List<string> failures = new List<string>();
            public string[] stillRequired = { "Actual Unity camera rendering and human visual review", "Interrupted/repeated runtime flows", "Full three-region playthrough", "Android device acceptance", "Explicit production review and unchanged production gate" };
        }
        // -executeMethod DesertRV.Editor.JourneyCandidateArtImport.Import
        // Inputs supplied by trusted Actions artifact download/extraction, not URLs fetched here.
        public static void Import()
        {
            string input = Environment.GetEnvironmentVariable("DESERTRV_ART_INPUT");
            string contractFile = Environment.GetEnvironmentVariable("DESERTRV_ART_CONTRACT");
            string archive = Environment.GetEnvironmentVariable("DESERTRV_ART_ARCHIVE");
            var report = new Report(); GameObject instance = null;
            Directory.CreateDirectory("JourneyEvidence/CandidateArt");
            try
            {
                Check(Application.unityVersion == "6000.3.19f1", "Exact Unity version required.");
                Check(!string.IsNullOrEmpty(input) && !string.IsNullOrEmpty(contractFile) && !string.IsNullOrEmpty(archive), "Three explicit input environment variables required.");
                var c = JsonUtility.FromJson<Contract>(File.ReadAllText(contractFile)); ValidateContract(c);
                report.scope=c.scope;report.kind=c.kind;
                report.contractSha256 = Sha(contractFile); report.runUrl=c.runUrl; report.sourceCommit=c.sourceCommit; report.artifactName=c.artifactName; report.artifactSha256=c.artifactSha256;
                Check(Sha(archive)==c.artifactSha256, "Downloaded artifact archive SHA256 mismatch.");
                string destination = Root + "/" + c.id;
                Check(!Directory.Exists(destination) && !File.Exists(destination+".meta"), "Candidate ID already exists. Use a fresh ID; never overwrite candidates or metas.");
                // Validate every input before writing any asset. Unknown files cannot be copied.
                foreach(var f in c.files) Check(Sha(Source(input,f.file))==f.sha256, "Input SHA256 mismatch: "+f.file);
                Directory.CreateDirectory(destination+"/Source");
                foreach(var f in c.files) { string path=destination+"/Source/"+f.file; Directory.CreateDirectory(Path.GetDirectoryName(path)); File.Copy(Source(input,f.file),path,false); }
                File.Copy(contractFile,destination+"/contract.json",false);
                AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                var paths = c.files.Where(f=>f.file.EndsWith(".fbx",StringComparison.OrdinalIgnoreCase)).Select(f=>destination+"/Source/"+f.file).ToArray();
                foreach(string path in paths) ConfigureModel(path,c,destination);
                ConfigureTextures(c,destination);
                var model=AssetDatabase.LoadAssetAtPath<GameObject>(destination+"/Source/"+c.modelFile); Check(model,"Actual model FBX did not import.");
                instance=new GameObject(c.id); instance.SetActive(false);
                var visual=(GameObject)PrefabUtility.InstantiatePrefab(model); visual.transform.SetParent(instance.transform,false);
                // All paths are model-root-relative and explicit, never name-search heuristics.
                var animatorRoot=At(visual.transform,c.bindings.animatorPath);
                var animators=visual.GetComponentsInChildren<Animator>(true);
                report.importedAnimatorPaths=animators.Select(a=>AnimationUtility.CalculateTransformPath(a.transform,visual.transform)).ToArray();
                foreach(var a in animators) Check(a.transform==animatorRoot,"Unexpected imported Animator: actual=["+AnimationUtility.CalculateTransformPath(a.transform,visual.transform)+"] expected=["+c.bindings.animatorPath+"]. No automatic relocation.");
                var animator=EnsureNativeAnimator(animatorRoot); animator.applyRootMotion=false;
                var clips=ReadClips(c,destination,animatorRoot,report);
                BindMaterials(c,destination,visual,report);
                string controllerPath=destination+"/Candidate.controller";
                var controller=AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
                foreach(var spec in c.clips) { var state=controller.layers[0].stateMachine.AddState(spec.state); state.motion=clips[spec.state]; if(spec.state=="Idle")controller.layers[0].stateMachine.defaultState=state; }
                animator.runtimeAnimatorController=controller;
                if(c.kind=="weapon") BindWeapon(c,destination,visual,instance,animator,clips.Values,report);
                else
                {
                    var actor=instance.AddComponent<BeastActor>(); actor.armored=c.kind=="armored"; actor.animator=animator;
                    var capsule=instance.AddComponent<CapsuleCollider>(); capsule.center=c.bindings.colliderCenter; capsule.radius=c.bindings.colliderRadius; capsule.height=c.bindings.colliderHeight;
                    if(actor.armored) BindArmored(c,destination,visual,instance,actor,clips.Values);
                }
                instance.SetActive(true);
                report.prefab=destination+"/Candidate.prefab";
                Check(PrefabUtility.SaveAsPrefabAsset(instance,report.prefab),"Prefab save failed.");
                AssetDatabase.SaveAssets(); AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                var dependencies=AssetDatabase.GetDependencies(report.prefab,true);report.dependencies=dependencies;
                foreach(string file in c.clips.Select(clip=>clip.file).Concat(new[]{c.modelFile}).Distinct())
                    Check(dependencies.Contains(destination+"/Source/"+file),"Prefab lost actual model/animation FBX dependency: "+file);
                report.dependencyHash=AssetDatabase.GetAssetDependencyHash(report.prefab).ToString();
                report.dependencySha256=JourneyContentChecks.DependencySha256(report.prefab);
                report.status="candidate-structure-imported-unreviewed";
            }
            catch(Exception e) { report.failures.Add(e.ToString()); throw; }
            finally
            {
                if(instance) UnityEngine.Object.DestroyImmediate(instance);
                // External evidence output cannot accidentally affect the dependency digest.
                File.WriteAllText("JourneyEvidence/CandidateArt/import-report.json",JsonUtility.ToJson(report,true));
            }
        }
        internal static void ValidateSourceContract(Contract c)
        {
            Check(c!=null && c.schema==1 && Regex.IsMatch(c.id??"","^[a-z0-9][a-z0-9-]{3,79}$"),"Invalid schema or immutable candidate ID.");
            Check(new[]{"pouncer","armored","weapon"}.Contains(c.kind),"Unknown candidate kind.");
            Check(c.repository=="yangerstar1/task-workbench" && Regex.IsMatch(c.sourceCommit??"","^[a-f0-9]{40}$") && Regex.IsMatch(c.artifactSha256??"","^[a-f0-9]{64}$") && !string.IsNullOrWhiteSpace(c.artifactName),"Exact source/artifact identity required.");
            Check(Regex.IsMatch(c.runUrl??"","^https://github\\.com/yangerstar1/task-workbench/actions/runs/[0-9]+$"),"Exact repository Actions run required.");
            Check(c.files!=null && c.files.Length>0 && c.files.Select(f=>f.file.ToLowerInvariant()).Distinct().Count()==c.files.Length,"Missing or case-colliding files.");
            foreach(var f in c.files) { SafeRelative(f.file); Check(Regex.IsMatch(f.sha256??"","^[a-f0-9]{64}$"),"Missing input hash."); Check(new[]{".fbx",".png",".tga"}.Contains(Path.GetExtension(f.file).ToLowerInvariant()),"Only declared FBX/PNG/TGA payloads allowed, no scripts or supplied metas."); }
            Check(c.files.Any(f=>f.file.EndsWith(".fbx",StringComparison.OrdinalIgnoreCase)),"At least one hashed FBX required.");
        }
        static void ValidateContract(Contract c)
        {
            ValidateSourceContract(c);
            Check(c.mode=="STRICT_BINDING" && c.scope=="FULL_CANDIDATE","Strict binding requires FULL_CANDIDATE source scope; discovery/partial diagnostic cannot promote itself.");
            Check(c.files.Any(f=>f.file==c.modelFile) && c.modelFile.EndsWith(".fbx",StringComparison.OrdinalIgnoreCase),"Model must be one hashed FBX.");
            string[] states=c.kind=="weapon"?new[]{"Idle","Fire","Reload"}:JourneyContentChecks.EnemyStates;
            Check(c.clips!=null && c.clips.Length==states.Length && c.clips.Select(s=>s.state).Distinct().Count()==states.Length && new HashSet<string>(states).SetEquals(c.clips.Select(s=>s.state)),"Exactly seven enemy / three weapon states required.");
            foreach(var s in c.clips)
            {
                Check(c.files.Any(f=>f.file==s.file) && s.file.EndsWith(".fbx",StringComparison.OrdinalIgnoreCase) && !string.IsNullOrWhiteSpace(s.take),"Explicit hashed FBX and exact take required.");
                Check(s.poseExpectation=="held" || s.poseExpectation=="varying","Explicit held/varying pose expectation required: "+s.state);
                float expected=ExpectedSeconds(c.kind,s.state);
                Check(Mathf.Abs(expected-s.seconds)<.00001f,"Duration differs from source/runtime contract: "+s.state);
                Check(s.loop==AllowedLoop(c.kind,s.state),"Only Idle/Walk and source-authored Armored Attack may loop; runtime still owns attack duration.");
            }
            Check(c.bindings!=null && c.materials!=null && c.materials.Length>0 && c.materials.Select(m=>m.sourceName).Distinct().Count()==c.materials.Length,"Explicit bindings/material mappings required.");
            if(c.kind!="weapon") Check(c.bindings.colliderRadius>=.15f && c.bindings.colliderRadius<=1.5f && c.bindings.colliderHeight>=.4f && c.bindings.colliderHeight<=4 && c.bindings.colliderHeight>=2*c.bindings.colliderRadius,"Explicit physical collider dimensions invalid.");
        }
        static float ExpectedSeconds(string kind,string state)
        {
            if(state=="Idle")return 2; if(state=="Death")return 1.8f; if(state=="Hit")return .28f;
            if(kind=="weapon") return state=="Fire"?.22f:1.65f;
            bool a=kind=="armored"; switch(state) { case "Walk":return a?.6f:.4f; case "Windup":return a?1.1f:.78f; case "Attack":return a?1.2f:.8f; case "Recover":return a?2:1.3f; default:throw new InvalidOperationException("Unknown state"); }
        }
        static void ConfigureModel(string path,Contract c,string destination)
        {
            var importer=AssetImporter.GetAtPath(path) as ModelImporter; Check(importer,"ModelImporter missing.");
            importer.isReadable=true; importer.animationType=ModelImporterAnimationType.Generic; importer.importAnimation=true; importer.optimizeGameObjects=false;
            importer.animationCompression=ModelImporterAnimationCompression.Off; importer.importCameras=false; importer.importLights=false;
            importer.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;
            var specs=c.clips.Where(s=>destination+"/Source/"+s.file==path).ToArray();
            var defaults=importer.defaultClipAnimations;
            Check(defaults.Length==specs.Length,"Unexpected/missing FBX takes: "+path);
            foreach(var spec in specs)
            {
                var matches=defaults.Where(d=>d.takeName==spec.take).ToArray(); Check(matches.Length==1,"Exact take missing/duplicate: "+spec.take);
                var clip=matches[0]; clip.name=spec.state; clip.loopTime=spec.loop; clip.loopPose=false;
                clip.lockRootRotation=true; clip.lockRootHeightY=true; clip.lockRootPositionXZ=true;
                clip.keepOriginalOrientation=true; clip.keepOriginalPositionY=true; clip.keepOriginalPositionXZ=true;
            }
            importer.clipAnimations=defaults; importer.SaveAndReimport();
        }
        static Dictionary<string,AnimationClip> ReadClips(Contract c,string destination,Transform root,Report report)
        {
            var result=new Dictionary<string,AnimationClip>();
            foreach(var group in c.clips.GroupBy(s=>s.file))
            {
                string path=destination+"/Source/"+group.Key;
                var imported=AssetDatabase.LoadAllAssetsAtPath(path).OfType<AnimationClip>().Where(a=>!a.name.StartsWith("__preview__",StringComparison.Ordinal)).ToArray();
                Check(imported.Length==group.Count(),"Unexpected actual AnimationClip count: "+path);
                foreach(var spec in group)
                {
                    var matches=imported.Where(a=>a.name==spec.state).ToArray(); Check(matches.Length==1,"Actual state clip missing/duplicate: "+spec.state);
                    var clip=matches[0]; var floats=AnimationUtility.GetCurveBindings(clip); var objects=AnimationUtility.GetObjectReferenceCurveBindings(clip);
                    Check(clip.frameRate>0 && !float.IsInfinity(clip.frameRate) && !float.IsNaN(clip.frameRate),"Invalid frame rate.");
                    Check(Mathf.Abs(clip.length-spec.seconds)<=1f/clip.frameRate+.0001f && clip.isLooping==spec.loop,"Actual clip duration/loop mismatch: "+spec.state);
                    Check(floats.Length>0 && objects.Length==0 && AnimationUtility.GetAnimationEvents(clip).Length==0,"No pose curves, object curves or forbidden AnimationEvents.");
                    Check(floats.Select(b=>b.path+"|"+b.type.FullName+"|"+b.propertyName).Distinct().Count()==floats.Length,"Duplicate curve binding.");
                    Check(!clip.hasRootCurves && !clip.hasMotionCurves,"Root/motion curves forbidden.");
                    foreach(var binding in floats)
                    {
                        Check(binding.type==typeof(Transform),"Only authored transform animation supported: "+binding.propertyName);
                        At(root,binding.path); var curve=AnimationUtility.GetEditorCurve(clip,binding);
                        Check(curve!=null && curve.keys.Length>0 && curve.keys.All(k=>Finite(k.value)),"Missing/nonfinite curve.");
                        if(binding.path=="")
                        {
                            bool constant=curve.keys.All(k=>Mathf.Abs(k.value-curve.keys[0].value)<.00001f);
                            bool tangentsSafe=curve.keys.All(k=>SafeConstantTangent(k.inTangent)&&SafeConstantTangent(k.outTangent));
                            report.rootCurves.Add(new RootCurveReadback{state=spec.state,property=binding.propertyName,keys=curve.keys.Length,minimum=curve.keys.Min(k=>k.value),maximum=curve.keys.Max(k=>k.value),constant=constant,tangentsSafe=tangentsSafe});
                            Check(constant && tangentsSafe,"Animated/interpolating model root forbidden.");
                        }
                        if(binding.propertyName.StartsWith("m_LocalScale",StringComparison.Ordinal)) Check(curve.keys.All(k=>k.value>.001f),"Animation scales geometry away.");
                    }
                    if(c.kind=="armored")RequireNeutralRootCurves(spec.state,report.rootCurves.Where(r=>r.state==spec.state).ToArray(),root);
                    // Euler and quaternion tracks on one transform would be competing rotation representations.
                    foreach(var track in floats.GroupBy(b=>b.path)) Check(!(track.Any(b=>b.propertyName.StartsWith("m_LocalRotation")) && track.Any(b=>b.propertyName.IndexOf("Euler",StringComparison.OrdinalIgnoreCase)>=0)),"Competing rotation curves: "+track.Key);
                    report.clips.Add(new ClipReadback { state=spec.state,file=spec.file,take=spec.take,poseExpectation=spec.poseExpectation,seconds=clip.length,frameRate=clip.frameRate,floatBindings=floats.Length,objectBindings=objects.Length,loop=clip.isLooping });
                    result.Add(spec.state,clip);
                }
            }
            return result;
        }
        static Animator EnsureNativeAnimator(Transform root)
        {
            Check(root,"Declared Animator root is missing.");
            var animator=root.GetComponent<Animator>();
            if(!animator)animator=root.gameObject.AddComponent<Animator>();
            Check(animator,"Actual native Animator could not be created on the declared root.");
            return animator;
        }
        static void RequireNeutralRootCurves(string state,RootCurveReadback[] rows,Transform root)
        {
            var required=new[]{"m_LocalPosition.x","m_LocalPosition.y","m_LocalPosition.z","m_LocalRotation.x","m_LocalRotation.y","m_LocalRotation.z","m_LocalRotation.w","m_LocalScale.x","m_LocalScale.y","m_LocalScale.z"};
            Check(rows.Length==10 && rows.Select(r=>r.property).Distinct().Count()==10 && required.All(p=>rows.Any(r=>r.property==p)),"Exact ten neutral root curves required: "+state);
            var values=rows.ToDictionary(r=>r.property,r=>r.minimum);
            var position=new Vector3(values["m_LocalPosition.x"],values["m_LocalPosition.y"],values["m_LocalPosition.z"]);
            var scale=new Vector3(values["m_LocalScale.x"],values["m_LocalScale.y"],values["m_LocalScale.z"]);
            var rotation=new Quaternion(values["m_LocalRotation.x"],values["m_LocalRotation.y"],values["m_LocalRotation.z"],values["m_LocalRotation.w"]);
            float norm=Quaternion.Dot(rotation,rotation);
            Check(Finite(norm) && Mathf.Abs(norm-1f)<=.00001f,"Invalid constant root quaternion: "+state);
            Check(Vector3.Distance(position,root.localPosition)<=.00001f && Vector3.Distance(scale,root.localScale)<=.00001f && Quaternion.Angle(rotation.normalized,root.localRotation.normalized)<=.001f,
                "Constant root curves differ from imported neutral: "+state+" expected position="+root.localPosition.ToString("G9")+" scale="+root.localScale.ToString("G9")+" rotation="+root.localRotation.ToString("G9")+"; actual position="+position.ToString("G9")+" scale="+scale.ToString("G9")+" rotation="+rotation.ToString("G9")+". Units are not automatically normalized.");
        }
        static void ConfigureTextures(Contract c,string destination)
        {
            var roles=new Dictionary<string,string>();
            foreach(var m in c.materials)
            {
                foreach(var pair in new[]{new[]{m.baseColorFile,"color"},new[]{m.normalFile,"normal"},new[]{m.metallicSmoothnessFile,"linear"},new[]{m.occlusionFile,"linear"},new[]{m.ormFile,"linear"}})
                {
                    if(string.IsNullOrEmpty(pair[0]))continue;
                    Check(c.files.Any(f=>f.file==pair[0]) && !pair[0].EndsWith(".fbx",StringComparison.OrdinalIgnoreCase),"Texture must be a declared hashed image.");
                    Check(!roles.ContainsKey(pair[0]) || roles[pair[0]]==pair[1],"Texture used with incompatible color/normal/linear roles."); roles[pair[0]]=pair[1];
                }
            }
            foreach(var pair in roles)
            {
                var importer=AssetImporter.GetAtPath(destination+"/Source/"+pair.Key) as TextureImporter; Check(importer,"TextureImporter missing.");
                importer.textureType=pair.Value=="normal"?TextureImporterType.NormalMap:TextureImporterType.Default;
                importer.sRGBTexture=pair.Value=="color"; importer.mipmapEnabled=true; importer.SaveAndReimport();
            }
        }
        static void BindMaterials(Contract c,string destination,GameObject visual,Report report)
        {
            var shader=Shader.Find("Universal Render Pipeline/Lit"); Check(shader,"URP Lit shader unavailable.");
            var maps=new Dictionary<string,Material>(); Directory.CreateDirectory(destination+"/Materials");
            for(int i=0;i<c.materials.Length;i++)
            {
                var s=c.materials[i]; Check(!string.IsNullOrWhiteSpace(s.sourceName),"Material source name required.");
                var material=new Material(shader); material.name=s.sourceName+"_Candidate"; material.SetColor("_BaseColor",s.baseColor); material.SetFloat("_Metallic",s.metallic); material.SetFloat("_Smoothness",s.smoothness);
                SetTexture(material,"_BaseMap",s.baseColorFile,destination,null);
                SetTexture(material,"_BumpMap",s.normalFile,destination,"_NORMALMAP");
                SetTexture(material,"_MetallicGlossMap",s.metallicSmoothnessFile,destination,"_METALLICSPECGLOSSMAP");
                SetTexture(material,"_OcclusionMap",s.occlusionFile,destination,"_OCCLUSIONMAP");
                if(!string.IsNullOrEmpty(s.ormFile))
                {
                    Check(string.IsNullOrEmpty(s.metallicSmoothnessFile)&&string.IsNullOrEmpty(s.occlusionFile),"Choose original ORM derivation or already packed textures, not both.");
                    var texture=CandidateOrmConversion.Convert(destination+"/Source/"+s.ormFile,destination+"/Derived/ORM_"+i.ToString("D2")+".png",out var conversion);
                    report.derivedTextures.Add(conversion);material.SetTexture("_MetallicGlossMap",texture);material.SetTexture("_OcclusionMap",texture);
                    material.SetFloat("_WorkflowMode",1);material.SetFloat("_SmoothnessTextureChannel",0);material.SetFloat("_Smoothness",1);material.SetFloat("_OcclusionStrength",1);
                    material.EnableKeyword("_METALLICSPECGLOSSMAP");material.EnableKeyword("_OCCLUSIONMAP");
                }
                AssetDatabase.CreateAsset(material,destination+"/Materials/Material_"+i.ToString("D2")+".mat"); maps.Add(s.sourceName,material);
            }
            var used=new HashSet<string>(); var renderers=visual.GetComponentsInChildren<Renderer>(true); Check(renderers.Length>0,"No model renderers.");
            foreach(var renderer in renderers)
            {
                Check(renderer.sharedMaterials.Length>0,"Renderer has no material slots.");
                renderer.sharedMaterials=renderer.sharedMaterials.Select(m=>{ Check(m && maps.ContainsKey(m.name),"Unmapped exact imported material: "+(m?m.name:"null")); used.Add(m.name); return maps[m.name]; }).ToArray();
            }
            Check(used.SetEquals(maps.Keys),"Unused material mappings may indicate stale contract.");
        }
        static void SetTexture(Material material,string property,string file,string destination,string keyword)
        {
            if(string.IsNullOrEmpty(file))return;
            var texture=AssetDatabase.LoadAssetAtPath<Texture2D>(destination+"/Source/"+file); Check(texture,"Declared texture missing.");
            material.SetTexture(property,texture); if(keyword!=null)material.EnableKeyword(keyword);
        }
        static void BindWeapon(Contract c,string destination,GameObject visual,GameObject instance,Animator animator,IEnumerable<AnimationClip> clips,Report report)
        {
            var b=c.bindings; Check(b.loadedNails!=null && b.loadedNails.Length==12 && b.incomingNails!=null && b.incomingNails.Length==12,"Exactly 12+12 renderer paths required.");
            var p=instance.AddComponent<WeaponPresentation>(); p.enabled=false; // Requires explicit scene actions/camera before enable.
            p.animator=animator; p.weaponRenderer=RendererAt(visual,b.body); p.leftHand=At(visual.transform,b.leftHand); p.rightHand=At(visual.transform,b.rightHand);
            p.muzzle=At(visual.transform,b.muzzle); p.incomingOffset=At(visual.transform,b.incomingOffset); p.leftReloadOffset=At(visual.transform,b.leftReloadOffset);
            Check(p.leftHand!=p.rightHand && p.leftHand.IsChildOf(p.leftReloadOffset) && !p.rightHand.IsChildOf(p.leftReloadOffset),"Hand carrier hierarchy mismatch.");
            Check(p.muzzle.name=="Muzzle" && p.muzzle.IsChildOf(animator.transform),"Muzzle must be the explicit authored Muzzle bone; no inferred tip.");
            p.loadedNails=b.loadedNails.Select(path=>RendererAt(visual,path)).ToArray(); p.incomingNails=b.incomingNails.Select(path=>RendererAt(visual,path)).ToArray();
            Check(p.loadedNails.Concat(p.incomingNails).Distinct().Count()==24,"Old/new nail renderers must be disjoint.");
            for(int i=0;i<12;i++)
            {
                Check(p.loadedNails[i].name=="LoadedNail_"+i.ToString("D2") && p.incomingNails[i].name=="IncomingNail_"+i.ToString("D2"),"Explicit round order/name mismatch.");
                Check(NailRigOwnership.ValidateLoaded(p.loadedNails[i],p.incomingOffset,animator.transform,out string loadedReason),"Loaded nail ownership: "+loadedReason);
                Check(NailRigOwnership.Validate(p.incomingNails[i],p.incomingOffset,animator.transform,out string incomingReason),"Incoming nail ownership: "+incomingReason);
            }
            Check(p.incomingOffset.parent && p.leftReloadOffset.parent,"Carriers require explicit parents.");
            Vector3 pitchWorld=Center(p.incomingNails[1])-Center(p.incomingNails[0]);
            for(int i=1;i<12;i++)
            {
                Check(Vector3.Distance(Center(p.incomingNails[i])-Center(p.incomingNails[i-1]),pitchWorld)<.001f,"Incoming nail spacing is nonuniform.");
                Check(Vector3.Distance(Center(p.loadedNails[i])-Center(p.loadedNails[i-1]),pitchWorld)<.001f,"Loaded/incoming nail order or spacing differs.");
            }
            foreach(var nail in p.loadedNails.Concat(p.incomingNails))
                Check(NailRigOwnership.TryGetAnimationTargets(nail,animator.transform,out _,out string targetReason),targetReason);
            p.nailPitch=p.incomingOffset.parent.InverseTransformVector(pitchWorld);
            Check(p.nailPitch.sqrMagnitude>.000001f && p.nailPitch.sqrMagnitude<.01f,"Imported pitch outside runtime limits.");
            RejectKeys(clips,animator.transform,new[]{p.incomingOffset,p.leftReloadOffset},false);
            report.muzzle=new MuzzleObservation
            {
                importedWorldPosition=p.muzzle.position,
                importedBasisX=p.muzzle.TransformDirection(Vector3.right),
                importedBasisY=p.muzzle.TransformDirection(Vector3.up),
                importedBasisZ=p.muzzle.TransformDirection(Vector3.forward)
            };
            // Source bone +Y is NOT automatically Unity +Z. These observations are not calibration evidence.
            // Intentionally leave flash unbound: normal ValidateBindings/production preflight cannot pass
            // before an explicit scene integration calibrates the imported barrel axis and authors the FX.
            p.muzzleFlash=null;
        }
        static Vector3 Center(Renderer renderer)
        {
            if(renderer is SkinnedMeshRenderer skin)
            {
                var baked=new Mesh(); try { skin.BakeMesh(baked); Check(baked.vertexCount>0,"Empty nail mesh."); return skin.transform.TransformPoint(baked.bounds.center); } finally { UnityEngine.Object.DestroyImmediate(baked); }
            }
            var filter=renderer.GetComponent<MeshFilter>(); Check(filter && filter.sharedMesh && filter.sharedMesh.vertexCount>0,"Nail requires actual geometry.");
            return renderer.transform.TransformPoint(filter.sharedMesh.bounds.center);
        }
        static void BindArmored(Contract c,string destination,GameObject visual,GameObject instance,BeastActor actor,IEnumerable<AnimationClip> clips)
        {
            var b=c.bindings; Check(b.plates!=null && b.plates.Length==2 && b.plateRenderers!=null && b.plateRenderers.Length==2 && b.openEuler!=null && b.openEuler.Length==2,"Exactly two authored plates required.");
            var root=At(visual.transform,b.weakPointRoot); var core=RendererAt(visual,b.core); var body=RendererAt(visual,b.body);
            Check(core is MeshRenderer && core!=body && core.sharedMaterials.Length==1,"Distinct rigid one-slot core required.");
            var plates=b.plates.Select(path=>At(visual.transform,path)).ToArray(); var renderers=b.plateRenderers.Select(path=>RendererAt(visual,path)).ToArray();
            Check(renderers.All(r=>r is MeshRenderer),"Plate renderers must be rigid MeshRenderer.");
            RejectKeys(clips,actor.animator.transform,new[]{root},true);
            Check(b.openEmission.maxColorComponent>0 && Finite(b.openEmission.r) && Finite(b.openEmission.g) && Finite(b.openEmission.b),"Explicit nonzero core emission required.");
            Check(b.openBaseColor.a>0 && b.openBaseColor.maxColorComponent>0 && Finite(b.openBaseColor.r) && Finite(b.openBaseColor.g) && Finite(b.openBaseColor.b),"Explicit candidate open base color required.");
            var open=CreatePersistedOpenCoreMaterial(core.sharedMaterials[0],b.openBaseColor,b.openEmission,destination+"/Materials/Core_Open.mat");
            var presenter=instance.AddComponent<BeastWeakPointPresentation>();
            var so=new SerializedObject(presenter);
            ObjectField(so,"actor",actor); ObjectField(so,"bodyRenderer",body); ObjectField(so,"weakPointRoot",root); ObjectField(so,"weakPointRenderer",core); ObjectField(so,"openMaterial",open);
            Property(so,"materialSlot").intValue=0;
            ArrayField(so,"armorPlates",plates); ArrayField(so,"plateRenderers",renderers);
            var angles=Property(so,"openLocalEulerAngles"); angles.arraySize=2; for(int i=0;i<2;i++)angles.GetArrayElementAtIndex(i).vector3Value=b.openEuler[i];
            so.ApplyModifiedPropertiesWithoutUndo();
            Check(presenter.ValidateBindings(out string reason),"Weakpoint candidate bindings failed: "+reason);
            var errors=new List<string>(); WeakPointContractChecks.Validate(presenter,"Imported candidate",errors); Check(errors.Count==0,string.Join("; ",errors));
        }
        // URP 17.3 rebuilds _EMISSION from AnyEmissive during material asset import.
        // A keyword alone (or clearing EmissiveIsBlack to None) does not survive that pass.
        internal static Material CreatePersistedOpenCoreMaterial(Material closed,Color baseColor,Color emission,string path)
        {
            Check(closed && closed.shader && closed.shader.name=="Universal Render Pipeline/Lit","Open core requires actual URP Lit closed source.");
            Check(emission.maxColorComponent>0 && Finite(emission.r) && Finite(emission.g) && Finite(emission.b),"Nonzero finite open emission required.");
            Check(!File.Exists(path) && !File.Exists(path+".meta"),"Open core asset already exists.");
            var open=new Material(closed);
            try
            {
                open.name="Candidate_Core_Open";open.SetColor("_BaseColor",baseColor);open.SetColor("_EmissionColor",emission);
                open.globalIlluminationFlags=(open.globalIlluminationFlags & ~MaterialGlobalIlluminationFlags.EmissiveIsBlack) | MaterialGlobalIlluminationFlags.BakedEmissive;
                MaterialEditor.FixupEmissiveFlag(open);open.EnableKeyword("_EMISSION");
                AssetDatabase.CreateAsset(open,path);EditorUtility.SetDirty(open);AssetDatabase.SaveAssets();
                AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceUpdate|ImportAssetOptions.ForceSynchronousImport);
                var persisted=AssetDatabase.LoadAssetAtPath<Material>(path);
                Check(persisted && persisted.GetColor("_EmissionColor").maxColorComponent>0 && persisted.IsKeywordEnabled("_EMISSION") &&
                    (persisted.globalIlluminationFlags & MaterialGlobalIlluminationFlags.AnyEmissive)!=0 &&
                    (persisted.globalIlluminationFlags & MaterialGlobalIlluminationFlags.EmissiveIsBlack)==0,
                    "Open core emission did not survive URP material save/reimport.");
                return persisted;
            }
            catch {if(open && !EditorUtility.IsPersistent(open))UnityEngine.Object.DestroyImmediate(open);throw;}
        }
        static void RejectKeys(IEnumerable<AnimationClip> clips,Transform root,IEnumerable<Transform> targets,bool descendants)
        {
            foreach(var target in targets)
            {
                Check(target.IsChildOf(root),"Unkeyed carrier is outside Animator hierarchy."); string path=AnimationUtility.CalculateTransformPath(target,root);
                foreach(var clip in clips) foreach(var b in AnimationUtility.GetCurveBindings(clip).Concat(AnimationUtility.GetObjectReferenceCurveBindings(clip)))
                    Check(b.path!=path && !(descendants && b.path.StartsWith(path+"/",StringComparison.Ordinal)),"Runtime-owned transform/assembly is keyed: "+clip.name+":"+b.path);
            }
        }
        static SerializedProperty Property(SerializedObject so,string name) { var p=so.FindProperty(name); Check(p!=null,"Required latest presenter contract field missing: "+name); return p; }
        static void ObjectField(SerializedObject so,string name,UnityEngine.Object value) => Property(so,name).objectReferenceValue=value;
        static void ArrayField<T>(SerializedObject so,string name,T[] values) where T:UnityEngine.Object { var p=Property(so,name); p.arraySize=values.Length; for(int i=0;i<values.Length;i++)p.GetArrayElementAtIndex(i).objectReferenceValue=values[i]; }
        static Renderer RendererAt(GameObject root,string path) { var r=At(root.transform,path).GetComponents<Renderer>(); Check(r.Length==1,"Exactly one renderer required at "+path); return r[0]; }
        static Transform At(Transform root,string path)
        {
            Check(path!=null,"Explicit path required (empty means model root)."); if(path=="")return root;
            SafeRelative(path); var current=root;
            foreach(string segment in path.Split('/')) { var children=current.Cast<Transform>().Where(t=>t.name==segment).ToArray(); Check(children.Length==1,"Missing/ambiguous actual imported hierarchy path: "+path); current=children[0]; }
            return current;
        }
        internal static void SafeRelative(string path) { Check(!string.IsNullOrWhiteSpace(path) && !Path.IsPathRooted(path) && !path.Contains('\\') && !path.Contains(':') && path.Split('/').All(s=>s!="" && s!="." && s!=".."),"Unsafe relative path."); }
        internal static string Source(string root,string relative)
        {
            SafeRelative(relative); var full=Path.GetFullPath(Path.Combine(root,relative)); var boundary=Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
            Check(full.StartsWith(boundary,StringComparison.Ordinal),"Input path escaped boundary.");
            string current=full; while(current.Length>=boundary.Length) { Check((File.GetAttributes(current)&FileAttributes.ReparsePoint)==0,"Symlink inputs forbidden."); current=Path.GetDirectoryName(current); }
            return full;
        }
        internal static string Sha(string path) { using(var sha=SHA256.Create()) using(var stream=File.OpenRead(path)) return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant(); }
        internal static bool AllowedLoop(string kind,string state)=>state=="Idle" || state=="Walk" || (kind=="armored" && state=="Attack");
        internal static bool SafeConstantTangent(float value)=>!float.IsNaN(value) && (float.IsInfinity(value)||value==0f);
        static bool Finite(float value)=>!float.IsNaN(value)&&!float.IsInfinity(value);
        internal static void Check(bool value,string message) { if(!value)throw new InvalidOperationException(message); }
    }
}


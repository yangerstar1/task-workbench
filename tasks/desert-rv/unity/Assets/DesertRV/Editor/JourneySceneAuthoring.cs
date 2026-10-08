using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using System.Collections.Generic;
using System.Security.Cryptography;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    // Explicit Actions authoring step. Never called by build/preprocess or on import.
    public static class JourneySceneAuthoring
    {
        public const string SourcePath = "Assets/DesertRV/Scenes/BodyStudy.unity";
        public const string Folder = "Assets/DesertRV/Scenes/Journey";
        public const string BootstrapPath = Folder + "/JourneyBootstrap.unity";
        public const string ManifestPath = Folder + "/JourneyContent.asset";
        public static readonly string[] RegionPaths = { Folder + "/FirstStation.unity", Folder + "/Scrapyard.unity", Folder + "/NightBeacon.unity" };
        public static readonly double[] RegionOffsets = { 0, 100, 200 };

        [MenuItem("Desert RV/Journey/Author candidate scenes (preserve originals)")]
        public static void AuthorCandidateScenes()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Author in Edit Mode only.");
            foreach (var path in new[] { BootstrapPath }.Concat(RegionPaths))
                if (File.Exists(path)) throw new IOException("Refusing to overwrite a saved scene: " + path + ". Review/archive it explicitly first.");
            var protectedFiles = SnapshotProtectedFiles();
            byte[] source = File.ReadAllBytes(SourcePath), meta = File.ReadAllBytes(SourcePath + ".meta");
            var previous = EditorSceneManager.GetSceneManagerSetup();
            if (previous.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty))
                throw new InvalidOperationException("Save or discard open scene edits before authoring.");
            Directory.CreateDirectory(Folder); AssetDatabase.Refresh();
            try
            {
                var sourceScene = EditorSceneManager.OpenScene(SourcePath, OpenSceneMode.Single);
                var viewer = Components<BodyViewer>(sourceScene).Single();
                if (!viewer.body || !viewer.view || !viewer.garageBench || !viewer.ramModule || !viewer.arcModule)
                    throw new InvalidOperationException("Saved RV/source bindings missing; original will not be regenerated.");
                var body = viewer.body;
                var nodes = body.GetComponentsInChildren<Transform>(true);
                var glass = nodes.Single(t => t.name == "GEO-windscreen").GetComponent<Renderer>();
                Vector3 forward = glass.bounds.center - body.position; forward.y = 0;
                if (forward.sqrMagnitude < .01f) throw new InvalidOperationException("RV forward reference invalid.");
                forward.Normalize(); var correction = Quaternion.FromToRotation(forward, Vector3.forward);
                Vector3 origin = body.position;
                // Rotate the complete environment around the RV anchor; fixed +Z world axis afterwards.
                foreach (var root in sourceScene.GetRootGameObjects())
                { root.transform.position = correction * (root.transform.position - origin); root.transform.rotation = correction * root.transform.rotation; }
                var boot = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
                var host = new GameObject("JourneyBootstrap"); SceneManager.MoveGameObjectToScene(host, boot);
                var session = host.AddComponent<JourneySession>(); var motor = host.AddComponent<JourneyMotor>();
                motor.journey = session; motor.vehicle = body; motor.view = viewer.view;
                motor.localForward = body.InverseTransformDirection(Vector3.forward);
                motor.doorHinge = nodes.Single(t => t.name == "RIG-entry_door_pivot");
                motor.entryStep = nodes.Single(t => t.name == "GEO-entry_step");
                motor.ram = viewer.ramModule; motor.arc = viewer.arcModule; motor.roofCargo = viewer.roofCargo;
                MoveUnder(body, host.transform, boot); MoveUnder(viewer.view.transform, host.transform, boot);
                // Exposure belongs to the persistent camera rig; lights/probes remain local to environments.
                foreach (var root in sourceScene.GetRootGameObjects().Where(r => r.name == "Exposure response")) MoveUnder(root.transform, host.transform, boot);
                motor.ram.SetActive(false); motor.arc.SetActive(false);
                var actions = host.AddComponent<JourneyActions>(); actions.journey = session; actions.motor = motor;
                var repair = nodes.Single(t => t.name == "GEO-rear_repair_bench");
                actions.workbenchSurface = ExactSurface(repair);
                actions.cabinWorkbench = Point("Cabin installation point", body, actions.workbenchSurface.bounds.center + Vector3.up * .18f);
                actions.shotSound = Audio("shot"); actions.hitSound = Audio("hit"); actions.reloadSound = Audio("reload");
                actions.pickupSound = Audio("pickup"); actions.upgradeSound = Audio("upgrade"); actions.windSound = Audio("wind");
                var loader = host.AddComponent<RegionLoader>(); loader.regionScenes = RegionPaths.Select(Path.GetFileNameWithoutExtension).ToArray();
                var hudObject = new GameObject("Journey HUD"); hudObject.transform.SetParent(host.transform, false);
                var hud = hudObject.AddComponent<JourneyHud>(); hud.journey = session; hud.motor = motor;
                hud.font = AssetDatabase.LoadAssetAtPath<Font>("Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf");
                var director = host.AddComponent<JourneyDirector>(); director.journey = session; director.motor = motor;
                director.actions = actions; director.loader = loader; director.hud = hud; hud.director = director;
                Object.DestroyImmediate(viewer); // Component only: never delete a source parent that may own dependencies.
                foreach (var preflight in Components<WebPreflight>(sourceScene)) Object.DestroyImmediate(preflight);
                var manifest = AssetDatabase.LoadAssetAtPath<JourneyContentManifest>(ManifestPath);
                if (!manifest) { manifest = ScriptableObject.CreateInstance<JourneyContentManifest>(); AssetDatabase.CreateAsset(manifest, ManifestPath); }
                // Do not infer weapon/arc presentation or review acceptance from a prefab's mere existence.
                Save(boot, BootstrapPath);
                var binding = NewBinding(sourceScene, 1); binding.spawn.rotation = body.rotation;
                var bench = viewerBench(sourceScene);
                binding.salvageSurface = ExactSurface(bench); binding.salvage = Point("Ram salvage interaction", binding.transform, binding.salvageSurface.bounds.center + Vector3.up * .18f);
                binding.salvageVisual = CopyModule(motor.ram, binding.salvage.position, binding.transform, "Ram salvage assembly");
                PopulateLayout(binding, manifest); DressEnvironment(sourceScene,binding); SetAtmosphere(sourceScene,1);
                Save(sourceScene, RegionPaths[0]);
                // Reuse authored source geometry/materials, never regenerate the accepted RV.
                Transform crate = Components<Transform>(sourceScene).Single(t => t.name == "GEO-workshop_drum");
                for (int region = 2; region <= 3; region++)
                {
                    var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
                    var next = NewBinding(scene, region); next.spawn.rotation = body.rotation; PopulateLayout(next, manifest);
                    for (int i = 0; i < 8 && crate; i++)
                    {
                        var holder = new GameObject("Retained workshop drum " + i).transform; holder.SetParent(next.transform,false);
                        var prop = Object.Instantiate(crate.gameObject, holder, true); ExactSurface(prop.transform);
                        PlaceGeometry(holder, new Vector3(i % 2 == 0 ? -7 : 7, 0, 12 + (i / 2) * 10));
                        holder.Rotate(Vector3.up,i*37,Space.World);
                    }
                    CopyCluster(sourceScene,next.transform,"Retained tower cluster",new Vector3(-11,0,36),"GEO-water_tower_","GEO-water_tank_","GEO-tower_cross_");
                    CopyCluster(sourceScene,next.transform,"Retained desert silhouette",new Vector3(-14,0,46),"GEO-saguaro_trunk.002","GEO-saguaro_arm.002");
                    if (region == 2) next.salvageVisual = CopyModule(motor.arc, next.salvage.position, next.transform, "Coil salvage assembly");
                    var light = new GameObject("Regional sunlight").AddComponent<Light>(); light.transform.SetParent(next.transform, false);
                    light.type = LightType.Directional; light.intensity = region == 3 ? .16f : 1.1f; light.color = region == 3 ? new Color(.38f,.5f,.8f) : new Color(1,.87f,.7f);
                    light.transform.rotation = Quaternion.Euler(45, -25, 0);
                    DressEnvironment(sourceScene,next); SetAtmosphere(scene,region);
                    Save(scene, RegionPaths[region - 1]);
                }
                AssetDatabase.SaveAssets();
                Debug.Log("JOURNEY_CANDIDATES_AUTHORED: NOT reviewed, NOT production-ready. Run JourneyContentChecks.CheckCandidateLayout and CheckProductionContent separately.");
            }
            finally
            {
                // In-memory source changes were saved exclusively to new paths.
                try { RestoreSceneSetup(previous); }
                finally
                {
                    if (!source.SequenceEqual(File.ReadAllBytes(SourcePath)) || !meta.SequenceEqual(File.ReadAllBytes(SourcePath + ".meta")))
                        throw new InvalidOperationException("Source preservation check failed.");
                    VerifyProtectedFiles(protectedFiles);
                }
            }
        }
        // One explicit CI command can author, inspect and render without importing any combat asset.
        public static void AuthorAndCaptureEnvironmentCandidates()
        { AuthorCandidateScenes(); JourneyContentChecks.CheckCandidateLayout(); CaptureEnvironmentCandidates(); }

        [Serializable] sealed class ImageRecord { public string region, view, path, sceneHash; public int width,height; public float minimum,maximum; }
        [Serializable] sealed class ImageReport { public string status="captured-environment-only-not-gameplay-acceptance"; public string graphicsDeviceType, graphicsDeviceName; public int bufferSceneTransitionsChecked; public bool captureBuffersReleased; public ImageRecord[] images; }
        public static void CaptureEnvironmentCandidates()
        {
            if (SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null) throw new InvalidOperationException("Actual GPU/software graphics device required; omit -nographics and use the runner virtual display.");
            var setup=EditorSceneManager.GetSceneManagerSetup();
            if (setup.Any(s=>s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty)) throw new InvalidOperationException("Save/discard scene edits before capture.");
            var protectedFiles=SnapshotProtectedFiles();
            var records=new List<ImageRecord>(); string output=Path.GetFullPath("JourneyEvidence/environment"); Directory.CreateDirectory(output);
            RenderTexture target=null; Texture2D pixels=null; var previousTarget=RenderTexture.active;
            int bufferChecks=0; bool buffersReleased=false;
            try
            {
                // OpenScene(Single) unloads unused native objects between regions.
                // Keep these explicit capture buffers alive, then destroy in finally.
                target=new RenderTexture(1440,900,24,RenderTextureFormat.ARGB32){antiAliasing=1,hideFlags=HideFlags.HideAndDontSave};
                if(!target.Create()) throw new InvalidOperationException("Failed to create screenshot render target.");
                pixels=new Texture2D(1440,900,TextureFormat.RGB24,false){hideFlags=HideFlags.HideAndDontSave};
                for(int i=0;i<3;i++)
                {
                    var boot=EditorSceneManager.OpenScene(BootstrapPath,OpenSceneMode.Single);
                    var env=EditorSceneManager.OpenScene(RegionPaths[i],OpenSceneMode.Additive);
                    if(!target || !target.IsCreated() || !pixels) throw new InvalidOperationException("Capture buffers were lost during scene loading.");
                    bufferChecks++;
                    SceneManager.SetActiveScene(env); var motor=Components<JourneyMotor>(boot).Single(); var b=Components<RegionBinding>(env).Single();
                    // EditMode capture: no Director.Begin, no enemy simulation, no fake combat acceptance.
                    motor.vehicle.SetPositionAndRotation(b.spawn.position,b.spawn.rotation);
                    var camera=motor.view; camera.enabled=false; camera.clearFlags=CameraClearFlags.Skybox;
                    camera.nearClipPlane=.04f; camera.farClipPlane=450; camera.allowHDR=true;
                    foreach(var particle in Components<ParticleSystem>(env)) particle.Simulate(7,true,true,true);
                    foreach(var key in new[]{"overview","ground","landmark","cabin"})
                    {
                        camera.fieldOfView=key=="cabin"?68:key=="overview"?54:58;
                        Vector3 at,look;
                        if(key=="overview") { at=new Vector3(31,39,-17);look=new Vector3(0,0,28); }
                        else if(key=="ground") { at=new Vector3(-5,1.65f,-7);look=new Vector3(2,2.2f,25); }
                        else if(key=="landmark") { var focus=i==0?b.salvage.position:b.powerPoint.position;at=focus+new Vector3(-7,2,-9);look=focus+Vector3.up; }
                        else { at=motor.vehicle.position+Vector3.forward*.55f+Vector3.up*2.38f;look=at-Vector3.forward*3-Vector3.up*.35f; }
                        camera.transform.position=at;camera.transform.LookAt(look);Physics.SyncTransforms();
                        var request=new UniversalRenderPipeline.SingleCameraRequest{destination=target};
                        if(!RenderPipeline.SupportsRenderRequest(camera,request)) throw new InvalidOperationException("Current render pipeline does not support actual URP screenshot capture.");
                        RenderPipeline.SubmitRenderRequest(camera,request); RenderTexture.active=target;
                        pixels.ReadPixels(new Rect(0,0,1440,900),0,0);pixels.Apply();
                        var colors=pixels.GetPixels32();float min=1,max=0;
                        for(int n=0;n<colors.Length;n+=97) { float value=(colors[n].r+colors[n].g+colors[n].b)/765f;min=Mathf.Min(min,value);max=Mathf.Max(max,value); }
                        if(max-min<.06f || max<.10f) throw new InvalidOperationException("Blank/near-black render rejected: "+env.name+"/"+key);
                        string file=Path.Combine(output,env.name+"-"+key+".png");File.WriteAllBytes(file,pixels.EncodeToPNG());
                        records.Add(new ImageRecord{region=env.name,view=key,path=file,width=1440,height=900,minimum=min,maximum=max,sceneHash=AssetDatabase.GetAssetDependencyHash(RegionPaths[i]).ToString()});
                        RenderTexture.active=previousTarget;
                    }
                }
            }
            finally
            {
                try
                {
                    RenderTexture.active=previousTarget;
                    try { if(pixels) Object.DestroyImmediate(pixels); }
                    finally
                    {
                        if(target) { try { target.Release(); } finally { Object.DestroyImmediate(target); } }
                    }
                    if(pixels || target) throw new InvalidOperationException("Capture buffers were not explicitly released.");
                    buffersReleased=true;
                }
                finally
                {
                    // Even failed buffer cleanup must restore scenes and verify all original bytes.
                    try { RestoreSceneSetup(setup); } finally { VerifyProtectedFiles(protectedFiles); }
                }
            }
            if(bufferChecks!=3 || !buffersReleased) throw new InvalidOperationException("Incomplete capture buffer lifecycle regression.");
            File.WriteAllText(Path.Combine(output,"capture-report.json"),JsonUtility.ToJson(new ImageReport{graphicsDeviceType=SystemInfo.graphicsDeviceType.ToString(),graphicsDeviceName=SystemInfo.graphicsDeviceName,bufferSceneTransitionsChecked=bufferChecks,captureBuffersReleased=buffersReleased,images=records.ToArray()},true));
        }
        // A cold batch Editor can have zero loaded scenes. Unity rejects restoring
        // that snapshot (and snapshots of an unnamed scene). Restore a disposable
        // empty in-memory scene instead; never write a fallback asset or settings.
        internal static void RestoreSceneSetup(SceneSetup[] setup)
        {
            bool restorable = setup != null && setup.Any(s => s.isLoaded && s.isActive) &&
                setup.All(s => !s.isLoaded || !string.IsNullOrEmpty(s.path));
            if (restorable) EditorSceneManager.RestoreSceneManagerSetup(setup);
            else EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        }
        static Dictionary<string,string> SnapshotProtectedFiles()
        {
            var result=new Dictionary<string,string>();
            foreach(string folder in new[]{"Assets","ProjectSettings","Packages"})
                if(Directory.Exists(folder)) foreach(string path in Directory.GetFiles(folder,"*",SearchOption.AllDirectories))
                { string p=path.Replace('\\','/');if(!p.StartsWith(Folder+"/",StringComparison.Ordinal)&&p!=Folder+".meta") result[p]=HashFile(p); }
            return result;
        }
        static string HashFile(string path)
        { using(var sha=SHA256.Create()) using(var file=File.OpenRead(path)) return BitConverter.ToString(sha.ComputeHash(file)).Replace("-","").ToLowerInvariant(); }
        static void VerifyProtectedFiles(Dictionary<string,string> before)
        {
            var after=SnapshotProtectedFiles();
            var changed=before.Keys.Union(after.Keys).Where(p=>!before.ContainsKey(p)||!after.ContainsKey(p)||before[p]!=after[p]).ToArray();
            Directory.CreateDirectory("JourneyEvidence");
            File.WriteAllLines("JourneyEvidence/protected-source-sha256.txt",before.OrderBy(x=>x.Key).Select(x=>x.Value+"  "+x.Key));
            if(changed.Length>0) throw new InvalidOperationException("Protected source/settings were changed outside new Journey folder: "+string.Join(", ",changed));
        }
        static void SetAtmosphere(Scene scene,int region)
        {
            SceneManager.SetActiveScene(scene);
            Color sky=region==1?new Color(.52f,.66f,.75f):region==2?new Color(.66f,.55f,.38f):new Color(.10f,.17f,.32f);
            Color horizon=region==1?new Color(.76f,.48f,.27f):region==2?new Color(.64f,.47f,.29f):new Color(.18f,.24f,.36f);
            var shader=Shader.Find("Skybox/Procedural"); if(!shader) throw new InvalidOperationException("Procedural sky shader missing.");
            var skybox=new Material(shader);skybox.SetColor("_SkyTint",sky);skybox.SetColor("_GroundColor",horizon);
            skybox.SetFloat("_AtmosphereThickness",region==2?1.7f:1.05f);skybox.SetFloat("_Exposure",region==3?.55f:1.05f);skybox.SetFloat("_SunSize",.035f);
            AssetDatabase.CreateAsset(skybox,Folder+"/Region-"+region+"-Sky.mat");RenderSettings.skybox=skybox;
            RenderSettings.ambientMode=AmbientMode.Trilight;RenderSettings.ambientSkyColor=region==3?new Color(.25f,.34f,.5f):sky;
            RenderSettings.ambientEquatorColor=region==3?new Color(.20f,.25f,.35f):horizon*.72f;
            RenderSettings.ambientGroundColor=region==3?new Color(.14f,.17f,.22f):new Color(.29f,.23f,.17f);
            RenderSettings.fog=true;RenderSettings.fogMode=FogMode.Linear;RenderSettings.fogColor=horizon;
            RenderSettings.fogStartDistance=region==2?30:65;RenderSettings.fogEndDistance=region==2?145:280;
            foreach(var light in Components<Light>(scene).Where(x=>x.type==LightType.Directional))
            {light.transform.rotation=Quaternion.Euler(region==3?35:18,-38,0);light.color=region==3?new Color(.55f,.68f,1):new Color(1,.72f,.43f);light.intensity=region==3?.62f:region==2?1.05f:1.4f;light.shadows=LightShadows.Soft;RenderSettings.sun=light;}
        }
        static void DressEnvironment(Scene source,RegionBinding b)
        {
            // Reuse material/mesh assets without editing or duplicating the accepted RV or its materials.
            var sand=AssetDatabase.LoadAssetAtPath<Material>("Assets/DesertRV/Art/Materials/LayeredSand.mat");
            if(!sand) throw new InvalidOperationException("Retained layered sand material missing.");
            var foundation=b.transform.Find("Route foundation");foundation.GetComponent<Renderer>().sharedMaterial=sand;
            foundation.localScale=new Vector3(250,.4f,320);foundation.position=new Vector3(0,-.24f,70);
            var asphalt=SourceGeometry(source).Single(t=>t.name=="GEO-asphalt_road").GetComponent<Renderer>().sharedMaterial;
            for(int i=0;i<9;i++)
            {
                var slab=Solid("Broken road segment "+i,b.transform,new Vector3((i%3-1)*.22f,-.015f,-8+i*9),new Vector3(7.6f,.10f,8.4f),Color.gray);
                slab.GetComponent<Renderer>().sharedMaterial=asphalt;slab.transform.Rotate(0,(i%3-1)*1.7f,0);
                // Existing authored marks/props frame the clear centre driving lane; shoulders remain walkable.
                if(i%2==0) CopyCluster(source,b.transform,"Roadside drum "+i,new Vector3(i%4==0?-5.4f:5.4f,0,-4+i*9),"GEO-workshop_drum.001");
            }
            for(int i=0;i<7;i++)
            {
                CopyCluster(source,b.transform,"Middle-distance mesas "+i,new Vector3(i%2==0?-48-i*5:45+i*4,0,5+i*22),"GEO-weathered_mesa."+(i%7+1).ToString("000"));
            }
            for(int i=0;i<3;i++)
            {
                string name="Far horizon ridge "+i;
                CopyCluster(source,b.transform,name,new Vector3(i%2==0?-92:95,-2,100+i*45),"GEO-weathered_mesa."+(i+3).ToString("000"));
                b.transform.Find(name).localScale=new Vector3(1.65f,1.2f,1.65f);
            }
            for(int i=0;i<6;i++)
                CopyCluster(source,b.transform,"Near agave cluster "+i,new Vector3(i%2==0?-11.5f:12,0,8+i*10),Enumerable.Range(1,18).Select(n=>"GEO-agave_leaf."+n.ToString("000")).ToArray());
            for(int i=0;i<10;i++)
                CopyCluster(source,b.transform,"Desert shoulder plants "+i,new Vector3(i%2==0?-14-i%3*2:15+i%3*3,0,4+i*7),"GEO-saguaro_trunk.002","GEO-saguaro_arm.002");
            for(int i=0;i<4;i++)
            {
                var lamp=new GameObject("Route/service amber lamp "+i).AddComponent<Light>();lamp.transform.SetParent(b.transform,false);
                lamp.transform.position=new Vector3(i%2==0?-5.8f:5.8f,2.4f,12+i*15);lamp.type=LightType.Point;lamp.range=10;lamp.intensity=b.region==3?2.4f:.35f;lamp.color=new Color(1,.57f,.22f);
            }
        }
        static Transform viewerBench(Scene scene) => Components<Transform>(scene).Single(t => t.name == "GEO-garage_workbench_top");
        static void MoveUnder(Transform obj, Transform parent, Scene scene)
        { obj.SetParent(null, true); SceneManager.MoveGameObjectToScene(obj.gameObject, scene); obj.SetParent(parent, true); }
        static RegionBinding NewBinding(Scene scene, int region)
        {
            var root = new GameObject("Region " + region + " environment"); SceneManager.MoveGameObjectToScene(root, scene);
            var b = root.AddComponent<RegionBinding>(); b.region = region; b.regionOffset = RegionOffsets[region - 1]; b.progressDirection = Vector3.forward;
            b.spawn = Point("Vehicle spawn", root.transform, Vector3.zero);
            b.spawn.rotation = Quaternion.identity; // caller copies the retained RV rotation (localForward need not be +Z)
            b.exit = Point("Vehicle exit", root.transform, new Vector3(0,0,64));
            b.exitVolume = Volume("Exit volume", root.transform, new Vector3(0,2,64), new Vector3(10,6,8));
            b.pickupId = region == 1 ? "first-station/ram" : "scrapyard/coil";
            b.environmentVerified = b.combatAssetsVerified = false;
            return b;
        }
        static void PopulateLayout(RegionBinding b, JourneyContentManifest manifest)
        {
            Solid("Route foundation", b.transform, new Vector3(0,-.24f,30), new Vector3(34,.4f,94), new Color(.46f,.37f,.25f));
            // Gaps and staggered cover create short on-foot loops beside a vehicle-clear centre lane.
            for (int i = 0; i < 6; i++)
                Solid("Cover " + i, b.transform, new Vector3(i % 2 == 0 ? -9 : 9,.7f,10+i*7), new Vector3(3.4f,1.4f,2.2f), new Color(.34f,.29f,.23f));
            if (b.region == 1)
                b.ramGate = Solid("Ram breakaway road gate", b.transform, new Vector3(0,1.1f,51), new Vector3(20,2.2f,.7f), new Color(.52f,.27f,.12f));
            else
            {
                var power = Solid(b.region == 3 ? "Beacon power cabinet" : "Scrapyard power cabinet", b.transform, new Vector3(6,.65f,23), new Vector3(1.1f,1.3f,.8f), new Color(.21f,.31f,.33f));
                b.powerSurface = power; b.powerPoint = Point("Power interaction", b.transform, power.bounds.center + Vector3.back * .45f);
                b.chargeSeconds = b.region == 3 ? 36 : 28;
                if (b.region == 2)
                {
                    b.salvageSurface = Solid("Coil salvage bench", b.transform, new Vector3(8,.45f,30), new Vector3(2,.9f,1), new Color(.42f,.3f,.19f));
                    b.salvage = Point("Coil interaction", b.transform, b.salvageSurface.bounds.center + Vector3.up * .65f);
                }
                else
                {
                    b.safeZone = Volume("Beacon safe zone", b.transform, new Vector3(0,2,62), new Vector3(12,6,12));
                    Solid("Beacon mast", b.transform, new Vector3(-8,4,30), new Vector3(.5f,8,.5f), new Color(.25f,.3f,.34f));
                    var beacon = new GameObject("Beacon lantern").AddComponent<Light>(); beacon.transform.SetParent(b.transform, false);
                    beacon.transform.position = new Vector3(-8,7.5f,30); beacon.type = LightType.Point; beacon.range = 22; beacon.intensity = 3; beacon.color = new Color(.3f,.8f,1);
                }
            }
            // Only real supplied prefabs are instantiated. Missing art leaves explicit empty arrays and a failing production gate.
            b.guards = b.region == 1 ? Spawn(manifest.pouncer, b, new[] { new Vector3(-6,0,18),new Vector3(6,0,24) }) : Array.Empty<BeastActor>();
            b.roadBeasts = b.region == 1 ? Spawn(manifest.armored, b, new[] { new Vector3(0,0,39) }) : Array.Empty<BeastActor>();
            b.waves = b.region == 1 ? Array.Empty<RegionWave>() : new[] {
                new RegionWave { enemies = Spawn(manifest.pouncer, b, new[] { new Vector3(-7,0,33), new Vector3(7,0,39) }) },
                new RegionWave { enemies = Spawn(manifest.armored, b, new[] { new Vector3(-5,0,43) }) }
            };
        }
        static BeastActor[] Spawn(JourneyAssetReview review, RegionBinding binding, Vector3[] at)
        {
            if (review == null || !review.prefab || !review.prefab.GetComponent<BeastActor>()) return Array.Empty<BeastActor>();
            return at.Select(position => { var go = (GameObject)PrefabUtility.InstantiatePrefab(review.prefab, binding.transform); go.transform.position = position; return go.GetComponent<BeastActor>(); }).ToArray();
        }
        static GameObject CopyModule(GameObject original, Vector3 position, Transform parent, string name)
        { var holder=new GameObject(name).transform; holder.SetParent(parent,false); var copy=Object.Instantiate(original,holder,true); copy.SetActive(true); PlaceGeometry(holder,Vector3.zero); holder.localScale=Vector3.one*.18f; holder.position=position; foreach(var c in holder.GetComponentsInChildren<Collider>()) Object.DestroyImmediate(c); return holder.gameObject; }
        static Transform[] SourceGeometry(Scene scene) => scene.GetRootGameObjects().Single(r=>r.name=="Station visual candidate").GetComponentsInChildren<Transform>(true);
        static void CopyCluster(Scene source,Transform parent,string name,Vector3 at,params string[] prefixes)
        {
            var holder=new GameObject(name).transform; holder.SetParent(parent,false);
            foreach(var part in SourceGeometry(source).Where(t=>prefixes.Any(p=>t.name.StartsWith(p,StringComparison.Ordinal))))
                Object.Instantiate(part.gameObject,holder,true);
            PlaceGeometry(holder,at);
        }
        static void PlaceGeometry(Transform root,Vector3 at)
        {
            var renderers=root.GetComponentsInChildren<Renderer>(true);
            if(renderers.Length==0) throw new InvalidOperationException("Retained scenery cluster has no visible geometry: "+root.name);
            Bounds bounds=renderers[0].bounds; foreach(var renderer in renderers.Skip(1)) bounds.Encapsulate(renderer.bounds);
            root.position += at-new Vector3(bounds.center.x,bounds.min.y,bounds.center.z);
            // Root becomes a local pivot at the requested anchor while all child world transforms stay fixed.
            var children=root.Cast<Transform>().ToArray(); foreach(var child in children) child.SetParent(root.parent,true);
            root.position=at; foreach(var child in children) child.SetParent(root,true);
        }
        static Collider ExactSurface(Transform t)
        { var collider = t.GetComponent<Collider>(); if (collider) return collider; var mesh = t.GetComponent<MeshFilter>(); if (!mesh || !mesh.sharedMesh) throw new InvalidOperationException("Missing exact interaction mesh: " + t.name); var box = t.gameObject.AddComponent<BoxCollider>(); box.center = mesh.sharedMesh.bounds.center; box.size = mesh.sharedMesh.bounds.size; return box; }
        static Collider Solid(string name, Transform parent, Vector3 at, Vector3 size, Color color)
        { var go = GameObject.CreatePrimitive(PrimitiveType.Cube); go.name = name; go.transform.SetParent(parent,false); go.transform.position = at; go.transform.localScale = size; var path = Folder + "/Layout-" + ColorUtility.ToHtmlStringRGB(color) + ".mat"; var material = AssetDatabase.LoadAssetAtPath<Material>(path); if (!material) { material = new Material(Shader.Find("Universal Render Pipeline/Lit")); material.color = color; AssetDatabase.CreateAsset(material,path); } go.GetComponent<Renderer>().sharedMaterial = material; return go.GetComponent<Collider>(); }
        static Collider Volume(string name, Transform parent, Vector3 at, Vector3 size)
        { var go = new GameObject(name); go.transform.SetParent(parent,false); go.transform.position = at; var c = go.AddComponent<BoxCollider>(); c.size = size; c.isTrigger = true; return c; }
        static Transform Point(string name, Transform parent, Vector3 at)
        { var t = new GameObject(name).transform; t.SetParent(parent,true); t.position = at; return t; }
        static AudioClip Audio(string name) => AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/DesertRV/Audio/" + name + ".wav");
        static T[] Components<T>(Scene scene) where T : Component => scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<T>(true)).ToArray();
        static void Save(Scene scene, string path) { if (!EditorSceneManager.SaveScene(scene,path)) throw new IOException("Failed to save " + path); }
    }
}

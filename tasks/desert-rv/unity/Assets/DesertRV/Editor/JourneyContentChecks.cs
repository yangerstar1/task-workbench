using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Reflection;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV.Editor
{
    public static class JourneyContentChecks
    {
        internal static string ValidatedBuildFingerprint;
        public static readonly string[] EnemyStates = { "Idle", "Walk", "Windup", "Attack", "Recover", "Hit", "Death" };
        [Serializable] public sealed class Report { public string mode; public bool passed; public string[] failures; public string[] sceneDependencyHashes; }
        public static void CheckCandidateLayout() => Run(false);
        public static void CheckProductionContent() => Run(true);
        static void Run(bool production)
        {
            var errors = Inspect(production);
            Directory.CreateDirectory("JourneyEvidence");
            var report = new Report { mode = production ? "production-content" : "candidate-layout-only-not-gameplay-approval", passed = errors.Count == 0,
                failures = errors.ToArray(), sceneDependencyHashes = new[] { JourneySceneAuthoring.BootstrapPath }.Concat(JourneySceneAuthoring.RegionPaths).Select(p => File.Exists(p) ? AssetDatabase.GetAssetDependencyHash(p).ToString() : "MISSING:" + p).ToArray() };
            File.WriteAllText("JourneyEvidence/" + (production ? "production-content" : "candidate-layout") + ".json", JsonUtility.ToJson(report,true));
            if (production) ValidatedBuildFingerprint = errors.Count == 0 ? BuildFingerprint() : null;
            if (errors.Count != 0) throw new BuildFailedException(string.Join("\n",errors));
            Debug.Log(production ? "JOURNEY_PRODUCTION_CONTENT_PASS (does not replace playthrough/device acceptance)" : "JOURNEY_CANDIDATE_LAYOUT_PASS (unreviewed combat and visual assets may still block production)");
        }
        public static List<string> Inspect(bool production)
        {
            var errors = new List<string>();
            var manifest = AssetDatabase.LoadAssetAtPath<JourneyContentManifest>(JourneySceneAuthoring.ManifestPath);
            if (production) ValidateManifest(manifest, errors);
            var setup = EditorSceneManager.GetSceneManagerSetup();
            if (setup.Any(s => s.isLoaded && SceneManager.GetSceneByPath(s.path).isDirty))
            { errors.Add("Save open scene edits before content inspection; refusing to discard them."); return errors; }
            try
            {
                if (!File.Exists(JourneySceneAuthoring.BootstrapPath)) errors.Add("Missing saved JourneyBootstrap scene. Run explicit candidate authoring in Actions.");
                else
                {
                    var scene = EditorSceneManager.OpenScene(JourneySceneAuthoring.BootstrapPath,OpenSceneMode.Single);
                    var directors = All<JourneyDirector>(scene); var sessions = All<JourneySession>(scene); var motors = All<JourneyMotor>(scene);
                    Require(directors.Length == 1 && sessions.Length == 1 && motors.Length == 1, "Bootstrap requires exactly one Director/Session/Motor.",errors);
                    Require(All<FirstStationJourney>(scene).Length == 0 && All<BodyViewer>(scene).Length == 0, "Bootstrap contains legacy simulation/viewer ownership.",errors);
                    Require(All<RegionBinding>(scene).Length == 0, "Bootstrap must not own regional environment state.",errors);
                    if (directors.Length == 1) ValidateBootstrap(directors[0], manifest, production, errors);
                    if (production && manifest) ReviewScene(JourneySceneAuthoring.BootstrapPath,manifest.bootstrapDependencyHash,manifest.bootstrapEvidence,errors);
                }
                double lastExit = double.NegativeInfinity;
                var pickupIds = new HashSet<string>();
                for (int i=0;i<3;i++)
                {
                    string path = JourneySceneAuthoring.RegionPaths[i];
                    if (!File.Exists(path)) { errors.Add("Missing saved regional scene: " + path); continue; }
                    var scene = EditorSceneManager.OpenScene(path,OpenSceneMode.Single);
                    var bindings = All<RegionBinding>(scene);
                    Require(bindings.Length == 1, path + ": exactly one RegionBinding required.",errors);
                    Require(All<JourneySession>(scene).Length == 0 && All<JourneyMotor>(scene).Length == 0 && All<JourneyDirector>(scene).Length == 0 && All<JourneyHud>(scene).Length == 0,
                        path + ": regional scene duplicates persistent objects.",errors);
                    Require(All<Camera>(scene).Length == 0 && All<AudioListener>(scene).Length == 0,path + ": regional scene duplicates persistent camera/audio listener.",errors);
                    if (bindings.Length != 1) continue;
                    var b = bindings[0]; string label = path + ": ";
                    Require(b.region == i+1,label+"wrong region ID.",errors);
                    Require(b.progressDirection == Vector3.forward && b.regionOffset == JourneySceneAuthoring.RegionOffsets[i],label+"fixed +Z/offset contract changed.",errors);
                    Require(b.spawn && b.exit && b.exitVolume,label+"missing spawn/exit.",errors);
                    if (b.spawn && b.exit)
                    {
                        Require(b.regionOffset >= lastExit,label+"world progress reverses across transition.",errors);
                        float distance = Vector3.Distance(b.spawn.position,b.exit.position);
                        Require(distance >= 30 && distance <= 100,label+"route must be a compact encounter loop, not empty driving padding.",errors);
                        lastExit = b.WorldProgress(b.exit.position) + (b.exitVolume ? b.exitVolume.bounds.extents.z : 0);
                        Require(b.exitVolume && b.exitVolume.isTrigger && RegionBinding.Contains(b.exitVolume,b.exit.position + Vector3.up),label+"exit marker must lie inside active trigger.",errors);
                    }
                    Require(All<Renderer>(scene).Length >= 8,label+"missing visible environment/cover.",errors);
                    if (i<2) Require(b.salvage && b.salvageSurface && b.salvageVisual && !string.IsNullOrWhiteSpace(b.pickupId) && pickupIds.Add(b.pickupId),label+"missing/duplicate real salvage binding.",errors);
                    if (i==0) Require(b.ramGate && !b.ramGate.isTrigger,label+"ram requires physical blocking collider.",errors);
                    if (i>0) Require(b.powerPoint && b.powerSurface && !b.powerSurface.isTrigger,label+"power requires exact physical interaction surface.",errors);
                    if (i==2) Require(b.safeZone && b.safeZone.isTrigger,label+"final safe zone must be a trigger.",errors);
                    if (production)
                    {
                        Require(b.Validate(out string reason),label+reason,errors);
                        Require(b.AllEnemies().Any(),label+"empty enemy list cannot pass production.",errors);
                        Require(All<BeastActor>(scene).Length == b.AllEnemies().Distinct().Count(),label+"unbound or duplicate scene enemies.",errors);
                        foreach (var actor in b.AllEnemies()) ValidateSceneEnemy(actor,manifest,errors);
                        if (manifest) ReviewScene(path,At(manifest.environmentDependencyHashes,i),At(manifest.environmentEvidence,i),errors);
                    }
                }
            }
            finally { JourneySceneAuthoring.RestoreSceneSetup(setup); }
            return errors;
        }
        public static void ValidateManifest(JourneyContentManifest m, List<string> errors)
        {
            if (!m) { errors.Add("Missing JourneyContent manifest and visual/action approvals."); return; }
            ValidateAsset(m.pouncer,"Pouncer",true,false,errors);
            ValidateAsset(m.armored,"Armored",true,true,errors);
            ValidateAsset(m.weapon,"Weapon viewmodel",false,false,errors);
            Require(m.pouncer != null && m.armored != null && m.pouncer.prefab != m.armored.prefab,"Armored must be an independent prefab, not the Pouncer reference.",errors);
            if (m.pouncer?.prefab && m.armored?.prefab)
            {
                var a = Meshes(m.pouncer.prefab); var b = Meshes(m.armored.prefab);
                Require(b.Except(a).Any(),"Armored requires distinct geometry, not a recolored Pouncer.",errors);
            }
            Require(m.weaponPresentation && m.arcPresentation && m.armoredWeakpointPresentation,"Missing implemented weapon, arc or armored weakpoint presentation components.",errors);
            Require(!string.IsNullOrWhiteSpace(m.combatIntegrationEvidence),"Missing reviewed weapon/arc/weakpoint in-game action evidence.",errors);
            if (m.armoredWeakpointPresentation && m.armored?.prefab)
            {
                Require(m.armoredWeakpointPresentation.transform.IsChildOf(m.armored.prefab.transform),"Weakpoint presenter must belong to the independent armored prefab.",errors);
                Require(References(m.armoredWeakpointPresentation,m.armored.prefab.GetComponent<BeastActor>()) && ReferencesType<Renderer>(m.armoredWeakpointPresentation),"Weakpoint presenter requires actual actor and visible renderer references.",errors);
                ValidatePresenter(m.armoredWeakpointPresentation,"Armored prefab weakpoint",errors);
            }
        }
        static void ValidateAsset(JourneyAssetReview review, string label, bool enemy, bool armored, List<string> errors)
        {
            if (review == null || !review.prefab) { errors.Add(label+": real prefab missing."); return; }
            var go = review.prefab; string path = AssetDatabase.GetAssetPath(go);
            Require(PrefabUtility.IsPartOfPrefabAsset(go),label+": must reference a persistent prefab asset.",errors);
            Require(review.accepted && !string.IsNullOrWhiteSpace(review.visualEvidence) && !string.IsNullOrWhiteSpace(review.motionEvidence),label+": visual and motion acceptance missing.",errors);
            Require(!string.IsNullOrWhiteSpace(review.dependencyHash) && review.dependencyHash == AssetDatabase.GetAssetDependencyHash(path).ToString(),label+": asset changed or approved dependency hash missing.",errors);
            Require(Meshes(go).Any() && go.GetComponentsInChildren<Renderer>(true).Any(r => r.enabled),label+": visible model missing.",errors);
            Require(go.GetComponentsInChildren<Renderer>(true).All(r => r.sharedMaterials.Length > 0 && r.sharedMaterials.All(mat => mat && mat.shader && !string.IsNullOrEmpty(AssetDatabase.GetAssetPath(mat)))),label+": missing persistent material/shader bindings.",errors);
            string modelPath = review.sourceModel ? AssetDatabase.GetAssetPath(review.sourceModel) : "";
            Require(modelPath.EndsWith(".fbx",StringComparison.OrdinalIgnoreCase) && AssetDatabase.GetDependencies(path,true).Contains(modelPath),label+": source FBX must exist and be an actual prefab dependency.",errors);
            Require(!string.IsNullOrWhiteSpace(review.reviewedDependencySha256) && review.reviewedDependencySha256 == DependencySha256(path),label+": exact reviewed dependency SHA256 missing or stale.",errors);
            Require(Uri.TryCreate(review.generationRunUrl,UriKind.Absolute,out var run) && run.Scheme == "https" && run.Host == "github.com" && run.AbsolutePath.Contains("/actions/runs/"),label+": exact generation Actions run URL missing.",errors);
            if (!enemy)
            {
                var viewAnimator=go.GetComponentInChildren<Animator>(true);
                ValidateWeaponAnimation(viewAnimator ? viewAnimator.runtimeAnimatorController as AnimatorController : null,label,errors);
                return;
            }
            var actor = go.GetComponent<BeastActor>(); Require(actor && actor.armored == armored,label+": wrong or missing actor identity.",errors);
            var collider = go.GetComponent<Collider>(); Require(collider && collider.enabled && !collider.isTrigger,label+": enabled physical root collider required.",errors);
            if (collider)
            {
                Vector3 size = collider is CapsuleCollider cap ? new Vector3(cap.radius*2,cap.height,cap.radius*2) : collider is BoxCollider box ? box.size : Vector3.zero;
                size = Vector3.Scale(size,go.transform.lossyScale);
                Require(size.x >= .3f && size.x <= 3 && size.y >= .4f && size.y <= 4 && size.z >= .3f && size.z <= 4,label+": unverified/unsupported collider dimensions.",errors);
            }
            var animator = actor ? actor.animator : null;
            var controller = animator ? animator.runtimeAnimatorController as AnimatorController : null;
            Require(controller,label+": real AnimatorController missing (override requires explicit review support).",errors);
            if (controller)
            {
                var states = controller.layers.SelectMany(l => States(l.stateMachine)).ToArray();
                foreach (string name in EnemyStates)
                    Require(states.Any(s => s.name == name && s.motion && HasMotion(s.motion)),label+": missing animated state " + name,errors);
            }
        }
        // Deterministic byte-level digest over sorted project dependencies, including their meta GUIDs.
        public static string DependencySha256(string path)
        {
            var trace=CandidateDependencyTrace.Begin(path);
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path)) {trace?.Finish("");return "";}
            using (var stream = new MemoryStream())
            {
                var dependencyPaths=AssetDatabase.GetDependencies(path,true).OrderBy(x=>x,StringComparer.Ordinal).ToArray();
                trace?.DependencyCount(dependencyPaths.Length);
                foreach (string dependency in dependencyPaths)
                    foreach (string file in new[] { dependency,dependency+".meta" })
                    {
                        if (!File.Exists(file)) {trace?.Record(file,false,null);continue;}
                        byte[] name = Encoding.UTF8.GetBytes(file.Replace('\\','/')), bytes = File.ReadAllBytes(file);
                        trace?.Record(file,true,bytes);
                        byte[] nameLength = Encoding.ASCII.GetBytes(name.Length+":"), length = Encoding.ASCII.GetBytes(bytes.LongLength+":");
                        stream.Write(nameLength,0,nameLength.Length); stream.Write(name,0,name.Length);
                        stream.Write(length,0,length.Length); stream.Write(bytes,0,bytes.Length);
                    }
                using (var sha = SHA256.Create()) {string digest=BitConverter.ToString(sha.ComputeHash(stream.ToArray())).Replace("-","").ToLowerInvariant();trace?.Finish(digest);return digest;}
            }
        }
        static bool HasMotion(Motion motion)
        {
            if (motion is AnimationClip clip) return clip.length > 0 && (AnimationUtility.GetCurveBindings(clip).Length > 0 || AnimationUtility.GetObjectReferenceCurveBindings(clip).Length > 0);
            return motion is BlendTree tree && tree.children.Length > 0 && tree.children.All(c => c.motion && HasMotion(c.motion));
        }
        static IEnumerable<AnimatorState> States(AnimatorStateMachine sm)
        { foreach (var state in sm.states) yield return state.state; foreach (var child in sm.stateMachines) foreach (var state in States(child.stateMachine)) yield return state; }
        static IEnumerable<Mesh> Meshes(GameObject go) => go.GetComponentsInChildren<MeshFilter>(true).Select(x=>x.sharedMesh).Concat(go.GetComponentsInChildren<SkinnedMeshRenderer>(true).Select(x=>x.sharedMesh)).Where(x=>x);
        static void ValidateBootstrap(JourneyDirector d, JourneyContentManifest m, bool production, List<string> errors)
        {
            Require(!d.transform.parent && d.journey && d.motor && d.actions && d.loader && d.hud,"Director persistent-root references missing.",errors);
            if (!d.motor || !d.actions || !d.loader || !d.hud) return;
            var motor = d.motor; var a = d.actions;
            Require(motor.vehicle && motor.view && motor.ram && motor.arc && motor.entryStep && motor.doorHinge,"Retained RV/camera/two upgrades/entry bindings missing.",errors);
            foreach (var c in new Component[] { d.journey,motor,a,d.loader,d.hud,motor.vehicle,motor.view }) Require(c && c.transform.IsChildOf(d.transform),"Persistent dependency lies outside JourneyBootstrap.",errors);
            Require(d.hud.director == d && !d.hud.station && a.motor == motor && a.journey == d.journey && motor.journey == d.journey,"Runtime ownership links disagree.",errors);
            Require(a.cabinWorkbench && a.workbenchSurface && motor.vehicle && a.cabinWorkbench.IsChildOf(motor.vehicle) && a.workbenchSurface.transform.IsChildOf(motor.vehicle),"Exact cabin workbench surface must travel with RV.",errors);
            Require(d.loader.regionScenes != null && d.loader.regionScenes.SequenceEqual(JourneySceneAuthoring.RegionPaths.Select(Path.GetFileNameWithoutExtension)),"Loader scene names/order mismatch.",errors);
            Require(d.hud.font,"Missing licensed Chinese HUD font.",errors);
            if (!production) return;
            foreach (var clip in new[] { a.shotSound,a.hitSound,a.reloadSound,a.pickupSound,a.upgradeSound,a.windSound }) Require(clip && clip.length > 0,"Missing/nonplayable shot, hit, reload, pickup, upgrade or wind audio.",errors);
            if (!m) return;
            var scripts = d.GetComponentsInChildren<MonoBehaviour>(true);
            var weapons=scripts.Where(s=>s && m.weaponPresentation && s.GetType()==m.weaponPresentation.GetType()).ToArray();
            var arcs=scripts.Where(s=>s && m.arcPresentation && s.GetType()==m.arcPresentation.GetType()).ToArray();
            Require(weapons.Length==1 && m.weapon?.prefab && References(weapons[0],a) && ReferencesType<Renderer>(weapons[0]),"Exactly one weapon presenter must be wired to live actions and visible viewmodel.",errors);
            Require(arcs.Length==1 && References(arcs[0],a) && motor.arc && References(arcs[0],motor.arc.transform) && ReferencesType<AudioClip>(arcs[0]),"Exactly one arc presenter must be wired to live actions, retained arc module Transform and real audio.",errors);
            foreach(var presenter in weapons.Concat(arcs)) ValidatePresenter(presenter,"Bootstrap "+presenter.GetType().Name,errors);
            foreach(var weapon in weapons.OfType<WeaponPresentation>()) ValidateReloadMeshContract(weapon,errors);
            if(motor.view && m.weapon?.prefab)
            {
                var instance=motor.view.GetComponentsInChildren<Transform>(true).FirstOrDefault(t=>PrefabUtility.GetCorrespondingObjectFromSource(t.gameObject)==m.weapon.prefab);
                var animator=instance?instance.GetComponentInChildren<Animator>(true):null;
                ValidateWeaponAnimation(animator?animator.runtimeAnimatorController as AnimatorController:null,"Live weapon instance",errors);
                Require(instance && new HashSet<Mesh>(Meshes(m.weapon.prefab)).SetEquals(Meshes(instance.gameObject)),"Live weapon geometry must match the reviewed prefab.",errors);
            }
            if (motor.view && m.weapon?.prefab) Require(motor.view.GetComponentsInChildren<Transform>(true).Any(t => PrefabUtility.GetCorrespondingObjectFromSource(t.gameObject) == m.weapon.prefab),"Real weapon prefab must be instantiated beneath the persistent camera.",errors);
        }
        static void ValidateSceneEnemy(BeastActor actor, JourneyContentManifest m, List<string> errors)
        {
            var expected = actor.armored ? m?.armored?.prefab : m?.pouncer?.prefab;
            Require(expected && PrefabUtility.GetCorrespondingObjectFromSource(actor.gameObject) == expected,"Scene enemy is not the matching reviewed prefab instance: "+actor.name,errors);
            if (!expected) return;
            var original = expected.GetComponent<BeastActor>();
            Require(original && actor.animator && original.animator && actor.animator.runtimeAnimatorController == original.animator.runtimeAnimatorController,"Scene enemy overrides/misses reviewed Animator: "+actor.name,errors);
            Require(new HashSet<Mesh>(Meshes(expected)).SetEquals(Meshes(actor.gameObject)),"Scene enemy geometry differs from reviewed prefab: "+actor.name,errors);
            var collider = actor.GetComponent<Collider>();
            Require(collider && collider.enabled && !collider.isTrigger,"Scene enemy physical root collider missing/disabled: "+actor.name,errors);
            if(actor.armored && m.armoredWeakpointPresentation)
            {
                var presenters=actor.GetComponentsInChildren<MonoBehaviour>(true).Where(s=>s && s.GetType()==m.armoredWeakpointPresentation.GetType()).ToArray();
                Require(presenters.Length==1,"Scene armored actor requires exactly one real weakpoint presenter: "+actor.name,errors);
                foreach(var presenter in presenters) ValidatePresenter(presenter,"Scene armored weakpoint "+actor.name,errors);
            }
        }
        static void ValidateWeaponAnimation(AnimatorController controller,string label,List<string> errors)
        {
            if(!controller || controller.layers.Length==0 || controller.layers[0].name!="Base Layer")
            { errors.Add(label+": weapon requires real Base Layer controller.");return; }
            // Runtime resolves full paths, so similarly named nested states do not satisfy the contract.
            var states=controller.layers[0].stateMachine.states.Select(s=>s.state).ToArray();
            foreach(string state in new[]{"Idle","Fire","Reload"})
            {
                var matches=states.Where(s=>s.name==state).ToArray();
                Require(matches.Length==1 && matches[0].motion && HasMotion(matches[0].motion),label+": missing/duplicate animated Base Layer."+state,errors);
                if(matches.Length!=1) continue;
                var clip=matches[0].motion as AnimationClip;
                if(!clip) { errors.Add(label+": timed weapon "+state+" requires a direct AnimationClip.");continue; }
                Require(AnimationUtility.GetAnimationEvents(clip).Length==0,label+": AnimationEvents forbidden on weapon "+state+"; actions own ammo/damage/audio.",errors);
                bool validRate=clip.frameRate>0 && !float.IsNaN(clip.frameRate) && !float.IsInfinity(clip.frameRate);
                Require(validRate,label+": invalid weapon clip frame rate for "+state,errors);
                float duration=state=="Fire"?.22f:state=="Reload"?1.65f:2f;
                float tolerance=validRate?1f/clip.frameRate:.0001f;
                if(state=="Idle") tolerance=Mathf.Max(.1f,tolerance);
                Require(Mathf.Abs(clip.length-duration)<=tolerance+.0001f,label+": "+state+" clip length does not match authoritative presentation duration.",errors);
                Require(state=="Idle"?clip.isLooping:!clip.isLooping,label+": only Idle may loop; Fire/Reload must be one-shot.",errors);
            }
        }
        static void ValidateReloadMeshContract(WeaponPresentation weapon,List<string> errors)
        {
            if (!weapon.animator || !weapon.incomingOffset || !weapon.leftReloadOffset ||
                weapon.loadedNails == null || weapon.incomingNails == null) return; // Missing bindings already fail above.
            string incomingPath=AnimationUtility.CalculateTransformPath(weapon.incomingOffset,weapon.animator.transform);
            string leftPath=AnimationUtility.CalculateTransformPath(weapon.leftReloadOffset,weapon.animator.transform);
            var nails=weapon.loadedNails.Concat(weapon.incomingNails).Where(n=>n).ToArray();
            Require(nails.Length==24 && nails.Distinct().Count()==24,"Partial reload requires exactly 24 independent round renderers.",errors);
            var targets=new HashSet<Transform>();
            foreach(var nail in nails)
            {
                if(!NailRigOwnership.TryGetAnimationTargets(nail,weapon.animator.transform,out var affected,out var reason))
                { errors.Add("Nail animation ownership unverifiable: "+reason);continue; }
                foreach(var target in affected) targets.Add(target);
            }
            var nailPaths=targets.Select(t=>AnimationUtility.CalculateTransformPath(t,weapon.animator.transform)).ToArray();
            foreach(var clip in weapon.animator.runtimeAnimatorController.animationClips.Distinct())
            foreach(var binding in AnimationUtility.GetCurveBindings(clip))
            {
                Require(binding.path!=incomingPath && binding.path!=leftPath,"Reload carrier offsets must be unkeyed: "+binding.path,errors);
                bool affectsNail=nailPaths.Any(path=>path==binding.path || path.StartsWith(binding.path+"/",StringComparison.Ordinal) || binding.path=="");
                if(!affectsNail) continue;
                Require(binding.propertyName!="m_Enabled" && binding.propertyName!="m_IsActive","Clips cannot override runtime nail visibility.",errors);
                if(binding.propertyName.StartsWith("m_LocalScale",StringComparison.Ordinal))
                {
                    var curve=AnimationUtility.GetEditorCurve(clip,binding);
                    Require(curve!=null && curve.keys.All(k=>k.value>.001f),"Clips cannot scale away runtime old/new nail geometry.",errors);
                }
            }
        }
        static void ValidatePresenter(MonoBehaviour presenter,string label,List<string> errors)
        {
            if(!presenter || !presenter.enabled) { errors.Add(label+": presenter is missing or disabled.");return; }
            var method=presenter.GetType().GetMethod("ValidateBindings",BindingFlags.Public|BindingFlags.Instance,null,new[]{typeof(string).MakeByRefType()},null);
            if(method==null || method.ReturnType!=typeof(bool)) { errors.Add(label+": pure ValidateBindings(out string) contract missing.");return; }
            try
            {
                object[] args={null};bool valid=(bool)method.Invoke(presenter,args);
                Require(valid,label+": "+(args[0] as string ?? "presenter binding validation failed"),errors);
                if(presenter is WeaponPresentation weapon && !WeaponArmCalibration.ValidateSourceAndBinding(weapon.armReach,out var reachReason)) errors.Add(label+": "+reachReason);
                if(presenter is BeastWeakPointPresentation weakpoint) WeakPointContractChecks.Validate(weakpoint,label,errors);
            }
            catch(Exception error) { errors.Add(label+": binding validation threw "+(error.InnerException??error).Message); }
        }
        static bool References(MonoBehaviour source, UnityEngine.Object target)
        { if (!source || !target) return false; var p = new SerializedObject(source).GetIterator(); while (p.Next(true)) if (p.propertyType == SerializedPropertyType.ObjectReference && p.objectReferenceValue == target) return true; return false; }
        static bool ReferencesType<T>(MonoBehaviour source) where T : UnityEngine.Object
        { if (!source) return false; var p = new SerializedObject(source).GetIterator(); while(p.Next(true)) if (p.propertyType == SerializedPropertyType.ObjectReference && p.objectReferenceValue is T) return true; return false; }
        static void ReviewScene(string path, string hash, string evidence,List<string> errors)
        { Require(!string.IsNullOrWhiteSpace(evidence) && hash == AssetDatabase.GetAssetDependencyHash(path).ToString(),path+": saved scene review/evidence hash missing or stale.",errors); }
        internal static string BuildFingerprint() => string.Join("|",new[] { JourneySceneAuthoring.ManifestPath,JourneySceneAuthoring.BootstrapPath }.Concat(JourneySceneAuthoring.RegionPaths).Select(p=>AssetDatabase.GetAssetDependencyHash(p).ToString()));
        // Explicit official entrypoint; never regenerates or silently approves scenes.
        public static void BuildAndroidProduction()
        {
            CheckProductionContent();
            var old = EditorBuildSettings.scenes;
            try
            {
                string[] paths = new[] { JourneySceneAuthoring.BootstrapPath }.Concat(JourneySceneAuthoring.RegionPaths).ToArray();
                EditorBuildSettings.scenes = paths.Select(p=>new EditorBuildSettingsScene(p,true)).ToArray();
                Directory.CreateDirectory("Build/JourneyAndroid");
                var result = BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes=paths, target=BuildTarget.Android, locationPathName="Build/JourneyAndroid/DesertRV.apk", options=BuildOptions.None });
                if (result.summary.result != BuildResult.Succeeded) throw new BuildFailedException("Formal Android journey build failed.");
            }
            finally { EditorBuildSettings.scenes=old; ValidatedBuildFingerprint=null; }
        }
        static string At(string[] values,int index) => values != null && index < values.Length ? values[index] : null;
        static T[] All<T>(Scene scene) where T:Component => scene.GetRootGameObjects().SelectMany(r=>r.GetComponentsInChildren<T>(true)).ToArray();
        static void Require(bool condition,string message,List<string> errors) { if (!condition) errors.Add(message); }
    }
    // Defense in depth for any build entrypoint using the formal journey scenes.
    public sealed class JourneyProductionBuildGate : IPreprocessBuildWithReport, IProcessSceneWithReport
    {
        public int callbackOrder => -1000;
        public void OnProcessScene(Scene scene, BuildReport report)
        {
            if (report == null) return;
            bool formal = scene.path == JourneySceneAuthoring.BootstrapPath || JourneySceneAuthoring.RegionPaths.Contains(scene.path);
            bool hasJourney = scene.GetRootGameObjects().Any(r=>r.GetComponentInChildren<JourneyDirector>(true) || r.GetComponentInChildren<RegionBinding>(true));
            if (!formal && !hasJourney) return;
            if (!formal) throw new BuildFailedException("Unreviewed alternate path contains formal journey components: "+scene.path);
            if (string.IsNullOrEmpty(JourneyContentChecks.ValidatedBuildFingerprint) || JourneyContentChecks.ValidatedBuildFingerprint != JourneyContentChecks.BuildFingerprint())
                throw new BuildFailedException("Formal journey scenes require current production content preflight. Use JourneyContentChecks.BuildAndroidProduction; direct scene-only builds cannot bypass asset acceptance.");
        }
        public void OnPreprocessBuild(BuildReport report)
        {
            if (EditorBuildSettings.scenes.Any(s => s.enabled && (s.path == JourneySceneAuthoring.BootstrapPath || JourneySceneAuthoring.RegionPaths.Contains(s.path))) &&
                (string.IsNullOrEmpty(JourneyContentChecks.ValidatedBuildFingerprint) || JourneyContentChecks.ValidatedBuildFingerprint != JourneyContentChecks.BuildFingerprint()))
                throw new BuildFailedException("Run formal content preflight before entering BuildPipeline. Use JourneyContentChecks.BuildAndroidProduction.");
        }
    }
}

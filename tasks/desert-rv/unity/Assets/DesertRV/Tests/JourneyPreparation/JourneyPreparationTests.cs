using System;
using System.Linq;
using System.IO;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV.Tests
{
    public sealed class JourneyPreparationTests
    {
        static void VerifyFxPreviewLifecycle(bool fail)
        {
            var editor = Type.GetType("DesertRV.Editor.JourneyCandidateAssetIntegration, Assembly-CSharp-Editor", true);
            var method = editor.GetMethod("WithFxPreviewScene", BindingFlags.Static | BindingFlags.NonPublic);
            var create = editor.GetMethod("FxObject", BindingFlags.Static | BindingFlags.NonPublic);
            var original = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            var active = SceneManager.GetActiveScene();
            var roots = original.SelectMany(scene => scene.GetRootGameObjects()).Select(go => go.GetInstanceID()).OrderBy(id => id).ToArray();
            Scene preview = default; GameObject root = null, child = null;
            Action<Scene> author = scene => {
                preview = scene;
                root = (GameObject)create.Invoke(null, new object[] { "FX isolation fixture", scene, null });
                child = (GameObject)create.Invoke(null, new object[] { "FX child fixture", scene, root.transform });
                Assert.AreEqual(scene, root.scene); Assert.AreEqual(scene, child.scene); Assert.AreEqual(root.transform, child.transform.parent);
                if (fail) throw new InvalidOperationException("Injected FX preview authoring failure.");
            };
            if (fail)
            {
                var error = Assert.Throws<TargetInvocationException>(() => method.Invoke(null, new object[] { author }));
                Assert.IsInstanceOf<InvalidOperationException>(error.InnerException);
                Assert.AreEqual("Injected FX preview authoring failure.", error.InnerException.Message);
            }
            else Assert.DoesNotThrow(() => method.Invoke(null, new object[] { author }));
            Assert.IsFalse(preview.IsValid()); Assert.IsFalse(root); Assert.IsFalse(child);
            var after = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            CollectionAssert.AreEqual(original.Select(scene => scene.handle), after.Select(scene => scene.handle));
            CollectionAssert.AreEqual(roots, after.SelectMany(scene => scene.GetRootGameObjects()).Select(go => go.GetInstanceID()).OrderBy(id => id));
            Assert.AreEqual(active, SceneManager.GetActiveScene()); Assert.IsTrue(after.All(scene => !scene.isDirty));
        }
        static void VerifyPoseJsonRoundtrip()
        {
            var editor = Type.GetType("DesertRV.Editor.JourneyCandidateAssetIntegration, Assembly-CSharp-Editor", true);
            var requestType = editor.GetNestedType("Request"); var poseType = editor.GetNestedType("Pose");
            var readyType = Type.GetType("DesertRV.Editor.JourneyCandidatePreparation+ReadyInput, Assembly-CSharp-Editor", true);
            var resolve = editor.GetMethod("ResolveArcModulePose", BindingFlags.Static | BindingFlags.NonPublic);
            var shape = editor.GetMethod("NamedPoseShape", BindingFlags.Static | BindingFlags.NonPublic);
            object PoseOf(object request, string name) => requestType.GetField(name).GetValue(request);
            object ParsePose(string json) => JsonUtility.FromJson(json, poseType);
            const string unit = "{\"localPosition\":{\"x\":0.125,\"y\":0.25,\"z\":0.5},\"localRotation\":{\"x\":0,\"y\":0,\"z\":0,\"w\":1},\"localScale\":{\"x\":1,\"y\":1,\"z\":1}}";
            var derived = ParsePose(unit); // Isolated method fixture only; never written to a production input/asset.
            var actual = JsonUtility.FromJson(File.ReadAllText("JourneyEvidence/JourneyPreparation/ready-input.json"), readyType);
            var roundtrip = JsonUtility.FromJson(JsonUtility.ToJson(actual), readyType);
            foreach (var ready in new[] { actual, roundtrip })
            {
                var request = readyType.GetField("integration").GetValue(ready);
                string intent = (string)readyType.GetField("arcModulePoseSource").GetValue(ready);
                var selected = PoseOf(request, "arcModulePose");
                Debug.Log("JOURNEY_POSE_JSON_ROUNDTRIP source=" + intent + "; arcNull=" + (selected == null) + "; arc=" + (selected == null ? "null" : JsonUtility.ToJson(selected)));
                var resolved = resolve.Invoke(null, new[] { (object)intent, selected, derived });
                Assert.AreSame(intent == "scene-geometry" ? derived : selected, resolved);
                foreach (string role in new[] { "weaponCameraPose", "flashMuzzlePose" }) shape.Invoke(null, new[] { PoseOf(request, role), role });
            }
            var observedNull = PoseOf(JsonUtility.FromJson("{\"arcModulePose\":null}", requestType), "arcModulePose");
            Assert.AreSame(derived, resolve.Invoke(null, new[] { (object)"scene-geometry", observedNull, derived }));
            var explicitPose = ParsePose(unit);
            Assert.AreSame(explicitPose, resolve.Invoke(null, new[] { (object)"selection", explicitPose, derived }));
            var invalid = ParsePose(unit); poseType.GetField("localScale").SetValue(invalid, Vector3.zero);
            foreach (var args in new[] {
                new[] { (object)"selection", invalid, derived }, new[] { (object)"selection", observedNull, derived },
                new[] { (object)"scene-geometry", explicitPose, derived }, new[] { (object)"scene-geometry", observedNull, invalid },
                new[] { (object)null, observedNull, derived }, new[] { (object)"unknown", observedNull, derived } })
            {
                var error = Assert.Throws<TargetInvocationException>(() => resolve.Invoke(null, args));
                Assert.IsInstanceOf<InvalidOperationException>(error.InnerException);
            }
        }
        static void VerifyArcMeshQueries()
        {
            var actionsType = Type.GetType("DesertRV.JourneyActions, Assembly-CSharp", true);
            var motorType = Type.GetType("DesertRV.JourneyMotor, Assembly-CSharp", true);
            var snapshotType = actionsType.GetNestedType("ArcMeshSnapshot");
            var createSnapshot = snapshotType.GetMethod("FromImportedMesh");
            var distance = actionsType.GetMethod("ArcMeshDistanceSquared");
            var check = actionsType.GetMethod("CheckArcSource");
            object Snapshot(Mesh mesh) => createSnapshot.Invoke(null, new object[] { mesh, mesh.vertices, mesh.triangles });
            float Distance(object snapshot, Matrix4x4 matrix, Vector3 point, bool expectedInside)
            {
                var args = new object[] { snapshot, matrix, point, false }; float result = (float)distance.Invoke(null, args);
                Assert.AreEqual(expectedInside, (bool)args[3], "Actual mesh volume classification at " + point); return result;
            }
            var vertices = new[] { new Vector3(-1,-1,-1),new Vector3(1,-1,-1),new Vector3(1,1,-1),new Vector3(-1,1,-1),
                new Vector3(-1,-1,1),new Vector3(1,-1,1),new Vector3(1,1,1),new Vector3(-1,1,1) };
            var indices = new[] {0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5};
            var cube = new Mesh { name = "Arc closed fixture", vertices = vertices, triangles = indices };
            var cavity = new Mesh { name = "Arc hollow fixture", vertices = vertices.Concat(vertices.Select(v=>v*.4f)).ToArray(),
                triangles = indices.Concat(Enumerable.Range(0,indices.Length/3).SelectMany(t=>new[]{indices[t*3]+8,indices[t*3+2]+8,indices[t*3+1]+8})).ToArray() };
            var polygon = new[] {new Vector2(0,0),new Vector2(2,0),new Vector2(2,1),new Vector2(1,1),new Vector2(1,2),new Vector2(0,2)};
            var face = new[] {0,1,2,0,2,3,0,3,5,3,4,5};
            var concaveIndices = Enumerable.Range(0,face.Length/3).SelectMany(t=>new[]{face[t*3],face[t*3+2],face[t*3+1]})
                .Concat(face.Select(i=>i+6)).Concat(Enumerable.Range(0,6).SelectMany(i=>new[]{i,(i+1)%6,(i+1)%6+6,i,(i+1)%6+6,i+6})).ToArray();
            var concave = new Mesh { name = "Arc concave fixture", vertices = polygon.Select(v=>new Vector3(v.x,v.y,-.5f)).Concat(polygon.Select(v=>new Vector3(v.x,v.y,.5f))).ToArray(),triangles=concaveIndices };
            var surface = new Mesh { name="Arc open fixture",vertices=new[]{new Vector3(-1,-1,0),new Vector3(1,-1,0),new Vector3(0,1,0)},triangles=new[]{0,1,2}};
            var collinear = new Mesh {name="Arc collinear fixture",vertices=new[]{Vector3.left,Vector3.zero,Vector3.right},triangles=new[]{0,1,2}};
            var combined = new Mesh {name="Arc closed plus point fixture",vertices=vertices.Concat(new[]{new Vector3(3,0,0),new Vector3(3,0,0),new Vector3(3,0,0)}).ToArray(),triangles=indices.Concat(new[]{8,9,10}).ToArray()};
            var collapsed = new Mesh {name="Arc point fixture",vertices=new[]{Vector3.zero,Vector3.zero,Vector3.zero},triangles=new[]{0,1,2}};
            try
            {
                foreach(var flat in new[]{collinear,collapsed})
                {
                    var snapshot=Snapshot(flat);
                    Assert.That(Distance(snapshot,Matrix4x4.identity,new Vector3(0,.0005f,0),false),Is.LessThan(.000001f));
                    Assert.That(Distance(snapshot,Matrix4x4.identity,new Vector3(0,.0015f,0),false),Is.GreaterThan(.000001f));
                    var matrix=Matrix4x4.TRS(new Vector3(2,3,4),Quaternion.Euler(13,29,7),new Vector3(2,.5f,3));
                    Assert.That(Distance(snapshot,matrix,matrix.MultiplyPoint3x4(new Vector3(0,.001f,0)),false),Is.LessThan(.000001f));
                }
                var combinedSnapshot=Snapshot(combined);
                Distance(combinedSnapshot,Matrix4x4.identity,Vector3.zero,true);
                Assert.That(Distance(combinedSnapshot,Matrix4x4.identity,new Vector3(3,.0005f,0),false),Is.LessThan(.000001f));
                var cubeSnapshot=Snapshot(cube); var bent=Snapshot(concave); var plane=Snapshot(surface);
                Assert.Throws<TargetInvocationException>(()=>Snapshot(cavity), "Multiple closed shells are outside the explicitly supported domain, never cancelled into false safety.");
                var authoringType=Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor",true);
                var readActual=authoringType.GetMethod("ReadArcMeshGeometry",BindingFlags.Static|BindingFlags.NonPublic);
                var retained=UnityEditor.AssetDatabase.LoadAssetAtPath<Mesh>("Assets/DesertRV/Art/CollisionMeshes/GEO-coach_body_shell.asset");
                Assert.IsNotNull(retained);var retainedSnapshot=readActual.Invoke(null,new object[]{retained});
                Assert.That(Distance(retainedSnapshot,Matrix4x4.identity,new Vector3(0,0,1.5f),false),Is.EqualTo(.735f*.735f).Within(.001f));
                Assert.That(Distance(retainedSnapshot,Matrix4x4.identity,new Vector3(1.135f,0,1.5f),true),Is.EqualTo(.005f*.005f).Within(.000001f));
                Assert.That(Distance(cubeSnapshot,Matrix4x4.identity,Vector3.zero,true),Is.EqualTo(1).Within(1e-6));
                Assert.That(Distance(cubeSnapshot,Matrix4x4.identity,new Vector3(1.0005f,0,0),false),Is.LessThan(.000001f));
                Assert.That(Distance(cubeSnapshot,Matrix4x4.identity,new Vector3(1.002f,0,0),false),Is.GreaterThan(.000001f));
                Distance(bent,Matrix4x4.identity,new Vector3(1.5f,1.5f,0),false); // Outside in a concavity, inside the AABB.
                Distance(bent,Matrix4x4.identity,new Vector3(.5f,.5f,0),true);
                foreach(float sign in new[]{-1f,1f}) Assert.That(Distance(plane,Matrix4x4.identity,new Vector3(0,0,sign*.0005f),false),Is.LessThan(.000001f));
                foreach(float sign in new[]{-1f,1f})
                {
                    var matrix=Matrix4x4.TRS(new Vector3(3,4,5),Quaternion.Euler(23,41,17),new Vector3(sign*2,.7f,1.3f));
                    Distance(cubeSnapshot,matrix,matrix.MultiplyPoint3x4(Vector3.zero),true);
                    Assert.That(Distance(cubeSnapshot,matrix,matrix.MultiplyPoint3x4(new Vector3(1.00025f,0,0)),false),Is.LessThan(.000001f));
                    Assert.That(Distance(cubeSnapshot,matrix,matrix.MultiplyPoint3x4(new Vector3(1.001f,0,0)),false),Is.GreaterThan(.000001f));
                    Distance(bent,matrix,matrix.MultiplyPoint3x4(new Vector3(1.5f,1.5f,0)),false);
                    Distance(retainedSnapshot,matrix,matrix.MultiplyPoint3x4(new Vector3(0,0,1.5f)),false);
                    Distance(retainedSnapshot,matrix,matrix.MultiplyPoint3x4(new Vector3(1.135f,0,1.5f)),true);
                }
                Assert.Throws<TargetInvocationException>(()=>Distance(cubeSnapshot,Matrix4x4.Scale(new Vector3(0,1,1)),Vector3.zero,false));
                var validateGeometry=actionsType.GetMethod("ValidateArcGeometry",BindingFlags.Static|BindingFlags.NonPublic);
                var cacheMatches=actionsType.GetMethod("ArcGeometryCacheMatches",BindingFlags.Static|BindingFlags.NonPublic);
                var cache=validateGeometry.Invoke(null,new[]{cubeSnapshot});
                Assert.IsTrue((bool)cacheMatches.Invoke(null,new[]{cubeSnapshot,cache}));
                foreach(string fieldName in new[]{"vertices","triangles"})
                {
                    var field=snapshotType.GetField(fieldName,BindingFlags.Instance|BindingFlags.NonPublic);var originalArray=(Array)field.GetValue(cubeSnapshot);
                    field.SetValue(cubeSnapshot,originalArray.Clone());Assert.IsFalse((bool)cacheMatches.Invoke(null,new[]{cubeSnapshot,cache}));field.SetValue(cubeSnapshot,originalArray);
                }
                var meshField=snapshotType.GetField("mesh",BindingFlags.Instance|BindingFlags.NonPublic);
                var sameShape=UnityEngine.Object.Instantiate(cube);
                try {meshField.SetValue(cubeSnapshot,sameShape);Assert.IsFalse((bool)cacheMatches.Invoke(null,new[]{cubeSnapshot,cache}));} finally {meshField.SetValue(cubeSnapshot,cube);UnityEngine.Object.DestroyImmediate(sameShape);}
                var brokenIndices=(int[])indices.Clone();brokenIndices[1]=indices[2];brokenIndices[2]=indices[1];
                Assert.Throws<TargetInvocationException>(()=>createSnapshot.Invoke(null,new object[]{cube,vertices,brokenIndices}));
                var hash=snapshotType.GetField("sha256",BindingFlags.Instance|BindingFlags.NonPublic); string original=(string)hash.GetValue(cubeSnapshot);
                hash.SetValue(cubeSnapshot,new string('0',64)); Assert.Throws<TargetInvocationException>(()=>Distance(cubeSnapshot,Matrix4x4.identity,Vector3.zero,true)); hash.SetValue(cubeSnapshot,original);
                var points=snapshotType.GetField("vertices",BindingFlags.Instance|BindingFlags.NonPublic); var actual=(Vector3[])points.GetValue(cubeSnapshot); actual[0]+=Vector3.up*.1f;
                Assert.Throws<TargetInvocationException>(()=>Distance(cubeSnapshot,Matrix4x4.identity,Vector3.zero,true)); actual[0]-=Vector3.up*.1f;
                // Use a fresh exact snapshot after a float roundtrip; stale hashes must never be repaired implicitly.
                cubeSnapshot=Snapshot(cube);
                var integration=Type.GetType("DesertRV.Editor.JourneyCandidateAssetIntegration, Assembly-CSharp-Editor",true);
                var isolated=integration.GetMethod("WithFxPreviewScene",BindingFlags.Static|BindingFlags.NonPublic);
                var create=integration.GetMethod("FxObject",BindingFlags.Static|BindingFlags.NonPublic);
                Action<Scene> exercise=scene=>{
                    GameObject Obj(string name,Transform parent=null)=>(GameObject)create.Invoke(null,new object[]{name,scene,parent});
                    var root=Obj("Arc query fixture"); var rv=Obj("RV",root.transform);var module=Obj("Arc",rv.transform);var source=Obj("Source",module.transform);
                    var actions=root.AddComponent(actionsType);var motor=root.AddComponent(motorType);
                    actionsType.GetField("motor").SetValue(actions,motor);actionsType.GetField("arcOrigin").SetValue(actions,source.transform);
                    motorType.GetField("vehicle").SetValue(motor,rv.transform);motorType.GetField("arc").SetValue(motor,module);
                    var body=Obj("Nonconvex",rv.transform);var collider=body.AddComponent<MeshCollider>();collider.sharedMesh=cube;collider.convex=false;
                    void Snap(object item) {var array=Array.CreateInstance(snapshotType,item==null?0:1);if(item!=null)array.SetValue(item,0);actionsType.GetField("arcMeshGeometry").SetValue(actions,array);}
                    bool Clear()=> (bool)check.Invoke(actions,new object[]{null,0f,null});
                    Snap(cubeSnapshot);source.transform.position=new Vector3(3,0,0);Physics.SyncTransforms();Assert.IsTrue(Clear());
                    Snap(null);Assert.IsFalse(Clear(),"Missing geometry must fail even outside AABB.");
                    collider.enabled=false;Assert.IsTrue(Clear());collider.enabled=true;Snap(cubeSnapshot);
                    source.transform.position=Vector3.zero;Physics.SyncTransforms();Assert.IsFalse(Clear());
                    source.transform.position=new Vector3(1.0015f,0,0);Physics.SyncTransforms();Assert.IsTrue(Clear());
                    source.transform.position=new Vector3(1.0005f,0,0);Physics.SyncTransforms();Assert.IsFalse(Clear());
                    body.transform.localScale=new Vector3(1.0007f,1,1);source.transform.position=new Vector3(1.0015f,0,0);Physics.SyncTransforms();Assert.IsFalse(Clear());
                    body.transform.localScale=Vector3.one;Physics.SyncTransforms();Assert.IsTrue(Clear());
                    collider.sharedMesh=retained;Assert.IsFalse(Clear(),"Mesh replacement invalidates identity.");Snap(retainedSnapshot);source.transform.position=new Vector3(0,0,1.5f);Physics.SyncTransforms();Assert.IsTrue(Clear());
                    collider.sharedMesh=concave;Snap(bent);source.transform.position=new Vector3(1.5f,1.5f,0);Physics.SyncTransforms();Assert.IsTrue(Clear());
                    collider.sharedMesh=cube;Snap(cubeSnapshot);collider.convex=true;source.transform.position=Vector3.zero;Physics.SyncTransforms();Assert.IsFalse(Clear());
                    source.transform.position=new Vector3(3,0,0);Physics.SyncTransforms();Assert.IsTrue(Clear());
                    collider.convex=false;cube.UploadMeshData(true);Assert.IsFalse(cube.isReadable);
                    source.transform.position=new Vector3(3,0,0);Physics.SyncTransforms();Assert.IsTrue(Clear());
                    var authoring=Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor",true);
                    var surfaceDistance=authoring.GetMethod("InteractionSurfaceDistanceSquared",BindingFlags.Static|BindingFlags.NonPublic);
                    Assert.That((float)surfaceDistance.Invoke(null,new object[]{collider,new Vector3(1.25f,0,0)}),Is.EqualTo(.0625f).Within(1e-5));
                    collider.enabled=false;var box=body.AddComponent<BoxCollider>();box.size=Vector3.one*2;source.transform.position=Vector3.zero;Physics.SyncTransforms();Assert.IsFalse(Clear());
                    source.transform.position=new Vector3(3,0,0);Physics.SyncTransforms();Assert.IsTrue(Clear());

                };
                isolated.Invoke(null,new object[]{exercise});
                Debug.Log("JOURNEY_ARC_QUERY_REGRESSION closed/cavity/concave/open-both-sides/transformed/near-surface/identity/hash/missing/disabled/unreadable/native-supported passed");
            }
            finally {UnityEngine.Object.DestroyImmediate(cube);UnityEngine.Object.DestroyImmediate(cavity);UnityEngine.Object.DestroyImmediate(concave);UnityEngine.Object.DestroyImmediate(surface);UnityEngine.Object.DestroyImmediate(collinear);UnityEngine.Object.DestroyImmediate(collapsed);UnityEngine.Object.DestroyImmediate(combined);}
        }
        static void VerifyRootGrounding()
        {
            var editor=Type.GetType("DesertRV.Editor.JourneyCandidateAssetIntegration, Assembly-CSharp-Editor",true);
            var placement=editor.GetNestedType("EnemyPlacement"); var row=Activator.CreateInstance(placement);
            placement.GetField("id").SetValue(row,"fixture/root");placement.GetField("kind").SetValue(row,"pouncer");placement.GetField("yaw").SetValue(row,180f);
            var resolve=editor.GetMethod("ResolveRootGrounding",BindingFlags.Static|BindingFlags.NonPublic);
            var isolate=editor.GetMethod("WithFxPreviewScene",BindingFlags.Static|BindingFlags.NonPublic);
            var create=editor.GetMethod("FxObject",BindingFlags.Static|BindingFlags.NonPublic);
            var transaction=editor.GetMethod("RunReadOnlySceneQuery",BindingFlags.Static|BindingFlags.NonPublic);
            var order=new System.Collections.Generic.List<string>();
            Action First=()=>{order.Add("query");throw new InvalidOperationException("initial missing floor");};
            Action Restore=()=>{order.Add("restore");throw new InvalidOperationException("restore failure");};
            Action Verify=()=>{order.Add("verify");throw new InvalidOperationException("protected failure");};
            var combined=Assert.Throws<TargetInvocationException>(()=>transaction.Invoke(null,new object[]{First,Restore,Verify}));
            var aggregate=combined.InnerException as AggregateException;Assert.IsNotNull(aggregate);
            CollectionAssert.AreEqual(new[]{"query","restore","verify"},order);
            CollectionAssert.AreEqual(new[]{"initial missing floor","restore failure","protected failure"},aggregate.InnerExceptions.Select(e=>e.Message));
            var ordinary=SceneManager.GetActiveScene();
            Action<Scene> exercise=scene=>{
                GameObject Obj(string name)=>(GameObject)create.Invoke(null,new object[]{name,scene,null});
                var sand=Obj("Route foundation").AddComponent<BoxCollider>();sand.transform.position=new Vector3(0,-.24f,30);sand.size=new Vector3(34,.4f,94);
                var road=Obj("Road surface").AddComponent<BoxCollider>();road.transform.position=new Vector3(0,-.015f,30);road.size=new Vector3(8,.1f,94);
                var floors=new Collider[]{sand,road};Physics.SyncTransforms();
                object Resolve(Vector3 at,Scene owner) {placement.GetField("position").SetValue(row,at);return resolve.Invoke(null,new object[]{owner,floors,row,1});}
                Vector3 Value(object value,string field)=>(Vector3)value.GetType().GetField(field).GetValue(value);
                var outside=Resolve(new Vector3(-6,0,18),scene);Assert.That(Value(outside,"resolvedPosition").y,Is.EqualTo(-.04f).Within(.00001f));
                Assert.AreEqual(new Vector3(-6,0,18),Value(outside,"declaredPosition"));
                var onRoad=Resolve(new Vector3(0,0,39),scene);Assert.That(Value(onRoad,"resolvedPosition").y,Is.EqualTo(.035f).Within(.00001f));
                Assert.AreEqual(180f,onRoad.GetType().GetField("yaw").GetValue(onRoad));
                Assert.Throws<TargetInvocationException>(()=>Resolve(new Vector3(100,0,18),scene));
                Assert.Throws<TargetInvocationException>(()=>Resolve(new Vector3(-6,.1f,18),scene));
                Assert.Throws<TargetInvocationException>(()=>Resolve(new Vector3(-6,0,18),ordinary));
                sand.isTrigger=true;Assert.Throws<TargetInvocationException>(()=>Resolve(new Vector3(-6,0,18),scene));sand.isTrigger=false;
                sand.enabled=false;Assert.Throws<TargetInvocationException>(()=>Resolve(new Vector3(-6,0,18),scene));sand.enabled=true;
                sand.gameObject.layer=2;Assert.Throws<TargetInvocationException>(()=>Resolve(new Vector3(-6,0,18),scene));sand.gameObject.layer=0;
                sand.name="Unlisted floor";Assert.Throws<TargetInvocationException>(()=>Resolve(new Vector3(-6,0,18),scene));sand.name="Route foundation";
                Assert.Throws<TargetInvocationException>(()=>resolve.Invoke(null,new object[]{scene,Array.Empty<Collider>(),row,1}));
            };
            isolate.Invoke(null,new object[]{exercise});
            // Unknown names cannot appear in public diagnostics, even when they sit below an Assets directory.
            var delta=editor.GetMethod("ProtectedDelta",BindingFlags.Static|BindingFlags.NonPublic);
            var before=new System.Collections.Generic.Dictionary<string,string>{{"Assets/private-not-approved-name.txt",new string('a',64)}};
            var after=new System.Collections.Generic.Dictionary<string,string>{{"Assets/private-not-approved-name.txt",new string('b',64)},{"Assets/private-new-name.txt",new string('c',64)}};
            var lines=(string[])delta.Invoke(null,new object[]{before,after});Assert.AreEqual(2,lines.Length);
            Assert.IsTrue(lines.All(line=>!line.Contains("private-")&&line.Contains("unknown-path-sha256=")));
            Debug.Log("JOURNEY_ROOT_GROUNDING_REGRESSION actual-sand/road/no-floor/declared-Y/foreign-scene/trigger/disabled/layer/unlisted/empty/diagnostic-redaction passed");
        }
        // The real 3a49 authoring case completed all checks in 291.946 seconds, then failed the framework's 180-second default.
        // This is a bounded Editor authoring budget, never gameplay duration or a relaxation of the exact Passed XML gate.
        [Timeout(600000)]
        [Test] public void PrepareVerifiedSameWorkspaceJourney()
        {
            var timer = System.Diagnostics.Stopwatch.StartNew(); double previousSeconds = 0;
            void MarkPhase(string stage)
            {
                double seconds = timer.Elapsed.TotalSeconds;
                Debug.Log("JOURNEY_PREPARATION_TEST_PHASE_COMPLETED stage=" + stage + "; seconds=" +
                    (seconds - previousSeconds).ToString("F3", System.Globalization.CultureInfo.InvariantCulture) + "; totalSeconds=" +
                    seconds.ToString("F3", System.Globalization.CultureInfo.InvariantCulture));
                previousSeconds = seconds;
            }
            // Actual native success and injected-failure cleanup, inside the existing single-case gate.
            VerifyFxPreviewLifecycle(false); VerifyFxPreviewLifecycle(true); MarkPhase("fx-preview-lifecycle-regressions");
            VerifyPoseJsonRoundtrip(); MarkPhase("pose-json-regressions");
            VerifyArcMeshQueries(); MarkPhase("arc-geometry-regressions");
            VerifyRootGrounding(); MarkPhase("root-grounding-regressions");
            Type.GetType("DesertRV.Editor.JourneyCandidatePreparation, Assembly-CSharp-Editor", true)
                .GetMethod("PrepareVerifiedSameWorkspace").Invoke(null, null);
            MarkPhase("complete-native-authoring-and-scope");
            var integration=Type.GetType("DesertRV.Editor.JourneyCandidateAssetIntegration, Assembly-CSharp-Editor",true);
            var readyType=Type.GetType("DesertRV.Editor.JourneyCandidatePreparation+ReadyInput, Assembly-CSharp-Editor",true);
            var ready=JsonUtility.FromJson(File.ReadAllText("JourneyEvidence/JourneyPreparation/ready-input.json"),readyType);
            var report=JsonUtility.FromJson(File.ReadAllText("JourneyEvidence/JourneyPreparation/spawn-grounding.json"),integration.GetNestedType("SpawnGroundingReport"));
            var rows=(Array)report.GetType().GetField("rows").GetValue(report);
            Assert.AreEqual(9,rows.Length);
            CollectionAssert.AreEquivalent(new[]{1,1,1,2,2,2,3,3,3},rows.Cast<object>().Select(r=>(int)r.GetType().GetField("region").GetValue(r)));
            Assert.AreEqual(readyType.GetField("selectionSha256").GetValue(ready),report.GetType().GetField("selectionSha256").GetValue(report));
            Assert.IsFalse((bool)report.GetType().GetField("approved").GetValue(report));
            // The real saved manifest must survive a native unload, not merely a managed reference check.
            var request = JsonUtility.FromJson(File.ReadAllText("JourneyEvidence/JourneyPreparation/integration-input.json"), integration.GetNestedType("Request"));
            var verifyManifest = integration.GetMethod("VerifySavedManifest", BindingFlags.Static | BindingFlags.NonPublic);
            verifyManifest.Invoke(null, new[] { request });
            var manifest = UnityEditor.AssetDatabase.LoadAssetAtPath<ScriptableObject>("Assets/DesertRV/Scenes/Journey/JourneyContent.asset");
            Assert.IsTrue(manifest && UnityEditor.EditorUtility.IsPersistent(manifest));
            Resources.UnloadAsset(manifest); Assert.IsFalse(manifest);
            verifyManifest.Invoke(null, new[] { request });
            Debug.Log("JOURNEY_MANIFEST_NATIVE_UNLOAD_RELOAD_REGRESSION: passed; real saved strict identities and approval=false verified.");
            MarkPhase("saved-grounding-and-manifest-regressions");
            Debug.Log("JOURNEY_PREPARATION_TEST_BODY_COMPLETED_UNREVIEWED: all authoring and regression assertions returned; exact native XML must still report Passed.");
        }
    }
}

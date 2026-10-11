using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.ExceptionServices;
using System.Reflection;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV.Tests
{
    // Actual Unity physics and skinned geometry tests; source authoring is not execution evidence.
    public sealed class PouncerGroundSupportTests
    {
        const BindingFlags Flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static void Set(object o, string name, object value) => o.GetType().GetField(name, Flags).SetValue(o, value);
        static object Call(object o, string name, params object[] args) => o.GetType().GetMethod(name, Flags).Invoke(o, args);
        static V Get<V>(object o, string name) => (V)o.GetType().GetProperty(name, Flags).GetValue(o);
        static bool Move(World world, Vector3 delta, out Collider contact, out string reason)
        {
            world.BeforePhysics();
            object[] args = { delta, null, null }; bool result = (bool)Call(world.Support, "TryMove", args);
            contact = args[1] as Collider; reason = args[2] as string; return result;
        }
        static void ThrowFailures(List<Exception> errors)
        {
            if (errors.Count == 1) ExceptionDispatchInfo.Capture(errors[0]).Throw();
            if (errors.Count > 1) throw new AggregateException("Original test failure is first; cleanup failures follow.", errors);
        }
        static void Run(Action<World> test)
        {
            World world = null; var errors = new List<Exception>();
            try { world = new World(); test(world); }
            catch (Exception primary) { errors.Add(primary); }
            finally { if (world != null) world.Cleanup(errors); }
            ThrowFailures(errors);
        }
        // Mirrors the already native-passed JourneyTracerMaterialTests batch recovery.
        // Named clean setups reload from untouched bytes. Dirty/Untitled inputs are copied
        // and byte-verified before replacement; that fallback is forbidden outside batch CI.
        sealed class EditorPhysicsScope
        {
            readonly SceneSetup[] setup = EditorSceneManager.GetSceneManagerSetup();
            readonly Scene[] previous = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
            readonly Dictionary<string, byte[]> originalFiles = new Dictionary<string, byte[]>();
            readonly Dictionary<string, byte[]> recoveryFiles = new Dictionary<string, byte[]>();
            readonly List<string> temporaryCopies = new List<string>();
            readonly string id = Guid.NewGuid().ToString("N");
            bool replaced, restorable;
            public void Begin()
            {
                Assert.That(!Application.isPlaying && !EditorApplication.isPlayingOrWillChangePlaymode, Is.True, "EditMode fixture required.");
                restorable = setup.Any(s => s.isLoaded && s.isActive) &&
                    setup.All(s => !string.IsNullOrEmpty(s.path) && File.Exists(s.path)) && previous.All(s => !s.isLoaded || !s.isDirty);
                Assert.That(restorable || previous.Length == 0 || Application.isBatchMode, Is.True,
                    "Dirty/Untitled recovery is supported only in isolated batch CI; save the Editor setup first.");
                foreach (string file in setup.Select(s => s.path).Where(p => !string.IsNullOrEmpty(p))
                    .SelectMany(p => new[] { p, p + ".meta" }).Distinct().Where(File.Exists)) originalFiles.Add(file, File.ReadAllBytes(file));
                if (!restorable && previous.Any(s => s.isLoaded))
                {
                    string recovery = "Library/DesertRVPouncerGroundFixture/" + id;
                    Assert.That(Directory.Exists(recovery), Is.False); Directory.CreateDirectory(recovery);
                    for (int i = 0; i < previous.Length; i++)
                    {
                        var initial = previous[i]; if (!initial.isLoaded) continue;
                        string initialPath = initial.path; bool initialDirty = initial.isDirty;
                        string copy = "Assets/PouncerGroundInitial_" + id + "_" + i + ".unity";
                        Assert.That(File.Exists(copy) || File.Exists(copy + ".meta"), Is.False);
                        temporaryCopies.Add(copy); // Own the temporary path before SaveScene.
                        Assert.That(EditorSceneManager.SaveScene(initial, copy, true), Is.True);
                        foreach (string suffix in new[] { "", ".meta" })
                        {
                            string destination = recovery + "/Initial-" + i + ".unity" + suffix;
                            byte[] bytes = File.ReadAllBytes(copy + suffix);
                            File.WriteAllBytes(destination, bytes); recoveryFiles.Add(destination, bytes);
                            Assert.That(File.ReadAllBytes(destination), Is.EqualTo(bytes));
                        }
                        string metadata = recovery + "/Initial-" + i + ".txt";
                        File.WriteAllText(metadata, "path=" + initialPath + "\ndirty=" + initialDirty +
                            "\nactive=" + (initial == SceneManager.GetActiveScene()) + "\nrootCount=" + initial.rootCount);
                        recoveryFiles.Add(metadata, File.ReadAllBytes(metadata));
                        Assert.That(initial.path, Is.EqualTo(initialPath)); Assert.That(initial.isDirty, Is.EqualTo(initialDirty));
                        Assert.That(AssetDatabase.DeleteAsset(copy), Is.True);
                    }
                }
                replaced = true; // A partly failed replacement still needs the recovery path.
                var empty = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                PouncerPawContactConstraintTests.Fixture.RequireActiveScene(empty, "Empty isolated fixture scene");
                Assert.That(empty.rootCount, Is.Zero);
                AssertCollisionDomain(null);
            }
            public static void AssertCollisionDomain(PouncerPawContactConstraintTests.Fixture fixture)
            {
                Physics.SyncTransforms();
                foreach (var collider in Resources.FindObjectsOfTypeAll<Collider>())
                {
                    var scene = collider.gameObject.scene;
                    if (!scene.IsValid() || !scene.isLoaded || !collider.enabled || !collider.gameObject.activeInHierarchy ||
                        !scene.GetPhysicsScene().Equals(Physics.defaultPhysicsScene)) continue;
                    Assert.That(fixture != null && fixture.OwnsScene(scene), Is.True,
                        "Unowned active collider in the default physics world: " + collider.name + " / " + scene.path);
                }
            }
            public void Cleanup(List<Exception> errors)
            {
                void Attempt(Action action) { try { action(); } catch (Exception error) { errors.Add(error); } }
                bool restored = false;
                if (replaced) Attempt(() => {
                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                    if (restorable) EditorSceneManager.RestoreSceneManagerSetup(setup);
                    restored = true;
                });
                // Copies whose byte-verified Library backup was not completed are retained
                // on setup failure; never destroy the only possible recovery material.
                foreach (string copy in temporaryCopies) Attempt(() => {
                    if (!File.Exists(copy) && !File.Exists(copy + ".meta")) return;
                    Assert.Fail("Temporary recovery asset retained after failed backup: " + copy);
                });
                foreach (var original in originalFiles) Attempt(() => Assert.That(File.ReadAllBytes(original.Key), Is.EqualTo(original.Value), original.Key));
                foreach (var recovery in recoveryFiles) Attempt(() => Assert.That(File.ReadAllBytes(recovery.Key), Is.EqualTo(recovery.Value), recovery.Key));
                if (restored) Attempt(() => {
                    var after = EditorSceneManager.GetSceneManagerSetup();
                    if (restorable)
                    {
                        Assert.That(after.Select(s => s.path), Is.EqualTo(setup.Select(s => s.path)));
                        Assert.That(after.Select(s => s.isLoaded), Is.EqualTo(setup.Select(s => s.isLoaded)));
                        Assert.That(after.Select(s => s.isActive), Is.EqualTo(setup.Select(s => s.isActive)));
                    }
                    else
                    {
                        Assert.That(SceneManager.sceneCount, Is.EqualTo(1)); var empty = SceneManager.GetActiveScene();
                        Assert.That(empty.IsValid() && empty.isLoaded, Is.True); Assert.That(empty.path, Is.Empty); Assert.That(empty.rootCount, Is.Zero);
                    }
                    Assert.That(Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).All(s => !s.isLoaded || !s.isDirty), Is.True);
                });
                Debug.Log("POUNCER_GROUND_FIXTURE_RECOVERY restoredNamedSetup=" + (restored && restorable) +
                    " recoveryFiles=" + recoveryFiles.Count + " replaced=" + replaced + " errors=" + errors.Count);
            }
        }
        sealed class World : IDisposable
        {
            internal readonly PouncerPawContactConstraintTests.Fixture F;
            readonly EditorPhysicsScope scope = new EditorPhysicsScope();
            bool disposed;
            internal readonly Component Region, Support;
            internal readonly BoxCollider Road;
            internal readonly CapsuleCollider Capsule;
            internal World()
            {
                try
                {
                scope.Begin();
                F = new PouncerPawContactConstraintTests.Fixture(ordinaryEditorScene: true);
                Assert.That(F.ActorPhysics.Equals(Physics.defaultPhysicsScene), Is.True, "Ordinary Editor scenes use the controlled default physics world.");
                F.Root.transform.rotation = Quaternion.identity;
                var regionObject = new GameObject("native authored region");
                EditorSceneManager.MoveGameObjectToScene(regionObject, F.ActorScene);
                Region = regionObject.AddComponent(T("RegionBinding"));
                F.Floor.name = "Route foundation"; F.Floor.transform.SetParent(regionObject.transform, true);
                Road = F.AddFloor(F.ActorScene, .075f, "Road surface"); Road.transform.SetParent(regionObject.transform, true);
                Road.size = new Vector3(2, .2f, 20);
                Set(Region, "pouncerSupportSurfaces", new[] { F.Floor, Road });
                Capsule = F.Root.AddComponent<CapsuleCollider>(); Capsule.direction = 1;
                Capsule.radius = .36f; Capsule.height = 1.27f; Capsule.center = new Vector3(0, .725f, 0);
                Support = F.Root.AddComponent(T("PouncerGroundSupport"));
                Set(Support, "actor", F.Actor); Set(Support, "paws", F.Constraint); Set(Support, "region", Region);
                F.Root.transform.position = new Vector3(-3, 0, 0); Physics.SyncTransforms();
                BeforePhysics();
                }
                catch (Exception primary)
                {
                    var errors = new List<Exception> { primary }; Cleanup(errors); ThrowFailures(errors); throw;
                }
            }
            internal void BeforePhysics() => EditorPhysicsScope.AssertCollisionDomain(F);
            internal bool Apply(out object report) { BeforePhysics(); return F.Apply(out report); }
            internal BoxCollider Obstacle(Vector3 center, Vector3 size, string name = "unbound solid obstacle")
            {
                var go = new GameObject(name); EditorSceneManager.MoveGameObjectToScene(go, F.ActorScene);
                go.transform.position = center; var box = go.AddComponent<BoxCollider>(); box.size = size;
                Physics.SyncTransforms(); return box;
            }
            internal void CheckPaws()
            {
                Assert.That(Apply(out var report), Is.True, JsonUtility.ToJson(report));
                Assert.That(F.Failed, Is.False);
                Assert.That((float)F.Constraint.GetType().GetField("maxCorrectionMeters").GetValue(F.Constraint), Is.EqualTo(.10f));
                // Independent native BoxCollider raycasts check every baked skin/claw vertex.
                foreach (var renderer in new[] { F.Skin, F.Claws })
                {
                    var mesh = new Mesh();
                    try
                    {
                        renderer.BakeMesh(mesh);
                        foreach (var vertex in mesh.vertices)
                        {
                            var point = renderer.transform.TransformPoint(vertex); float surface = float.NegativeInfinity;
                            foreach (var floor in new[] { F.Floor, Road })
                                if (floor.Raycast(new Ray(point + Vector3.up * 2, Vector3.down), out var hit, 4)) surface = Mathf.Max(surface, hit.point.y);
                            Assert.That(surface, Is.Not.EqualTo(float.NegativeInfinity));
                            Assert.That(point.y - surface, Is.GreaterThanOrEqualTo(-.004f), "Actual finite-surface baked-vertex penetration.");
                        }
                    }
                    finally { UnityEngine.Object.DestroyImmediate(mesh); }
                }
            }
            internal void Cleanup(List<Exception> errors)
            {
                if (disposed) return; disposed = true;
                try { if (F != null) F.Dispose(); } catch (Exception error) { errors.Add(error); }
                scope.Cleanup(errors);
            }
            public void Dispose() { var errors = new List<Exception>(); Cleanup(errors); ThrowFailures(errors); }
        }

        [Test]
        public void FollowsRaisedRoadUpAndDownAtNormalMovementCadence() => FollowRoad(1f / 60);
        [Test]
        public void FollowsRaisedRoadUpAndDownAtLowMovementCadence() => FollowRoad(.1f);
        static void FollowRoad(float dt)
        {
            Run(w => {
                bool high = false, mixed = false;
                while (w.F.Root.transform.position.x < 3)
                {
                    w.F.RewriteRawPose();
                    float delta = Mathf.Min(2.7f * dt, 3 - w.F.Root.transform.position.x);
                    Assert.That(Move(w, Vector3.right * delta, out _, out string reason), Is.True, reason);
                    w.CheckPaws();
                    float x = w.F.Root.transform.position.x, y = w.F.Root.transform.position.y;
                    if (Mathf.Abs(x) < .1f) { Assert.That(y, Is.EqualTo(.075f).Within(.0001f)); high = true; }
                    if (x < -1.1f && y > .07f) mixed = true;
                }
                Assert.That(high, Is.True); Assert.That(mixed, Is.True, "The high-side paw must lift the datum before the root reaches the road.");
                Assert.That(w.F.Root.transform.position.y, Is.EqualTo(0).Within(.0001f));
            });
        }

        [Test]
        public void MixedSoleUsesFiniteHighSideInsteadOfExtrapolatedPawCenterPlane()
        {
            Run(w => {
                // The right-paw center is outside the road; part of the actual sole is inside it.
                float edge = w.F.Foot[1].position.x - w.F.Root.transform.position.x - .03f;
                w.Road.transform.position = new Vector3(-5, -.025f, 0); w.Road.size = new Vector3(2 * (5 + edge), .2f, 20);
                w.F.Root.transform.position = Vector3.zero; Physics.SyncTransforms(); w.CheckPaws();
                Assert.That(w.F.Root.transform.position.y, Is.EqualTo(.075f).Within(.0001f));
            });
        }

        [Test]
        public void SafeDropKeepsFifteenMillimeterRoadClearanceWithoutExtraVerticalLookAhead()
        {
            Run(w => {
                w.Road.transform.position = new Vector3(-5, -.025f, 0); w.Road.size = new Vector3(10, .2f, 20);
                foreach (var upper in w.F.Upper) { var p = upper.localPosition; p.x = 0; upper.localPosition = p; }
                w.F.Root.transform.position = new Vector3(.10f, .075f, 0); Physics.SyncTransforms();
                Assert.That(Move(w, Vector3.zero, out _, out string reason), Is.True, reason);
                Assert.That(w.F.Root.transform.position.y, Is.EqualTo(0).Within(.0001f));
                Assert.That(w.Capsule.bounds.min.y - w.Road.bounds.max.y, Is.EqualTo(.015f).Within(.0001f));
            });
        }

        [Test]
        public void BlocksWallAndCeilingBeforeAnyRootWrite()
        {
            Run(w => {
                var start = w.F.Root.transform.position;
                w.Obstacle(new Vector3(-2.4f, .8f, 0), new Vector3(.1f, 2, 4), "wall");
                Assert.That(Move(w, Vector3.right, out var wall, out _), Is.False);
                Assert.That(wall.name, Is.EqualTo("wall")); Assert.That(w.F.Root.transform.position, Is.EqualTo(start));
                UnityEngine.Object.DestroyImmediate(wall.gameObject);
                w.F.Root.transform.position = new Vector3(-1.6f, 0, 0); start = w.F.Root.transform.position;
                w.Obstacle(new Vector3(-1.6f, 1.41f, 0), new Vector3(2, .04f, 2), "low ceiling");
                Assert.That(Move(w, Vector3.right * .05f, out var ceiling, out _), Is.False);
                Assert.That(ceiling.name, Is.EqualTo("low ceiling")); Assert.That(w.F.Root.transform.position, Is.EqualTo(start));
            });
        }

        [Test]
        public void RejectsExcessiveRiseDropAndMissingSupportTransactionally()
        {
            Run(w => {
                var start = w.F.Root.transform.position;
                w.Road.transform.position += Vector3.up * .2f;
                Assert.That(Move(w, Vector3.right * 3, out _, out string rise), Is.False); StringAssert.Contains("step/drop", rise);
                Assert.That(w.F.Root.transform.position, Is.EqualTo(start));
                w.F.Root.transform.position = new Vector3(-3, .3f, 0); start = w.F.Root.transform.position;
                Assert.That(Move(w, Vector3.zero, out _, out string drop), Is.False); StringAssert.Contains("step/drop", drop);
                Assert.That(w.F.Root.transform.position, Is.EqualTo(start));
                w.F.Root.transform.position = new Vector3(20, 0, 0); start = w.F.Root.transform.position;
                Assert.That(Move(w, Vector3.right * .1f, out _, out string missing), Is.False); StringAssert.Contains("No eligible", missing);
                Assert.That(w.F.Root.transform.position, Is.EqualTo(start));
            });
        }

        [Test]
        public void UnboundPropIsNotSupportAndStillBlocksCapsuleMovement()
        {
            Run(w => {
                var tiny = w.Obstacle(w.F.Foot[0].position + Vector3.up * .07f, new Vector3(.2f, .1f, .2f), "unbound pawn-ray prop");
                w.CheckPaws(); Assert.That(w.F.Root.transform.position.y, Is.EqualTo(0).Within(.0001f));
                UnityEngine.Object.DestroyImmediate(tiny.gameObject);
                var prop = w.Obstacle(new Vector3(-2.4f, .4f, 0), new Vector3(.1f, .6f, .5f));
                var start = w.F.Root.transform.position;
                Assert.That(Move(w, Vector3.right, out var hit, out _), Is.False);
                Assert.That(hit, Is.SameAs(prop)); Assert.That(w.F.Root.transform.position, Is.EqualTo(start));
            });
        }

        [Test]
        public void InvalidDynamicForeignDisabledAndTriggerBindingsFailWithoutWrites()
        {
            Run(w => {
                var start = w.F.Root.transform.position;
                var rb = w.Road.gameObject.AddComponent<Rigidbody>(); rb.isKinematic = true;
                Assert.That(Move(w, Vector3.right * .1f, out _, out _), Is.False); UnityEngine.Object.DestroyImmediate(rb);
                w.Road.isTrigger = true; Assert.That(Move(w, Vector3.right * .1f, out _, out _), Is.False); w.Road.isTrigger = false;
                w.Road.enabled = false; Assert.That(Move(w, Vector3.right * .1f, out _, out _), Is.False); w.Road.enabled = true;
                var foreign = w.F.AddFloor(w.F.CreateOwnedScene(), .4f, "Road surface");
                Set(w.Region, "pouncerSupportSurfaces", new[] { w.F.Floor, foreign });
                Assert.That(Move(w, Vector3.right * .1f, out _, out _), Is.False);
                Assert.That(w.F.Root.transform.position, Is.EqualTo(start));
            });
        }

        [Test]
        public void GentleSlopesMatchNativeBoxFacesAndSteepUnsupportedSlopesReject()
        {
            Run(w => {
                w.Road.size = new Vector3(8, .2f, 20); w.Road.transform.rotation = Quaternion.Euler(0, 0, 5);
                w.F.Root.transform.position = new Vector3(0, .075f, 0); Physics.SyncTransforms();
                float highest = float.NegativeInfinity;
                foreach (var renderer in new[] { w.F.Skin, w.F.Claws })
                {
                    var mesh = new Mesh();
                    try
                    {
                        renderer.BakeMesh(mesh);
                        foreach (var vertex in mesh.vertices)
                        {
                            var point = renderer.transform.TransformPoint(vertex);
                            foreach (var floor in new[] { w.F.Floor, w.Road })
                                if (floor.Raycast(new Ray(point + Vector3.up * 2, Vector3.down), out var hit, 4)) highest = Mathf.Max(highest, hit.point.y);
                        }
                    }
                    finally { UnityEngine.Object.DestroyImmediate(mesh); }
                }
                Assert.That(Move(w, Vector3.zero, out _, out string reason), Is.True, reason);
                Assert.That(w.F.Root.transform.position.y, Is.EqualTo(highest).Within(.0001f));
                w.F.Floor.transform.position += Vector3.right * 100;
                w.Road.transform.rotation = Quaternion.Euler(0, 0, 65); var start = w.F.Root.transform.position;
                Assert.That(Move(w, Vector3.zero, out _, out _), Is.False);
                Assert.That(w.F.Root.transform.position, Is.EqualTo(start));
            });
        }

        [Test]
        public void PausedBoundPoseDoesNotMoveAndSupportFailureRequiresExplicitReset()
        {
            Run(w => {
                w.F.Root.transform.position = Vector3.zero; var start = w.F.Root.transform.position;
                w.F.Animator.speed = 0;
                Assert.That(w.Apply(out var paused), Is.False, JsonUtility.ToJson(paused));
                Assert.That(w.F.Root.transform.position, Is.EqualTo(start)); Assert.That(w.F.Failed, Is.False);
                w.F.Animator.speed = 1; w.CheckPaws();
                w.Road.enabled = false;
                Assert.That(w.Apply(out _), Is.False); Assert.That(w.F.Failed, Is.True);
                w.Road.enabled = true;
                ((Behaviour)w.F.Constraint).enabled = false; ((Behaviour)w.F.Constraint).enabled = true;
                Assert.That(w.Apply(out _), Is.False, "Re-enable alone must not clear the original failure latch.");
                w.F.Reset(); w.F.RewriteRawPose(); w.CheckPaws();
            });
        }

        [Test]
        public void StationarySupportDoesNotTurnExistingBodyContactIntoPawFailure()
        {
            Run(w => {
                w.Obstacle(w.F.Root.transform.position + Vector3.up * .8f, new Vector3(.2f, .2f, .2f));
                var before = w.F.Root.transform.position; w.F.Root.transform.hasChanged = false; w.CheckPaws();
                Assert.That(w.F.Root.transform.position, Is.EqualTo(before)); Assert.That(w.F.Failed, Is.False);
                Assert.That(w.F.Root.transform.hasChanged, Is.False, "Sub-epsilon support jitter must not write the root.");
            });
        }

        [Test]
        public void SuccessfulRootMoveSynchronizesColliderWithoutAutomaticPhysicsSync()
        {
            bool automatic = Physics.autoSyncTransforms;
            try
            {
                Physics.autoSyncTransforms = false;
                Run(w => {
                    Assert.That(Move(w, Vector3.right * 3, out _, out string reason), Is.True, reason);
                    var probe = w.F.Root.transform.position + Vector3.up * .8f + Vector3.left * 2;
                    Assert.That(w.F.ActorPhysics.Raycast(probe, Vector3.right, out var hit, 4, ~0, QueryTriggerInteraction.Ignore), Is.True);
                    Assert.That(hit.collider, Is.SameAs(w.Capsule));
                    Assert.That(w.Capsule.bounds.min.y, Is.EqualTo(w.F.Root.transform.position.y + .09f).Within(.0001f));
                });
            }
            finally { Physics.autoSyncTransforms = automatic; }
        }

        [Test]
        public void DeathKeepsDisabledCapsuleAndResetRestoresGroundedLifecycle()
        {
            Run(w => {
                var owner = new GameObject("session"); EditorSceneManager.MoveGameObjectToScene(owner, w.F.ActorScene);
                var session = owner.AddComponent(T("JourneySession"));
                if (Get<object>(session, "State") == null) Call(session, "Awake");
                Call(session, "StartJourney");
                Set(w.F.Actor, "journey", session);
                var controller = (AnimatorController)w.F.Animator.runtimeAnimatorController;
                var idle = controller.layers[0].stateMachine.defaultState;
                var death = controller.layers[0].stateMachine.AddState("Death"); death.motion = idle.motion;
                w.F.Animator.Rebind(); w.F.Animator.Update(0);
                // The shared skin fixture originally has no capsule. Re-run initialization
                // now that this movement fixture has the same collider ordering as the prefab.
                Set(w.F.Actor, "initialized", false); Call(w.F.Actor, "Awake");
                Call(w.F.Actor, "TakeHit", 1000, Vector3.forward, false);
                Assert.That(Get<bool>(w.F.Actor, "Dead"), Is.True); Assert.That(w.Capsule.enabled, Is.False);
                var before = w.F.Root.transform.position;
                w.F.Animator.Play("Death", 0, 0); w.F.Animator.Update(0); w.CheckPaws();
                Assert.That(w.F.Root.transform.position, Is.EqualTo(before)); Assert.That(w.Capsule.enabled, Is.False);
                Call(w.F.Actor, "ResetActor"); Assert.That(w.Capsule.enabled, Is.True); Assert.That(w.F.Failed, Is.False);
                w.F.Animator.Play("Idle", 0, 0); w.F.Animator.Update(0); w.CheckPaws();
            });
        }
    }
}

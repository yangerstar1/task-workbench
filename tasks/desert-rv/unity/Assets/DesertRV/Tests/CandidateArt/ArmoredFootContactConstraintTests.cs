using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using Unity.Collections;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV.Tests
{
    // Native EditMode fixture source, not a claim of native execution or imported-asset acceptance.
    // Runtime types deliberately use reflection: the candidate-art/EditMode asmdefs have no Assembly-CSharp reference.
    public sealed class ArmoredFootContactConstraintTests
    {
        const float MeasuredMinimum = -.0415903f;
        const float StanceClearance = .005f;
        const float PositionTolerance = .00002f;
        const float LengthTolerance = .0001f;
        const int GroundLayer = 30;
        const BindingFlags All = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static readonly string[] LegIds = { "fore.L", "fore.R", "hind.L", "hind.R" };
        static Type RuntimeType(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static void Set(object target, string name, object value) => target.GetType().GetField(name, All).SetValue(target, value);
        static T Field<T>(object target, string name) => (T)target.GetType().GetField(name, All).GetValue(target);
        static T Property<T>(object target, string name) => (T)target.GetType().GetProperty(name, All).GetValue(target);
        static object Call(object target, string name, params object[] args) => target.GetType().GetMethod(name, All).Invoke(target, args);
        static IList Rows(object report) => Field<IList>(report, "legs");
        static string Diagnostic(object report) => report == null ? "No report returned." : JsonUtility.ToJson(report);
        static Transform Child(string name, Transform parent)
        {
            var go = new GameObject(name);
            EditorSceneManager.MoveGameObjectToScene(go, parent.gameObject.scene);
            go.transform.SetParent(parent, false);
            return go.transform;
        }
        static void SameVector(Vector3 expected, Vector3 actual, string message, float tolerance = PositionTolerance)
        {
            Assert.That(Vector3.Distance(expected, actual), Is.LessThanOrEqualTo(tolerance), message);
        }
        static void SameRotation(Quaternion expected, Quaternion actual, string message)
        {
            // Quaternion.Angle has a near-unity dot rounding band; compare quaternion components,
            // accepting equivalent q/-q representations, to retain sensitivity to tiny changes.
            var a = new Vector4(expected.x, expected.y, expected.z, expected.w);
            var b = new Vector4(actual.x, actual.y, actual.z, actual.w);
            Assert.That(Mathf.Min((a - b).magnitude, (a + b).magnitude), Is.LessThanOrEqualTo(.00002f), message);
        }

        sealed class PoseSnapshot
        {
            readonly Transform[] nodes;
            readonly Vector3[] localPositions, localScales, worldPositions;
            readonly Quaternion[] localRotations, worldRotations;
            readonly float[] upperLengths = new float[4], lowerLengths = new float[4];
            readonly Fixture fixture;
            public PoseSnapshot(Fixture f)
            {
                fixture = f;
                nodes = f.Root.GetComponentsInChildren<Transform>(true);
                localPositions = new Vector3[nodes.Length]; localScales = new Vector3[nodes.Length];
                worldPositions = new Vector3[nodes.Length]; localRotations = new Quaternion[nodes.Length];
                worldRotations = new Quaternion[nodes.Length];
                for (int i = 0; i < nodes.Length; i++)
                {
                    localPositions[i] = nodes[i].localPosition; localScales[i] = nodes[i].localScale;
                    worldPositions[i] = nodes[i].position; localRotations[i] = nodes[i].localRotation;
                    worldRotations[i] = nodes[i].rotation;
                }
                for (int i = 0; i < 4; i++)
                {
                    upperLengths[i] = Vector3.Distance(f.Upper[i].position, f.Lower[i].position);
                    lowerLengths[i] = Vector3.Distance(f.Lower[i].position, f.Foot[i].position);
                }
            }
            public void AssertImmutableTransformsAndLengths()
            {
                for (int i = 0; i < nodes.Length; i++)
                {
                    // Positions and scales are never legitimate outputs of this constraint.
                    Assert.That(nodes[i].localPosition, Is.EqualTo(localPositions[i]), nodes[i].name + " localPosition changed.");
                    Assert.That(nodes[i].localScale, Is.EqualTo(localScales[i]), nodes[i].name + " localScale changed.");
                    if (!fixture.IsLegBone(nodes[i]))
                    {
                        SameRotation(localRotations[i], nodes[i].localRotation, nodes[i].name + " non-leg rotation changed.");
                        SameVector(worldPositions[i], nodes[i].position, nodes[i].name + " non-leg world position changed.");
                        SameRotation(worldRotations[i], nodes[i].rotation, nodes[i].name + " non-leg world rotation changed.");
                    }
                }
                for (int i = 0; i < 4; i++)
                {
                    Assert.That(Vector3.Distance(fixture.Upper[i].position, fixture.Lower[i].position),
                        Is.EqualTo(upperLengths[i]).Within(LengthTolerance), LegIds[i] + " upper length changed.");
                    Assert.That(Vector3.Distance(fixture.Lower[i].position, fixture.Foot[i].position),
                        Is.EqualTo(lowerLengths[i]).Within(LengthTolerance), LegIds[i] + " lower length changed.");
                }
            }
            public void AssertWholePoseUnchanged()
            {
                AssertImmutableTransformsAndLengths();
                for (int i = 0; i < nodes.Length; i++)
                {
                    SameRotation(localRotations[i], nodes[i].localRotation, nodes[i].name + " local rotation was not restored.");
                    SameRotation(worldRotations[i], nodes[i].rotation, nodes[i].name + " world rotation was not restored.");
                    SameVector(worldPositions[i], nodes[i].position, nodes[i].name + " world position was not restored.");
                }
            }
        }

        sealed class Fixture : IDisposable
        {
            public GameObject Root;
            public Component Actor, Constraint;
            public Animator Animator;
            public Transform Rig;
            public readonly Transform[] Upper = new Transform[4], Lower = new Transform[4], Foot = new Transform[4];
            public readonly Quaternion[] RawUpper = new Quaternion[4], RawLower = new Quaternion[4], RawFoot = new Quaternion[4];
            public SkinnedMeshRenderer Skin;
            public Mesh Source;
            public BoxCollider Floor;
            public Scene ActorScene;
            public PhysicsScene ActorPhysics => ActorScene.GetPhysicsScene();
            public string PhysicsDiagnostic(Scene otherScene = default)
            {
                string actor = "actorSceneHandle=" + ActorScene.handle + "; actorPhysics=" + ActorPhysics +
                    "; actorPhysicsEqualsDefault=" + ActorPhysics.Equals(Physics.defaultPhysicsScene);
                if (!otherScene.IsValid()) return actor;
                return actor + "; otherSceneHandle=" + otherScene.handle +
                    "; sceneHandlesEqual=" + (ActorScene.handle == otherScene.handle) +
                    "; otherPhysics=" + otherScene.GetPhysicsScene() +
                    "; physicsHandlesEqual=" + ActorPhysics.Equals(otherScene.GetPhysicsScene()) +
                    "; otherPhysicsEqualsDefault=" + otherScene.GetPhysicsScene().Equals(Physics.defaultPhysicsScene);
            }
            readonly List<Scene> ownedScenes = new List<Scene>();
            readonly Scene originalActive;
            readonly string controllerPath = "Assets/__ArmoredFootNative_" + Guid.NewGuid().ToString("N") + ".controller";
            AnimationClip clip;
            bool disposed;
            int rawPoseEvaluation;

            public Fixture(bool nonuniformAncestor = false, bool withFloor = true)
            {
                originalActive = SceneManager.GetActiveScene();
                try
                {
                    ActorScene = CreateOwnedScene();
                    Assert.That(ActorPhysics.IsValid(), Is.True, "Fixture requires a valid owning PhysicsScene. " + PhysicsDiagnostic());
                    Root = new GameObject("native armored foot actor"); Root.SetActive(false);
                    EditorSceneManager.MoveGameObjectToScene(Root, ActorScene);
                    Root.transform.localRotation = Quaternion.Euler(0, 17, 0);
                    Actor = Root.AddComponent(RuntimeType("BeastActor"));
                    ((Behaviour)Actor).enabled = false; Set(Actor, "armored", true);
                    Rig = Child("Rig", Root.transform);
                    Rig.localScale = nonuniformAncestor ? new Vector3(2, 1, 1) : Vector3.one;
                    var legType = RuntimeType("ArmoredFootContactConstraint+Leg");
                    var bindings = Array.CreateInstance(legType, 4);
                    for (int i = 0; i < 4; i++)
                    {
                        Upper[i] = Child("upper_" + i, Rig);
                        Lower[i] = Child("lower_" + i, Upper[i]);
                        Foot[i] = Child("foot_" + i, Lower[i]);
                        RawUpper[i] = Quaternion.Euler(0, 0, 12);
                        RawLower[i] = Quaternion.Euler(0, 0, -24);
                        RawFoot[i] = Quaternion.Euler(0, 0, 12);
                        Upper[i].localRotation = RawUpper[i]; Lower[i].localRotation = RawLower[i]; Foot[i].localRotation = RawFoot[i];
                        Lower[i].localPosition = new Vector3(.3f, -.5f, 0);
                        Foot[i].localPosition = new Vector3(-.3f, -.5f, 0);
                        var displacement = RawUpper[i] * Lower[i].localPosition + RawUpper[i] * RawLower[i] * Foot[i].localPosition;
                        Upper[i].localPosition = new Vector3(i % 2 == 0 ? -.75f : .75f, -displacement.y, i < 2 ? .65f : -.65f);
                        var leg = Activator.CreateInstance(legType);
                        Set(leg, "id", LegIds[i]); Set(leg, "upper", Upper[i]); Set(leg, "lower", Lower[i]); Set(leg, "foot", Foot[i]);
                        bindings.SetValue(leg, i);
                    }
                    Skin = Child("Body", Root.transform).gameObject.AddComponent<SkinnedMeshRenderer>();
                    Skin.rootBone = Rig; Skin.updateWhenOffscreen = true;
                    var bones = new Transform[8];
                    Array.Copy(Foot, bones, 4);
                    for (int i = 4; i < bones.Length; i++) bones[i] = Child("nonfoot_influence_" + i, Rig);
                    Skin.bones = bones;
                    BuildActualMesh();
                    var controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
                    clip = new AnimationClip { name = "Idle keyed raw bone pose", frameRate = 60 };
                    for (int i = 0; i < 4; i++)
                    {
                        KeyRotation(Upper[i], RawUpper[i]); KeyRotation(Lower[i], RawLower[i]); KeyRotation(Foot[i], RawFoot[i]);
                    }
                    clip.EnsureQuaternionContinuity();
                    var rotationBindings = AnimationUtility.GetCurveBindings(clip);
                    Assert.That(rotationBindings.Length, Is.EqualTo(4 * 3 * 4), "All twelve leg bones need four quaternion channels.");
                    foreach (var binding in rotationBindings)
                    {
                        var curve = AnimationUtility.GetEditorCurve(clip, binding);
                        Assert.That(curve.length, Is.EqualTo(5), binding.path + "/" + binding.propertyName);
                        Assert.That(Mathf.Abs(curve.Evaluate(0) - curve.Evaluate(.25f)), Is.GreaterThan(.0001f),
                            "Each channel must be animated, not optimized into a constant: " + binding.path + "/" + binding.propertyName);
                    }
                    AssetDatabase.AddObjectToAsset(clip, controller);
                    var state = controller.layers[0].stateMachine.AddState("Idle");
                    state.motion = clip; state.writeDefaultValues = false;
                    controller.layers[0].stateMachine.defaultState = state;
                    Animator = Root.AddComponent<Animator>();
                    Animator.runtimeAnimatorController = controller;
                    Animator.applyRootMotion = false; Animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
                    Set(Actor, "animator", Animator);
                    Constraint = Root.AddComponent(RuntimeType("ArmoredFootContactConstraint"));
                    ((Behaviour)Constraint).enabled = false; // Invoke the production entry point explicitly; no Editor timing dependency.
                    Set(Constraint, "actor", Actor); Set(Constraint, "animator", Animator);
                    Set(Constraint, "bodyRenderer", Skin); Set(Constraint, "legs", bindings);
                    Set(Constraint, "groundMask", (LayerMask)(1 << GroundLayer));
                    Set(Constraint, "maxCorrectionMeters", .20f);
                    if (withFloor) Floor = AddFloor(ActorScene, 0, "actual actor-scene floor");
                    Root.SetActive(true);
                    Animator.Rebind(); RewriteRawPose();
                    Physics.SyncTransforms();
                    for (int i = 0; i < 4; i++)
                    {
                        Assert.That(Lower[i].parent, Is.SameAs(Upper[i]));
                        Assert.That(Foot[i].parent, Is.SameAs(Lower[i]));
                    }
                    AssertRawNativeGeometry();
                }
                catch { Dispose(); throw; }
            }
            public Scene CreateOwnedScene()
            {
                // Preview scenes avoid changing/saving the caller's untitled active scene.
                // Both owners contain real colliders; neither PhysicsScene handle is assumed.
                var scene = EditorSceneManager.NewPreviewScene();
                ownedScenes.Add(scene);
                return scene;
            }
            public BoxCollider AddFloor(Scene scene, float top, string name)
            {
                var go = new GameObject(name); EditorSceneManager.MoveGameObjectToScene(go, scene);
                go.layer = GroundLayer; go.transform.position = new Vector3(0, top - .1f, 0);
                var collider = go.AddComponent<BoxCollider>(); collider.size = new Vector3(20, .2f, 20);
                Physics.SyncTransforms(); return collider;
            }
            void KeyRotation(Transform bone, Quaternion rotation)
            {
                string path = AnimationUtility.CalculateTransformPath(bone, Root.transform);
                string[] channels = { "x", "y", "z", "w" };
                float[] values = { rotation.x, rotation.y, rotation.z, rotation.w };
                var moving = rotation * Quaternion.Euler(7, 9, 11);
                float[] movingValues = { moving.x, moving.y, moving.z, moving.w };
                for (int i = 0; i < channels.Length; i++)
                    AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve(path, typeof(Transform), "m_LocalRotation." + channels[i]),
                        new AnimationCurve(new Keyframe(0, movingValues[i]), new Keyframe(.25f, values[i]),
                            new Keyframe(.5f, movingValues[i]), new Keyframe(.75f, values[i]),
                            new Keyframe(1, movingValues[i])));
            }
            void BuildActualMesh()
            {
                var vertices = new Vector3[32]; var triangles = new List<int>();
                var bindposes = new Matrix4x4[Skin.bones.Length];
                for (int i = 0; i < bindposes.Length; i++) bindposes[i] = Skin.bones[i].worldToLocalMatrix * Skin.transform.localToWorldMatrix;
                int[] cube = { 0, 2, 1, 1, 2, 3, 4, 5, 6, 5, 7, 6, 0, 1, 4, 1, 5, 4, 2, 6, 3, 3, 6, 7, 0, 4, 2, 2, 4, 6, 1, 3, 5, 3, 7, 5 };
                for (int leg = 0; leg < 4; leg++)
                {
                    for (int corner = 0; corner < 8; corner++)
                    {
                        var footLocal = new Vector3((corner & 1) == 0 ? -.09f : .09f,
                            corner < 4 ? MeasuredMinimum : .045f, (corner & 2) == 0 ? -.13f : .13f);
                        vertices[leg * 8 + corner] = Skin.transform.InverseTransformPoint(Foot[leg].TransformPoint(footLocal));
                    }
                    foreach (int index in cube) triangles.Add(leg * 8 + index);
                }
                Source = new Mesh { name = "four actual rigid foot boxes with native bindposes" };
                Source.vertices = vertices; Source.triangles = triangles.ToArray(); Source.bindposes = bindposes;
                Source.RecalculateNormals(); Source.RecalculateBounds(); Skin.sharedMesh = Source;
                SetNativeWeights(false);
            }
            public void SetNativeWeights(bool hiddenFifthFootInfluence)
            {
                var counts = new byte[Source.vertexCount]; var weights = new List<BoneWeight1>();
                for (int vertex = 0; vertex < Source.vertexCount; vertex++)
                {
                    if (hiddenFifthFootInfluence && vertex == 0)
                    {
                        // The foot influence is FIFTH, after four larger non-foot influences. A legacy
                        // Mesh.boneWeights scan would miss this mixed vertex and still find seven foot vertices.
                        counts[vertex] = 5;
                        // Integer UNorm16 numerators sum to 65535, so native weight quantization
                        // cannot turn this test into an unrelated normalization rejection.
                        for (int bone = 4; bone < 8; bone++) weights.Add(new BoneWeight1 { boneIndex = bone, weight = 15728f / 65535f });
                        weights.Add(new BoneWeight1 { boneIndex = 0, weight = 2623f / 65535f });
                    }
                    else
                    {
                        counts[vertex] = 1;
                        weights.Add(new BoneWeight1 { boneIndex = vertex / 8, weight = 1 });
                    }
                }
                using (var nativeCounts = new NativeArray<byte>(counts, Allocator.Temp))
                using (var nativeWeights = new NativeArray<BoneWeight1>(weights.ToArray(), Allocator.Temp))
                    Source.SetBoneWeights(nativeCounts, nativeWeights);
            }
            public bool Validate(out string reason)
            {
                object[] args = { null }; bool result = (bool)Call(Constraint, "ValidateBindings", args);
                reason = (string)args[0]; return result;
            }
            public bool Apply(out object report)
            {
                object[] args = { null }; bool result = (bool)Call(Constraint, "ApplyFootContact", args);
                report = args[0]; return result;
            }
            public void Reset() => Call(Constraint, "ResetContactState");
            public bool Failed => Property<bool>(Constraint, "HasFailure");
            public void RewriteRawPose()
            {
                Animator.speed = 1;
                // Vary every quaternion channel and advance real Animator time. Constant curves
                // plus repeatedly evaluating the same time can retain a post-animation edit.
                float targetTime = (++rawPoseEvaluation % 2 == 1) ? .25f : .75f;
                const float frameDelta = 1f / 60f;
                Animator.Play("Idle", 0, targetTime - frameDelta);
                Animator.Update(0); // Establish the Play request before advancing the next evaluation.
                Animator.Update(frameDelta);
                Assert.That(Animator.GetCurrentAnimatorStateInfo(0).normalizedTime,
                    Is.EqualTo(targetTime).Within(.00001f), "Animator must advance to the keyed raw pose.");
                Assert.That(Animator.GetCurrentAnimatorStateInfo(0).shortNameHash, Is.EqualTo(UnityEngine.Animator.StringToHash("Idle")),
                    "A genuine Animator state must be evaluated, not a fabricated state label.");
                Assert.That(Animator.IsInTransition(0), Is.False);
                for (int i = 0; i < 4; i++)
                {
                    SameRotation(RawUpper[i], Upper[i].localRotation, LegIds[i] + " Animator upper rewrite missing.");
                    SameRotation(RawLower[i], Lower[i].localRotation, LegIds[i] + " Animator lower rewrite missing.");
                    SameRotation(RawFoot[i], Foot[i].localRotation, LegIds[i] + " Animator foot rewrite missing.");
                }
            }
            public float[] BakedMinimums()
            {
                var baked = new Mesh();
                try
                {
                    Skin.BakeMesh(baked);
                    var vertices = baked.vertices;
                    Assert.That(vertices.Length, Is.EqualTo(32), "Native skin bake must retain all actual fixture vertices.");
                    var minimums = new[] { float.PositiveInfinity, float.PositiveInfinity, float.PositiveInfinity, float.PositiveInfinity };
                    for (int i = 0; i < vertices.Length; i++)
                        minimums[i / 8] = Mathf.Min(minimums[i / 8], Skin.transform.TransformPoint(vertices[i]).y);
                    return minimums;
                }
                finally { UnityEngine.Object.DestroyImmediate(baked); }
            }
            public void AssertRawNativeGeometry()
            {
                var minimums = BakedMinimums();
                for (int i = 0; i < 4; i++)
                    Assert.That(minimums[i], Is.EqualTo(MeasuredMinimum).Within(PositionTolerance), LegIds[i] + " native raw sole must reproduce the measured violation.");
            }
            public bool IsLegBone(Transform transform)
            {
                return Array.IndexOf(Upper, transform) >= 0 || Array.IndexOf(Lower, transform) >= 0 || Array.IndexOf(Foot, transform) >= 0;
            }
            public void ClearTransformChangedFlags()
            {
                foreach (var node in Root.GetComponentsInChildren<Transform>(true)) node.hasChanged = false;
            }
            public void AssertNoTransformWrites()
            {
                foreach (var node in Root.GetComponentsInChildren<Transform>(true))
                    Assert.That(node.hasChanged, Is.False, node.name + " received a Transform write.");
            }
            public void AssertOwnFloorIsQueryable()
            {
                Physics.SyncTransforms();
                string diagnostic = PhysicsDiagnostic();
                Assert.That(Floor, Is.Not.Null, "The fixture must provide an actual collider. " + diagnostic);
                Assert.That(Floor.gameObject.scene, Is.EqualTo(ActorScene), diagnostic);
                var hits = new RaycastHit[32];
                for (int i = 0; i < 4; i++)
                {
                    int count = ActorPhysics.Raycast(Foot[i].position + Vector3.up * .5f, Vector3.down,
                        hits, 1.5f, 1 << GroundLayer, QueryTriggerInteraction.Ignore);
                    Assert.That(count, Is.LessThan(hits.Length), "Native query must not be truncated. " + diagnostic);
                    bool foundOwnedFloor = false;
                    for (int hitIndex = 0; hitIndex < count; hitIndex++)
                    {
                        var hit = hits[hitIndex];
                        if (hit.collider != Floor) continue;
                        Assert.That(hit.collider.gameObject.scene, Is.EqualTo(ActorScene), diagnostic);
                        Assert.That(hit.point.y, Is.EqualTo(0).Within(PositionTolerance), diagnostic);
                        foundOwnedFloor = true;
                    }
                    Assert.That(foundOwnedFloor, Is.True, LegIds[i] + " owning PhysicsScene must actually return its scene-owned floor. " + diagnostic);
                }
            }
            public void Dispose()
            {
                if (disposed) return; disposed = true;
                if (Root) UnityEngine.Object.DestroyImmediate(Root);
                if (Source) UnityEngine.Object.DestroyImmediate(Source);
                if (!string.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(controllerPath))) AssetDatabase.DeleteAsset(controllerPath);
                else if (clip) UnityEngine.Object.DestroyImmediate(clip);
                if (originalActive.IsValid() && originalActive.isLoaded) SceneManager.SetActiveScene(originalActive);
                for (int i = ownedScenes.Count - 1; i >= 0; i--)
                {
                    var scene = ownedScenes[i];
                    if (!scene.IsValid() || !scene.isLoaded) continue;
                    if (EditorSceneManager.IsPreviewScene(scene)) EditorSceneManager.ClosePreviewScene(scene);
                    else EditorSceneManager.CloseScene(scene, true);
                }
            }
        }

        static void AssertCorrected(Fixture f, object report)
        {
            Assert.That(Field<bool>(report, "valid"), Is.True, Diagnostic(report));
            Assert.That(Rows(report).Count, Is.EqualTo(4));
            var actualMinimums = f.BakedMinimums();
            for (int i = 0; i < 4; i++)
            {
                var row = Rows(report)[i];
                Assert.That(Field<string>(row, "id"), Is.EqualTo(LegIds[i]));
                Assert.That(Field<string>(row, "sourceState"), Is.EqualTo("Idle"));
                Assert.That(Field<string>(row, "destinationState"), Is.EqualTo("Idle"));
                Assert.That(Field<bool>(row, "sourceAirborne"), Is.False);
                Assert.That(Field<bool>(row, "destinationAirborne"), Is.False);
                Assert.That(Field<bool>(row, "valid"), Is.True, Diagnostic(report));
                Assert.That(Field<bool>(row, "corrected"), Is.True, Diagnostic(report));
                Assert.That(Field<float>(row, "preMinDistance"), Is.EqualTo(MeasuredMinimum).Within(PositionTolerance));
                Assert.That(Field<float>(row, "correctionMeters"), Is.EqualTo(StanceClearance - MeasuredMinimum).Within(PositionTolerance));
                Assert.That(Field<float>(row, "postMinDistance"), Is.EqualTo(StanceClearance).Within(LengthTolerance * 2));
                Assert.That(actualMinimums[i], Is.EqualTo(StanceClearance).Within(LengthTolerance * 2),
                    LegIds[i] + " actual native skin result disagrees with the report.");
                Assert.That(actualMinimums[i], Is.GreaterThanOrEqualTo(-.004f));
                Assert.That(Field<Vector3>(row, "groundPoint").y, Is.EqualTo(0).Within(PositionTolerance));
            }
            Assert.That(Field<bool>(report, "fullMeshValidated"), Is.False, "Foot-only correction cannot certify the whole armor mesh.");
            Assert.That(Field<bool>(report, "slipValidated"), Is.False);
            Assert.That(Field<bool>(report, "swingArcValidated"), Is.False);
        }

        [Test]
        public void CorrectsMeasuredFortyOneMillimeterViolationByRotation()
        {
            using (var f = new Fixture())
            {
                f.AssertOwnFloorIsQueryable();
                Assert.That(f.Validate(out var reason), Is.True, reason);
                var raw = new PoseSnapshot(f);
                var footRotations = new Quaternion[4];
                for (int i = 0; i < 4; i++) footRotations[i] = f.Foot[i].rotation;
                Assert.That(f.Apply(out var report), Is.True, Diagnostic(report));
                AssertCorrected(f, report); raw.AssertImmutableTransformsAndLengths();
                for (int i = 0; i < 4; i++)
                {
                    Assert.That(Quaternion.Angle(f.RawUpper[i], f.Upper[i].localRotation), Is.GreaterThan(.1f), LegIds[i] + " upper never rotated.");
                    Assert.That(Quaternion.Angle(f.RawLower[i], f.Lower[i].localRotation), Is.GreaterThan(.1f), LegIds[i] + " lower never rotated.");
                    SameRotation(footRotations[i], f.Foot[i].rotation, LegIds[i] + " world sole orientation changed.");
                }
                Assert.That(f.Failed, Is.False);
            }
        }

        [Test]
        public void FailedPostSolveRestoresWholeLegRotations()
        {
            using (var f = new Fixture(nonuniformAncestor: true))
            {
                f.AssertOwnFloorIsQueryable();
                Assert.That(f.Validate(out var reason), Is.True, "The genuine nonuniform hierarchy must reach the post-write guard: " + reason);
                var raw = new PoseSnapshot(f); f.ClearTransformChangedFlags();
                Assert.That(f.Apply(out var report), Is.False, Diagnostic(report));
                Assert.That(Rows(report).Count, Is.EqualTo(4));
                for (int i = 0; i < 4; i++)
                {
                    var row = Rows(report)[i];
                    StringAssert.Contains("Post-solve", Field<string>(row, "reason"), "Must exercise post-write rollback, not an earlier refusal.");
                    Assert.That(Field<bool>(row, "valid"), Is.False);
                    Assert.That(Field<bool>(row, "corrected"), Is.False);
                    Assert.That(f.Upper[i].hasChanged, Is.True, "A real rotation attempt must occur before rollback.");
                    Assert.That(float.IsNaN(Field<float>(row, "attemptedPostMinDistance")), Is.False);
                    Assert.That(Mathf.Abs(Field<float>(row, "attemptedPostMinDistance") - Field<float>(row, "preMinDistance")),
                        Is.GreaterThan(.0001f), "Attempted geometry must differ before it is rolled back.");
                    Assert.That(Field<float>(row, "postMinDistance"), Is.EqualTo(MeasuredMinimum).Within(PositionTolerance));
                }
                raw.AssertWholePoseUnchanged(); f.AssertRawNativeGeometry();
                Assert.That(f.Failed, Is.True);
            }
        }

        [Test]
        public void RepeatedSamePoseDoesNotAccumulateCorrection()
        {
            using (var f = new Fixture())
            {
                Assert.That(f.Apply(out var first), Is.True, Diagnostic(first)); AssertCorrected(f, first);
                var solved = new PoseSnapshot(f);
                Assert.That(Field<object>(f.Constraint, "lastCorrectionReport"), Is.SameAs(first));
                for (int repeat = 0; repeat < 25; repeat++)
                {
                    f.ClearTransformChangedFlags();
                    Assert.That(f.Apply(out var report), Is.True, Diagnostic(report));
                    foreach (object row in Rows(report))
                    {
                        Assert.That(Field<bool>(row, "corrected"), Is.False, "An already solved pose must not receive an additional correction.");
                        Assert.That(Field<float>(row, "preMinDistance"), Is.EqualTo(StanceClearance).Within(LengthTolerance * 2));
                    }
                    solved.AssertWholePoseUnchanged(); f.AssertNoTransformWrites();
                    Assert.That(Field<object>(f.Constraint, "lastCorrectionReport"), Is.SameAs(first), "The raw failure-height witness must survive harmless repeats.");
                }
                foreach (float minimum in f.BakedMinimums()) Assert.That(minimum, Is.EqualTo(StanceClearance).Within(LengthTolerance * 2));
            }
        }

        [Test]
        public void PauseDoesNotWriteAndAnimatorRewriteCanBeCorrectedAgain()
        {
            using (var f = new Fixture())
            {
                var raw = new PoseSnapshot(f); f.Animator.speed = 0; f.ClearTransformChangedFlags();
                Assert.That(f.Apply(out var pausedRaw), Is.False);
                Assert.That(Field<bool>(pausedRaw, "paused"), Is.True); Assert.That(Field<bool>(pausedRaw, "valid"), Is.False);
                Assert.That(Rows(pausedRaw), Is.Empty); raw.AssertWholePoseUnchanged(); f.AssertNoTransformWrites();
                Assert.That(f.Failed, Is.False, "A paused non-sample must not latch a failure.");
                f.Animator.speed = 1;
                Assert.That(f.Apply(out var first), Is.True, Diagnostic(first)); AssertCorrected(f, first);
                var solved = new PoseSnapshot(f); f.Animator.speed = 0; f.ClearTransformChangedFlags();
                Assert.That(f.Apply(out var pausedSolved), Is.False);
                Assert.That(Field<bool>(pausedSolved, "paused"), Is.True); solved.AssertWholePoseUnchanged(); f.AssertNoTransformWrites();
                Assert.That(Field<object>(f.Constraint, "lastReport"), Is.SameAs(first), "Pause must not replace the last actual validation sample.");
                Assert.That(Field<object>(f.Constraint, "lastCorrectionReport"), Is.SameAs(first));
                f.RewriteRawPose(); // Actual Animator.Update evaluates the keyed raw rotations, not a manual transform reset.
                f.AssertRawNativeGeometry();
                var rewritten = new PoseSnapshot(f);
                Assert.That(f.Apply(out var second), Is.True, Diagnostic(second)); AssertCorrected(f, second);
                rewritten.AssertImmutableTransformsAndLengths();
                solved.AssertWholePoseUnchanged();
                Assert.That(Field<object>(f.Constraint, "lastCorrectionReport"), Is.SameAs(second));
            }
        }

        [Test]
        public void FailureRemainsLatchedUntilExplicitReset()
        {
            using (var f = new Fixture())
            {
                f.Floor.enabled = false; Physics.SyncTransforms();
                var raw = new PoseSnapshot(f);
                Assert.That(f.Apply(out var missingGround), Is.False, Diagnostic(missingGround));
                Assert.That(f.Failed, Is.True); raw.AssertWholePoseUnchanged();
                foreach (object row in Rows(missingGround)) StringAssert.Contains("No supported actual ground", Field<string>(row, "reason"));
                f.Floor.enabled = true; f.AssertOwnFloorIsQueryable();
                Assert.That(f.Apply(out var recoveredGeometry), Is.False, "Valid geometry must not erase an earlier failed sample.");
                Assert.That(Field<bool>(recoveredGeometry, "valid"), Is.False);
                StringAssert.Contains("prior failure", Field<string>(recoveredGeometry, "reason"));
                foreach (object row in Rows(recoveredGeometry)) Assert.That(Field<bool>(row, "valid"), Is.True);
                Assert.That(f.Failed, Is.True);
                Assert.That(f.Apply(out var repeated), Is.False); Assert.That(f.Failed, Is.True);
                StringAssert.Contains("prior failure", Field<string>(repeated, "reason"));
                f.Reset();
                Assert.That(f.Failed, Is.False); Assert.That(Field<object>(f.Constraint, "lastReport"), Is.Null);
                Assert.That(Field<object>(f.Constraint, "lastCorrectionReport"), Is.Null);
                f.RewriteRawPose(); f.AssertRawNativeGeometry();
                Assert.That(f.Apply(out var resetReport), Is.True, Diagnostic(resetReport)); AssertCorrected(f, resetReport);
                Assert.That(f.Failed, Is.False);
            }
        }

        [Test]
        public void RejectsMoreThanFourFootInfluences()
        {
            using (var f = new Fixture())
            {
                f.SetNativeWeights(true);
                // These are borrowed native mesh views; only the Allocator.Temp inputs in SetNativeWeights are disposed.
                var counts = f.Source.GetBonesPerVertex(); var weights = f.Source.GetAllBoneWeights();
                Assert.That(counts.Length, Is.EqualTo(f.Source.vertexCount));
                Assert.That(counts[0], Is.EqualTo(5), "Native input must really retain more than four influences.");
                Assert.That(weights.Length, Is.EqualTo(f.Source.vertexCount + 4));
                for (int i = 0; i < 4; i++)
                {
                    Assert.That(weights[i].boneIndex, Is.InRange(4, 7));
                    Assert.That(weights[i].weight, Is.GreaterThan(0));
                }
                Assert.That(weights[4].boneIndex, Is.EqualTo(0), "Foot ownership must be hidden beyond the legacy four-weight view.");
                Assert.That(weights[4].weight, Is.GreaterThan(0));
                float nativeTotal = 0;
                for (int i = 0; i < counts[0]; i++) nativeTotal += weights[i].weight;
                Assert.That(nativeTotal, Is.EqualTo(1).Within(.00001f), "The full native input must remain normalized.");
                var pose = new PoseSnapshot(f);
                Assert.That(f.Validate(out var reason), Is.False, "A positive fifth foot influence makes this vertex non-rigid.");
                StringAssert.Contains("full-stream influences", reason, "Reject the actual mixed foot weights, not another binding condition.");
                Assert.That(f.Apply(out var report), Is.False, Diagnostic(report));
                Assert.That(f.Failed, Is.True); Assert.That(Field<bool>(report, "valid"), Is.False);
                pose.AssertWholePoseUnchanged();
            }
        }

        [Test]
        public void UsesActorPhysicsSceneAndRejectsOtherSceneGround()
        {
            using (var f = new Fixture(withFloor: false))
            {
                var wrongScene = f.CreateOwnedScene();
                string physicsDiagnostic = f.PhysicsDiagnostic(wrongScene);
                Assert.That(wrongScene.handle, Is.Not.EqualTo(f.ActorScene.handle), physicsDiagnostic);
                Assert.That(wrongScene.GetPhysicsScene().IsValid(), Is.True, physicsDiagnostic);
                var wrongFloor = f.AddFloor(wrongScene, .15f, "wrong-scene higher floor");
                var origin = f.Foot[0].position + Vector3.up * .5f;
                Assert.That(wrongScene.GetPhysicsScene().Raycast(origin, Vector3.down, out var wrongHit, 1.5f, 1 << GroundLayer, QueryTriggerInteraction.Ignore),
                    Is.True, "The foreign-scene decoy must be physically queryable. " + physicsDiagnostic);
                Assert.That(wrongHit.collider, Is.SameAs(wrongFloor), "The foreign scene must contain a real tempting hit. " + physicsDiagnostic);
                var actorHits = new RaycastHit[32];
                int actorCount = f.ActorPhysics.Raycast(origin, Vector3.down, actorHits, 1.5f, 1 << GroundLayer, QueryTriggerInteraction.Ignore);
                Assert.That(actorCount, Is.LessThan(actorHits.Length), physicsDiagnostic);
                bool actorQuerySeesWrongFloor = false;
                for (int i = 0; i < actorCount; i++) if (actorHits[i].collider == wrongFloor) actorQuerySeesWrongFloor = true;
                // When handles are shared, this intentionally proves scene filtering within a shared
                // hit set. When distinct, it also proves native query isolation. Neither is presumed.
                Assert.That(actorQuerySeesWrongFloor, Is.EqualTo(f.ActorPhysics.Equals(wrongScene.GetPhysicsScene())), physicsDiagnostic);
                var raw = new PoseSnapshot(f);
                Assert.That(f.Apply(out var wrongOnly), Is.False, "A collider in another scene must not provide support. " + physicsDiagnostic);
                Assert.That(Rows(wrongOnly).Count, Is.EqualTo(4), physicsDiagnostic);
                foreach (object row in Rows(wrongOnly)) StringAssert.Contains("No supported actual ground", Field<string>(row, "reason"), physicsDiagnostic);
                raw.AssertWholePoseUnchanged();
                f.Floor = f.AddFloor(f.ActorScene, 0, "actual actor-scene floor");
                f.AssertOwnFloorIsQueryable(); f.Reset(); f.RewriteRawPose();
                Assert.That(wrongScene.GetPhysicsScene().Raycast(origin, Vector3.down, out wrongHit, 1.5f, 1 << GroundLayer, QueryTriggerInteraction.Ignore), Is.True, physicsDiagnostic);
                Assert.That(wrongHit.collider, Is.SameAs(wrongFloor), "Keep the wrong higher ground present while the actor-scene solve succeeds. " + physicsDiagnostic);
                Assert.That(f.Apply(out var ownGround), Is.True, Diagnostic(ownGround) + "; " + physicsDiagnostic); AssertCorrected(f, ownGround);
                raw.AssertImmutableTransformsAndLengths();
                foreach (object row in Rows(ownGround))
                    Assert.That(Field<Vector3>(row, "groundPoint").y, Is.EqualTo(0).Within(PositionTolerance),
                        "Support must come from the actor's scene-owned collider. " + physicsDiagnostic);
            }
        }
    }
}

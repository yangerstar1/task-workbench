using NUnit.Framework;
using UnityEngine;

namespace CIProof
{
    public sealed class NativeProofTests
    {
        [Test]
        public void EditorVersionIsPinned()
        {
            Assert.That(Application.unityVersion, Is.EqualTo("6000.3.19f1"));
        }

        [Test]
        public void TransformHierarchyPreservesExpectedWorldPosition()
        {
            var parent = new GameObject("Test parent");
            var child = new GameObject("Test child");
            try
            {
                child.transform.SetParent(parent.transform, false);
                parent.transform.position = new Vector3(2f, 0f, 0f);
                parent.transform.rotation = Quaternion.Euler(0f, 90f, 0f);
                child.transform.localPosition = Vector3.forward;
                Assert.That(Vector3.Distance(child.transform.position, new Vector3(3f, 0f, 0f)),
                    Is.LessThan(0.00001f));
            }
            finally { Object.DestroyImmediate(child); Object.DestroyImmediate(parent); }
        }

        [Test]
        public void NativeColliderRaycastHitsExpectedSurface()
        {
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            try
            {
                cube.transform.position = Vector3.zero;
                Physics.SyncTransforms();
                RaycastHit hit;
                Assert.That(cube.GetComponent<Collider>().Raycast(
                    new Ray(new Vector3(0f, 0f, -3f), Vector3.forward), out hit, 5f), Is.True);
                Assert.That(hit.distance, Is.EqualTo(2.5f).Within(0.0001f));
            }
            finally { Object.DestroyImmediate(cube); }
        }

        [Test]
        public void NativeAnimationSamplesIntermediatePose()
        {
            var target = new GameObject("Animation proof");
            var clip = new AnimationClip { legacy = true };
            try
            {
                clip.SetCurve("", typeof(Transform), "localPosition.x",
                    AnimationCurve.Linear(0f, 0f, 1f, 2f));
                clip.SampleAnimation(target, 0.25f);
                Assert.That(target.transform.localPosition.x, Is.EqualTo(0.5f).Within(0.00001f));
            }
            finally { Object.DestroyImmediate(clip); Object.DestroyImmediate(target); }
        }
    }
}

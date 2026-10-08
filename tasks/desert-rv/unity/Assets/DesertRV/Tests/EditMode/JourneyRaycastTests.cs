using System;
using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class JourneyRaycastTests
    {
        readonly List<GameObject> objects = new List<GameObject>();
        // Far from authored scenes; all objects are removed even if an assertion fails.
        static readonly Vector3 Origin = new Vector3(10000, 20000, 30000);
        Type raycasts;

        [SetUp]
        public void SetUp()
        {
            raycasts = Type.GetType("DesertRV.JourneyRaycast, Assembly-CSharp", true);
        }

        [TearDown]
        public void TearDown()
        {
            foreach (var obj in objects) if (obj) UnityEngine.Object.DestroyImmediate(obj);
            objects.Clear();
            Physics.SyncTransforms();
        }

        BoxCollider Box(string name, float z, float depth = .2f)
        {
            var obj = new GameObject(name);
            objects.Add(obj);
            obj.transform.position = Origin + Vector3.forward * z;
            var collider = obj.AddComponent<BoxCollider>();
            collider.size = new Vector3(1, 1, depth);
            return collider;
        }

        bool Cast(Collider self, float distance, out RaycastHit hit)
        {
            Physics.SyncTransforms();
            object[] args = { Origin, Vector3.forward, distance, self, default(RaycastHit) };
            bool found = (bool)raycasts.GetMethod("TryFirstHit").Invoke(null, args);
            hit = (RaycastHit)args[4];
            return found;
        }

        bool Reach(float z, Collider self, Collider target)
        {
            Physics.SyncTransforms();
            return (bool)raycasts.GetMethod("CanReachPoint").Invoke(null,
                new object[] { Origin, Origin + Vector3.forward * z, self, target });
        }

        [Test]
        public void ExactControllerIsSkippedButAnotherControllerStillBlocks()
        {
            var obj = new GameObject("Journey walker"); objects.Add(obj);
            obj.transform.position = Origin + Vector3.forward;
            var self = obj.AddComponent<CharacterController>();
            var otherObject = new GameObject("Other walker"); objects.Add(otherObject);
            otherObject.transform.position = Origin + Vector3.forward * 2;
            var other = otherObject.AddComponent<CharacterController>();
            Box("enemy", 3);
            Assert.That(Cast(self, 10, out var hit), Is.True);
            Assert.That(hit.collider, Is.SameAs(other));
            UnityEngine.Object.DestroyImmediate(otherObject);
            Assert.That(Cast(self, 10, out hit), Is.True);
            Assert.That(hit.collider.name, Is.EqualTo("enemy"));
        }

        [Test]
        public void NearestWorldWallAndVehicleBodyRemainBlockers()
        {
            var self = Box("self", .5f);
            var enemy = Box("enemy", 5);
            var vehicle = Box("RV body", 3);
            var wall = Box("wall", 2);
            Assert.That(Cast(self, 10, out var hit), Is.True);
            Assert.That(hit.collider, Is.SameAs(wall));
            wall.enabled = false;
            Assert.That(Cast(self, 10, out hit), Is.True);
            Assert.That(hit.collider, Is.SameAs(vehicle));
            vehicle.enabled = false;
            Assert.That(Cast(self, 10, out hit), Is.True);
            Assert.That(hit.collider, Is.SameAs(enemy));
        }

        [Test]
        public void UnorderedHitsSelectNearestNonSelf()
        {
            var self = Box("self", 1);
            var near = Box("near enemy", 2);
            var far = Box("far wall", 4);
            Physics.SyncTransforms();
            var ray = new Ray(Origin, Vector3.forward);
            Assert.That(self.Raycast(ray, out var selfHit, 10), Is.True);
            Assert.That(near.Raycast(ray, out var nearHit, 10), Is.True);
            Assert.That(far.Raycast(ray, out var farHit, 10), Is.True);
            object[] args = { new[] { farHit, selfHit, nearHit }, self, default(RaycastHit) };
            Assert.That((bool)raycasts.GetMethod("TrySelectFirst").Invoke(null, args), Is.True);
            Assert.That(((RaycastHit)args[2]).collider, Is.SameAs(near));
        }

        [Test]
        public void DenseRayDoesNotTruncateEnemyBeyondManySelfOrWorldHits()
        {
            var self = Box("self", .5f);
            for (int i = 0; i < 80; i++) Box("far wall " + i, 5 + i * .3f);
            var enemy = Box("nearest enemy", 2);
            Assert.That(Cast(self, 45, out var hit), Is.True);
            Assert.That(hit.collider, Is.SameAs(enemy));
        }

        [Test]
        public void TriggerAndRangeAreRespected()
        {
            Box("trigger", 1).isTrigger = true;
            var enemy = Box("enemy", 4);
            Assert.That(Cast(null, 3, out _), Is.False);
            Assert.That(Cast(null, 5, out var hit), Is.True);
            Assert.That(hit.collider, Is.SameAs(enemy));
            Assert.That(Cast(null, 0, out _), Is.False);
        }

        [Test]
        public void OnlyExactTargetSurfaceGetsEndpointAllowance()
        {
            var self = Box("self", .5f);
            var surface = Box("workbench", 3);
            Assert.That(Reach(3, self, surface), Is.True);
            var thinWall = Box("thin wall", 2.8f, .02f);
            // Wall is only .21m from the point; the previous .35m waiver accepted it.
            Assert.That(Reach(3, self, surface), Is.False);
            thinWall.enabled = false;
            Assert.That(Reach(3, self, null), Is.False);
            Assert.That(Reach(4, self, surface), Is.False);
            surface.enabled = false;
            Assert.That(Reach(3, self, null), Is.True);
        }
    }
}

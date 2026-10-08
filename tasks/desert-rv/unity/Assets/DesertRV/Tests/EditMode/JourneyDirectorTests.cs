using System;
using System.Collections;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class JourneyDirectorTests
    {
        static Type TypeOf(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Get(object target, string name) => target.GetType().GetProperty(name).GetValue(target);
        static object Call(object target, string name, params object[] args) => target.GetType().GetMethod(name).Invoke(target, args);

        [Test] public void Telemetry_ExclusiveBucketsEqualPlayingTime()
        {
            var telemetry = Activator.CreateInstance(TypeOf("JourneyTelemetry"));
            var activity = TypeOf("JourneyActivity");
            foreach (string kind in new[] { "Driving", "OnFoot", "Reloading", "Installing", "PoweredDefense" })
                Call(telemetry, "Record", 2, Enum.Parse(activity, kind), 10d);
            var rows = (IList)Get(telemetry, "Regions");
            Assert.That(rows.Count, Is.EqualTo(1));
            Assert.That(Get(rows[0], "Total"), Is.EqualTo(50d));
            Call(telemetry, "Reset"); Assert.That(rows.Count, Is.Zero);
        }
        [Test] public void Telemetry_RejectsNonfiniteOrInvalidSamples()
        {
            var telemetry = Activator.CreateInstance(TypeOf("JourneyTelemetry"));
            var activity = Enum.Parse(TypeOf("JourneyActivity"), "Driving");
            Call(telemetry, "Record", 0, activity, 2d);
            Call(telemetry, "Record", 1, activity, double.NaN);
            Call(telemetry, "Record", 1, activity, double.PositiveInfinity);
            Call(telemetry, "Record", 1, activity, -1d);
            Assert.That(((IList)Get(telemetry, "Regions")).Count, Is.Zero);
        }
        [Test] public void Binding_UnverifiedAssetsCannotPass()
        {
            var go = new GameObject("unverified region");
            try
            {
                var binding = go.AddComponent(TypeOf("RegionBinding"));
                object[] args = { null };
                Assert.That(Call(binding, "Validate", args), Is.False);
                Assert.That(args[0], Is.Not.Null);
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        [Test] public void Binding_UsesFixedDirectionAndOffset()
        {
            var go = new GameObject("region coordinate");
            try
            {
                var binding = go.AddComponent(TypeOf("RegionBinding"));
                binding.GetType().GetField("spawn").SetValue(binding, go.transform);
                binding.GetType().GetField("regionOffset").SetValue(binding, 400d);
                binding.GetType().GetField("progressDirection").SetValue(binding, Vector3.forward);
                go.transform.position = new Vector3(20, 0, 30);
                Assert.That(Call(binding, "WorldProgress", new Vector3(20, 0, 50)), Is.EqualTo(420d));
                // Rotating the RV cannot change the region's progress axis.
                go.transform.rotation = Quaternion.Euler(0, 180, 0);
                Assert.That(Call(binding, "WorldProgress", new Vector3(20, 0, 50)), Is.EqualTo(420d));
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        [Test] public void SafeVolume_RejectsDisabledAndOutsidePoints()
        {
            var go = new GameObject("real safety collider");
            try
            {
                var box = go.AddComponent<BoxCollider>(); box.size = Vector3.one * 4;
                Physics.SyncTransforms();
                var method = TypeOf("RegionBinding").GetMethod("Contains");
                Assert.That(method.Invoke(null, new object[] { box, Vector3.zero }), Is.True);
                Assert.That(method.Invoke(null, new object[] { box, Vector3.one * 4 }), Is.False);
                box.enabled = false;
                Assert.That(method.Invoke(null, new object[] { box, Vector3.zero }), Is.False);
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        [Test] public void Placement_DoesNotHealOrRefill()
        {
            var root = new GameObject("placement root"); root.SetActive(false);
            try
            {
                var host = root.AddComponent(TypeOf("JourneySession"));
                host.GetType().GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(host, null);
                Call(host, "StartJourney");
                var state = Get(host, "State"); Call(state, "DamagePlayer", 17); Call(state, "DamageVehicle", 29); Call(state, "TryFire");
                var vehicle = new GameObject("vehicle"); vehicle.transform.SetParent(root.transform);
                var door = new GameObject("door"); door.transform.SetParent(vehicle.transform);
                var camera = new GameObject("camera"); camera.transform.SetParent(root.transform);
                var motor = root.AddComponent(TypeOf("JourneyMotor"));
                motor.GetType().GetField("journey").SetValue(motor, host);
                motor.GetType().GetField("vehicle").SetValue(motor, vehicle.transform);
                motor.GetType().GetField("doorHinge").SetValue(motor, door.transform);
                motor.GetType().GetField("view").SetValue(motor, camera.AddComponent<Camera>());
                motor.GetType().GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(motor, null);
                Call(motor, "PlaceForRegion", new Vector3(100, 0, 200), Quaternion.identity);
                Assert.That(vehicle.transform.position, Is.EqualTo(new Vector3(100, 0, 200)));
                Assert.That(Get(state, "PlayerHealth"), Is.EqualTo(83));
                Assert.That(Get(state, "VehicleHealth"), Is.EqualTo(271));
                Assert.That(Get(state, "LoadedAmmo"), Is.EqualTo(11));
                Assert.That(Get(motor, "Speed"), Is.EqualTo(0f));
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }
        [TestCase(false)] [TestCase(true)]
        public void Session_PausedStartOrRestartStillIssuesLoadTicket(bool restart)
        {
            var go = new GameObject("paused ticket host");
            try
            {
                var host = go.AddComponent(TypeOf("JourneySession"));
                if (Get(host, "State") == null) host.GetType().GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(host, null);
                if (restart)
                {
                    Call(host, "StartJourney"); Call(Get(host, "State"), "DamagePlayer", 100);
                    Call(host, "TogglePause"); Assert.That(Call(host, "RestartJourney"), Is.True);
                }
                else { Call(host, "TogglePause"); Assert.That(Call(host, "StartJourney"), Is.True); }
                var state = Get(host, "State");
                Assert.That(Get(state, "Status").ToString(), Is.EqualTo("Paused"));
                var ticket = Call(host, "BeginCurrentRegionLoad");
                Assert.That(Call(host, "IsCurrentLoad", ticket), Is.True);
                Assert.That(Get(state, "Status").ToString(), Is.EqualTo("Paused"));
                Assert.That(Call(host, "CompleteRegionLoad", ticket, 0d), Is.True);
                Assert.That(Get(state, "Status").ToString(), Is.EqualTo("Paused"));
                Call(host, "TogglePause");
                Assert.That(Get(state, "Status").ToString(), Is.EqualTo("Playing"));
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        [TestCase(float.NaN, TestName = "Binding_RejectsNonfiniteCharge_NaN")]
        [TestCase(float.PositiveInfinity, TestName = "Binding_RejectsNonfiniteCharge_PositiveInfinity")]
        public void Binding_RejectsNonfiniteCharge(float charge)
        {
            var go = new GameObject("nonfinite encounter");
            try
            {
                var binding = go.AddComponent(TypeOf("RegionBinding")); var type = binding.GetType();
                type.GetField("region").SetValue(binding, 2);
                type.GetField("environmentVerified").SetValue(binding, true);
                type.GetField("combatAssetsVerified").SetValue(binding, true);
                type.GetField("spawn").SetValue(binding, go.transform);
                type.GetField("exitVolume").SetValue(binding, go.AddComponent<BoxCollider>());
                type.GetField("powerPoint").SetValue(binding, go.transform);
                type.GetField("powerSurface").SetValue(binding, go.GetComponent<BoxCollider>());
                type.GetField("waves").SetValue(binding, Array.CreateInstance(TypeOf("RegionWave"), 1));
                type.GetField("chargeSeconds").SetValue(binding, charge);
                object[] args = { null };
                Assert.That(Call(binding, "Validate", args), Is.False);
                StringAssert.Contains("供电", (string)args[0]);
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        [Test] public void Nonowner_PublicBeginCannotMutateSession()
        {
            var go = new GameObject("inactive nonowner"); go.SetActive(false);
            try
            {
                var host = go.AddComponent(TypeOf("JourneySession"));
                host.GetType().GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(host, null);
                var director = go.AddComponent(TypeOf("JourneyDirector"));
                director.GetType().GetField("journey").SetValue(director, host);
                ((Behaviour)director).enabled = false;
                Call(director, "Begin"); Call(director, "Restart"); Call(director, "RetryLoad");
                Assert.That(Get(Get(host, "State"), "Status").ToString(), Is.EqualTo("Menu"));
                Assert.That(Get(Get(host, "State"), "Generation"), Is.EqualTo(0));
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        [Test] public void Session_RetryKeepsTicketAndDuplicateCompletionRejected()
        {
            var go = new GameObject("ticket host");
            try
            {
                var host = go.AddComponent(TypeOf("JourneySession"));
                if (Get(host, "State") == null) host.GetType().GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(host, null);
                Assert.That(Call(host, "StartJourney"), Is.True);
                var state = Get(host, "State");
                var ticket = Call(host, "BeginCurrentRegionLoad");
                Assert.That(Call(host, "IsCurrentLoad", ticket), Is.True);
                // No new ticket or scene advancement is required after a failed attempt.
                Assert.That(Get(state, "SceneId"), Is.EqualTo(1));
                Assert.That(Call(host, "CompleteRegionLoad", ticket, 0d), Is.True);
                Assert.That(Call(host, "CompleteRegionLoad", ticket, 0d), Is.False);
                Call(state, "DamagePlayer", 100);
                Call(host, "RestartJourney");
                Assert.That(Call(host, "IsCurrentLoad", ticket), Is.False);
                Assert.That(Get(host, "Generation"), Is.EqualTo(Get(state, "Generation")));
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
    }
}

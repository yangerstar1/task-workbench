using System;
using NUnit.Framework;
using System.Reflection;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class CombatTimingRulesTests
    {
        static int Gen(object s) => Production.Get<int>(s, "Generation");
        static object Beast(object s) => Production.New("BeastCombatState", s, 1, Gen(s));
        static object Arc(object s) => Production.New("ArcCombatState", s, 1, Gen(s), 3.0, .2);
        static void ArcUpgrade(object s) => Production.Install(s, "Coil", "coil");
        [Test]
        public void ChargeHitsOnceAndOnlyForMatchingAttackIdentity()
        {
            var s = Production.Session(); var b = Beast(s); int g = Gen(s);
            Assert.That(Production.Call(b, "TryBeginCharge", 2, g), Is.EqualTo(0));
            int id = (int)Production.Call(b, "TryBeginCharge", 1, g);
            Assert.That(id, Is.GreaterThan(0));
            Assert.That(Production.Call(b, "TryBeginCharge", 1, g), Is.EqualTo(0));
            Production.No(b, "TryRegisterChargeHit", 1, g + 1, id);
            Production.No(b, "TryRegisterChargeHit", 1, g, id + 1);
            Production.Yes(b, "TryRegisterChargeHit", 1, g, id);
            Production.No(b, "TryRegisterChargeHit", 1, g, id);
            Production.Yes(b, "TryBeginRecovery", 1, g, id, 2.0);
            Production.No(b, "TryRegisterChargeHit", 1, g, id);
            Production.No(b, "TryBeginRecovery", 1, g, id, 2.0);
        }
        [Test]
        public void RecoveryWeakPointClosesAndAllowsNextDistinctCharge()
        {
            var s = Production.Session(); var b = Beast(s); int g = Gen(s);
            int id = (int)Production.Call(b, "TryBeginCharge", 1, g);
            Production.Yes(b, "TryBeginRecovery", 1, g, id, 2.0);
            Assert.That(Production.Get<bool>(b, "WeakPointOpen"), Is.True);
            Assert.That(Production.Call(b, "TryBeginCharge", 1, g), Is.EqualTo(0));
            Production.Call(b, "Tick", 1.0);
            Assert.That(Production.Get<double>(b, "WeakPointRemaining"), Is.EqualTo(1));
            Production.Call(b, "Tick", 1.0);
            Assert.That(Production.Get<bool>(b, "WeakPointOpen"), Is.False);
            int next = (int)Production.Call(b, "TryBeginCharge", 1, g);
            Assert.That(next, Is.GreaterThan(id));
            Production.No(b, "TryRegisterChargeHit", 1, g, id);
            Production.Yes(b, "TryRegisterChargeHit", 1, g, next);
        }
        [Test]
        public void PauseFreezesRecoveryButUnplugDoesNot()
        {
            var s = Production.Session(); var b = Beast(s); int g = Gen(s);
            int id = (int)Production.Call(b, "TryBeginCharge", 1, g);
            Production.Yes(b, "TryBeginRecovery", 1, g, id, 2.0);
            Production.Call(s, "Pause"); Production.Call(b, "Tick", 99.0);
            Assert.That(Production.Get<double>(b, "WeakPointRemaining"), Is.EqualTo(2));
            Production.Call(s, "Resume"); Production.Yes(s, "SetPowerConnected", false);
            Production.Call(b, "Tick", 2.0);
            Assert.That(Production.Get<bool>(b, "WeakPointOpen"), Is.False);
        }
        [Test]
        public void ArcRequiresUpgradeDrivingAndCorrectRegionGeneration()
        {
            var s = Production.Session(); var a = Arc(s); int g = Gen(s);
            Assert.That(Production.Call(a, "TryBeginPulse", 1, g), Is.EqualTo(0));
            ArcUpgrade(s);
            Assert.That(Production.Call(a, "TryBeginPulse", 2, g), Is.EqualTo(0));
            Assert.That(Production.Call(a, "TryBeginPulse", 1, g + 1), Is.EqualTo(0));
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "OnFoot"));
            Assert.That(Production.Call(a, "TryBeginPulse", 1, g), Is.EqualTo(0));
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "Driving"));
            Assert.That(Production.Call(a, "TryBeginPulse", 1, g), Is.GreaterThan(0));
        }
        [Test]
        public void ArcDeduplicatesTargetsPerPulseAndRejectsExpiredPulse()
        {
            var s = Production.Session(); ArcUpgrade(s); var a = Arc(s); int g = Gen(s);
            int id = (int)Production.Call(a, "TryBeginPulse", 1, g);
            Production.No(a, "TryHitTarget", 1, g, id, "");
            Production.No(a, "TryHitTarget", 2, g, id, "one");
            Production.Yes(a, "TryHitTarget", 1, g, id, "one");
            Production.No(a, "TryHitTarget", 1, g, id, "one");
            Production.Yes(a, "TryHitTarget", 1, g, id, "two");
            Production.Call(a, "Tick", .2);
            Production.No(a, "TryHitTarget", 1, g, id, "three");
            Assert.That(Production.Call(a, "TryBeginPulse", 1, g), Is.EqualTo(0));
            Production.Call(a, "Tick", 3.0);
            int next = (int)Production.Call(a, "TryBeginPulse", 1, g);
            Assert.That(next, Is.GreaterThan(id));
            Production.No(a, "TryHitTarget", 1, g, id, "three");
            Production.Yes(a, "TryHitTarget", 1, g, next, "one");
        }
        [Test]
        public void ArcCooldownAndHitWindowFreezeDuringPause()
        {
            var s = Production.Session(); ArcUpgrade(s); var a = Arc(s); int g = Gen(s);
            int id = (int)Production.Call(a, "TryBeginPulse", 1, g);
            Production.Call(s, "Pause"); Production.Call(a, "Tick", 99.0);
            Assert.That(Production.Get<double>(a, "CooldownRemaining"), Is.EqualTo(3));
            Production.No(a, "TryHitTarget", 1, g, id, "one");
            Production.Call(s, "Resume"); Production.Yes(a, "TryHitTarget", 1, g, id, "one");
            Production.Call(a, "Tick", 3.0);
            Assert.That(Production.Get<double>(a, "CooldownRemaining"), Is.Zero);
        }
        [Test]
        public void OldCombatInstancesAreInvalidAfterWholeJourneyRestart()
        {
            var s = Production.Session(); ArcUpgrade(s); var a = Arc(s); var b = Beast(s); int old = Gen(s);
            int pulse = (int)Production.Call(a, "TryBeginPulse", 1, old);
            int charge = (int)Production.Call(b, "TryBeginCharge", 1, old);
            Production.Call(s, "DamagePlayer", 100); Production.Yes(s, "RestartJourney"); ArcUpgrade(s);
            Production.No(a, "TryHitTarget", 1, old, pulse, "one");
            Production.No(b, "TryRegisterChargeHit", 1, old, charge);
            Production.Call(a, "Tick", 99.0);
            Assert.That(Production.Get<double>(a, "CooldownRemaining"), Is.EqualTo(3));
            Assert.That(Production.Call(a, "TryBeginPulse", 1, Gen(s)), Is.EqualTo(0));
        }
        [Test]
        public void InvalidCombatTimeCannotCorruptTimers()
        {
            var s = Production.Session(); var b = Beast(s); var a = Arc(s);
            Assert.Throws<ArgumentOutOfRangeException>(() => Production.Call(b, "Tick", double.PositiveInfinity));
            Assert.Throws<ArgumentOutOfRangeException>(() => Production.Call(a, "Tick", double.NaN));
            Assert.Throws<ArgumentOutOfRangeException>(() => Production.Call(a, "Tick", -1.0));
        }
    }

    public sealed class BeastActorCombatIntegrationTests
    {
        GameObject owner, beastObject;
        Component host, beast;
        object session;
        [SetUp]
        public void SetUp()
        {
            owner = new GameObject("combat session test");
            host = owner.AddComponent(Production.Type("JourneySession"));
            if (Production.Get(host, "State") == null) Production.Call(host, "Awake");
            Production.Yes(host, "StartJourney");
            session = Production.Get(host, "State");
            beastObject = new GameObject("armored creature test");
            beast = beastObject.AddComponent(Production.Type("BeastActor"));
            beast.GetType().GetField("journey").SetValue(beast, host);
            beast.GetType().GetField("armored").SetValue(beast, true);
            Production.Call(beast, "ResetActor");
        }
        [TearDown]
        public void TearDown()
        {
            if (beastObject) UnityEngine.Object.DestroyImmediate(beastObject);
            if (owner) UnityEngine.Object.DestroyImmediate(owner);
        }
        [Test]
        public void ActorDamageUsesRecoveringWeakPointThenRestoresArmor()
        {
            Assert.That(Production.Call(beast, "TakeHit", 25, Vector3.forward, false), Is.EqualTo(5));
            var combat = beast.GetType().GetField("combat", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(beast);
            int g = Production.Get<int>(session, "Generation");
            int charge = (int)Production.Call(combat, "TryBeginCharge", 1, g);
            Production.Yes(combat, "TryBeginRecovery", 1, g, charge, 2.0);
            Assert.That(Production.Call(beast, "TakeHit", 25, Vector3.forward, false), Is.EqualTo(25));
            Production.Call(combat, "Tick", 2.0);
            Assert.That(Production.Call(beast, "TakeHit", 25, Vector3.forward, false), Is.EqualTo(5));
            Assert.That(Production.Get<int>(beast, "Health"), Is.EqualTo(125));
        }
        [Test]
        public void ActorRejectsNegativePausedAndStaleGenerationDamage()
        {
            Assert.That(Production.Call(beast, "TakeHit", -25, Vector3.forward, true), Is.EqualTo(0));
            Production.Call(session, "Pause");
            Assert.That(Production.Call(beast, "TakeHit", 25, Vector3.forward, true), Is.EqualTo(0));
            Production.Call(session, "Resume"); Production.Call(session, "DamagePlayer", 100);
            Production.Yes(host, "RestartJourney");
            Assert.That(Production.Call(beast, "TakeHit", 25, Vector3.forward, true), Is.EqualTo(0));
            Production.Call(beast, "ResetActor");
            Assert.That(Production.Call(beast, "TakeHit", 25, Vector3.forward, true), Is.EqualTo(25));
        }
        [Test]
        public void ActorDeathAndResetPreservePublicCombatContract()
        {
            Assert.That(Production.Call(beast, "TakeHit", 200, Vector3.forward, true), Is.EqualTo(200));
            Assert.That(Production.Get<bool>(beast, "Dead"), Is.True);
            Assert.That(Production.Get<bool>(beast, "KilledByRam"), Is.True);
            Assert.That(Production.Call(beast, "TakeHit", 200, Vector3.forward, true), Is.EqualTo(0));
            Production.Call(beast, "ResetActor");
            Assert.That(Production.Get<bool>(beast, "Dead"), Is.False);
            Assert.That(Production.Get<bool>(beast, "KilledByRam"), Is.False);
            Assert.That(Production.Get<int>(beast, "Health"), Is.EqualTo(160));
        }
    }
}

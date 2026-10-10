using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    // Invoke production state, actor contact handling, physics queries and actions.
    // These are native EditMode tests; host source checks do not execute them.
    public sealed class JourneyCombatFeedbackTests
    {
        static readonly Vector3 Origin = new Vector3(18000, 18000, 18000);
        GameObject owner, regionObject, enemy, wall;
        Component session, motor, actions, region, actor;
        object state;
        Camera camera;
        static void Set(object target, string field, object value) => target.GetType().GetField(field,
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).SetValue(target, value);
        static void Property(object target, string name, object value) => Set(target, "<" + name + ">k__BackingField", value);
        Transform Child(string name, Vector3 at)
        {
            var go = new GameObject(name); go.transform.SetParent(owner.transform); go.transform.position = at;
            return go.transform;
        }
        [SetUp] public void SetUp()
        {
            owner = new GameObject("feedback test inactive services"); owner.SetActive(false);
            session = owner.AddComponent(Production.Type("JourneySession")); state = Production.Session();
            Production.Call(state, "SetControl", Production.Enum("ControlMode", "OnFoot")); Property(session, "State", state);
            Property(session, "Input", owner.AddComponent(Production.Type("MobileInputAdapter")));
            motor = owner.AddComponent(Production.Type("JourneyMotor")); Set(motor, "journey", session);
            Set(motor, "vehicle", Child("vehicle", Origin)); Set(motor, "doorHinge", Child("hinge", Origin));
            Set(motor, "closedDoor", Quaternion.identity);
            camera = Child("view", Origin + Vector3.up * 1.52f).gameObject.AddComponent<Camera>(); Set(motor, "view", camera);
            Set(motor, "walker", Child("body", Origin).gameObject.AddComponent<CharacterController>());
            var step = GameObject.CreatePrimitive(PrimitiveType.Cube); step.transform.SetParent(owner.transform);
            step.transform.position = Origin + Vector3.right * 2; step.transform.localScale = Vector3.one * .2f;
            UnityEngine.Object.DestroyImmediate(step.GetComponent<Collider>()); Set(motor, "entryStep", step.transform);
            actions = owner.AddComponent(Production.Type("JourneyActions")); Set(actions, "journey", session); Set(actions, "motor", motor);
            regionObject = new GameObject("feedback test region"); region = regionObject.AddComponent(Production.Type("RegionBinding"));
            Property(actions, "Region", region); Property(actions, "PresentationGeneration", 1);
            enemy = new GameObject("real test beast"); enemy.transform.position = Origin + Vector3.back * 3;
            enemy.AddComponent<CapsuleCollider>(); actor = enemy.AddComponent(Production.Type("BeastActor"));
            Set(actor, "journey", session); Set(actor, "player", motor); Production.Call(actor, "ResetActor");
            var guards = Array.CreateInstance(Production.Type("BeastActor"), 1); guards.SetValue(actor, 0); Set(region, "guards", guards);
            Physics.SyncTransforms();
        }
        [TearDown] public void TearDown()
        {
            if (wall) UnityEngine.Object.DestroyImmediate(wall);
            if (enemy) UnityEngine.Object.DestroyImmediate(enemy);
            if (regionObject) UnityEngine.Object.DestroyImmediate(regionObject);
            if (owner) UnityEngine.Object.DestroyImmediate(owner);
            Physics.SyncTransforms();
        }
        [Test] public void ContactUsesActualDamageAndCameraRelativeBearing()
        {
            Assert.That(Production.Get<float>(motor, "DamageCueRemaining"), Is.Zero);
            Production.Call(actor, "ApplyContactDamage", false);
            Assert.That(Production.Get<int>(state, "PlayerHealth"), Is.EqualTo(85));
            Assert.That(Production.Get<int>(motor, "DamageAmount"), Is.EqualTo(15));
            Assert.That(Production.Get<bool>(motor, "DamageToVehicle"), Is.False);
            Assert.That(Production.Get<Vector2>(motor, "DamageBearing").y, Is.LessThan(-.99f));
            camera.transform.rotation = Quaternion.Euler(0, 180, 0);
            Assert.That(Production.Get<Vector2>(motor, "DamageBearing").y, Is.GreaterThan(.99f));
            camera.transform.rotation = Quaternion.Euler(0, 90, 0);
            Assert.That(Production.Get<Vector2>(motor, "DamageBearing").x, Is.GreaterThan(.99f));
            camera.transform.rotation = Quaternion.Euler(0, -90, 0);
            Assert.That(Production.Get<Vector2>(motor, "DamageBearing").x, Is.LessThan(-.99f));
            Production.Call(actor, "ApplyContactDamage", true);
            Assert.That(Production.Get<int>(state, "VehicleHealth"), Is.EqualTo(281));
            Assert.That(Production.Get<int>(motor, "DamageAmount"), Is.EqualTo(19));
            Assert.That(Production.Get<bool>(motor, "DamageToVehicle"), Is.True);
        }
        [Test] public void ContactCueRejectsNoLossExpiresAndClearsOnRegionPlacement()
        {
            Production.Call(state, "Pause"); Production.Call(actor, "ApplyContactDamage", false);
            Assert.That(Production.Get<float>(motor, "DamageCueRemaining"), Is.Zero);
            Production.Call(state, "Resume"); Production.Call(state, "DamagePlayer", 94);
            Production.Call(actor, "ApplyContactDamage", false);
            Assert.That(Production.Get<int>(motor, "DamageAmount"), Is.EqualTo(6), "Display capped health loss, not nominal attack damage.");
            Production.Call(motor, "AdvanceDamageCue", 1f);
            Assert.That(Production.Get<float>(motor, "DamageCueRemaining"), Is.Zero);
            Production.Call(state, "RestartJourney"); Production.Call(actor, "ResetActor");
            Production.Call(actor, "ApplyContactDamage", true); Production.Call(state, "Pause");
            Production.Call(motor, "Tick", 10f);
            Assert.That(Production.Get<float>(motor, "DamageCueRemaining"), Is.EqualTo(.8f), "Pause freezes the cue with gameplay.");
            Production.Call(motor, "PlaceForRegion", Origin, Quaternion.identity);
            Assert.That(Production.Get<float>(motor, "DamageCueRemaining"), Is.Zero);
        }
        [Test] public void RearWarningRequiresLiveBehindInRangeThreatAndClearsWithState()
        {
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.Null);
            Production.Call(actor, "SetPhase", Production.Enum("BeastPhase", "Stalk"));
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.SameAs(actor));
            camera.transform.rotation = Quaternion.Euler(0, 180, 0);
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.Null);
            camera.transform.rotation = Quaternion.identity; enemy.transform.position = Origin + Vector3.back * 7; Physics.SyncTransforms();
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.Null);
            Set(actor, "armored", true); Assert.That(Production.Get(actions, "CloseRearThreat"), Is.SameAs(actor));
            enemy.SetActive(false); Assert.That(Production.Get(actions, "CloseRearThreat"), Is.Null); enemy.SetActive(true);
            Production.Call(actor, "SetPhase", Production.Enum("BeastPhase", "Recover"));
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.Null);
            Production.Call(actor, "SetPhase", Production.Enum("BeastPhase", "Attack"));
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.SameAs(actor));
            Production.Call(state, "Pause"); Assert.That(Production.Get(actions, "CloseRearThreat"), Is.Null); Production.Call(state, "Resume");
            Production.Call(actor, "SetPhase", Production.Enum("BeastPhase", "Dead")); Assert.That(Production.Get(actions, "CloseRearThreat"), Is.Null);
            Production.Call(actor, "SetPhase", Production.Enum("BeastPhase", "Stalk"));
            Production.Call(state, "DamagePlayer", 100); Production.Call(state, "RestartJourney");
            Property(actions, "PresentationGeneration", 2);
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.Null, "Old actor combat binding cannot warn in a restarted journey.");
        }
        [Test] public void RearWarningDoesNotSeeThroughWorldCover()
        {
            Production.Call(actor, "SetPhase", Production.Enum("BeastPhase", "Windup"));
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.SameAs(actor));
            wall = new GameObject("rear cover"); wall.transform.position = Origin + new Vector3(0, .65f, -1.5f);
            wall.AddComponent<BoxCollider>().size = new Vector3(2, 2, .2f); Physics.SyncTransforms();
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.Null);
            wall.SetActive(false); Physics.SyncTransforms();
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.SameAs(actor));
        }
        [Test] public void RepairNoticeReportsCappedVehicleGainAndLeavesPlayerHealthAlone()
        {
            Production.Call(state, "DamagePlayer", 15); Production.Call(state, "DamageVehicle", 19);
            Set(actions, "interaction", 5); Production.Call(actions, "Interact");
            Assert.That(Production.Get<int>(state, "VehicleHealth"), Is.EqualTo(300));
            Assert.That(Production.Get<int>(state, "PlayerHealth"), Is.EqualTo(85));
            Assert.That(Production.Get<int>(state, "RepairKits"), Is.EqualTo(1));
            Assert.That(Production.Get<string>(actions, "Notice"), Is.EqualTo("车况 +19 · 不恢复体力。"));
            Production.Call(state, "DamageVehicle", 120); Production.Call(actions, "Interact");
            Assert.That(Production.Get<string>(actions, "Notice"), Is.EqualTo("车况 +95 · 不恢复体力。"));
            Assert.That(Production.Get<int>(state, "VehicleHealth"), Is.EqualTo(275));
            Assert.That(Production.Get<int>(state, "PlayerHealth"), Is.EqualTo(85));
        }
        [Test] public void DriverPromptAndFailureShareExistingCableAndLineOfSightGates()
        {
            Production.Call(state, "SetPowerConnected", true); Production.Call(actions, "FindInteraction");
            Assert.That(Production.Get<string>(actions, "Prompt"), Does.Contain("先拔除电缆"));
            Set(actions, "reloadRemaining", 1f); Production.Call(actions, "Interact");
            Assert.That(Production.Get<string>(actions, "Notice"), Does.Contain("先拔除电缆"));
            Assert.That(Production.Get<float>(actions, "ReloadRemaining"), Is.EqualTo(1));
            Assert.That(Production.Get(state, "Control").ToString(), Is.EqualTo("OnFoot"));
            Production.Call(state, "SetPowerConnected", false);
            wall = new GameObject("door obstruction"); wall.transform.position = Origin + new Vector3(1, 1.3f, 0);
            wall.AddComponent<BoxCollider>().size = new Vector3(.2f, 2, 2); Physics.SyncTransforms();
            Production.Call(actions, "FindInteraction"); Assert.That(Production.Get<string>(actions, "Prompt"), Does.Contain("门前受阻"));
            Production.Call(actions, "Interact"); Assert.That(Production.Get<string>(actions, "Notice"), Does.Contain("门前受阻"));
            Assert.That(Production.Get(state, "Control").ToString(), Is.EqualTo("OnFoot"));
            wall.SetActive(false); Physics.SyncTransforms(); Production.Call(actions, "FindInteraction");
            Assert.That(Production.Get<string>(actions, "Prompt"), Is.EqualTo("回到驾驶位"));
            Production.Call(actions, "Interact"); Assert.That(Production.Get(state, "Control").ToString(), Is.EqualTo("Driving"));
            Assert.That(Production.Get<float>(actions, "ReloadRemaining"), Is.Zero);
        }
        [Test] public void DisconnectExplainsChargePauseWhileExistingWaveAndThreatRemain()
        {
            Production.Advance(state, "RamPart", "test-ram");
            Set(region, "region", 2); Production.Call(state, "SetControl", Production.Enum("ControlMode", "OnFoot"));
            Set(region, "powerPoint", Child("socket", Origin));
            Production.Call(state, "SetPowerConnected", true); Production.Call(actor, "ResetActor");
            Production.Call(actor, "SetPhase", Production.Enum("BeastPhase", "Stalk"));
            var encounter = Production.New("PoweredEncounterState", state, 2, 1, 1, 30d);
            Production.Yes(encounter, "TryBeginWave", 2, 1, 1);
            Production.Yes(encounter, "TryRegisterEnemy", 2, 1, 1, "test-beast");
            Production.Yes(encounter, "TrySealWave", 2, 1, 1, 1); Production.Call(encounter, "Tick", 5d);
            double progress = Production.Get<double>(encounter, "ChargeProgress");
            Set(actions, "interaction", 6); Production.Call(actions, "Interact");
            Assert.That(Production.Get<bool>(state, "PowerConnected"), Is.False);
            Assert.That(Production.Get<string>(actions, "Notice"), Is.EqualTo("断电：充能暂停，现有敌人仍会攻击。"));
            Production.Call(encounter, "Tick", 10d);
            Assert.That(Production.Get<double>(encounter, "ChargeProgress"), Is.EqualTo(progress));
            Assert.That(Production.Get<int>(encounter, "AliveCount"), Is.EqualTo(1));
            Assert.That(enemy.activeInHierarchy, Is.True);
            Assert.That(Production.Get(actions, "CloseRearThreat"), Is.SameAs(actor));
            Production.Call(actor, "ApplyContactDamage", false);
            Assert.That(Production.Get<int>(state, "PlayerHealth"), Is.EqualTo(85));
        }
    }
}

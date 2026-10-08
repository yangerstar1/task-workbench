using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class JourneySupplyInteractionTests
    {
        static readonly Vector3 Origin = new Vector3(15000, 15000, 15000);
        GameObject owner, regionObject, cache, wall;
        Component actions, region;
        object state, supply;
        static void Set(object target, string field, object value)
            => target.GetType().GetField(field, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).SetValue(target, value);
        static void Property(object target, string name, object value) => Set(target, "<" + name + ">k__BackingField", value);
        object Reach() { Physics.SyncTransforms(); return Production.Call(actions, "FindReachableSupply"); }
        [SetUp] public void SetUp()
        {
            owner = new GameObject("supply-test inactive services"); owner.SetActive(false);
            var host = owner.AddComponent(Production.Type("JourneySession"));
            state = Production.Session(); Production.Call(state, "SetControl", Production.Enum("ControlMode", "OnFoot"));
            Property(host, "State", state);
            var motor = owner.AddComponent(Production.Type("JourneyMotor")); Set(motor, "journey", host);
            var cameraObject = new GameObject("test camera"); cameraObject.transform.SetParent(owner.transform); cameraObject.transform.position = Origin;
            Set(motor, "view", cameraObject.AddComponent<Camera>());
            var walker = new GameObject("test body"); walker.transform.SetParent(owner.transform); walker.transform.position = Origin;
            Set(motor, "walker", walker.AddComponent<CharacterController>());
            actions = owner.AddComponent(Production.Type("JourneyActions")); Set(actions, "journey", host); Set(actions, "motor", motor);
            regionObject = new GameObject("test supply region"); region = regionObject.AddComponent(Production.Type("RegionBinding"));
            Property(actions, "Region", region); Property(actions, "PresentationGeneration", 1);
            cache = new GameObject("test cache"); cache.transform.SetParent(regionObject.transform); cache.transform.position = Origin + Vector3.forward * 2;
            var surface = cache.AddComponent<BoxCollider>(); surface.size = new Vector3(.5f, .5f, .2f);
            supply = Production.New("JourneySupplyPoint");
            Set(supply, "id", "cache"); Set(supply, "label", "Ammo"); Set(supply, "riskHint", "Exposed");
            Set(supply, "point", cache.transform); Set(supply, "surface", surface); Set(supply, "visual", cache);
            Set(supply, "kind", Production.Enum("SupplyKind", "Ammo")); Set(supply, "amount", 24); Set(supply, "choiceGroup", "route");
            var supplies = Array.CreateInstance(Production.Type("JourneySupplyPoint"), 1); supplies.SetValue(supply, 0); Set(region, "supplies", supplies);
        }
        [TearDown] public void TearDown()
        {
            if (wall) UnityEngine.Object.DestroyImmediate(wall);
            if (regionObject) UnityEngine.Object.DestroyImmediate(regionObject);
            if (owner) UnityEngine.Object.DestroyImmediate(owner);
            Physics.SyncTransforms();
        }
        [Test] public void SupplyReachRequiresRealDistanceAndDoesNotIgnoreWorldWalls()
        {
            Assert.That(Reach(), Is.SameAs(supply));
            wall = new GameObject("world wall"); wall.transform.position = Origin + Vector3.forward;
            wall.AddComponent<BoxCollider>().size = new Vector3(1, 1, .1f);
            Assert.That(Reach(), Is.Null);
            wall.SetActive(false); cache.transform.position = Origin + Vector3.forward * 3;
            Assert.That(Reach(), Is.Null);
        }
        [Test] public void SupplyRejectsTriggerInactiveVisualAndDetachedSurface()
        {
            cache.GetComponent<BoxCollider>().isTrigger = true; Assert.That(Reach(), Is.Null);
            cache.GetComponent<BoxCollider>().isTrigger = false; cache.SetActive(false); Assert.That(Reach(), Is.Null);
            cache.SetActive(true);
            wall = new GameObject("wrong visual"); Set(supply, "visual", wall); Assert.That(Reach(), Is.Null);
        }
        [Test] public void SupplyRejectsOldBindingGenerationAndLoadingOrPausedState()
        {
            Production.Call(state, "Pause"); Assert.That(Reach(), Is.Null); Production.Call(state, "Resume");
            Production.Yes(state, "BeginLoading"); Assert.That(Reach(), Is.Null); Production.Yes(state, "CompleteLoading");
            Production.Call(state, "DamagePlayer", 100); Production.Yes(state, "RestartJourney");
            Production.Call(state, "SetControl", Production.Enum("ControlMode", "OnFoot")); Assert.That(Reach(), Is.Null);
        }
        [Test] public void LoadedButInactiveOldRegionCannotSupplyCurrentJourney()
        {
            var original = regionObject.scene;
            var stale = UnityEditor.SceneManagement.EditorSceneManager.NewScene(
                UnityEditor.SceneManagement.NewSceneSetup.EmptyScene, UnityEditor.SceneManagement.NewSceneMode.Additive);
            UnityEngine.SceneManagement.SceneManager.SetActiveScene(original);
            try
            {
                UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(regionObject, stale);
                Assert.That(stale.isLoaded, Is.True);
                Assert.That(Reach(), Is.Null);
            }
            finally
            {
                UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(regionObject, original);
                UnityEditor.SceneManagement.EditorSceneManager.CloseScene(stale, true);
            }
            Assert.That(Reach(), Is.SameAs(supply));
        }
        [Test] public void ReloadingBlocksCollectionAndDoesNotCancelReloadAudioPlan()
        {
            Set(actions, "reloadRemaining", 1f); Property(actions, "ReloadLoadedBefore", 0); Property(actions, "ReloadPlannedAdded", 1);
            Assert.That(Reach(), Is.Null);
            Set(actions, "interaction", 7); Set(actions, "nearbySupply", supply); Production.Call(actions, "Interact");
            Assert.That(Production.Get<float>(actions, "ReloadRemaining"), Is.EqualTo(1));
            Assert.That(Production.Get<int>(actions, "ReloadPlannedAdded"), Is.EqualTo(1));
            Assert.That(Production.Get<int>(state, "ReserveAmmo"), Is.EqualTo(96));
            Assert.That(Production.Get<string>(actions, "Notice"), Does.Contain("装填中"));
            Assert.That(Production.Call(state, "HasCollectedSupply", "cache"), Is.False);
            Assert.That(Production.Call(state, "HasChosenSupplyGroup", "route"), Is.False);
            Assert.That(cache.activeSelf, Is.True);
            // The existing reload timer owns completion; simulate its completed boundary here.
            Production.Call(state, "Reload"); Set(actions, "reloadRemaining", 0f);
            Production.Call(actions, "Interact");
            Assert.That(Production.Get<int>(state, "ReserveAmmo"), Is.EqualTo(120));
            Assert.That(Production.Call(state, "HasChosenSupplyGroup", "route"), Is.True);
        }
        [Test] public void InstallationBlocksWithoutConsumingChoiceAndAllowsCollectionAfterward()
        {
            Set(actions, "installRemaining", 1f); Set(actions, "interaction", 7); Set(actions, "nearbySupply", supply);
            Production.Call(actions, "Interact"); Assert.That(Reach(), Is.Null);
            Assert.That(Production.Get<string>(actions, "Notice"), Does.Contain("改装中"));
            Assert.That(Production.Call(state, "HasCollectedSupply", "cache"), Is.False);
            Assert.That(Production.Call(state, "HasChosenSupplyGroup", "route"), Is.False);
            Set(actions, "installRemaining", 0f); Production.Call(actions, "Interact");
            Assert.That(Production.Get<int>(state, "ReserveAmmo"), Is.EqualTo(120));
        }
        [Test] public void FullAmmoInteractionExplainsCapacityAndRetainsCacheUntilSpaceIsAvailable()
        {
            var ammo = Production.Enum("SupplyKind", "Ammo");
            Production.Yes(state, "TryCollectSupply", 1, 1, "other-a", ammo, 24, null);
            Production.Yes(state, "TryCollectSupply", 1, 1, "other-b", ammo, 24, null);
            Set(actions, "interaction", 7); Set(actions, "nearbySupply", supply); Production.Call(actions, "Interact");
            Assert.That(Production.Get<string>(actions, "Notice"), Does.Contain("备弹已满"));
            Assert.That(Production.Get<int>(state, "ReserveAmmo"), Is.EqualTo(144));
            Assert.That(cache.activeSelf, Is.True);
            Assert.That(Production.Call(state, "HasCollectedSupply", "cache"), Is.False);
            Assert.That(Production.Call(state, "HasChosenSupplyGroup", "route"), Is.False);
            Production.Yes(state, "TryFire"); Production.Call(state, "Reload");
            Assert.That(Production.Get<int>(state, "ReserveAmmo"), Is.EqualTo(143));
            Production.Call(actions, "Interact");
            Assert.That(Production.Get<int>(state, "ReserveAmmo"), Is.EqualTo(144));
            Assert.That(cache.activeSelf, Is.False);
            Assert.That(Production.Call(state, "HasCollectedSupply", "cache"), Is.True);
            Assert.That(Production.Call(state, "HasChosenSupplyGroup", "route"), Is.True);
        }
        [Test] public void FullKitInteractionExplainsCapacityAndRetainsCacheUntilKitIsUsed()
        {
            var kit = Production.Enum("SupplyKind", "RepairKit"); Set(supply, "kind", kit); Set(supply, "amount", 1);
            Production.Yes(state, "TryCollectSupply", 1, 1, "other-kit", kit, 1, null);
            Set(actions, "interaction", 7); Set(actions, "nearbySupply", supply); Production.Call(actions, "Interact");
            Assert.That(Production.Get<string>(actions, "Notice"), Does.Contain("维修包已满"));
            Assert.That(Production.Get<int>(state, "RepairKits"), Is.EqualTo(3));
            Assert.That(cache.activeSelf, Is.True);
            Assert.That(Production.Call(state, "HasCollectedSupply", "cache"), Is.False);
            Assert.That(Production.Call(state, "HasChosenSupplyGroup", "route"), Is.False);
            Production.Call(state, "DamageVehicle", 100); Production.Yes(state, "TryRepair");
            Assert.That(Production.Get<int>(state, "RepairKits"), Is.EqualTo(2));
            Production.Call(actions, "Interact");
            Assert.That(Production.Get<int>(state, "RepairKits"), Is.EqualTo(3));
            Assert.That(cache.activeSelf, Is.False);
            Assert.That(Production.Call(state, "HasCollectedSupply", "cache"), Is.True);
            Assert.That(Production.Call(state, "HasChosenSupplyGroup", "route"), Is.True);
        }
        [Test] public void SupplyInteractionRechecksSelectedObjectAndAwardsOnce()
        {
            Set(actions, "interaction", 7); Set(actions, "nearbySupply", Production.New("JourneySupplyPoint"));
            Production.Call(actions, "Interact"); Assert.That(Production.Get<int>(state, "ReserveAmmo"), Is.EqualTo(96));
            Set(actions, "nearbySupply", supply); Production.Call(actions, "Interact");
            Assert.That(Production.Get<int>(state, "ReserveAmmo"), Is.EqualTo(120)); Assert.That(cache.activeSelf, Is.False);
            cache.SetActive(true); Production.Call(actions, "Interact");
            Assert.That(Production.Get<int>(state, "ReserveAmmo"), Is.EqualTo(120));
        }
    }
}

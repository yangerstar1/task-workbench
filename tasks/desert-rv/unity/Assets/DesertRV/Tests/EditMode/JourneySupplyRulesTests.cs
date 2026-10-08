using NUnit.Framework;

namespace DesertRV.Tests
{
    public sealed class JourneySupplyRulesTests
    {
        static object State()
        {
            var s = Production.Session();
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "OnFoot")); return s;
        }
        static bool Take(object s, string id, string kind = "Ammo", int amount = 24, string group = null, int region = 1, int generation = -1)
            => (bool)Production.Call(s, "TryCollectSupply", region, generation < 0 ? Production.Get<int>(s, "Generation") : generation,
                id, Production.Enum("SupplyKind", kind), amount, group);
        [Test] public void SupplyOnceLeavesLoadedMagazineAndOtherResourcesUnchanged()
        {
            var s = State(); Assert.That(Take(s, "a"), Is.True); Assert.That(Take(s, "a"), Is.False);
            Assert.That(Production.Get<int>(s, "ReserveAmmo"), Is.EqualTo(120));
            Assert.That(Production.Get<int>(s, "LoadedAmmo"), Is.EqualTo(12));
            Assert.That(Production.Get<int>(s, "PlayerHealth"), Is.EqualTo(100));
            Assert.That(Production.Get<int>(s, "VehicleHealth"), Is.EqualTo(300));
            Assert.That(Production.Get<double>(s, "StormElapsedSeconds"), Is.Zero);
        }
        [Test] public void SupplyRejectsInvalidAmountsKindsAndBlankIdsWithoutConsumingAnything()
        {
            var s = State();
            foreach (int n in new[] { int.MinValue, -1, 0, 25, int.MaxValue }) Assert.That(Take(s, "a", amount: n), Is.False);
            foreach (int n in new[] { int.MinValue, -1, 0, 2, int.MaxValue }) Assert.That(Take(s, "kit", "RepairKit", n), Is.False);
            Assert.That(Take(s, "bad", "99"), Is.False);
            foreach (string id in new[] { null, "", " " }) Assert.That(Take(s, id), Is.False);
            Assert.That(Take(s, "a", group: " "), Is.False);
            Assert.That(Take(s, "a"), Is.True);
        }
        [Test] public void SupplyRejectsWrongRegionWrongGenerationAndAllNonplayingStates()
        {
            var s = State();
            foreach (int region in new[] { -1, 0, 2, 3, int.MaxValue }) Assert.That(Take(s, "a", region: region), Is.False);
            Assert.That(Take(s, "a", generation: 0), Is.False); Assert.That(Take(s, "a", generation: 2), Is.False);
            Production.Call(s, "Pause"); Assert.That(Take(s, "a"), Is.False); Production.Call(s, "Resume");
            Production.Yes(s, "BeginLoading"); Assert.That(Take(s, "a"), Is.False); Production.Yes(s, "CompleteLoading");
            Production.Call(s, "DamagePlayer", 100); Assert.That(Take(s, "a"), Is.False);
            var menu = Production.New("SessionState"); Assert.That(Take(menu, "a"), Is.False);
        }
        [Test] public void SupplyRejectsDrivingAndAllowsOnFootAfterwards()
        {
            var s = Production.Session(); Assert.That(Take(s, "a"), Is.False);
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "OnFoot")); Assert.That(Take(s, "a"), Is.True);
        }
        [Test] public void FullCacheDoesNotConsumeIdOrMutuallyExclusiveChoice()
        {
            var s = State(); Assert.That(Take(s, "a"), Is.True); Assert.That(Take(s, "b"), Is.True);
            Assert.That(Take(s, "full", group: "route"), Is.False);
            Assert.That(Production.Call(s, "HasCollectedSupply", "full"), Is.False);
            Assert.That(Production.Call(s, "HasChosenSupplyGroup", "route"), Is.False);
            Assert.That(Take(s, "kit", "RepairKit", 1, "route"), Is.True);
            Assert.That(Take(s, "full", group: "route"), Is.False);
        }
        [Test] public void PartialCapConsumesOnceAndLaterSpaceDoesNotRefillSameCache()
        {
            var s = State(); Take(s, "a"); Take(s, "b");
            Production.Yes(s, "TryFire"); Production.Call(s, "Reload");
            Assert.That(Production.Get<int>(s, "ReserveAmmo"), Is.EqualTo(143));
            Assert.That(Take(s, "partial"), Is.True);
            Assert.That(Production.Get<int>(s, "ReserveAmmo"), Is.EqualTo(144));
            Production.Yes(s, "TryFire"); Production.Call(s, "Reload");
            Assert.That(Take(s, "partial"), Is.False);
        }
        [Test] public void ChoiceLocksOnlyItsOwnGroupAndDoesNotCollideWithComponentIds()
        {
            var s = State();
            Production.Yes(s, "TryCollect", "supply/cache", Production.Enum("ComponentPart", "RamPart"));
            Assert.That(Take(s, "cache", group: "left-or-right"), Is.True);
            Assert.That(Take(s, "right", "RepairKit", 1, "left-or-right"), Is.False);
            Assert.That(Take(s, "other", "RepairKit", 1, "other-group"), Is.True);
        }
        [Test] public void RepairKitCollectionDoesNotRepairAndHonorsOneKitCap()
        {
            var s = State(); Production.Call(s, "DamageVehicle", 100);
            Assert.That(Take(s, "kit", "RepairKit", 1), Is.True);
            Assert.That(Production.Get<int>(s, "VehicleHealth"), Is.EqualTo(200));
            Assert.That(Production.Get<int>(s, "RepairKits"), Is.EqualTo(3));
            Assert.That(Take(s, "kit2", "RepairKit", 1), Is.False);
            Production.Yes(s, "TryRepair"); Assert.That(Take(s, "kit2", "RepairKit", 1), Is.True);
        }
        [Test] public void RestartClearsIdsChoicesAndResourcesButRejectsOldGeneration()
        {
            var s = State(); Assert.That(Take(s, "a", group: "route"), Is.True);
            Production.Call(s, "DamageVehicle", 300); Production.Yes(s, "RestartJourney");
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "OnFoot"));
            Assert.That(Production.Get<int>(s, "ReserveAmmo"), Is.EqualTo(96));
            Assert.That(Production.Get<int>(s, "RepairKits"), Is.EqualTo(2));
            Assert.That(Production.Call(s, "HasCollectedSupply", "a"), Is.False);
            Assert.That(Production.Call(s, "HasChosenSupplyGroup", "route"), Is.False);
            Assert.That(Take(s, "a", group: "route", generation: 1), Is.False);
            Assert.That(Take(s, "a", group: "route"), Is.True);
        }
        [Test] public void CompletedJourneyRejectsSuppliesAndSuccessfulRestartClearsChoices()
        {
            var s = State(); Assert.That(Take(s, "a", group: "route"), Is.True);
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "Driving"));
            Production.Advance(s, "RamPart", "ram"); Production.Advance(s, "Coil", "coil");
            Production.Yes(s, "SetObjectivesResolved", true); Production.Yes(s, "SetGateOpen", true);
            Production.Yes(s, "TryReachSafety", true);
            Assert.That(Take(s, "b", region: 3), Is.False);
            Production.Yes(s, "RestartJourney"); Production.Call(s, "SetControl", Production.Enum("ControlMode", "OnFoot"));
            Assert.That(Take(s, "a", group: "route"), Is.True);
        }
        [Test] public void RegionTransitionPreservesCacheIdsAndChoicesAcrossTheRun()
        {
            var s = State(); Assert.That(Take(s, "a", group: "route"), Is.True);
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "Driving")); Production.Advance(s, "RamPart", "ram");
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "OnFoot"));
            Assert.That(Take(s, "a", region: 2), Is.False);
            Assert.That(Take(s, "b", "RepairKit", 1, "route", region: 2), Is.False);
            Assert.That(Take(s, "c", region: 2), Is.True);
        }
    }
}

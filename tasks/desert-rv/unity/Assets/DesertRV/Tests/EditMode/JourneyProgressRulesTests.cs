using System;
using NUnit.Framework;

namespace DesertRV.Tests
{
    public sealed class JourneyProgressRulesTests
    {
        static int Generation(object session) => Production.Get<int>(session, "Generation");
        static object Region(object session) => Production.New("RegionProgressState", session, Generation(session));
        static object Scrapyard()
        {
            var session = Production.Session();
            Production.Advance(session, "RamPart", "ram");
            return session;
        }
        static object Encounter(object session, int waves = 1, double charge = 2)
            => Production.New("PoweredEncounterState", session, Production.Get<int>(session, "SceneId"), Generation(session), waves, charge);
        static void ClearWave(object session, object encounter, int wave)
        {
            int region = Production.Get<int>(session, "SceneId"), generation = Generation(session);
            Production.Yes(session, "SetPowerConnected", true);
            Production.Yes(encounter, "TryBeginWave", region, generation, wave);
            Production.Yes(encounter, "TryRegisterEnemy", region, generation, wave, "beast");
            Production.Yes(encounter, "TrySealWave", region, generation, wave, 1);
            Production.Yes(encounter, "TryDefeatEnemy", region, generation, wave, "beast");
            Production.Call(encounter, "Tick", 2.0);
            Production.Yes(encounter, "TryCompleteWave", region, generation, wave);
        }
        [Test]
        public void GenerationChangesOnlyOnSuccessfulStartAndWholeRunRestart()
        {
            var session = Production.New("SessionState");
            Assert.That(Generation(session), Is.Zero);
            Production.No(session, "Start");
            Assert.That(Generation(session), Is.Zero);
            Production.Yes(session, "ConfigureStorm", -40.0, 2.0, 4.0);
            Production.Yes(session, "Start");
            Assert.That(Generation(session), Is.EqualTo(1));
            Production.No(session, "Start"); Production.No(session, "RestartJourney");
            Production.Call(session, "DamagePlayer", 100);
            Assert.That(Generation(session), Is.EqualTo(1));
            Production.Yes(session, "RestartJourney");
            Assert.That(Generation(session), Is.EqualTo(2));
        }
        [Test]
        public void LoadingCanBeginWhilePausedWithoutResumingOrDuplicatingRequest()
        {
            var s = Production.Session();
            Production.Call(s, "Pause");
            Production.Yes(s, "BeginLoading"); Production.Status(s, "Paused");
            Production.No(s, "BeginLoading");
            Production.Yes(s, "CompleteLoading"); Production.Status(s, "Paused");
            Production.No(s, "CompleteLoading");
            Production.Call(s, "Resume"); Production.Status(s, "Playing");
        }
        [Test]
        public void ResumingPendingLoadingKeepsGameplayStoppedUntilCompletion()
        {
            var s = Production.Session();
            Production.Call(s, "Pause"); Production.Yes(s, "BeginLoading");
            Production.Call(s, "Resume"); Production.Status(s, "Loading");
            Production.No(s, "BeginLoading");
            Production.Yes(s, "CompleteLoading"); Production.Status(s, "Playing");
        }
        [Test]
        public void RamEventsRejectWrongRegionGenerationOrderAndDuplicates()
        {
            var s = Production.Session(); var r = Region(s); int g = Generation(s);
            Production.No(r, "TryInstallRam", 1, g);
            Production.No(r, "TryAcquireRam", 2, g, "ram");
            Production.No(r, "TryAcquireRam", 1, g + 1, "ram");
            Production.Yes(r, "TryAcquireRam", 1, g, "ram");
            Production.No(r, "TryAcquireRam", 1, g, "ram");
            Production.Yes(r, "TryInstallRam", 1, g);
            Production.No(r, "TryInstallRam", 1, g);
            Production.No(r, "TryOpenRamGate", 1, g, false);
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "OnFoot"));
            Production.No(r, "TryOpenRamGate", 1, g, true);
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "Driving"));
            Production.Yes(r, "TryOpenRamGate", 1, g, true);
            Production.No(r, "TryOpenRamGate", 1, g, true);
            Production.No(r, "CanExitRegion", 1, g, false);
            Production.Yes(r, "CanExitRegion", 1, g, true);
            Assert.That(Production.Get<int>(s, "SceneId"), Is.EqualTo(1), "Exit validation cannot consume the load ticket.");
        }
        [Test]
        public void EmptyAndPartiallyRegisteredWavesCannotComplete()
        {
            var s = Scrapyard(); var e = Encounter(s); int g = Generation(s);
            Production.No(e, "TryBeginWave", 2, g, 1);
            Production.Yes(s, "SetPowerConnected", true);
            Production.Yes(e, "TryBeginWave", 2, g, 1);
            Production.No(e, "TrySealWave", 2, g, 1, 0);
            Production.Call(e, "Tick", 20.0);
            Production.No(e, "TryCompleteWave", 2, g, 1);
            Production.Yes(e, "TryRegisterEnemy", 2, g, 1, "one");
            Production.No(e, "TrySealWave", 2, g, 1, 2);
            Production.No(e, "TryDefeatEnemy", 2, g, 1, "missing");
            Production.No(e, "TryCompleteWave", 2, g, 1);
            Assert.That(Production.Get<double>(e, "ChargeProgress"), Is.Zero);
        }
        [Test]
        public void EncounterRejectsWrongWaveRegionGenerationAndDuplicateCallbacks()
        {
            var s = Scrapyard(); var e = Encounter(s); int g = Generation(s);
            Production.Yes(s, "SetPowerConnected", true);
            Production.No(e, "TryBeginWave", 3, g, 1);
            Production.No(e, "TryBeginWave", 2, g + 1, 1);
            Production.No(e, "TryBeginWave", 2, g, 2);
            Production.Yes(e, "TryBeginWave", 2, g, 1);
            Production.No(e, "TryBeginWave", 2, g, 1);
            Production.Yes(e, "TryRegisterEnemy", 2, g, 1, "one");
            Production.No(e, "TryRegisterEnemy", 2, g, 1, "one");
            Production.Yes(e, "TrySealWave", 2, g, 1, 1);
            Production.No(e, "TrySealWave", 2, g, 1, 1);
            Production.No(e, "TryRegisterEnemy", 2, g, 1, "late");
            Production.No(e, "TryDefeatEnemy", 3, g, 1, "one");
            Production.No(e, "TryDefeatEnemy", 2, g + 1, 1, "one");
            Production.No(e, "TryDefeatEnemy", 2, g, 2, "one");
            Production.Yes(e, "TryDefeatEnemy", 2, g, 1, "one");
            Production.No(e, "TryDefeatEnemy", 2, g, 1, "one");
            Production.No(e, "TryCompleteWave", 2, g, 1);
            Production.Call(e, "Tick", 2.0);
            Production.Yes(e, "TryCompleteWave", 2, g, 1);
            Production.No(e, "TryCompleteWave", 2, g, 1);
        }
        [Test]
        public void UnplugFreezesDeviceButEnemyDeathsRemainValidAndReconnectKeepsProgress()
        {
            var s = Scrapyard(); var e = Encounter(s); int g = Generation(s);
            Production.Yes(s, "SetPowerConnected", true);
            Production.Yes(e, "TryBeginWave", 2, g, 1);
            Production.Yes(e, "TryRegisterEnemy", 2, g, 1, "one");
            Production.Yes(e, "TrySealWave", 2, g, 1, 1);
            Production.Call(e, "Tick", 1.0);
            Production.Yes(s, "SetPowerConnected", false);
            Production.Call(e, "Tick", 100.0);
            Assert.That(Production.Get<double>(e, "ChargeProgress"), Is.EqualTo(.5));
            Production.Yes(e, "TryDefeatEnemy", 2, g, 1, "one");
            Production.No(e, "TryCompleteWave", 2, g, 1);
            Production.Yes(s, "SetPowerConnected", true);
            Production.No(e, "TryBeginWave", 2, g, 1);
            Production.Call(e, "Tick", 1.0);
            Production.Yes(e, "TryCompleteWave", 2, g, 1);
            Production.Yes(s, "SetPowerConnected", false);
            Production.Yes(s, "SetPowerConnected", true);
            Production.No(e, "TryBeginWave", 2, g, 1);
            Assert.That(Production.Get<int>(e, "CompletedWaves"), Is.EqualTo(1));
        }
        [Test]
        public void PauseFreezesDeviceAndRejectsCallbacks()
        {
            var s = Scrapyard(); var e = Encounter(s); int g = Generation(s);
            Production.Yes(s, "SetPowerConnected", true);
            Production.Yes(e, "TryBeginWave", 2, g, 1);
            Production.Yes(e, "TryRegisterEnemy", 2, g, 1, "one");
            Production.Yes(e, "TrySealWave", 2, g, 1, 1);
            Production.Call(s, "Pause"); Production.Call(e, "Tick", 100.0);
            Production.No(e, "TryDefeatEnemy", 2, g, 1, "one");
            Assert.That(Production.Get<double>(e, "ChargeProgress"), Is.Zero);
            Production.Call(s, "Resume"); Production.Call(e, "Tick", 2.0);
            Production.Yes(e, "TryDefeatEnemy", 2, g, 1, "one");
            Production.Yes(e, "TryCompleteWave", 2, g, 1);
        }
        [Test]
        public void MultiwaveRequiresEveryNonemptyWaveAndCharge()
        {
            var s = Scrapyard(); var e = Encounter(s, 2); int g = Generation(s);
            ClearWave(s, e, 1);
            Assert.That(Production.Get<bool>(e, "Complete"), Is.False);
            Production.No(e, "TryBeginWave", 2, g, 3);
            ClearWave(s, e, 2);
            Assert.That(Production.Get<bool>(e, "Complete"), Is.True);
            Production.No(e, "TryBeginWave", 2, g, 3);
        }
        [Test]
        public void CoilRequiresThisSessionsCompletedPoweredEncounterAndRewardsOnce()
        {
            var s = Scrapyard(); var r = Region(s); var e = Encounter(s); int g = Generation(s);
            Production.No(r, "TryAcquireCoil", 2, g, "coil");
            Production.No(r, "TryResolvePoweredEncounter", 2, g, e);
            var other = Scrapyard(); var foreign = Encounter(other); ClearWave(other, foreign, 1);
            Production.No(r, "TryResolvePoweredEncounter", 2, g, foreign);
            ClearWave(s, e, 1);
            Production.Yes(r, "TryResolvePoweredEncounter", 2, g, e);
            Production.No(r, "TryResolvePoweredEncounter", 2, g, e);
            Production.Yes(r, "TryAcquireCoil", 2, g, "coil");
            Production.Yes(r, "TryInstallArc", 2, g);
            Production.No(r, "TryAcquireCoil", 2, g, "coil-again");
            Production.No(r, "TryInstallArc", 2, g);
            Production.No(r, "CanExitRegion", 2, g, true);
            Production.Yes(s, "SetPowerConnected", false);
            Production.Yes(r, "CanExitRegion", 2, g, true);
        }
        [Test]
        public void WholeJourneyRequiresRamPoweredScrapyardAndBeaconThenUnpluggedVehicleEscape()
        {
            var s = Production.Session(); var r = Region(s); int g = Generation(s);
            Production.Yes(r, "TryAcquireRam", 1, g, "ram"); Production.Yes(r, "TryInstallRam", 1, g);
            Production.Yes(r, "TryOpenRamGate", 1, g, true); Production.Yes(r, "CanExitRegion", 1, g, true);
            Production.Yes(s, "TryAdvance"); Production.Yes(s, "CompleteLoading");
            var e = Encounter(s); ClearWave(s, e, 1);
            Production.Yes(r, "TryResolvePoweredEncounter", 2, g, e);
            Production.Yes(r, "TryAcquireCoil", 2, g, "coil"); Production.Yes(r, "TryInstallArc", 2, g);
            Production.No(r, "CanExitRegion", 2, g, true); Production.Yes(s, "SetPowerConnected", false);
            Production.Yes(r, "CanExitRegion", 2, g, true); Production.Yes(s, "TryAdvance"); Production.Yes(s, "CompleteLoading");
            var beacon = Encounter(s, 2); ClearWave(s, beacon, 1);
            Production.No(r, "TryResolvePoweredEncounter", 3, g, beacon);
            ClearWave(s, beacon, 2); Production.Yes(r, "TryResolvePoweredEncounter", 3, g, beacon);
            Production.No(s, "TryReachSafety", true); Production.Yes(s, "SetPowerConnected", false);
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "OnFoot"));
            Production.No(r, "CanExitRegion", 3, g, true); Production.No(s, "TryReachSafety", true);
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "Driving"));
            Production.No(r, "CanExitRegion", 3, g, false); Production.Yes(r, "CanExitRegion", 3, g, true);
            Production.Yes(s, "TryReachSafety", true); Production.Status(s, "Completed");
        }
        [Test]
        public void OldObjectsCannotMutateRestartedJourneyEvenWithOldMatchingEventTokens()
        {
            var s = Production.Session(); var r = Region(s); int old = Generation(s);
            Production.Call(s, "DamagePlayer", 100); Production.Yes(s, "RestartJourney");
            Production.No(r, "TryAcquireRam", 1, old, "stale");
            Production.No(r, "TryAcquireRam", 1, Generation(s), "new-token-old-object");
            var fresh = Region(s); Production.Yes(fresh, "TryAcquireRam", 1, Generation(s), "fresh");
        }
        [Test]
        public void OldEncounterDoesNotResumeAfterReturningToSameRegionInNewJourney()
        {
            var s = Scrapyard(); var e = Encounter(s); int old = Generation(s);
            Production.Yes(s, "SetPowerConnected", true); Production.Yes(e, "TryBeginWave", 2, old, 1);
            Production.Yes(e, "TryRegisterEnemy", 2, old, 1, "old"); Production.Yes(e, "TrySealWave", 2, old, 1, 1);
            Production.Call(s, "DamageVehicle", 300); Production.Yes(s, "RestartJourney");
            Production.Advance(s, "RamPart", "new-ram"); Production.Yes(s, "SetPowerConnected", true);
            Production.Call(e, "Tick", 100.0); Production.No(e, "TryDefeatEnemy", 2, old, 1, "old");
            Assert.That(Production.Get<double>(e, "ChargeProgress"), Is.Zero);
        }
        [Test]
        public void InvalidEncounterTimeThrowsWithoutChangingCharge()
        {
            var s = Scrapyard(); var e = Encounter(s);
            Assert.Throws<ArgumentOutOfRangeException>(() => Production.Call(e, "Tick", double.NaN));
            Assert.Throws<ArgumentOutOfRangeException>(() => Production.Call(e, "Tick", -1.0));
            Assert.That(Production.Get<double>(e, "ChargeProgress"), Is.Zero);
        }
    }
}

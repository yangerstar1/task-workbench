using System;
using System.Collections;
using NUnit.Framework;

namespace DesertRV.Tests
{
    public sealed class JourneyPacingTelemetryTests
    {
        static object Telemetry(object s) { var t = Production.New("JourneyPacingTelemetry"); Production.Call(t, "Reset", s); return t; }
        static IList Rows(object t) => (IList)Production.Get(t, "Regions");
        static T Field<T>(object row, string name) => (T)row.GetType().GetField(name).GetValue(row);
        static void Sample(object t, object s, double time = 1, double displacement = 0, bool cabin = false,
            bool busy = false, bool threat = false, bool pending = false, int alive = 0, double margin = 100)
            => Production.Call(t, "Sample", s, time, displacement, cabin, busy, threat, pending, alive, margin);
        [Test] public void TelemetryDoesNotAdvanceStormOrChangeGameplayResources()
        {
            var s = Production.Session(); var t = Telemetry(s); Sample(t, s, 10);
            Assert.That(Field<double>(Rows(t)[0], "playingSeconds"), Is.EqualTo(10));
            Assert.That(Production.Get<double>(s, "StormElapsedSeconds"), Is.Zero);
            Assert.That(Production.Get<int>(s, "PlayerHealth"), Is.EqualTo(100));
            Assert.That(Production.Get<int>(s, "VehicleHealth"), Is.EqualTo(300));
            Assert.That(Production.Get<int>(s, "ReserveAmmo"), Is.EqualTo(96));
            Assert.That(Production.Get<int>(s, "LoadedAmmo"), Is.EqualTo(12));
            Assert.That(Production.Get<int>(s, "SceneId"), Is.EqualTo(1));
            Production.Status(s, "Playing");
        }
        [Test] public void InvalidSamplesAndForeignSessionsDoNotCreateRows()
        {
            var s = Production.Session(); var t = Telemetry(s);
            foreach (double time in new[] { -1, 0, double.NaN, double.PositiveInfinity }) Sample(t, s, time);
            Sample(t, s, displacement: -1); Sample(t, s, displacement: double.NaN);
            Sample(t, s, margin: double.NegativeInfinity); Sample(t, s, alive: -1);
            Sample(t, Production.Session());
            Production.Call(s, "Pause"); Sample(t, s);
            Assert.That(Rows(t).Count, Is.Zero);
        }
        [Test] public void WaitingExcludesExplorationThreatAndBusyActions()
        {
            var s = Production.Session(); var t = Telemetry(s); Production.Yes(s, "SetPowerConnected", true);
            Sample(t, s, pending: true); // Sole truly stationary empty powered observation.
            Sample(t, s, displacement: 1, pending: true);
            Sample(t, s, threat: true, pending: true);
            Sample(t, s, busy: true, pending: true);
            Sample(t, s, pending: true, alive: 1);
            Production.Yes(s, "SetPowerConnected", false); Sample(t, s, pending: true);
            Assert.That(Field<double>(Rows(t)[0], "emptyPoweredWaitSeconds"), Is.EqualTo(1));
            Assert.That(Field<double>(Rows(t)[0], "playingSeconds"), Is.EqualTo(6));
        }
        [Test] public void DiagnosticEventsDeduplicateAndRejectStaleWrongRegionOrPaused()
        {
            var s = Production.Session(); var t = Telemetry(s);
            Production.Call(t, "RecordSupply", 1, 1, "a"); Production.Call(t, "RecordSupply", 1, 1, "a");
            Production.Call(t, "RecordSupply", 2, 1, "b"); Production.Call(t, "RecordSupply", 1, 2, "b");
            Production.Call(t, "RecordShot", 1, 1, 1, 1); Production.Call(t, "RecordShot", 1, 1, 1, 1);
            Production.Call(t, "RecordShot", 1, 1, 2, 1); Production.Call(t, "RecordShot", 1, 1, 0, 1);
            Production.Call(s, "Pause"); Production.Call(t, "RecordShot", 1, 1, 2, 2);
            Assert.That(Field<int>(Rows(t)[0], "suppliesTaken"), Is.EqualTo(1));
            Assert.That(Field<int>(Rows(t)[0], "shotsFired"), Is.EqualTo(2));
            Assert.That(Field<bool>(Rows(t)[0], "hasStormMargin"), Is.False);
            Assert.That(double.IsInfinity(Field<double>(Rows(t)[0], "minimumStormMarginSeconds")), Is.False);
        }
        [Test] public void RestartRequiresResetBeforeNewGenerationCanRecord()
        {
            var s = Production.Session(); var t = Telemetry(s); Sample(t, s);
            Production.Call(s, "DamagePlayer", 100); Production.Yes(s, "RestartJourney");
            Sample(t, s); Production.Call(t, "RecordSupply", 1, 2, "a");
            Assert.That(Field<double>(Rows(t)[0], "playingSeconds"), Is.EqualTo(1));
            Production.Call(t, "Reset", s); Assert.That(Rows(t).Count, Is.Zero);
            Production.Call(t, "RecordShot", 1, 1, 1, 1); Assert.That(Rows(t).Count, Is.Zero);
            Production.Call(t, "RecordShot", 1, 2, 1, 1); Assert.That(Rows(t).Count, Is.EqualTo(1));
        }
        [Test] public void SampledHealthLossIsNetDeclineAndMarginIsMinimum()
        {
            var s = Production.Session(); var t = Telemetry(s);
            Production.Call(s, "DamagePlayer", 9); Production.Call(s, "DamageVehicle", 100); Sample(t, s, margin: 5);
            Production.Yes(s, "TryRepair"); Sample(t, s, margin: 20);
            Production.Call(s, "DamageVehicle", 5); Sample(t, s, margin: -3);
            Assert.That(Field<int>(Rows(t)[0], "observedPlayerHealthLoss"), Is.EqualTo(9));
            Assert.That(Field<int>(Rows(t)[0], "observedVehicleHealthLoss"), Is.EqualTo(105));
            Assert.That(Field<double>(Rows(t)[0], "minimumStormMarginSeconds"), Is.EqualTo(-3));
        }
        [Test] public void ExtremeFiniteSamplesSaturateWithoutNonfiniteCounters()
        {
            var s = Production.Session(); var t = Telemetry(s);
            Sample(t, s, double.MaxValue, threat: true); Sample(t, s, double.MaxValue, threat: true);
            Assert.That(Field<double>(Rows(t)[0], "playingSeconds"), Is.EqualTo(double.MaxValue));
            Assert.That(Field<double>(Rows(t)[0], "threatSeconds"), Is.EqualTo(double.MaxValue));
        }
    }
}

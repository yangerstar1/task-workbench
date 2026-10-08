using System;
using System.Collections.Generic;

namespace DesertRV
{
    [Serializable] public sealed class RegionPacingSample
    {
        public int region;
        public double playingSeconds, threatSeconds, emptyPoweredWaitSeconds, stationaryCabinSeconds;
        public bool hasStormMargin;
        public double minimumStormMarginSeconds;
        public int suppliesTaken, shotsFired, observedPlayerHealthLoss, observedVehicleHealthLoss;
    }
    // Observations only. Never advances a clock, changes inventory, or decides encounter outcomes.
    public sealed class JourneyPacingTelemetry
    {
        readonly List<RegionPacingSample> rows = new List<RegionPacingSample>();
        readonly HashSet<string> supplyEvents = new HashSet<string>();
        readonly HashSet<string> shotEvents = new HashSet<string>();
        SessionState owner;
        int generation, previousHealth, previousVehicle;
        public IReadOnlyList<RegionPacingSample> Regions => rows;
        public void Reset(SessionState state)
        {
            rows.Clear(); supplyEvents.Clear(); shotEvents.Clear(); owner = state;
            generation = state == null ? 0 : state.Generation;
            previousHealth = state == null ? 0 : state.PlayerHealth;
            previousVehicle = state == null ? 0 : state.VehicleHealth;
        }
        bool Current(int region, int eventGeneration) => owner != null && owner.Status == SessionStatus.Playing &&
            generation > 0 && eventGeneration == generation && owner.Generation == generation &&
            region >= 1 && region <= 3 && region == owner.SceneId;
        RegionPacingSample Row(int region)
        {
            var row = rows.Find(r => r.region == region);
            if (row == null) { row = new RegionPacingSample { region = region }; rows.Add(row); }
            return row;
        }
        public void RecordSupply(int region, int eventGeneration, string id)
        {
            if (Current(region, eventGeneration) && !string.IsNullOrWhiteSpace(id) && supplyEvents.Add(id))
            { var row = Row(region); row.suppliesTaken = Add(row.suppliesTaken, 1); }
        }
        public void RecordShot(int region, int eventGeneration, int epoch, int sequence)
        {
            if (Current(region, eventGeneration) && epoch > 0 && sequence > 0 && shotEvents.Add(region + "/" + epoch + "/" + sequence))
            { var row = Row(region); row.shotsFired = Add(row.shotsFired, 1); }
        }
        public void Sample(SessionState state, double seconds, double actualDisplacement, bool insideCabin,
            bool actionBusy, bool threatNearby, bool poweredEncounterPending, int aliveEnemies, double stormMarginSeconds)
        {
            if (!ReferenceEquals(state, owner) || state == null || !Current(state.SceneId, state.Generation) ||
                seconds <= 0 || !Finite(seconds) || !Finite(actualDisplacement) || actualDisplacement < 0 ||
                !Finite(stormMarginSeconds) || aliveEnemies < 0) return;
            var row = Row(state.SceneId); row.playingSeconds = Add(row.playingSeconds, seconds);
            if (threatNearby) row.threatSeconds = Add(row.threatSeconds, seconds);
            bool stationary = actualDisplacement / seconds < .15;
            if (poweredEncounterPending && state.PowerConnected && aliveEnemies == 0 && !threatNearby && !actionBusy && stationary)
                row.emptyPoweredWaitSeconds = Add(row.emptyPoweredWaitSeconds, seconds);
            if (insideCabin && stationary && !actionBusy) row.stationaryCabinSeconds = Add(row.stationaryCabinSeconds, seconds);
            row.minimumStormMarginSeconds = row.hasStormMargin ? Math.Min(row.minimumStormMarginSeconds, stormMarginSeconds) : stormMarginSeconds;
            row.hasStormMargin = true;
            row.observedPlayerHealthLoss = Add(row.observedPlayerHealthLoss, Math.Max(0, previousHealth - state.PlayerHealth));
            row.observedVehicleHealthLoss = Add(row.observedVehicleHealthLoss, Math.Max(0, previousVehicle - state.VehicleHealth));
            previousHealth = state.PlayerHealth; previousVehicle = state.VehicleHealth;
        }
        static int Add(int a, int b) => (int)Math.Min(int.MaxValue, (long)a + b);
        static double Add(double a, double b) => a > double.MaxValue - b ? double.MaxValue : a + b;
        static bool Finite(double x) => !double.IsNaN(x) && !double.IsInfinity(x);
    }
}

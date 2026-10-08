using System;

namespace DesertRV
{
    // Thin, ordered scene facts. SessionState remains the sole owner of resources and upgrades.
    public sealed class RegionProgressState
    {
        readonly SessionState session;
        readonly int generation;
        bool ramGateOpened, scrapyardResolved, beaconResolved;
        public RegionProgressState(SessionState session, int generation)
        {
            this.session = session ?? throw new ArgumentNullException(nameof(session));
            if (generation <= 0) throw new ArgumentOutOfRangeException(nameof(generation));
            this.generation = generation;
        }
        bool Live(int region, int eventGeneration) => region == session.SceneId &&
            eventGeneration == generation && session.Generation == generation && session.Status == SessionStatus.Playing;
        public bool TryAcquireRam(int region, int eventGeneration, string pickupId) =>
            Live(region, eventGeneration) && region == 1 && session.TryCollect(pickupId, ComponentPart.RamPart);
        public bool TryInstallRam(int region, int eventGeneration) =>
            Live(region, eventGeneration) && region == 1 && session.TryInstall(ComponentPart.RamPart);
        public bool TryOpenRamGate(int region, int eventGeneration, bool ramContact)
        {
            if (!Live(region, eventGeneration) || region != 1 || !ramContact || ramGateOpened ||
                session.Control != ControlMode.Driving || (session.Upgrades & VehicleUpgrades.Ram) == 0) return false;
            ramGateOpened = true; session.SetGateOpen(true); session.SetObjectivesResolved(true); return true;
        }
        public bool TryResolvePoweredEncounter(int region, int eventGeneration, PoweredEncounterState encounter)
        {
            if (!Live(region, eventGeneration) || encounter == null || !encounter.BelongsTo(session) ||
                encounter.Region != region || encounter.Generation != generation || !encounter.Complete) return false;
            if (region == 2)
            {
                if (scrapyardResolved) return false;
                scrapyardResolved = true; return true;
            }
            if (region != 3 || beaconResolved) return false;
            beaconResolved = true; session.SetGateOpen(true); session.SetObjectivesResolved(true); return true;
        }
        public bool TryAcquireCoil(int region, int eventGeneration, string pickupId) =>
            Live(region, eventGeneration) && region == 2 && scrapyardResolved && session.TryCollect(pickupId, ComponentPart.Coil);
        public bool TryInstallArc(int region, int eventGeneration)
        {
            if (!Live(region, eventGeneration) || region != 2 || !scrapyardResolved || !session.TryInstall(ComponentPart.Coil)) return false;
            session.SetGateOpen(true); session.SetObjectivesResolved(true); return true;
        }
        // Does not advance: JourneySession must issue the matching async load ticket exactly once.
        public bool CanExitRegion(int region, int eventGeneration, bool vehicleInsideExit)
        {
            if (!Live(region, eventGeneration) || !vehicleInsideExit || session.Control != ControlMode.Driving ||
                session.PowerConnected || !session.GateOpen || !session.ObjectivesResolved) return false;
            return region == 1 ? ramGateOpened && (session.Upgrades & VehicleUpgrades.Ram) != 0 :
                region == 2 ? scrapyardResolved && (session.Upgrades & VehicleUpgrades.Arc) != 0 : region == 3 && beaconResolved;
        }
    }
}

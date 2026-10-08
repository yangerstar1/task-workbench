using System;
using System.Collections.Generic;

namespace DesertRV
{
    public enum SessionStatus { Menu, Loading, Playing, Paused, Failed, Completed }
    public enum ControlMode { Driving, OnFoot }
    public enum ComponentPart { RamPart, Coil }
    [Flags] public enum VehicleUpgrades { None = 0, Ram = 1, Arc = 2 }

    // One journey's facts. No Unity objects, persistence or network handles.
    public sealed class SessionState
    {
        public SessionStatus Status { get; private set; } = SessionStatus.Menu;
        public ControlMode Control { get; private set; } = ControlMode.Driving;
        public int SceneId { get; private set; } = 1;
        public int PlayerHealth { get; private set; } = 100;
        public int VehicleHealth { get; private set; } = 300;
        public int LoadedAmmo { get; private set; } = 12;
        public int ReserveAmmo { get; private set; } = 96;
        public int RepairKits { get; private set; } = 2;
        public VehicleUpgrades Upgrades { get; private set; }
        public bool PowerConnected { get; private set; }
        public bool GateOpen { get; private set; }
        public bool ObjectivesResolved { get; private set; }
        public bool StormConfigured { get; private set; }
        public double StormSpeed { get; private set; }
        public double StormDamagePerSecond { get; private set; }
        public double StormElapsedSeconds { get; private set; }
        public double StormFrontProgress => stormStartProgress + StormSpeed * StormElapsedSeconds;
        double stormStartProgress;
        double stormDamageRemainder;
        SessionStatus resumeStatus = SessionStatus.Playing;
        readonly HashSet<string> collected = new HashSet<string>();
        readonly HashSet<ComponentPart> parts = new HashSet<ComponentPart>();

        // Configure once, before the journey starts. Distances use the shared journey coordinate,
        // never a scene-local origin or the overhead camera position. Balance comes from the level.
        public bool ConfigureStorm(double initialFrontProgress, double speed, double damagePerSecond)
        {
            if (Status != SessionStatus.Menu || StormConfigured || !Finite(initialFrontProgress) ||
                !Finite(speed) || speed <= 0 || !Finite(damagePerSecond) || damagePerSecond <= 0) return false;
            stormStartProgress = initialFrontProgress;
            StormSpeed = speed; StormDamagePerSecond = damagePerSecond; StormConfigured = true;
            return true;
        }

        static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
        public bool IsInStorm(double playerProgress) => StormConfigured && playerProgress <= StormFrontProgress;

        // The player's actual start/end positions include driving and being inside the RV.
        // Integrating a boundary crossing avoids a full frame of damage when only partly exposed.
        public void AdvanceStorm(double deltaSeconds, double playerProgressAtStart, double playerProgressAtEnd)
        {
            if (Status != SessionStatus.Playing || !StormConfigured) return;
            if (!Finite(deltaSeconds) || deltaSeconds < 0 || !Finite(playerProgressAtStart) || !Finite(playerProgressAtEnd))
                throw new ArgumentOutOfRangeException(nameof(deltaSeconds), "Storm simulation requires finite time and positions.");
            if (deltaSeconds == 0) return;
            double startDepth = StormFrontProgress - playerProgressAtStart;
            StormElapsedSeconds += deltaSeconds;
            double endDepth = StormFrontProgress - playerProgressAtEnd;
            double exposedSeconds = 0;
            if (startDepth >= 0 && endDepth >= 0) exposedSeconds = deltaSeconds;
            else if ((startDepth >= 0) != (endDepth >= 0))
            {
                double crossingFraction = -startDepth / (endDepth - startDepth);
                exposedSeconds = deltaSeconds * (startDepth >= 0 ? crossingFraction : 1 - crossingFraction);
            }
            stormDamageRemainder += exposedSeconds * StormDamagePerSecond;
            // Retain fractional damage across frames and brief exits; roundoff must not lose ticks.
            int damage = (int)Math.Min(PlayerHealth, Math.Floor(stormDamageRemainder + 1e-9));
            stormDamageRemainder = Math.Max(0, stormDamageRemainder - damage);
            DamagePlayer(damage);
        }

        public bool Start()
        {
            if (Status != SessionStatus.Menu || !StormConfigured) return false;
            Status = SessionStatus.Playing;
            return true;
        }
        public void Pause()
        {
            if (Status != SessionStatus.Playing && Status != SessionStatus.Loading) return;
            resumeStatus = Status;
            Status = SessionStatus.Paused;
        }
        public void Resume() { if (Status == SessionStatus.Paused) Status = resumeStatus; }
        public void SetControl(ControlMode mode)
        {
            if (Status == SessionStatus.Playing && Enum.IsDefined(typeof(ControlMode), mode)) Control = mode;
        }
        public bool BeginLoading()
        {
            if (Status != SessionStatus.Playing) return false;
            Status = SessionStatus.Loading;
            return true;
        }
        public bool CompleteLoading()
        {
            // Async loading may finish while the app is in the background.
            // That callback must not unpause the game or start the storm.
            if (Status == SessionStatus.Paused && resumeStatus == SessionStatus.Loading)
            {
                resumeStatus = SessionStatus.Playing;
                return true;
            }
            if (Status != SessionStatus.Loading) return false;
            Status = SessionStatus.Playing;
            return true;
        }
        public bool SetPowerConnected(bool connected)
        {
            if (Status != SessionStatus.Playing) return false;
            PowerConnected = connected;
            return true;
        }
        public bool SetGateOpen(bool open)
        {
            if (Status != SessionStatus.Playing) return false;
            GateOpen = open;
            return true;
        }
        public bool SetObjectivesResolved(bool resolved)
        {
            if (Status != SessionStatus.Playing) return false;
            ObjectivesResolved = resolved;
            return true;
        }
        public bool HasPart(ComponentPart part) => parts.Contains(part);

        public bool TryCollect(string id, ComponentPart part)
        {
            if (Status != SessionStatus.Playing || string.IsNullOrWhiteSpace(id) ||
                !Enum.IsDefined(typeof(ComponentPart), part) || parts.Contains(part)) return false;
            var upgrade = part == ComponentPart.RamPart ? VehicleUpgrades.Ram : VehicleUpgrades.Arc;
            if ((Upgrades & upgrade) != 0 || !collected.Add(id)) return false;
            parts.Add(part);
            return true;
        }

        public bool TryInstall(ComponentPart part)
        {
            if (Status != SessionStatus.Playing || !parts.Contains(part)) return false;
            var upgrade = part == ComponentPart.RamPart ? VehicleUpgrades.Ram : VehicleUpgrades.Arc;
            if ((Upgrades & upgrade) != 0) return false;
            parts.Remove(part);
            Upgrades |= upgrade;
            return true;
        }

        public bool TryFire()
        {
            if (Status != SessionStatus.Playing || LoadedAmmo == 0) return false;
            LoadedAmmo--;
            return true;
        }

        public void Reload()
        {
            if (Status != SessionStatus.Playing) return;
            int moved = Math.Min(12 - LoadedAmmo, ReserveAmmo);
            LoadedAmmo += moved; ReserveAmmo -= moved;
        }

        public void DamagePlayer(int amount)
        {
            if (Status != SessionStatus.Playing || amount <= 0) return;
            PlayerHealth = Math.Max(0, PlayerHealth - amount);
            if (PlayerHealth == 0) Status = SessionStatus.Failed;
        }

        public void DamageVehicle(int amount)
        {
            if (Status != SessionStatus.Playing || amount <= 0) return;
            VehicleHealth = Math.Max(0, VehicleHealth - amount);
            if (VehicleHealth == 0) Status = SessionStatus.Failed;
        }

        public bool TryRepair()
        {
            if (Status != SessionStatus.Playing || RepairKits == 0 || VehicleHealth == 300) return false;
            RepairKits--; VehicleHealth = Math.Min(300, VehicleHealth + 95); return true;
        }

        public bool TryAdvance()
        {
            // Called by the real RV exit trigger, never by the on-foot controller.
            if (Status != SessionStatus.Playing || Control != ControlMode.Driving || !ObjectivesResolved) return false;
            if (SceneId == 1 && (Upgrades & VehicleUpgrades.Ram) == 0) return false;
            if (SceneId == 2 && (Upgrades & VehicleUpgrades.Arc) == 0) return false;
            if (SceneId == 3 || PowerConnected) return false;
            // Moving to another region is not a free heal, refill or new journey.
            // Pickup IDs are journey-global so revisiting cannot duplicate rewards.
            SceneId++;
            PowerConnected = false; GateOpen = false; ObjectivesResolved = false;
            Control = ControlMode.Driving;
            Status = SessionStatus.Loading;
            return true;
        }

        // The world controller supplies this fact from the actual vehicle-safe-zone trigger.
        public bool TryReachSafety(bool vehicleInsideSafeZone)
        {
            if (Status != SessionStatus.Playing || SceneId != 3 || !ObjectivesResolved ||
                !GateOpen || PowerConnected || Control != ControlMode.Driving || !vehicleInsideSafeZone) return false;
            Status = SessionStatus.Completed;
            return true;
        }

        public bool RestartJourney()
        {
            if (Status != SessionStatus.Failed && Status != SessionStatus.Completed) return false;
            ResetJourney();
            return true;
        }

        // Retained for callers in the old slice; it now obeys the approved whole-run reset.
        [Obsolete("Use RestartJourney: failure restarts the entire journey, not the current stage.")]
        public void RetryStage() { if (Status == SessionStatus.Failed) RestartJourney(); }

        void ResetJourney()
        {
            SceneId = 1; Upgrades = VehicleUpgrades.None;
            StormElapsedSeconds = 0;
            stormDamageRemainder = 0;
            PlayerHealth = 100; VehicleHealth = 300;
            LoadedAmmo = 12; ReserveAmmo = 96; RepairKits = 2;
            PowerConnected = false; GateOpen = false; ObjectivesResolved = false;
            collected.Clear(); parts.Clear();
            resumeStatus = SessionStatus.Playing;
            Control = ControlMode.Driving; Status = SessionStatus.Playing;
        }
    }
}

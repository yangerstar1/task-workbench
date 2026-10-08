using System;
using System.Collections.Generic;

namespace DesertRV
{
    // A pulse can damage each actor once even if it owns multiple colliders.
    public sealed class ArcCombatState
    {
        readonly SessionState session;
        readonly int region, generation;
        readonly double cooldownSeconds, pulseSeconds;
        readonly HashSet<string> hitTargets = new HashSet<string>();
        double pulseRemaining;
        public int PulseId { get; private set; }
        public double CooldownRemaining { get; private set; }
        public ArcCombatState(SessionState session, int region, int generation, double cooldownSeconds, double pulseSeconds)
        {
            this.session = session ?? throw new ArgumentNullException(nameof(session));
            if (region < 1 || region > 3 || generation <= 0 || double.IsNaN(cooldownSeconds) ||
                double.IsInfinity(cooldownSeconds) || cooldownSeconds <= 0 || double.IsNaN(pulseSeconds) ||
                double.IsInfinity(pulseSeconds) || pulseSeconds <= 0 || pulseSeconds > cooldownSeconds)
                throw new ArgumentOutOfRangeException(nameof(cooldownSeconds));
            this.region = region; this.generation = generation;
            this.cooldownSeconds = cooldownSeconds; this.pulseSeconds = pulseSeconds;
        }
        bool Live(int eventRegion, int eventGeneration) => session.Status == SessionStatus.Playing &&
            session.SceneId == region && eventRegion == region && eventGeneration == generation && session.Generation == generation;
        public int TryBeginPulse(int eventRegion, int eventGeneration)
        {
            if (!Live(eventRegion, eventGeneration) || session.Control != ControlMode.Driving ||
                (session.Upgrades & VehicleUpgrades.Arc) == 0 || CooldownRemaining > 0) return 0;
            PulseId++; CooldownRemaining = cooldownSeconds; pulseRemaining = pulseSeconds; hitTargets.Clear(); return PulseId;
        }
        public bool TryHitTarget(int eventRegion, int eventGeneration, int pulseId, string targetId)
        {
            if (!Live(eventRegion, eventGeneration) || pulseId != PulseId || pulseId <= 0 || pulseRemaining <= 0 ||
                session.Control != ControlMode.Driving || string.IsNullOrWhiteSpace(targetId)) return false;
            return hitTargets.Add(targetId);
        }
        public void Tick(double deltaSeconds)
        {
            if (!Live(region, generation)) return;
            if (double.IsNaN(deltaSeconds) || double.IsInfinity(deltaSeconds) || deltaSeconds < 0)
                throw new ArgumentOutOfRangeException(nameof(deltaSeconds));
            CooldownRemaining = Math.Max(0, CooldownRemaining - deltaSeconds);
            pulseRemaining = Math.Max(0, pulseRemaining - deltaSeconds);
        }
    }
}

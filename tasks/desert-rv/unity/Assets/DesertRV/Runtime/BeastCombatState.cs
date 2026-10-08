using System;

namespace DesertRV
{
    // Attack identity and weak-point timer only; BeastActor owns this creature's health and motion.
    public sealed class BeastCombatState
    {
        readonly SessionState session;
        readonly int region, generation;
        bool charging, chargeHit;
        public int ChargeId { get; private set; }
        public double WeakPointRemaining { get; private set; }
        public bool WeakPointOpen => WeakPointRemaining > 0;
        public BeastCombatState(SessionState session, int region, int generation)
        {
            this.session = session ?? throw new ArgumentNullException(nameof(session));
            if (region < 1 || region > 3 || generation <= 0) throw new ArgumentOutOfRangeException(nameof(region));
            this.region = region; this.generation = generation;
        }
        bool Live(int eventRegion, int eventGeneration) => session.Status == SessionStatus.Playing &&
            session.SceneId == region && eventRegion == region && eventGeneration == generation && session.Generation == generation;
        public int TryBeginCharge(int eventRegion, int eventGeneration)
        {
            if (!Live(eventRegion, eventGeneration) || charging || WeakPointOpen) return 0;
            charging = true; chargeHit = false; ChargeId++; return ChargeId;
        }
        public bool TryRegisterChargeHit(int eventRegion, int eventGeneration, int chargeId)
        {
            if (!Live(eventRegion, eventGeneration) || !charging || chargeHit || chargeId != ChargeId) return false;
            chargeHit = true; return true;
        }
        public bool TryBeginRecovery(int eventRegion, int eventGeneration, int chargeId, double seconds)
        {
            if (!Live(eventRegion, eventGeneration) || !charging || chargeId != ChargeId ||
                double.IsNaN(seconds) || double.IsInfinity(seconds) || seconds <= 0) return false;
            charging = false; WeakPointRemaining = seconds; return true;
        }
        public void Tick(double deltaSeconds)
        {
            if (!Live(region, generation)) return;
            if (double.IsNaN(deltaSeconds) || double.IsInfinity(deltaSeconds) || deltaSeconds < 0)
                throw new ArgumentOutOfRangeException(nameof(deltaSeconds));
            WeakPointRemaining = Math.Max(0, WeakPointRemaining - deltaSeconds);
        }
    }
}

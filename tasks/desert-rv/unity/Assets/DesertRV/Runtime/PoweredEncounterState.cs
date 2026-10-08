using System;
using System.Collections.Generic;

namespace DesertRV
{
    // Device progress is powered; already spawned enemies remain active when unplugged.
    // The scene must register real actors and seal a nonempty spawn batch before it can win.
    public sealed class PoweredEncounterState
    {
        readonly SessionState session;
        readonly HashSet<string> registered = new HashSet<string>();
        readonly HashSet<string> alive = new HashSet<string>();
        readonly int requiredWaves;
        readonly double chargeSeconds;
        bool sealedWave, waveActive;
        double chargedSeconds;
        public int Region { get; }
        public int Generation { get; }
        public int CurrentWave { get; private set; }
        public int CompletedWaves { get; private set; }
        public int AliveCount => alive.Count;
        public double ChargeProgress => Math.Min(1, chargedSeconds / chargeSeconds);
        public bool Complete => CompletedWaves == requiredWaves;

        public PoweredEncounterState(SessionState session, int region, int generation, int requiredWaves, double chargeSeconds)
        {
            this.session = session ?? throw new ArgumentNullException(nameof(session));
            if (region < 2 || region > 3 || generation <= 0 || requiredWaves <= 0 ||
                double.IsNaN(chargeSeconds) || double.IsInfinity(chargeSeconds) || chargeSeconds <= 0)
                throw new ArgumentOutOfRangeException(nameof(requiredWaves));
            Region = region; Generation = generation;
            this.requiredWaves = requiredWaves; this.chargeSeconds = chargeSeconds;
        }
        internal bool BelongsTo(SessionState state) => ReferenceEquals(session, state);
        bool Live(int region, int generation) => session.Status == SessionStatus.Playing &&
            session.SceneId == Region && region == Region && generation == Generation && session.Generation == Generation;
        bool Wave(int region, int generation, int wave) => Live(region, generation) && waveActive && wave == CurrentWave;
        public bool TryBeginWave(int region, int generation, int wave)
        {
            if (!Live(region, generation) || !session.PowerConnected || Complete || waveActive || wave != CompletedWaves + 1) return false;
            CurrentWave = wave; waveActive = true; sealedWave = false; chargedSeconds = 0;
            registered.Clear(); alive.Clear(); return true;
        }
        public bool TryRegisterEnemy(int region, int generation, int wave, string enemyId)
        {
            if (!Wave(region, generation, wave) || sealedWave || string.IsNullOrWhiteSpace(enemyId) || !registered.Add(enemyId)) return false;
            alive.Add(enemyId); return true;
        }
        public bool TrySealWave(int region, int generation, int wave, int expectedCount)
        {
            if (!Wave(region, generation, wave) || sealedWave || expectedCount <= 0 || registered.Count != expectedCount) return false;
            sealedWave = true; return true;
        }
        public bool TryDefeatEnemy(int region, int generation, int wave, string enemyId)
        {
            // Deaths before sealing are retained too; spawning and actor callbacks may interleave.
            if (!Wave(region, generation, wave) || string.IsNullOrWhiteSpace(enemyId)) return false;
            return alive.Remove(enemyId);
        }
        public void Tick(double deltaSeconds)
        {
            if (!Live(Region, Generation)) return;
            if (double.IsNaN(deltaSeconds) || double.IsInfinity(deltaSeconds) || deltaSeconds < 0)
                throw new ArgumentOutOfRangeException(nameof(deltaSeconds));
            if (waveActive && sealedWave && session.PowerConnected)
                chargedSeconds = Math.Min(chargeSeconds, chargedSeconds + deltaSeconds);
        }
        public bool TryCompleteWave(int region, int generation, int wave)
        {
            if (!Wave(region, generation, wave) || !sealedWave || registered.Count == 0 || alive.Count != 0 ||
                !session.PowerConnected || chargedSeconds < chargeSeconds) return false;
            CompletedWaves++; waveActive = false; return true;
        }
    }
}

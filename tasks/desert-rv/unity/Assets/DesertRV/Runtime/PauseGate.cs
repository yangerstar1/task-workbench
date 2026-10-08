using System;

namespace DesertRV
{
    public enum PauseReason { Manual, Background, SystemOverlay }

    // Unity focus/pause callbacks and the menu must use the same gate.
    // Returning to the app only releases Background; it must not dismiss Manual.
    public sealed class PauseGate
    {
        readonly SessionState session;
        readonly bool[] reasons = new bool[3];
        bool ownsPause;

        public PauseGate(SessionState session)
        {
            this.session = session ?? throw new ArgumentNullException(nameof(session));
        }

        public bool IsBlocked => reasons[0] || reasons[1] || reasons[2];

        public bool Set(PauseReason reason, bool blocked)
        {
            if (!Enum.IsDefined(typeof(PauseReason), reason)) return false;
            reasons[(int)reason] = blocked;
            Reconcile();
            return true;
        }

        // Also call after starting/restarting a run, before ticking its simulation.
        // A queued New Game request must not run while the application is hidden.
        public void Reconcile()
        {
            if (IsBlocked)
            {
                if (session.Status == SessionStatus.Playing || session.Status == SessionStatus.Loading)
                {
                    session.Pause();
                    ownsPause = true;
                }
                return;
            }
            if (!ownsPause) return;
            if (session.Status == SessionStatus.Paused) session.Resume();
            ownsPause = false;
        }
    }
}

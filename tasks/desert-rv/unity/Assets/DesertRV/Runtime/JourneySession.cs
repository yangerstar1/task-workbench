using UnityEngine;

namespace DesertRV
{
    // One host per journey. Region controllers never own separate clocks/resources.
    [DefaultExecutionOrder(-100)]
    public sealed class JourneySession : MonoBehaviour
    {
        public SessionState State { get; private set; }
        public PauseGate Pauses { get; private set; }
        public MobileInputAdapter Input { get; private set; }
        public int Generation => State == null ? 0 : State.Generation;
        bool hidden, unfocused, manual, gameplayOverlay;
        int loadSequence, pendingLoad;
        bool previousProgressValid;
        double previousProgress;
        public bool ManualPause => manual;

        void Awake()
        {
            State = new SessionState();
            // First station begins around journey coordinate zero. Balance is provisional;
            // this is a constant-speed world front, not accumulated distance travelled.
            State.ConfigureStorm(-420, .50, 9);
            Pauses = new PauseGate(State);
            Input = GetComponent<MobileInputAdapter>();
            if (!Input) Input = gameObject.AddComponent<MobileInputAdapter>();
        }

        public bool StartJourney()
        {
            if (!State.Start()) return false;
            pendingLoad = 0; gameplayOverlay = false; previousProgressValid = false;
            Pauses.Reconcile(); ApplyContext(); return true;
        }
        public bool RestartJourney()
        {
            if (!State.RestartJourney()) return false;
            pendingLoad = 0; gameplayOverlay = false; previousProgressValid = false;
            Input.ReleaseAll(); Pauses.Reconcile(); ApplyContext(); return true;
        }
        public void TogglePause()
        {
            manual = !manual; Pauses.Set(PauseReason.Manual, manual);
            Input.ReleaseAll(); ApplyContext();
        }
        void OnApplicationPause(bool paused) { hidden = paused; ReconcileBackground(); }
        void OnApplicationFocus(bool focused) { unfocused = !focused; ReconcileBackground(); }
        void ReconcileBackground()
        {
            if (Pauses == null) return;
            Pauses.Set(PauseReason.Background, hidden || unfocused);
            Input.ReleaseAll(); ApplyContext();
        }
        void Update()
        {
            if (UnityEngine.Input.GetKeyDown(KeyCode.Escape) &&
                (State.Status == SessionStatus.Playing || State.Status == SessionStatus.Paused)) TogglePause();
            Pauses.Reconcile(); ApplyContext(); Input.Sample();
        }
        // Workbench/cargo UI blocks gameplay input but deliberately does not stop the storm.
        public void SetGameplayOverlay(bool visible)
        { gameplayOverlay = visible; Input.ReleaseAll(); ApplyContext(); }
        public void ApplyContext()
        {
            Input.SetContext(State.Status != SessionStatus.Playing || gameplayOverlay ? TouchContext.Overlay :
                State.Control == ControlMode.Driving ? TouchContext.Driving : TouchContext.OnFoot);
            bool capture = State.Status == SessionStatus.Playing && !gameplayOverlay &&
                State.Control == ControlMode.OnFoot && !Application.isMobilePlatform;
            Cursor.lockState = capture ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !capture;
        }
        // Region loading calls this with the real position after placing the same RV.
        public void ResetPositionSample(double worldProgress)
        { previousProgress = worldProgress; previousProgressValid = true; }
        public void TickStorm(double seconds, double worldProgress)
        {
            if (!previousProgressValid) ResetPositionSample(worldProgress);
            State.AdvanceStorm(seconds, previousProgress, worldProgress);
            previousProgress = worldProgress;
        }
        public readonly struct LoadTicket
        {
            public readonly int Generation, Sequence, Scene;
            public bool IsValid => Sequence != 0;
            public LoadTicket(int generation, int sequence, int scene)
            { Generation = generation; Sequence = sequence; Scene = scene; }
        }
        public bool IsCurrentLoad(LoadTicket ticket) => ticket.IsValid && ticket.Generation == Generation &&
            ticket.Sequence == pendingLoad && ticket.Scene == State.SceneId;
        // Initial scene and whole-run reset use the same callback fencing as transitions.
        public LoadTicket BeginCurrentRegionLoad()
        {
            if (!State.BeginLoading()) return default;
            pendingLoad = ++loadSequence;
            Input.ReleaseAll(); ApplyContext();
            return new LoadTicket(Generation, pendingLoad, State.SceneId);
        }
        public LoadTicket BeginRegionAdvance()
        {
            if (!State.TryAdvance()) return default;
            pendingLoad = ++loadSequence;
            Input.ReleaseAll(); ApplyContext();
            return new LoadTicket(Generation, pendingLoad, State.SceneId);
        }
        // A callback must identify both this journey and this exact transition.
        public bool CompleteRegionLoad(LoadTicket ticket, double spawnProgress)
        {
            if (!ticket.IsValid || ticket.Generation != Generation || ticket.Sequence != pendingLoad ||
                ticket.Scene != State.SceneId || !State.CompleteLoading()) return false;
            pendingLoad = 0;
            Input.ReleaseAll(); ResetPositionSample(spawnProgress);
            Pauses.Reconcile(); ApplyContext(); return true;
        }
    }
}

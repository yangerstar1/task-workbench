using UnityEngine;

namespace DesertRV
{
    // The only Motor / storm / actions tick and input-consumption owner in production.
    [DefaultExecutionOrder(50)]
    public sealed class JourneyDirector : MonoBehaviour
    {
        static JourneyDirector active;
        public JourneySession journey;
        public JourneyMotor motor;
        public JourneyActions actions;
        public RegionLoader loader;
        public JourneyHud hud;
        public RegionBinding Region { get; private set; }
        public PoweredEncounterState Encounter { get; private set; }
        public JourneyPacingTelemetry Pacing { get; } = new JourneyPacingTelemetry();
        public JourneyTelemetry Telemetry { get; } = new JourneyTelemetry();
        public string LoadError { get; private set; }
        public double WorldProgress => Region ? Region.WorldProgress(motor.PlayerPosition) : 0;
        public bool OwnsJourney => active == this && isActiveAndEnabled;
        public bool CanRetryLoad => OwnsJourney && !string.IsNullOrEmpty(LoadError) && journey.IsCurrentLoad(pending) && !loader.Busy;
        RegionProgressState progress;
        JourneySession.LoadTicket pending;
        bool roadActivated;
        double minimumSpawnProgress;
        void Awake()
        {
            if (active && active != this)
            { Debug.LogError("Only one JourneyDirector may own simulation and input.", this); enabled = false; return; }
            if (!journey || !motor || !actions || !loader || !hud || transform.parent ||
                !journey.transform.IsChildOf(transform) || !motor.transform.IsChildOf(transform) ||
                !motor.vehicle.IsChildOf(transform) || !motor.view.transform.IsChildOf(transform) ||
                !hud.transform.IsChildOf(transform) || !actions.transform.IsChildOf(transform) ||
                !loader.transform.IsChildOf(transform))
            { Debug.LogError("Journey requires one configured persistent root with Session/Motor/RV/camera/HUD/actions/loader.", this); enabled = false; return; }
            active = this;
            DontDestroyOnLoad(gameObject);
            motor.ObstacleContact += OnObstacleContact;
            actions.SupplyCollected += OnSupplyCollected;
            actions.ShotPresented += OnShotPresented;
        }
        void OnDestroy()
        {
            if (active == this) active = null;
            if (motor) motor.ObstacleContact -= OnObstacleContact;
            if (actions) { actions.SupplyCollected -= OnSupplyCollected; actions.ShotPresented -= OnShotPresented; }
        }
        void OnSupplyCollected(int region, string id, SupplyKind kind, int amount)
        {
            if (OwnsJourney && actions.PresentationPlaying && amount > 0 && region == journey.State.SceneId)
                Pacing.RecordSupply(region, actions.PresentationGeneration, id);
        }
        void OnShotPresented(ShotPresentationEvent shot)
        {
            if (OwnsJourney && actions.PresentationPlaying && shot.Epoch == actions.PresentationEpoch)
                Pacing.RecordShot(journey.State.SceneId, actions.PresentationGeneration, shot.Epoch, shot.Sequence);
        }
        public void Begin() { if (OwnsJourney && journey.StartJourney()) ResetRun(); }
        public void Restart() { if (OwnsJourney && journey.RestartJourney()) ResetRun(); }
        void ResetRun()
        {
            minimumSpawnProgress = double.NegativeInfinity;
            Pacing.Reset(journey.State); Telemetry.Reset(); progress = new RegionProgressState(journey.State, journey.Generation);
            pending = journey.BeginCurrentRegionLoad(); RequestLoad();
        }
        public void RetryLoad() { if (CanRetryLoad) RequestLoad(); }
        void RequestLoad()
        {
            LoadError = null;
            loader.Load(journey, pending, BindRegion, error => { LoadError = error; actions.Say(error, 30); });
        }
        bool BindRegion(RegionBinding region)
        {
            if (!OwnsJourney || !journey.IsCurrentLoad(pending) || region.regionOffset < minimumSpawnProgress) return false;
            Region = region;
            // Mapping is authored in a fixed direction plus monotonically increasing regionOffset.
            motor.PlaceForRegion(region.spawn.position, region.spawn.rotation);
            foreach (var enemy in region.AllEnemies()) { enemy.journey = journey; enemy.player = motor; enemy.ResetActor(); }
            if (region.guards != null) foreach (var enemy in region.guards) enemy.gameObject.SetActive(true);
            if (region.roadBeasts != null) foreach (var enemy in region.roadBeasts) enemy.gameObject.SetActive(false);
            if (region.waves != null) foreach (var wave in region.waves) foreach (var enemy in wave.enemies) enemy.gameObject.SetActive(false);
            roadActivated = false;
            Encounter = region.region >= 2 ? new PoweredEncounterState(journey.State, region.region, journey.Generation, region.waves.Length, region.chargeSeconds) : null;
            actions.Bind(region, progress);
            return journey.CompleteRegionLoad(pending, WorldProgress);
        }
        void OnObstacleContact(RaycastHit hit, float speed)
        {
            var collider = hit.collider;
            if (!Region || collider != Region.ramGate || speed <= 3 || Vector3.Dot(-hit.normal, motor.Forward) <= .45f) return;
            // Motor emits only real swept forward contacts. Confirm the gate is ahead too.
            if (Vector3.Dot(hit.point - motor.vehicle.position, motor.Forward) <= 1.8f) return;
            if (progress.TryOpenRamGate(Region.region, journey.Generation, true))
            { collider.enabled = false; actions.Say("撞开路障，驶向下一地区。", 4); }
        }
        void Update()
        {
            if (!OwnsJourney || !journey || journey.Input == null) return;
            try
            {
                if (!Region || journey.State.Status != SessionStatus.Playing) { actions.SetPaused(true); return; }
                float dt = Time.deltaTime;
                Vector3 beforeMove = motor.PlayerPosition;
                motor.Tick(dt);
                journey.TickStorm(dt, WorldProgress);
                if (journey.State.Status != SessionStatus.Playing) return;
                actions.Tick(dt);
                if (!roadActivated && (journey.State.Upgrades & VehicleUpgrades.Ram) != 0)
                {
                    roadActivated = true;
                    if (Region.roadBeasts != null) foreach (var enemy in Region.roadBeasts) enemy.gameObject.SetActive(true);
                }
                TickEncounter(dt);
                bool threat = false;
                foreach (var enemy in Region.AllEnemies())
                    if (enemy && enemy.gameObject.activeInHierarchy && !enemy.Dead && Vector3.Distance(enemy.transform.position, motor.PlayerPosition) < 19)
                    { threat = true; break; }
                Pacing.Sample(journey.State, dt, Vector3.Distance(beforeMove, motor.PlayerPosition), motor.InsideCabin,
                    actions.Installing || actions.Reloading, threat, Encounter != null && !Encounter.Complete,
                    Encounter != null ? Encounter.AliveCount : 0, (WorldProgress - journey.State.StormFrontProgress) / journey.State.StormSpeed);
                Telemetry.Record(Region.region, actions.Installing ? JourneyActivity.Installing : actions.Reloading ? JourneyActivity.Reloading :
                    Encounter != null && !Encounter.Complete && journey.State.PowerConnected ? JourneyActivity.PoweredDefense :
                    journey.State.Control == ControlMode.Driving ? JourneyActivity.Driving : JourneyActivity.OnFoot, dt);
                if (Region.region == 3)
                {
                    if (progress.CanExitRegion(3, journey.Generation, Region.VehicleInsideSafety(motor)))
                        journey.State.TryReachSafety(Region.VehicleInsideSafety(motor));
                }
                else if (progress.CanExitRegion(Region.region, journey.Generation, Region.VehicleInsideExit(motor)))
                { minimumSpawnProgress = WorldProgress; pending = journey.BeginRegionAdvance(); if (pending.IsValid) RequestLoad(); }
            }
            finally { journey.Input.ConsumeFrame(); }
        }
        void TickEncounter(float dt)
        {
            if (Encounter == null || Encounter.Complete) return;
            int r = Region.region, g = journey.Generation;
            int next = Encounter.CompletedWaves + 1;
            if (Encounter.TryBeginWave(r, g, next))
            {
                var enemies = Region.waves[next - 1].enemies;
                for (int i = 0; i < enemies.Length; i++)
                {
                    var enemy = enemies[i];
                    if (!enemy) { LoadError = "遭遇敌人丢失，不能判定完成。"; return; }
                    enemy.gameObject.SetActive(true);
                    Encounter.TryRegisterEnemy(r, g, next, enemy.GetInstanceID().ToString());
                }
                Encounter.TrySealWave(r, g, next, enemies.Length);
            }
            int current = Encounter.CurrentWave;
            if (current > 0) foreach (var enemy in Region.waves[current - 1].enemies)
                if (enemy && enemy.Dead) Encounter.TryDefeatEnemy(r, g, current, enemy.GetInstanceID().ToString());
            Encounter.Tick(dt);
            Encounter.TryCompleteWave(r, g, current);
            if (Encounter.Complete) progress.TryResolvePoweredEncounter(r, g, Encounter);
        }
    }
}


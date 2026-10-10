using UnityEngine;

namespace DesertRV
{
    // First playable station controller. Three-region completion is deliberately not
    // faked here: reaching this station's exit reports a slice checkpoint, not victory.
    public sealed class FirstStationJourney : MonoBehaviour
    {
        public bool combatUnavailable;
        public JourneySession journey;
        public JourneyMotor motor;
        public JourneyHud hud;
        public Transform salvagePoint, cabinWorkbench, exitPoint;
        public GameObject salvageVisual;
        public BeastActor[] guards, roadBeasts;
        public AudioClip shotSound, hitSound, reloadSound, pickupSound, upgradeSound, windSound;
        public Material nailTrajectoryMaterial;
        public string Notice { get; private set; }
        public string Prompt { get; private set; }
        public double WorldProgress => Vector3.Dot(motor.PlayerPosition, journeyDirection);
        public bool SliceComplete { get; private set; }
        public float HitConfirmation => hitFlash;
        public float DamageFeedback => damageFlash;
        public bool Reloading => reloadRemaining > 0;
        public bool Installing => installRemaining > 0;
        public float ActionProgress => installRemaining > 0 ? 1 - installRemaining / 5f : reloadRemaining > 0 ? 1 - reloadRemaining / 1.65f : 0;
        public string Objective => combatUnavailable && (journey.State.Upgrades & VehicleUpgrades.Ram) != 0 ? "控制测试：战斗资产尚未通过，不代表关卡完成" : SliceComplete ? "第一站已贯通 · 后续地区制作中" :
            (journey.State.Upgrades & VehicleUpgrades.Ram) != 0 ? "用新撞角清开公路，驶向北方" :
            journey.State.HasPart(ComponentPart.RamPart) ? "回到房车工作台，装上撞角" : "停车下车，搜索修理间的撞角组件";
        float fireClock, reloadRemaining, installRemaining, noticeRemaining, hitFlash, damageFlash;
        int lastHealth;
        AudioSource effects, wind;
        Vector3 journeyDirection;
        bool roadActivated;
        LineRenderer tracer;
        bool tracerReady;
        float tracerRemaining;
        int interaction;
        Collider salvageSurface, workbenchSurface;

        void Awake()
        {
            // Legacy scenes are traversal-only until replaced by authored RegionBindings.
            combatUnavailable = true;
            if (FindFirstObjectByType<JourneyDirector>()) { enabled = false; return; }
            effects = gameObject.AddComponent<AudioSource>(); effects.spatialBlend = 0; effects.playOnAwake = false;
            wind = gameObject.AddComponent<AudioSource>(); wind.spatialBlend = 0; wind.playOnAwake = false;
            wind.clip = windSound; wind.loop = true; wind.volume = .16f;
            journeyDirection = motor.Forward;
            // Exact surfaces from the saved scene / JourneyBuild bindings. The cabin
            // point is parented to the RV, so never exempt its whole parent hierarchy.
            salvageSurface = salvagePoint && salvagePoint.parent
                ? salvagePoint.parent.GetComponent<Collider>() : null;
            var bench = motor.vehicle.Find("GEO-rear_repair_bench");
            workbenchSurface = bench ? bench.GetComponent<Collider>() : null;
            tracer = new GameObject("Nail trajectory").AddComponent<LineRenderer>();
            tracer.positionCount = 2; tracer.startWidth = .008f; tracer.endWidth = .003f;
            tracer.sharedMaterial = JourneyTracerMaterial.Validate(nailTrajectoryMaterial, this);
            tracerReady = tracer.sharedMaterial != null; tracer.enabled = false;
            tracer.transform.SetParent(transform, true);
            foreach (var beast in guards) if (beast) beast.gameObject.SetActive(false);
            foreach (var beast in roadBeasts) if (beast) beast.gameObject.SetActive(false);
        }
        public void Begin()
        {
            if (!journey.StartJourney()) return;
            ResetWorld(); Say("先停稳。下车搜索修理间，别让风暴追上。", 6);
        }
        public void Restart()
        {
            if (!journey.RestartJourney()) return;
            ResetWorld(); Say("新的一趟旅程。上一趟的物资不会保留。", 5);
        }
        void ResetWorld()
        {
            motor.ResetVehicle(); motor.RefreshModules();
            fireClock = reloadRemaining = installRemaining = hitFlash = damageFlash = tracerRemaining = 0;
            tracer.enabled = false; roadActivated = SliceComplete = false;
            if (salvageVisual) salvageVisual.SetActive(true);
            foreach (var beast in guards) if (beast) { beast.ResetActor(); beast.gameObject.SetActive(false); }
            foreach (var beast in roadBeasts) if (beast) { beast.ResetActor(); beast.gameObject.SetActive(false); }
            lastHealth = journey.State.PlayerHealth;
            journey.ResetPositionSample(Vector3.Dot(motor.PlayerPosition, journeyDirection));
            if (windSound) wind.Play();
        }
        void Update()
        {
            var state = journey.State;
            if (state.Status != SessionStatus.Playing)
            {
                if (wind.isPlaying) wind.Pause();
                effects.Pause(); journey.Input.ConsumeFrame(); return;
            }
            if (windSound && !wind.isPlaying) wind.UnPause();
            effects.UnPause();
            float delta = Time.deltaTime;
            motor.Tick(delta);
            journey.TickStorm(delta, Vector3.Dot(motor.PlayerPosition, journeyDirection));
            if (state.Status != SessionStatus.Playing) { journey.Input.ReleaseAll(); return; }
            fireClock = Mathf.Max(0, fireClock - delta); hitFlash = Mathf.Max(0, hitFlash - delta); damageFlash = Mathf.Max(0, damageFlash - delta);
            tracerRemaining -= delta; tracer.enabled = tracerReady && tracerRemaining > 0;
            noticeRemaining -= delta; if (noticeRemaining <= 0) Notice = "";
            if (state.PlayerHealth < lastHealth) { damageFlash = .3f; installRemaining = 0; }
            lastHealth = state.PlayerHealth;
            if (reloadRemaining > 0)
            {
                reloadRemaining -= delta;
                if (reloadRemaining <= 0) state.Reload();
            }
            if (installRemaining > 0)
            {
                if (!motor.InsideCabin || !Near(cabinWorkbench, 2.1f) || state.Control != ControlMode.OnFoot) { installRemaining = 0; Say("改装中断，组件仍在。", 2); }
                else
                {
                    installRemaining -= delta;
                    if (installRemaining <= 0 && state.TryInstall(ComponentPart.RamPart))
                    {
                        motor.RefreshModules(); Play(upgradeSound, .7f);
                        ActivateRoad(); Say("撞角已锁紧。回到驾驶位，试试冲开公路。", 6);
                    }
                }
            }
            FindInteraction();
            if (journey.Input.Interact && !Installing) Interact();
            if (state.Control == ControlMode.OnFoot && !Installing)
            {
                if (journey.Input.Reload && reloadRemaining <= 0 && state.LoadedAmmo < 12 && state.ReserveAmmo > 0)
                { reloadRemaining = 1.65f; Play(reloadSound, .4f); }
                if (journey.Input.Fire && fireClock <= 0 && reloadRemaining <= 0) Fire();
            }
            if (roadActivated)
            {
                bool clear = true;
                foreach (var beast in roadBeasts) if (beast && !beast.Dead) clear = false;
                state.SetObjectivesResolved(clear);
                if (!SliceComplete && clear && state.Control == ControlMode.Driving && Vector3.Distance(motor.vehicle.position, exitPoint.position) < 7)
                { SliceComplete = true; Say("第一站完整闭环已到达出口。后续地区尚未接入。", 8); journey.TogglePause(); }
            }
            journey.Input.ConsumeFrame();
        }
        void ActivateRoad()
        {
            if (combatUnavailable || roadActivated) return; roadActivated = true;
            foreach (var beast in roadBeasts) if (beast) { beast.gameObject.SetActive(true); beast.ResetActor(); }
        }
        bool Near(Transform point, float distance)
        {
            if (!point || Vector3.Distance(motor.view.transform.position, point.position) >= distance) return false;
            Vector3 origin = motor.view.transform.position;
            Collider surface = point == salvagePoint ? salvageSurface :
                point == cabinWorkbench ? workbenchSurface : null;
            return JourneyRaycast.CanReachPoint(origin, point.position,
                motor.Walker.GetComponent<CharacterController>(), surface);
        }
        void FindInteraction()
        {
            interaction = 0; Prompt = "";
            if (journey.State.Control == ControlMode.Driving)
            { interaction = 1; Prompt = Mathf.Abs(motor.Speed) > .6f ? "停稳后下车" : "下车"; return; }
            if (Near(salvagePoint, 2.5f) && !journey.State.HasPart(ComponentPart.RamPart) && (journey.State.Upgrades & VehicleUpgrades.Ram) == 0)
            { interaction = 2; Prompt = "收取撞角组件"; }
            else if (motor.InsideCabin && Near(cabinWorkbench, 2.1f) && journey.State.HasPart(ComponentPart.RamPart))
            { interaction = 3; Prompt = "安装撞角 · 5 秒"; }
            else if (motor.InsideCabin && Near(cabinWorkbench, 2.1f) && journey.State.VehicleHealth < 300 && journey.State.RepairKits > 0)
            { interaction = 5; Prompt = "修理房车 · 消耗 1 修理包"; }
            else if (Vector3.Distance(motor.PlayerPosition, motor.EntryPosition) < 2.8f)
            { interaction = 4; Prompt = "回到驾驶位"; }
        }
        void Interact()
        {
            switch (interaction)
            {
                case 1: if (!motor.TryExitVehicle()) Say("先停稳，并给车门留出下车空间。", 3); break;
                case 2:
                    if (journey.State.TryCollect("station1.ram-part", ComponentPart.RamPart))
                    { if (salvageVisual) salvageVisual.SetActive(false); Play(pickupSound, .6f); Say("组件已收好，回房车工作台安装。", 4); }
                    break;
                case 3: reloadRemaining = 0; installRemaining = 5; break;
                case 4: motor.TryEnterDriver(); break;
                case 5: if (journey.State.TryRepair()) Say("房车修复 +95。", 3); break;
            }
        }
        void Fire()
        {
            fireClock = .22f;
            if (!journey.State.TryFire()) { Say("钉匣空了，需要装填。", 1); return; }
            Play(shotSound, .48f); motor.AddRecoil(1.6f);
            Vector3 start = motor.view.transform.position;
            Vector3 direction = motor.view.transform.forward;
            Vector3 end = start + direction * 45;
            if (JourneyRaycast.TryFirstHit(start, direction, 45,
                motor.Walker.GetComponent<CharacterController>(), out var hit))
            {
                end = hit.point;
                var beast = hit.collider.GetComponentInParent<BeastActor>();
                if (beast && beast.TakeHit(24, direction) > 0) { Play(hitSound, .35f); hitFlash = .1f; }
            }
            tracer.SetPosition(0, start + motor.view.transform.right * .2f - motor.view.transform.up * .18f + direction * .4f);
            tracer.SetPosition(1, end); tracerRemaining = .06f; tracer.enabled = tracerReady;
        }
        void Play(AudioClip clip, float volume) { if (clip) effects.PlayOneShot(clip, volume); }
        void Say(string message, float seconds) { Notice = message; noticeRemaining = seconds; }
    }
}

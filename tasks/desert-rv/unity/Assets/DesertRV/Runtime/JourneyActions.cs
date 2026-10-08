using UnityEngine;

namespace DesertRV
{
    // Shared actions retain exact self-collider filtering for shots and interactions.
    public sealed class JourneyActions : MonoBehaviour
    {
        public JourneySession journey;
        public JourneyMotor motor;
        public Transform cabinWorkbench;
        public Collider workbenchSurface;
        public AudioClip shotSound, hitSound, reloadSound, pickupSound, upgradeSound, windSound;
        public RegionBinding Region { get; private set; }
        public RegionProgressState Progress { get; private set; }
        public string Notice { get; private set; }
        public string Prompt { get; private set; }
        public float HitConfirmation => hitFlash;
        public float DamageFeedback => damageFlash;
        public bool Reloading => reloadRemaining > 0;
        public bool Installing => installRemaining > 0;
        public float ActionProgress => Installing ? 1 - installRemaining / 5f : Reloading ? 1 - reloadRemaining / 1.65f : 0;
        ComponentPart installPart;
        ArcCombatState arc;
        float fireClock, reloadRemaining, installRemaining, noticeRemaining, hitFlash, damageFlash;
        int lastHealth;
        AudioSource effects, wind;
        LineRenderer tracer;
        float tracerRemaining;
        int interaction;


        void Awake()
        {
            effects = gameObject.AddComponent<AudioSource>(); effects.spatialBlend = 0; effects.playOnAwake = false;
            wind = gameObject.AddComponent<AudioSource>(); wind.spatialBlend = 0; wind.playOnAwake = false;
            wind.clip = windSound; wind.loop = true; wind.volume = .16f;
            tracer = new GameObject("Nail trajectory").AddComponent<LineRenderer>();
            tracer.positionCount = 2; tracer.startWidth = .008f; tracer.endWidth = .003f;
            tracer.material = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            tracer.material.color = new Color(1, .72f, .3f); tracer.enabled = false;
            tracer.transform.SetParent(transform, true);
        }
        public void Bind(RegionBinding region, RegionProgressState progress)
        {
            Region = region; Progress = progress;
            arc = new ArcCombatState(journey.State, region.region, journey.Generation, 3, .2);
            fireClock = reloadRemaining = installRemaining = hitFlash = damageFlash = tracerRemaining = 0;
            tracer.enabled = false; Prompt = Notice = "";
            lastHealth = journey.State.PlayerHealth;
            if (windSound) wind.Play();
        }
        public void SetPaused(bool paused)
        {
            if (paused) { wind.Pause(); effects.Pause(); }
            else { if (windSound && !wind.isPlaying) wind.UnPause(); effects.UnPause(); }
        }
        public void Tick(float delta)
        {
            var state = journey.State;
            if (state.Status != SessionStatus.Playing || !Region) { SetPaused(true); return; }
            SetPaused(false);
            fireClock = Mathf.Max(0, fireClock - delta); hitFlash = Mathf.Max(0, hitFlash - delta); damageFlash = Mathf.Max(0, damageFlash - delta);
            tracerRemaining -= delta; tracer.enabled = tracerRemaining > 0;
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
                    if (installRemaining <= 0 && (installPart == ComponentPart.RamPart ? Progress.TryInstallRam(Region.region, journey.Generation) : Progress.TryInstallArc(Region.region, journey.Generation)))
                    {
                        motor.RefreshModules(); Play(upgradeSound, .7f);
                        Say("改装已锁紧。回到驾驶位继续前进。", 6);
                    }
                }
            }
            TickArc(delta);
            FindInteraction();
            if (journey.Input.Interact && !Installing) Interact();
            if (state.Control == ControlMode.OnFoot && !Installing)
            {
                if (journey.Input.Reload && reloadRemaining <= 0 && state.LoadedAmmo < 12 && state.ReserveAmmo > 0)
                { reloadRemaining = 1.65f; Play(reloadSound, .4f); }
                if (journey.Input.Fire && fireClock <= 0 && reloadRemaining <= 0) Fire();
            }
        }
        bool Near(Transform point, float distance)
        {
            if (!point || Vector3.Distance(motor.view.transform.position, point.position) >= distance) return false;
            Vector3 origin = motor.view.transform.position;
            Collider surface = point == Region.salvage ? Region.salvageSurface :
                point == cabinWorkbench ? workbenchSurface : point == Region.powerPoint ? Region.powerSurface : null;
            return JourneyRaycast.CanReachPoint(origin, point.position,
                motor.Walker.GetComponent<CharacterController>(), surface);
        }
        void FindInteraction()
        {
            interaction = 0; Prompt = "";
            if (journey.State.Control == ControlMode.Driving)
            { interaction = 1; Prompt = Mathf.Abs(motor.Speed) > .6f ? "停稳后下车" : "下车"; return; }
            ComponentPart part = Region.region == 1 ? ComponentPart.RamPart : ComponentPart.Coil;
            VehicleUpgrades upgrade = Region.region == 1 ? VehicleUpgrades.Ram : VehicleUpgrades.Arc;
            if (Region.region >= 2 && Near(Region.powerPoint, 2.5f))
            { interaction = 6; Prompt = journey.State.PowerConnected ? "拔除电缆" : "连接房车供电"; }
            else if (Region.region <= 2 && Near(Region.salvage, 2.5f) && !journey.State.HasPart(part) && (journey.State.Upgrades & upgrade) == 0)
            { interaction = 2; Prompt = Region.region == 1 ? "收取撞角组件" : "收取线圈"; }
            else if (motor.InsideCabin && Near(cabinWorkbench, 2.1f) && (journey.State.HasPart(ComponentPart.RamPart) || journey.State.HasPart(ComponentPart.Coil)))
            { interaction = 3; Prompt = "安装改装 · 5 秒"; }
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
                    if ((Region.region == 1 ? Progress.TryAcquireRam(Region.region, journey.Generation, Region.pickupId) : Progress.TryAcquireCoil(Region.region, journey.Generation, Region.pickupId)))
                    { if (Region.salvageVisual) Region.salvageVisual.SetActive(false); Play(pickupSound, .6f); Say("组件已收好，回房车工作台安装。", 4); }
                    break;
                case 3: installPart = journey.State.HasPart(ComponentPart.RamPart) ? ComponentPart.RamPart : ComponentPart.Coil; reloadRemaining = 0; installRemaining = 5; break;
                case 4: motor.TryEnterDriver(); break;
                case 5: if (journey.State.TryRepair()) Say("房车修复 +95。", 3); break;
                case 6:
                    if (Vector3.Distance(motor.vehicle.position, Region.powerPoint.position) > 12) Say("房车离插座太远。", 3);
                    else journey.State.SetPowerConnected(!journey.State.PowerConnected);
                    break;
            }
        }
        void TickArc(float delta)
        {
            arc.Tick(delta);
            int pulse = arc.TryBeginPulse(Region.region, journey.Generation);
            if (pulse == 0) return;
            Vector3 origin = motor.vehicle.position + Vector3.up * 2.5f;
            foreach (var collider in Physics.OverlapSphere(origin, 5, ~0, QueryTriggerInteraction.Ignore))
            {
                var beast = collider.GetComponentInParent<BeastActor>();
                if (!beast || beast.Dead) continue;
                Vector3 target = collider.bounds.center;
                if (Physics.Linecast(origin, target, out var obstruction, ~0, QueryTriggerInteraction.Ignore) &&
                    obstruction.collider.GetComponentInParent<BeastActor>() != beast) continue;
                if (arc.TryHitTarget(Region.region, journey.Generation, pulse, beast.GetInstanceID().ToString()))
                    beast.TakeHit(40, (target - origin).normalized);
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
            tracer.SetPosition(1, end); tracerRemaining = .06f; tracer.enabled = true;
        }
        void Play(AudioClip clip, float volume) { if (clip) effects.PlayOneShot(clip, volume); }
        public void Say(string message, float seconds) { Notice = message; noticeRemaining = seconds; }
    }
}

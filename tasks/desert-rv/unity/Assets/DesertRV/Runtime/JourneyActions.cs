using System;
using UnityEngine;

namespace DesertRV
{
    // Shared actions retain exact self-collider filtering for shots and interactions.
    public sealed partial class JourneyActions : MonoBehaviour
    {
        public event Action<ShotPresentationEvent> ShotPresented;
        public event Action<ArcPresentationEvent> ArcPresented;
        public event Action<ReloadPresentationEvent> ReloadPresented;
        public event Action PresentationReset;
        public Transform shotMuzzle, arcOrigin;
        public int PresentationEpoch { get; private set; }
        public int PresentationGeneration { get; private set; }
        public bool PresentationCurrent => journey && journey.State != null && Region && PresentationGeneration == journey.Generation && Region.region == journey.State.SceneId;
        public int ReloadLoadedBefore { get; private set; }
        public int ReloadPlannedAdded { get; private set; }
        public bool ArcSourceReady => CheckArcSource(out _, out _, out _);
        public float FireRemaining => fireClock;
        public float ReloadRemaining => Mathf.Max(0, reloadRemaining);
        public bool PresentationPlaying => PresentationCurrent && journey.State.Status == SessionStatus.Playing;
        int shotSequence, arcSequence, reloadSequence;
        // Bad visual listeners cannot stop authoritative combat or frame processing.
        void Emit<T>(Action<T> listeners, T value)
        {
            if (listeners == null) return;
            foreach (Action<T> listener in listeners.GetInvocationList())
                try { listener(value); } catch (Exception error) { Debug.LogException(error, this); }
        }
        void ResetPresentation()
        {
            PresentationEpoch++; shotSequence = arcSequence = reloadSequence = 0;
            if (PresentationReset == null) return;
            foreach (Action listener in PresentationReset.GetInvocationList())
                try { listener(); } catch (Exception error) { Debug.LogException(error, this); }
        }
        public JourneySession journey;
        public JourneyMotor motor;
        public Transform cabinWorkbench;
        public Collider workbenchSurface;
        public AudioClip shotSound, hitSound, reloadSound, pickupSound, upgradeSound, windSound;
        public Material nailTrajectoryMaterial;
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
        AudioSource effects, wind, reloadAudio;
        LineRenderer tracer;
        bool tracerReady;
        float tracerRemaining;
        int interaction;
        JourneySupplyPoint nearbySupply;
        public event Action<int, string, SupplyKind, int> SupplyCollected;


        void Awake()
        {
            effects = gameObject.AddComponent<AudioSource>(); effects.spatialBlend = 0; effects.playOnAwake = false;
            reloadAudio = gameObject.AddComponent<AudioSource>(); reloadAudio.spatialBlend = 0; reloadAudio.playOnAwake = false;
            wind = gameObject.AddComponent<AudioSource>(); wind.spatialBlend = 0; wind.playOnAwake = false;
            wind.clip = windSound; wind.loop = true; wind.volume = .16f;
            tracer = new GameObject("Nail trajectory").AddComponent<LineRenderer>();
            tracer.positionCount = 2; tracer.startWidth = .008f; tracer.endWidth = .003f;
            tracer.sharedMaterial = JourneyTracerMaterial.Validate(nailTrajectoryMaterial, this);
            tracerReady = tracer.sharedMaterial != null; tracer.enabled = false;
            tracer.transform.SetParent(transform, true);
        }
        public void Bind(RegionBinding region, RegionProgressState progress)
        {
            effects.Stop(); wind.Stop(); CancelReloadPresentation();
            Region = region; Progress = progress; PresentationGeneration = journey.Generation;
            arc = new ArcCombatState(journey.State, region.region, journey.Generation, 3, .2);
            fireClock = reloadRemaining = installRemaining = hitFlash = damageFlash = tracerRemaining = 0;
            tracer.enabled = false; Prompt = Notice = ""; interaction = 0; nearbySupply = null;
            ResetPresentation();
            lastHealth = journey.State.PlayerHealth;
            if (windSound) wind.Play();
        }
        public void SetPaused(bool paused)
        {
            // Only a current on-foot play/pause can preserve the in-progress reload.
            // Director calls this even when terminal/loading states no longer call Tick.
            if (!PresentationCurrent || journey.State.Control != ControlMode.OnFoot ||
                (journey.State.Status != SessionStatus.Playing && journey.State.Status != SessionStatus.Paused))
                CancelReloadPresentation();
            if (paused)
            {
                if (wind) wind.Pause(); if (effects) effects.Pause(); if (reloadAudio) reloadAudio.Pause();
                tracerRemaining = 0; if (tracer) tracer.enabled = false;
            }
            else
            {
                if (windSound && wind && !wind.isPlaying) wind.UnPause();
                if (effects) effects.UnPause();
                if (reloadAudio && Reloading) reloadAudio.UnPause();
            }
        }
        void OnDisable()
        {
            CancelReloadPresentation();
            if (effects) effects.Stop(); if (wind) wind.Pause();
            tracerRemaining = 0; if (tracer) tracer.enabled = false;
        }
        public void Tick(float delta)
        {
            // The external director may retain this component after it is disabled.
            if (!isActiveAndEnabled) { CancelReloadPresentation(); return; }
            var state = journey.State;
            if (!PresentationPlaying || !Region.gameObject.scene.IsValid() || !Region.gameObject.scene.isLoaded) { SetPaused(true); return; }
            SetPaused(false);
            fireClock = Mathf.Max(0, fireClock - delta); hitFlash = Mathf.Max(0, hitFlash - delta); damageFlash = Mathf.Max(0, damageFlash - delta);
            tracerRemaining -= delta; tracer.enabled = tracerReady && tracerRemaining > 0;
            noticeRemaining -= delta; if (noticeRemaining <= 0) Notice = "";
            if (state.PlayerHealth < lastHealth) { damageFlash = .3f; installRemaining = 0; }
            lastHealth = state.PlayerHealth;
            AdvanceReload(delta);
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
                {
                    BeginReloadPresentation();
                }
                if (journey.Input.Fire && fireClock <= 0 && reloadRemaining <= 0) Fire();
            }
        }
        void AdvanceReload(float delta)
        {
            if (reloadRemaining <= 0) return;
            reloadRemaining -= delta;
            if (reloadRemaining <= 0) { journey.State.Reload(); CancelReloadPresentation(); }
        }
        void BeginReloadPresentation()
        {
            ReloadLoadedBefore = journey.State.LoadedAmmo;
            ReloadPlannedAdded = ReloadPresentationPlan.Added(journey.State.LoadedAmmo, journey.State.ReserveAmmo);
            reloadRemaining = 1.65f;
            if (reloadSound && reloadAudio)
            {
                // A single seekable voice, not an overlapping fire-and-forget one-shot.
                reloadAudio.Stop(); reloadAudio.clip = reloadSound;
                reloadAudio.loop = false; reloadAudio.pitch = 1; reloadAudio.volume = .4f;
                reloadAudio.Play();
            }
            Emit(ReloadPresented, new ReloadPresentationEvent(PresentationEpoch, ++reloadSequence, ReloadLoadedBefore, ReloadPlannedAdded));
        }
        void CancelReloadPresentation()
        {
            reloadRemaining = 0; ReloadLoadedBefore = ReloadPlannedAdded = 0;
            if (reloadAudio) { reloadAudio.Stop(); reloadAudio.clip = null; }
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
            interaction = 0; Prompt = ""; nearbySupply = null;
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
            else if ((nearbySupply = FindSupplyInReach()) != null)
            {
                interaction = 7;
                Prompt = Reloading ? "装填中，完成后可领取补给" : Installing ? "改装中，完成后可领取补给" :
                    nearbySupply.label + " · " + nearbySupply.riskHint;
            }
            else if (Vector3.Distance(motor.PlayerPosition, motor.EntryPosition) < 2.8f)
            { interaction = 4; Prompt = "回到驾驶位"; }
        }
        void Interact()
        {
            if (!PresentationPlaying) return;
            switch (interaction)
            {
                case 1: if (!motor.TryExitVehicle()) Say("先停稳，并给车门留出下车空间。", 3); break;
                case 2:
                    if ((Region.region == 1 ? Progress.TryAcquireRam(Region.region, journey.Generation, Region.pickupId) : Progress.TryAcquireCoil(Region.region, journey.Generation, Region.pickupId)))
                    { if (Region.salvageVisual) Region.salvageVisual.SetActive(false); Play(pickupSound, .6f); Say("组件已收好，回房车工作台安装。", 4); }
                    break;
                case 3: installPart = journey.State.HasPart(ComponentPart.RamPart) ? ComponentPart.RamPart : ComponentPart.Coil; CancelReloadPresentation(); installRemaining = 5; break;
                case 4: if (motor.TryEnterDriver()) CancelReloadPresentation(); break;
                case 5: if (journey.State.TryRepair()) Say("房车修复 +95。", 3); break;
                case 7:
                    if (Reloading || Installing)
                    { Say(Reloading ? "装填中，完成后可领取补给。" : "改装中，完成后可领取补给。", 2); break; }
                    var supply = FindReachableSupply();
                    if (supply == null || supply != nearbySupply) break;
                    int before = supply.kind == SupplyKind.RepairKit ? journey.State.RepairKits : journey.State.ReserveAmmo;
                    if ((supply.kind == SupplyKind.Ammo && before >= 144) || (supply.kind == SupplyKind.RepairKit && before >= 3))
                    {
                        Say(supply.kind == SupplyKind.Ammo ? "备弹已满，可选其他补给或稍后回来。" : "维修包已满，可选其他补给或稍后回来。", 3);
                        break;
                    }
                    if (journey.State.TryCollectSupply(Region.region, PresentationGeneration, supply.id, supply.kind, supply.amount, supply.choiceGroup))
                    {
                        supply.visual.SetActive(false); Play(pickupSound, .6f);
                        int granted = (supply.kind == SupplyKind.RepairKit ? journey.State.RepairKits : journey.State.ReserveAmmo) - before;
                        // Observers cannot interrupt authoritative collection or subsequent actions.
                        if (SupplyCollected != null) foreach (Action<int, string, SupplyKind, int> listener in SupplyCollected.GetInvocationList())
                            try { listener(Region.region, supply.id, supply.kind, granted); }
                            catch (Exception error) { Debug.LogException(error, this); }
                        Say(supply.kind == SupplyKind.Ammo ? "钉弹已补入备弹。" : "维修包已收好，可在车内工作台使用。", 3);
                    }
                    break;
                case 6:
                    if (Vector3.Distance(motor.vehicle.position, Region.powerPoint.position) > 12) Say("房车离插座太远。", 3);
                    else journey.State.SetPowerConnected(!journey.State.PowerConnected);
                    break;
            }
        }
        JourneySupplyPoint FindReachableSupply() => Reloading || Installing ? null : FindSupplyInReach();
        JourneySupplyPoint FindSupplyInReach()
        {
            if (!PresentationPlaying || !motor || !motor.view || !motor.Walker || Region.supplies == null ||
                !Region.gameObject.activeInHierarchy || !Region.gameObject.scene.IsValid() || !Region.gameObject.scene.isLoaded ||
                Region.gameObject.scene != UnityEngine.SceneManagement.SceneManager.GetActiveScene() ||
                journey.State.Control != ControlMode.OnFoot) return null;
            foreach (var supply in Region.supplies)
            {
                if (supply == null || !supply.point || !supply.surface || !supply.visual || !supply.visual.activeInHierarchy ||
                    !supply.surface.enabled || supply.surface.isTrigger || !supply.surface.gameObject.activeInHierarchy ||
                    supply.point.gameObject.scene != Region.gameObject.scene || supply.surface.gameObject.scene != Region.gameObject.scene ||
                    supply.visual.scene != Region.gameObject.scene || !supply.surface.transform.IsChildOf(supply.visual.transform) ||
                    !supply.point.IsChildOf(supply.visual.transform) || journey.State.HasCollectedSupply(supply.id) ||
                    journey.State.HasChosenSupplyGroup(supply.choiceGroup) ||
                    Vector3.Distance(motor.view.transform.position, supply.point.position) > 2.2f) continue;
                if (JourneyRaycast.CanReachPoint(motor.view.transform.position, supply.point.position,
                    motor.Walker.GetComponent<CharacterController>(), supply.surface)) return supply;
            }
            return null;
        }
        void TickArc(float delta)
        {
            if (!ArcSourceReady) return; // Missing/embedded socket cannot spend a pulse or bypass roof geometry.
            arc.Tick(delta);
            int pulse = arc.TryBeginPulse(Region.region, journey.Generation);
            if (pulse == 0) return;
            Vector3 origin = arcOrigin.position;
            foreach (var collider in Physics.OverlapSphere(origin, 5, ~0, QueryTriggerInteraction.Ignore))
            {
                var beast = collider.GetComponentInParent<BeastActor>();
                if (!beast || beast.Dead) continue;
                Vector3 target = collider.bounds.center;
                if (Physics.Linecast(origin, target, out var obstruction, ~0, QueryTriggerInteraction.Ignore) &&
                    obstruction.collider.GetComponentInParent<BeastActor>() != beast) continue;
                if (arc.TryHitTarget(Region.region, journey.Generation, pulse, beast.GetInstanceID().ToString()))
                {
                    if (beast.TakeHit(40, (target - origin).normalized) > 0)
                        Emit(ArcPresented, new ArcPresentationEvent(PresentationEpoch, ++arcSequence, pulse, beast, origin, target));
                }
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
            // Aim/damage remain camera based; only the visible tracer starts at the authored muzzle.
            tracer.SetPosition(0, shotMuzzle ? shotMuzzle.position : start);
            tracer.SetPosition(1, end); tracerRemaining = shotMuzzle ? .06f : 0; tracer.enabled = tracerReady && tracerRemaining > 0;
            Emit(ShotPresented, new ShotPresentationEvent(PresentationEpoch, ++shotSequence, end));
        }
        void Play(AudioClip clip, float volume) { if (clip) effects.PlayOneShot(clip, volume); }
        public void Say(string message, float seconds) { Notice = message; noticeRemaining = seconds; }
    }
}



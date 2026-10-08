using UnityEngine;

namespace DesertRV
{
    [DisallowMultipleComponent]
    public sealed class WeaponPresentation : MonoBehaviour
    {
        public JourneyActions actions;
        public Animator animator;
        public Renderer weaponRenderer;
        public Transform leftHand, rightHand, muzzle;
        public ParticleSystem muzzleFlash;
        // One renderer per actual round. These are authored meshes, never generated placeholders.
        public Renderer[] loadedNails, incomingNails;
        public Transform incomingOffset, leftReloadOffset;
        public Vector3 nailPitch;
        Vector3 incomingRest, leftRest;
        JourneyActions subscribed;
        readonly PresentationEventCursor shots = new PresentationEventCursor();
        readonly PresentationEventCursor reloads = new PresentationEventCursor();
        bool owns, firing, flashPaused;
        int epoch, generation;
        float idleTime;
        Renderer[] renderers;
        bool[] rendererEnabled;
        static readonly int Idle = Animator.StringToHash("Base Layer.Idle");
        static readonly int Fire = Animator.StringToHash("Base Layer.Fire");
        static readonly int Reload = Animator.StringToHash("Base Layer.Reload");
        public bool ValidateBindings(out string reason)
        {
            reason = null;
            if (!actions || !animator || !animator.runtimeAnimatorController || !weaponRenderer || !leftHand || !rightHand || !muzzle || !muzzleFlash)
                reason = "Weapon needs real model, both hands, Animator, muzzle and authored flash.";
            else if (leftHand == rightHand || !leftHand.IsChildOf(animator.transform) || !rightHand.IsChildOf(animator.transform) ||
                     !weaponRenderer.transform.IsChildOf(animator.transform) || !muzzle.IsChildOf(animator.transform) || !muzzleFlash.transform.IsChildOf(muzzle))
                reason = "Weapon mesh, hands and muzzle must belong to the bound animated viewmodel.";
            else if (actions.shotMuzzle != muzzle || !actions.motor || !actions.motor.view || !animator.transform.IsChildOf(actions.motor.view.transform))
                reason = "Viewmodel must be under the gameplay camera and share the actual shot muzzle.";
            else if (Application.isPlaying && (!animator.HasState(0, Idle) || !animator.HasState(0, Fire) || !animator.HasState(0, Reload)))
                reason = "Animator requires Base Layer Idle/Fire/Reload.";
            if (reason == null && (!incomingOffset || !leftReloadOffset || incomingOffset == leftReloadOffset ||
                !incomingOffset.IsChildOf(animator.transform) || !leftReloadOffset.IsChildOf(animator.transform) ||
                !leftHand.IsChildOf(leftReloadOffset) || rightHand.IsChildOf(leftReloadOffset) ||
                !FinitePitch(nailPitch) || !ValidNails(loadedNails, animator.transform, animator.transform) || !ValidNails(incomingNails, incomingOffset, animator.transform)))
                reason = "Partial reload requires 12 separate old/new round meshes, unkeyed strip/left-hand carriers and finite nail pitch.";
            if (reason == null)
                foreach (var oldNail in loadedNails)
                {
                    if (!NailRigOwnership.ValidateLoaded(oldNail, incomingOffset, animator.transform, out var ownershipReason))
                        reason = "Loaded nail ownership invalid: " + ownershipReason;
                    foreach (var incomingNail in incomingNails)
                        if (oldNail == incomingNail) reason = "Old/new nail geometry must be disjoint.";
                }
            return reason == null;
        }
        static bool FinitePitch(Vector3 pitch) => !float.IsNaN(pitch.x) && !float.IsNaN(pitch.y) && !float.IsNaN(pitch.z) &&
            !float.IsInfinity(pitch.x) && !float.IsInfinity(pitch.y) && !float.IsInfinity(pitch.z) && pitch.sqrMagnitude > .000001f && pitch.sqrMagnitude < .01f;
        static bool ValidNails(Renderer[] nails, Transform owner, Transform rig)
        {
            if (nails == null || nails.Length != ReloadPresentationPlan.Capacity) return false;
            for (int i = 0; i < nails.Length; i++)
            {
                if (!NailRigOwnership.Validate(nails[i], owner, rig, out _)) return false;
                for (int j = 0; j < i; j++) if (nails[j] == nails[i]) return false;
            }
            return true;
        }
        void OnEnable()
        {
            if (!ValidateBindings(out var error)) { Debug.LogError(error, this); enabled = false; return; }
            if (!PresentationOwnership.Acquire(actions, this, "weapon")) { Debug.LogError("Duplicate weapon presenter.", this); enabled = false; return; }
            owns = true; subscribed = actions;
            incomingRest = incomingOffset.localPosition; leftRest = leftReloadOffset.localPosition;
            var nextRenderers = animator.GetComponentsInChildren<Renderer>(true);
            var nextEnabled = new bool[nextRenderers.Length];
            for (int i = 0; i < nextRenderers.Length; i++)
            {
                int previous = renderers == null ? -1 : System.Array.IndexOf(renderers, nextRenderers[i]);
                nextEnabled[i] = previous >= 0 ? rendererEnabled[previous] : nextRenderers[i].enabled;
            }
            renderers = nextRenderers; rendererEnabled = nextEnabled;
            subscribed.ShotPresented += OnShot; subscribed.ReloadPresented += OnReload; subscribed.PresentationReset += ResetVisuals;
            animator.speed = 0; animator.applyRootMotion = false;
            ResetVisuals();
            RestoreReloadPose(); // Re-enable during pause must recover the frozen pose, not Idle.
        }
        void OnDisable()
        {
            if (subscribed) { subscribed.ShotPresented -= OnShot; subscribed.ReloadPresented -= OnReload; subscribed.PresentationReset -= ResetVisuals; }
            if (owns) { ResetVisuals(); PresentationOwnership.Release(subscribed, this, "weapon"); }
            if (owns && renderers != null)
                for (int i = 0; i < renderers.Length; i++) if (renderers[i]) renderers[i].enabled = false; // No orphan rig or incoming nails.
            subscribed = null; owns = false;
        }
        void ResetVisuals()
        {
            epoch = actions ? actions.PresentationEpoch : 0;
            generation = actions && actions.journey ? actions.journey.Generation : 0;
            shots.Reset(epoch); reloads.Reset(epoch); firing = false; flashPaused = false; idleTime = 0;
            if (muzzleFlash) muzzleFlash.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            if (incomingOffset) incomingOffset.localPosition = incomingRest;
            if (leftReloadOffset) leftReloadOffset.localPosition = leftRest;
            if (incomingNails != null) foreach (var nail in incomingNails) if (nail) nail.enabled = false;
            if (animator && animator.isActiveAndEnabled && animator.runtimeAnimatorController) Sample(Idle, 0);
        }
        void OnShot(ShotPresentationEvent e)
        {
            if (!owns || !actions.PresentationPlaying || !shots.Consume(actions.PresentationEpoch, e.Epoch, e.Sequence)) return;
            firing = true; Sample(Fire, 0); muzzleFlash.Play(true);
        }
        void OnReload(ReloadPresentationEvent e)
        {
            if (!owns || !actions.PresentationPlaying || !reloads.Consume(actions.PresentationEpoch, e.Epoch, e.Sequence)) return;
            firing = false; muzzleFlash.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear); Sample(Reload, 0); ApplyAmmunition(true);
        }
        void RestoreReloadPose()
        {
            if (!owns || !actions || !actions.PresentationCurrent || !actions.Reloading ||
                (actions.journey.State.Status != SessionStatus.Playing && actions.journey.State.Status != SessionStatus.Paused)) return;
            Sample(Reload, Mathf.Clamp01(1 - actions.ReloadRemaining / 1.65f));
            ApplyAmmunition(actions.journey.State.Control == ControlMode.OnFoot);
        }
        void Sample(int state, float normalized)
        { animator.speed = 0; animator.Play(state, 0, normalized); animator.Update(0); }
        void ApplyAmmunition(bool visible)
        {
            visible &= actions.PresentationCurrent;
            bool reloading = actions.PresentationCurrent && actions.Reloading;
            int before = reloading ? actions.ReloadLoadedBefore : actions.journey.State.LoadedAmmo;
            int added = reloading ? actions.ReloadPlannedAdded : 0;
            float normalized = reloading ? Mathf.Clamp01(1 - actions.ReloadRemaining / 1.65f) : 0;
            bool carrying = reloading && normalized >= 34f / 99f;
            for (int i = 0; i < ReloadPresentationPlan.Capacity; i++)
            {
                loadedNails[i].enabled = visible && i < before;
                incomingNails[i].enabled = visible && carrying && i < added;
            }
            Vector3 stripOffset = reloading ? nailPitch * before : Vector3.zero;
            incomingOffset.localPosition = incomingRest + stripOffset;
            // The two carrier parents can have different imported rotations/scales.
            Vector3 worldOffset = incomingOffset.parent.TransformVector(stripOffset);
            leftReloadOffset.localPosition = leftRest + leftReloadOffset.parent.InverseTransformVector(worldOffset) * ReloadPresentationPlan.GripWeight(normalized);
        }
        void LateUpdate()
        {
            if (!owns || !actions || !actions.journey) return;
            bool visible = actions.PresentationCurrent && actions.journey.State.Control == ControlMode.OnFoot &&
                (actions.journey.State.Status == SessionStatus.Playing || actions.journey.State.Status == SessionStatus.Paused);
            for (int i = 0; i < renderers.Length; i++) if (renderers[i]) renderers[i].enabled = visible && rendererEnabled[i];
            if (generation != actions.journey.Generation || epoch != actions.PresentationEpoch) ResetVisuals();
            ApplyAmmunition(visible);
            if (!actions.PresentationPlaying)
            {
                if (actions.journey.State.Status == SessionStatus.Paused) RestoreReloadPose();
                if (muzzleFlash.isPlaying) { muzzleFlash.Pause(true); flashPaused = true; }
                if (actions.journey.State.Status != SessionStatus.Paused) ResetVisuals();
                return;
            }
            if (flashPaused) { muzzleFlash.Play(true); flashPaused = false; }
            // Sampling is a read-only projection of the authoritative timers. No AnimationEvents.
            if (actions.Reloading) { firing = false; Sample(Reload, 1 - actions.ReloadRemaining / 1.65f); }
            else if (firing && actions.FireRemaining > 0) Sample(Fire, 1 - actions.FireRemaining / .22f);
            else { if (firing) muzzleFlash.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear); firing = false; idleTime += Mathf.Min(Time.deltaTime, .1f); Sample(Idle, (idleTime / 2f) % 1); }
            ApplyAmmunition(visible); // Animator sampling must not overwrite the unkeyed count projection.
        }
    }
}

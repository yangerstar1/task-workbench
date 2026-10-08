using UnityEngine;

namespace DesertRV
{
    [DisallowMultipleComponent]
    public sealed class WeaponPresentation : MonoBehaviour
    {
        public JourneyActions actions;
        public Animator animator;
        public WeaponArmReach armReach;
        public string ArmReachFailure { get; private set; }
        public int ArmReachRejectedSamples { get; private set; }
        public event System.Action<ArmReachFailureReport> ArmReachFailed;
        readonly System.Collections.Generic.HashSet<string> reportedArmFailures = new System.Collections.Generic.HashSet<string>();
        int activeReloadSequence;
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
                !WeaponPitchSpace.ValidPitch(incomingOffset.parent,nailPitch) || !WeaponPitchSpace.ValidParent(leftReloadOffset.parent) || !ValidNails(loadedNails, animator.transform, animator.transform) || !ValidNails(incomingNails, incomingOffset, animator.transform)))
                reason = "Partial reload requires 12 separate old/new round meshes, unkeyed strip/left-hand carriers and finite nail pitch.";
            if (reason == null)
                foreach (var oldNail in loadedNails)
                {
                    if (!NailRigOwnership.ValidateLoaded(oldNail, incomingOffset, animator.transform, out var ownershipReason))
                        reason = "Loaded nail ownership invalid: " + ownershipReason;
                    foreach (var incomingNail in incomingNails)
                        if (oldNail == incomingNail) reason = "Old/new nail geometry must be disjoint.";
                }
            if (reason == null)
            {
                if (!armReach || !armReach.enabled || armReach.animator != animator) reason = "Weapon requires the explicitly calibrated arm reach component.";
                else if (!armReach.ValidateBindings(out var armReason)) reason = armReason;
                else if (!armReach.left.wristTarget.IsChildOf(leftHand) || !armReach.right.wristTarget.IsChildOf(rightHand) ||
                    armReach.left.upperArm.IsChildOf(leftReloadOffset) || armReach.right.upperArm.IsChildOf(leftReloadOffset))
                    reason = "Wrist targets must be hand-owned; fixed shoulders must not inherit the count carrier.";
            }
            return reason == null;
        }
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
            if (!ValidateBindings(out var error)) { ReportArmFailure("Binding: "+error); enabled = false; return; }
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
            if (owns) { ResetVisuals(); if (armReach) armReach.RestoreBindPose(); PresentationOwnership.Release(subscribed, this, "weapon"); }
            if (owns && renderers != null)
                for (int i = 0; i < renderers.Length; i++) if (renderers[i]) renderers[i].enabled = false; // No orphan rig or incoming nails.
            subscribed = null; owns = false;
        }
        void ResetVisuals()
        {
            ArmReachFailure = null; ArmReachRejectedSamples = 0; activeReloadSequence = 0; reportedArmFailures.Clear();
            if (armReach) armReach.RestoreBindPose();
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
            activeReloadSequence = e.Sequence;
            firing = false; muzzleFlash.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear); Sample(Reload, 0); ApplyAmmunition(true); SolveArms();
        }
        void RestoreReloadPose()
        {
            if (!owns || !actions || !actions.PresentationCurrent || !actions.Reloading ||
                (actions.journey.State.Status != SessionStatus.Playing && actions.journey.State.Status != SessionStatus.Paused)) return;
            Sample(Reload, Mathf.Clamp01(1 - actions.ReloadRemaining / 1.65f));
            ApplyAmmunition(actions.journey.State.Control == ControlMode.OnFoot);
            SolveArms();
        }
        void Sample(int state, float normalized)
        { if (armReach) armReach.RestoreBindPose(); animator.speed = 0; animator.Play(state, 0, normalized); animator.Update(0); }
        void SolveArms()
        {
            // The hand/target already received its absolute count offset. Rotate the separate arm chain only.
            if (!actions.Reloading) { ArmReachFailure = null; return; } // Cancel/end returns to freshly sampled base animation, no residual IK.
            string reason="Missing or disabled arm calibration.";
            if (armReach && armReach.enabled && armReach.TrySolveBoth(out reason)) { ArmReachFailure = null; return; }
            ReportArmFailure(reason);
            for (int i = 0; i < renderers.Length; i++) if (renderers[i]) renderers[i].enabled = false;
            muzzleFlash.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        }
        void ReportArmFailure(string reason)
        {
            if(string.IsNullOrWhiteSpace(reason))reason="Unspecified arm solver failure.";
            ArmReachFailure = reason; ArmReachRejectedSamples++;
            int currentEpoch=actions?actions.PresentationEpoch:0;
            int currentGeneration=actions&&actions.journey?actions.journey.Generation:0;
            string key=currentGeneration+":"+currentEpoch+":"+activeReloadSequence+":"+reason;
            if(!reportedArmFailures.Add(key)) return;
            var report=new ArmReachFailureReport {unityFrame=Time.frameCount,generation=currentGeneration,epoch=currentEpoch,reloadSequence=activeReloadSequence,
                normalizedReload=actions&&actions.Reloading?Mathf.Clamp01(1-actions.ReloadRemaining/1.65f):0,
                loadedBefore=actions?actions.ReloadLoadedBefore:0,plannedAdded=actions?actions.ReloadPlannedAdded:0,
                reason=reason,left=armReach&&!reason.StartsWith("Binding:")?armReach.LeftDiagnostics:default,right=armReach&&!reason.StartsWith("Binding:")?armReach.RightDiagnostics:default};
            Debug.LogError("Arm reach failed (visual rejected): "+reason,this);
            if(ArmReachFailed!=null) foreach(System.Action<ArmReachFailureReport> listener in ArmReachFailed.GetInvocationList())
                try { listener(report); } catch(System.Exception error) { Debug.LogException(error,this); }
        }
        void ApplyAmmunition(bool visible)
        {
            visible &= actions.PresentationCurrent;
            bool reloading = actions.PresentationCurrent && actions.Reloading;
            int before = reloading ? actions.ReloadLoadedBefore : actions.journey.State.LoadedAmmo;
            int added = reloading ? actions.ReloadPlannedAdded : 0;
            float normalized = reloading ? Mathf.Clamp01(1 - actions.ReloadRemaining / 1.65f) : 0;
            ApplyCountPose(visible,reloading,before,added,normalized,incomingRest,leftRest);
        }
        void ApplyCountPose(bool visible,bool reloading,int before,int added,float normalized,Vector3 incomingBase,Vector3 leftBase)
        {
            bool carrying = reloading && normalized >= 34f / 99f;
            for (int i = 0; i < ReloadPresentationPlan.Capacity; i++)
            {
                loadedNails[i].enabled = visible && i < before;
                incomingNails[i].enabled = visible && carrying && i < added;
            }
            Vector3 stripOffset = reloading ? nailPitch * before : Vector3.zero;
            incomingOffset.localPosition = incomingBase + stripOffset;
            // The two carrier parents can have different imported rotations/scales.
            Vector3 leftOffset = WeaponPitchSpace.InOtherParent(stripOffset,incomingOffset.parent,leftReloadOffset.parent);
            leftReloadOffset.localPosition = leftBase + leftOffset * ReloadPresentationPlan.GripWeight(normalized);
        }
#if UNITY_EDITOR
        // Executes the very same count projection as runtime; never changes ammo/gameplay state.
        // Only the disabled candidate presenter may use this bounded EditMode-only entry.
        public void ApplyCandidateCountPose(bool reloading,int before,int added,float normalized,Vector3 incomingBase,Vector3 leftBase)
        {
            if(Application.isPlaying || enabled || before<0 || before>ReloadPresentationPlan.Capacity || added<0 ||
                added>ReloadPresentationPlan.Capacity-before || float.IsNaN(normalized) || float.IsInfinity(normalized) || normalized<0 || normalized>1)
                throw new System.InvalidOperationException("Only a disabled EditMode candidate may sample valid count snapshots.");
            ApplyCountPose(true,reloading,before,added,normalized,incomingBase,leftBase);
        }
#endif
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
                if (actions.journey.State.Status == SessionStatus.Paused)
                {
                    if (actions.Reloading) RestoreReloadPose();
                    else if (armReach && (armReach.LastSolveAccepted || ArmReachFailure != null))
                    { Sample(Idle, (idleTime / 2f) % 1); ApplyAmmunition(visible); ArmReachFailure = null; }
                }
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
            SolveArms();
        }
    }
}

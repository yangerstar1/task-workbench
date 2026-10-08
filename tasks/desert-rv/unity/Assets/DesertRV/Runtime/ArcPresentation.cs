using UnityEngine;

namespace DesertRV
{
    [DisallowMultipleComponent]
    public sealed class ArcPresentation : MonoBehaviour
    {
        public JourneyActions actions;
        public Transform arcModule, source;
        public AudioSource audioSource;
        public AudioClip arcSound;
        // Authored beam/impact pairs allow a single authoritative pulse to hit several targets.
        public LineRenderer[] beams;
        public ParticleSystem[] impacts;
        JourneyActions subscribed;
        bool owns, wasPaused;
        int epoch, generation, soundPulse = -1;
        float[] remaining;
        readonly PresentationEventCursor hits = new PresentationEventCursor();
        public bool ValidateBindings(out string reason)
        {
            reason = null;
            if (!actions || !arcModule || !source || actions.arcOrigin != source || !source.IsChildOf(arcModule) ||
                !actions.motor || actions.motor.arc == null || actions.motor.arc.transform != arcModule || !audioSource || !audioSource.transform.IsChildOf(arcModule) || !arcSound || !actions.ArcSourceReady)
                reason = "Arc requires retained module, shared LOS source and real audio.";
            else if (beams == null || impacts == null || beams.Length == 0 || beams.Length != impacts.Length)
                reason = "Arc requires authored beam/impact pairs.";
            else for (int i = 0; i < beams.Length; i++)
            {
                if (!beams[i] || !beams[i].sharedMaterial || !impacts[i]) { reason = "Missing authored arc beam/impact."; break; }
                for (int j = 0; j < i; j++) if (beams[i] == beams[j] || impacts[i] == impacts[j]) reason = "Arc slots must be unique.";
            }
            return reason == null;
        }
        void OnEnable()
        {
            if (!ValidateBindings(out var error)) { Debug.LogError(error, this); enabled = false; return; }
            if (!PresentationOwnership.Acquire(actions, this, "arc")) { Debug.LogError("Duplicate arc presenter.", this); enabled = false; return; }
            owns = true; subscribed = actions; remaining = new float[beams.Length];
            subscribed.ArcPresented += OnHit; subscribed.PresentationReset += ResetVisuals;
            audioSource.playOnAwake = false; audioSource.spatialBlend = 1; ResetVisuals();
        }
        void OnDisable()
        {
            if (subscribed) { subscribed.ArcPresented -= OnHit; subscribed.PresentationReset -= ResetVisuals; }
            if (owns) { ResetVisuals(); PresentationOwnership.Release(subscribed, this, "arc"); }
            owns = false; subscribed = null;
        }
        void ResetVisuals()
        {
            epoch = actions ? actions.PresentationEpoch : 0; generation = actions && actions.journey ? actions.journey.Generation : 0;
            hits.Reset(epoch); soundPulse = -1; wasPaused = false;
            if (audioSource) audioSource.Stop();
            if (remaining == null) return;
            for (int i = 0; i < remaining.Length; i++)
            { remaining[i] = 0; beams[i].enabled = false; impacts[i].Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear); }
        }
        void OnHit(ArcPresentationEvent e)
        {
            if (!owns || !actions.PresentationPlaying || !e.Target || !hits.Consume(actions.PresentationEpoch, e.Epoch, e.Sequence)) return;
            // No physics queries or damage here. Even a killing hit retains its captured endpoint.
            int slot = System.Array.FindIndex(remaining, value => value <= 0);
            if (slot < 0) { Debug.LogError("Arc presentation pool exhausted; increase reviewed slot count.", this); return; }
            beams[slot].useWorldSpace = true; beams[slot].positionCount = 2;
            beams[slot].SetPosition(0, e.Origin); beams[slot].SetPosition(1, e.End); beams[slot].enabled = true;
            impacts[slot].transform.position = e.End; impacts[slot].Play(true); remaining[slot] = .16f;
            if (soundPulse != e.Pulse) { soundPulse = e.Pulse; audioSource.PlayOneShot(arcSound, .55f); }
        }
        void LateUpdate()
        {
            if (!owns || !actions || !actions.journey) return;
            if (generation != actions.journey.Generation || epoch != actions.PresentationEpoch) ResetVisuals();
            if (!actions.PresentationPlaying)
            {
                if (actions.journey.State.Status != SessionStatus.Paused) { ResetVisuals(); return; }
                if (!wasPaused) { audioSource.Pause(); foreach (var effect in impacts) effect.Pause(true); }
                wasPaused = true; return;
            }
            if (wasPaused) { audioSource.UnPause(); for (int i = 0; i < impacts.Length; i++) if (remaining[i] > 0) impacts[i].Play(true); wasPaused = false; }
            for (int i = 0; i < remaining.Length; i++)
            {
                remaining[i] = Mathf.Max(0, remaining[i] - Mathf.Min(Time.deltaTime, .1f));
                beams[i].enabled = remaining[i] > 0;
                if (remaining[i] <= 0) impacts[i].Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            }
        }
    }
}

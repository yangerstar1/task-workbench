using System;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Rendering;
using UnityEngine;

namespace Lottery.G3.Interaction
{
    public enum G3AudioBus { Environment, Interaction, Music }

    // Real Unity audio, mixed through three source groups. This is presentation only:
    // no game RNG, economic writes, automated reveal or synthetic reward event.
    public sealed class G3AudioController : MonoBehaviour
    {
        const string ResourceRoot = "G3Audio/";
        const string PreferencePrefix = "lottery.g3.audio.v1.";
        const float ScratchSilenceSeconds = .085f;
        readonly int[] percent = { 50, 75, 25 };
        readonly AudioSource[] voices = new AudioSource[5];
        readonly float[] voiceGains = new float[5];
        G3Presenter owner;
        AudioSource scratch, environment, music;
        AudioListener ownedListener;
        AudioClip press, paper, coin, flat, prize, transfer, reveal;
        bool ready, appFocused = true, appPaused, inputFocused = true, suspended;
        float lastStroke = -10, scratchGain, scratchPitch = 1, lastButton = -10;
        int nextVoice, variation;
        public bool ClipsLoaded => ready;
        public bool ScratchPlaying => scratch != null && scratch.isPlaying;
        public int VolumePercent(G3AudioBus bus) => percent[BusIndex(bus)];
        public float GetVolume(G3AudioBus bus) => VolumePercent(bus) / 100f;
        bool MayPlay => ready && isActiveAndEnabled && appFocused && !appPaused && inputFocused;
        static int BusIndex(G3AudioBus bus)
        { int i = (int)bus; if (i < 0 || i > 2) throw new ArgumentOutOfRangeException(nameof(bus)); return i; }

        public void Initialize(G3Presenter presenter)
        {
            if (ready || presenter == null) throw new InvalidOperationException("Audio initialization requires one presenter");
            owner = presenter;
            for (int i = 0; i < percent.Length; i++) percent[i] = Mathf.Clamp(PlayerPrefs.GetInt(PreferencePrefix + i, percent[i]), 0, 100);
            press = Clip("ui_press"); paper = Clip("ticket_take"); coin = Clip("coin_settle");
            flat = Clip("settle_flat"); prize = Clip("prize_high"); transfer = Clip("transfer"); reveal = Clip("paper_reveal");
            scratch = Source("Interaction - contact friction", true, 32); scratch.clip = Clip("scratch_loop");
            environment = Source("Environment - quiet shop and street", true, 160); environment.clip = Clip("shop_ambient");
            music = Source("Music - sparse original felt plucks", true, 176); music.clip = Clip("shop_music");
            for (int i = 0; i < voices.Length; i++) voices[i] = Source("Interaction - voice " + i, false, 48);
            // G3 creates its camera at runtime. Do not disable another scene's listener.
            if (!UnityEngine.Object.FindObjectsByType<AudioListener>(FindObjectsSortMode.None).Any(x => x.enabled && x.gameObject.activeInHierarchy))
                ownedListener = owner.View.SceneCamera.gameObject.AddComponent<AudioListener>();
            ready = true; ApplyGains();
        }
        static AudioClip Clip(string name)
        { return Resources.Load<AudioClip>(ResourceRoot + name) ?? throw new InvalidOperationException("Required G3 audio clip missing: " + name); }
        AudioSource Source(string label, bool loop, int priority)
        {
            var child = new GameObject(label); child.transform.SetParent(transform, false);
            var source = child.AddComponent<AudioSource>(); source.playOnAwake = false; source.loop = loop;
            source.spatialBlend = 0; source.dopplerLevel = 0; source.priority = priority;
            source.volume = 0; source.pitch = 1; source.ignoreListenerPause = false; return source;
        }
        // Preferences are separate from the transactional save. No frame-by-frame writes.
        public bool SetVolume(G3AudioBus bus, float value)
        {
            if (float.IsNaN(value) || float.IsInfinity(value)) throw new ArgumentOutOfRangeException(nameof(value));
            int i = BusIndex(bus); percent[i] = Mathf.RoundToInt(Mathf.Clamp01(value) * 100);
            ApplyGains();
            try { PlayerPrefs.SetInt(PreferencePrefix + i, percent[i]); PlayerPrefs.Save(); return true; }
            catch (PlayerPrefsException) { return false; }
        }
        public bool CycleVolume(G3AudioBus bus)
        { int next = ((VolumePercent(bus) / 25 + 1) % 5) * 25; return SetVolume(bus, next / 100f); }
        void ApplyGains()
        {
            if (!ready) return;
            environment.volume = GetVolume(G3AudioBus.Environment) * .40f;
            music.volume = GetVolume(G3AudioBus.Music) * .34f;
            scratch.volume = GetVolume(G3AudioBus.Interaction) * scratchGain;
            for (int i = 0; i < voices.Length; i++) voices[i].volume = voiceGains[i] * GetVolume(G3AudioBus.Interaction);
        }
        public void RecordScratch(CellBrushProposal proposal)
        {
            if (!MayPlay || owner == null || !owner.CanScratch || !proposal.HasFrom) return;
            var ticket = owner.Snapshot.CurrentTicket;
            if (ticket == null || ticket.Scratch.CellCoverage(proposal.CoreIndex) >= 1) { StopScratch(); return; }
            double du = proposal.ToLocal.U - proposal.FromLocal.U, dv = proposal.ToLocal.V - proposal.FromLocal.V;
            float distance = (float)Math.Sqrt(du * du + dv * dv);
            if (distance < .0005f) return; // A held, stationary pointer never sustains friction.
            float now = Time.unscaledTime;
            float dt = lastStroke < 0 || now - lastStroke > .2f ? .0167f : Mathf.Max(.004f, now - lastStroke);
            float strength = Mathf.Clamp01(distance / dt / 4f);
            lastStroke = now; scratchGain = Mathf.Lerp(.11f, .52f, Mathf.Sqrt(strength));
            scratchPitch = Mathf.Lerp(.78f, 1.28f, strength); scratch.pitch = scratchPitch;
            scratch.volume = GetVolume(G3AudioBus.Interaction) * scratchGain;
            if (!scratch.isPlaying && GetVolume(G3AudioBus.Interaction) > 0) scratch.Play();
        }
        public void StopScratch()
        { lastStroke = -10; scratchGain = 0; if (scratch != null) { scratch.Stop(); scratch.volume = 0; } }
        public void ButtonPressed()
        {
            if (Time.unscaledTime - lastButton < .045f) return;
            lastButton = Time.unscaledTime; Play(press, .28f);
        }
        void Play(AudioClip clip, float gain)
        {
            if (!MayPlay || clip == null || GetVolume(G3AudioBus.Interaction) <= 0) return;
            int index = nextVoice++ % voices.Length; var source = voices[index]; source.Stop();
            voiceGains[index] = gain; source.clip = clip; source.volume = gain * GetVolume(G3AudioBus.Interaction);
            // Small timbral variety without consuming UnityEngine.Random or game RNG.
            source.pitch = .97f + (variation++ % 7) * .01f; source.Play();
        }
        // Only confirmed state is audible. A compound claim/buy may return the buy
        // receipt, or reject its buy after the claim has already committed.
        public void Confirmed(RunState before, RunState state, CommandReceipt receipt)
        {
            if (before == null || state == null) return;
            if (before.RunId == state.RunId)
            {
                var result = state.Settlements.LastOrDefault(x => !before.Settlements.Any(old => old.TicketId == x.TicketId));
                if (result != null)
                {
                    StopScratch();
                    if (result.NetMinor <= 0) Play(flat, .38f); // Zero and break-even never celebrate.
                    else if (result.RawPrizeMinor >= result.TicketPriceMinor * 20) Play(prize, .50f);
                    else Play(coin, .48f);
                }
            }
            if (receipt == null) return;
            switch (receipt.Kind)
            {
                case "BUY_TICKET": Play(paper, .50f); break;
                case "CELL_SCRATCH": case "QUICK_REVEAL":
                    var ticket = state.CurrentTicket;
                    if (ticket != null && ticket.SelectedCell < 0 && (ticket.TicketType == "challenge" || ticket.Phase == TicketPhase.REVEALED_UNCLAIMED))
                    { StopScratch(); Play(ticket.Busted ? flat : reveal, .28f); }
                    break;
                case "BUY_STOCK": case "UPGRADE_TOOL": case "SELL_TOOL":
                case "BORROW": case "REPAY_LOAN": case "REPAY_PRINCIPAL": case "PAY_NIGHT_BILL":
                    if (receipt.CashDeltaMinor != 0) Play(transfer, .40f);
                    break;
                case "RESTART_DAY": StopScratch(); Play(paper, .35f); break;
            }
        }
        public void SetInputFocused(bool value)
        { inputFocused = value; if (!value) Suspend(); }
        void Suspend()
        {
            StopScratch(); if (!ready || suspended) return; suspended = true;
            environment.Pause(); music.Pause(); foreach (var source in voices) source.Stop();
        }
        void Update()
        {
            if (!MayPlay) { Suspend(); return; }
            if (suspended) { environment.UnPause(); music.UnPause(); suspended = false; }
            if (!environment.isPlaying) environment.Play();
            if (!music.isPlaying) music.Play();
            if (owner == null || !owner.CanScratch || Time.unscaledTime - lastStroke > ScratchSilenceSeconds) StopScratch();
        }
        void OnApplicationFocus(bool value) { appFocused = value; if (!value) Suspend(); }
        void OnApplicationPause(bool value) { appPaused = value; if (value) Suspend(); }
        void OnDisable() { Suspend(); }
        void OnDestroy()
        {
            if (ownedListener != null) Destroy(ownedListener);
            // Sources are owned children; imported clips remain shared Resources assets.
            if (scratch != null) Destroy(scratch.gameObject);
            if (environment != null) Destroy(environment.gameObject);
            if (music != null) Destroy(music.gameObject);
            foreach (var source in voices) if (source != null) Destroy(source.gameObject);
        }
    }
}

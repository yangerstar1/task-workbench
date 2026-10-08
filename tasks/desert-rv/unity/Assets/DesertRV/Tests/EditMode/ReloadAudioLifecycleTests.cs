using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    // These exercise the real JourneyActions/State/driver code. They do not prove audible output.
    public sealed class ReloadAudioLifecycleTests
    {
        const BindingFlags All = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Get(object target, string name) => target.GetType().GetProperty(name, All).GetValue(target);
        static void Field(object target, string name, object value) => target.GetType().GetField(name, All).SetValue(target, value);
        static void Property(object target, string name, object value) => target.GetType().GetProperty(name, All).SetValue(target, value);
        static object Call(object target, string name, params object[] args) => target.GetType().GetMethod(name, All).Invoke(target, args);
        static object EnumValue(string type, string name) => Enum.Parse(T(type), name);
        static Component Add(GameObject root, string name) => root.AddComponent(T(name));

        sealed class Fixture : IDisposable
        {
            public readonly GameObject Root = new GameObject("reload audio lifecycle fixture");
            public readonly Component Session, Actions;
            public readonly object State;
            public readonly AudioSource Voice;
            public readonly AudioClip TestClip;
            public readonly int Ammo, Reserve, Epoch;
            public Fixture(bool active = false)
            {
                Root.SetActive(false); // No automatic Awake or live sound is asserted in EditMode.
                Session = Add(Root, "JourneySession"); State = Activator.CreateInstance(T("SessionState"));
                Call(State, "ConfigureStorm", -100d, 1d, 1d); Call(State, "Start");
                Call(State, "SetControl", EnumValue("ControlMode", "OnFoot"));
                for (int i=0; i<7; i++) Call(State, "TryFire");
                Property(Session, "State", State);
                Property(Session, "Input", Add(Root, "MobileInputAdapter"));
                Actions = Add(Root, "JourneyActions"); Field(Actions, "journey", Session);
                var region = Add(Root, "RegionBinding"); Field(region, "region", 1);
                Property(Actions, "Region", region); Property(Actions, "PresentationGeneration", 1);
                Field(Actions, "effects", Root.AddComponent<AudioSource>());
                Field(Actions, "wind", Root.AddComponent<AudioSource>());
                Voice = Root.AddComponent<AudioSource>(); Voice.playOnAwake = false; Field(Actions, "reloadAudio", Voice);
                Field(Actions, "tracer", Root.AddComponent<LineRenderer>());
                // A clearly named silent test fixture, never the authored reload asset.
                TestClip = AudioClip.Create("TEST_ONLY_reload_lifecycle_silence", 79200, 1, 48000, false);
                Voice.clip = TestClip; Voice.loop = false;
                if (active)
                {
                    Root.SetActive(true);
                    // Awake is allowed to run, then bind this test's explicit authority and voice.
                    Property(Session, "State", State); Field(Actions, "reloadAudio", Voice);
                }
                Field(Actions, "reloadRemaining", .85f);
                Property(Actions, "ReloadLoadedBefore", 5); Property(Actions, "ReloadPlannedAdded", 7);
                Ammo = (int)Get(State, "LoadedAmmo"); Reserve = (int)Get(State, "ReserveAmmo"); Epoch = (int)Get(Actions, "PresentationEpoch");
            }
            public void AssertNoAmmoOrEpochChange()
            {
                Assert.That(Get(State, "LoadedAmmo"), Is.EqualTo(Ammo));
                Assert.That(Get(State, "ReserveAmmo"), Is.EqualTo(Reserve));
                Assert.That(Get(Actions, "PresentationEpoch"), Is.EqualTo(Epoch));
            }
            public void AssertCancelled()
            {
                Assert.That(Get(Actions, "ReloadRemaining"), Is.EqualTo(0f));
                Assert.That(Get(Actions, "ReloadLoadedBefore"), Is.EqualTo(0));
                Assert.That(Get(Actions, "ReloadPlannedAdded"), Is.EqualTo(0));
                Assert.That(Voice.clip, Is.Null); Assert.That(Voice.isPlaying, Is.False);
                AssertNoAmmoOrEpochChange();
            }
            public void Dispose() { UnityEngine.Object.DestroyImmediate(Root); UnityEngine.Object.DestroyImmediate(TestClip); }
        }

        [Test] public void PausedReload_RetainsClipTimerSnapshotWithoutRestartOrAmmoChange()
        {
            using (var f = new Fixture())
            {
                Call(f.State, "Pause"); Call(f.Actions, "SetPaused", true); Call(f.Actions, "SetPaused", true);
                Assert.That(f.Voice.clip, Is.SameAs(f.TestClip));
                Assert.That(Get(f.Actions, "ReloadRemaining"), Is.EqualTo(.85f));
                Assert.That(Get(f.Actions, "ReloadLoadedBefore"), Is.EqualTo(5));
                Assert.That(Get(f.Actions, "ReloadPlannedAdded"), Is.EqualTo(7));
                Call(f.State, "Resume"); Call(f.Actions, "SetPaused", false);
                Assert.That(Get(f.Actions, "ReloadRemaining"), Is.EqualTo(.85f));
                Assert.That(f.Voice.clip, Is.SameAs(f.TestClip)); f.AssertNoAmmoOrEpochChange();
            }
        }
        [TestCase("Menu")]
        [TestCase("Loading")]
        [TestCase("Failed")]
        [TestCase("Completed")]
        public void TerminalOrLoadingState_CancelsRatherThanKeepingAudioForLater(string status)
        {
            using (var f = new Fixture())
            {
                Property(f.State, "Status", EnumValue("SessionStatus", status));
                Call(f.Actions, "SetPaused", true); f.AssertCancelled();
                Call(f.Actions, "SetPaused", false); f.AssertCancelled();
            }
        }
        [Test] public void StaleGeneration_CancelsBeforeAnyAudioResume()
        {
            using (var f = new Fixture())
            {
                Property(f.Actions, "PresentationGeneration", 0);
                Call(f.Actions, "SetPaused", false); f.AssertCancelled();
            }
        }
        [Test] public void DisableAndRepeatedCancel_CannotSpendAmmoOrLeaveQueuedAudio()
        {
            using (var f = new Fixture())
            {
                Call(f.State, "Pause"); Call(f.Actions, "SetPaused", true);
                Call(f.Actions, "OnDisable"); Call(f.Actions, "CancelReloadPresentation");
                Call(f.State, "Resume"); Call(f.Actions, "SetPaused", false); f.AssertCancelled();
            }
        }
        [TestCase(false)]
        [TestCase(true)]
        public void DisabledOrInactiveActions_ExternalTickCannotRestartOrCommitReload(bool disableComponent)
        {
            using (var f = new Fixture(active: true))
            {
                Assert.That(((Behaviour)f.Actions).isActiveAndEnabled, Is.True);
                if (disableComponent) ((Behaviour)f.Actions).enabled = false;
                else f.Root.SetActive(false);
                // Queue a real reload input edge after the disable; an external director still holds Actions.
                var input = Get(f.Session, "Input"); var touch = Get(input, "State");
                Call(touch, "SetContext", EnumValue("TouchContext", "OnFoot"));
                Assert.That(Call(touch, "Begin", 91, EnumValue("TouchControl", "Reload")), Is.True);
                Call(f.Actions, "Tick", 2f); Call(f.Actions, "Tick", 2f);
                f.AssertCancelled();
            }
        }
        [Test] public void BeginReload_Uses165SecondsAndDoesNotCommitBeforeCompletion()
        {
            using (var f = new Fixture())
            {
                Call(f.Actions, "CancelReloadPresentation");
                // No authored sound in this test; gameplay must not depend on a clip being present.
                Call(f.Actions, "BeginReloadPresentation");
                Assert.That(Get(f.Actions, "ReloadRemaining"), Is.EqualTo(1.65f));
                Assert.That(Get(f.Actions, "ReloadLoadedBefore"), Is.EqualTo(5));
                Assert.That(Get(f.Actions, "ReloadPlannedAdded"), Is.EqualTo(7));
                f.AssertNoAmmoOrEpochChange();
            }
        }
        [Test] public void ReloadCompletion_AdvancesTo165SecondsAndCommitsExactlyOnce()
        {
            using (var f = new Fixture())
            {
                Call(f.Actions, "CancelReloadPresentation"); Call(f.Actions, "BeginReloadPresentation");
                Call(f.Actions, "AdvanceReload", 1.64f);
                Assert.That(Get(f.State, "LoadedAmmo"), Is.EqualTo(5));
                float remaining = (float)Get(f.Actions, "ReloadRemaining");
                Assert.That(remaining, Is.EqualTo(.01f).Within(.000001f));
                // Consume exactly the authoritative floating-point remainder, not a rounded duplicate clock.
                Call(f.Actions, "AdvanceReload", remaining);
                Assert.That(Get(f.Actions, "ReloadRemaining"), Is.EqualTo(0f));
                Assert.That(Get(f.State, "LoadedAmmo"), Is.EqualTo(12));
                Assert.That(Get(f.State, "ReserveAmmo"), Is.EqualTo(f.Reserve - 7));
                Assert.That(f.Voice.clip, Is.Null);
                Assert.That(Call(f.State, "TryFire"), Is.True);
                Call(f.Actions, "AdvanceReload", 3f);
                Assert.That(Get(f.State, "LoadedAmmo"), Is.EqualTo(11)); // A duplicate commit would wrongly refill this shot.
                Assert.That(Get(f.State, "ReserveAmmo"), Is.EqualTo(f.Reserve - 7));
                Assert.That(Get(f.Actions, "PresentationEpoch"), Is.EqualTo(f.Epoch));
            }
        }
        [TestCase(false)]
        [TestCase(true)]
        public void DriverInteraction_OnlySuccessfulEntryCancelsReload(bool withinReach)
        {
            using (var f = new Fixture())
            {
                var motor = Add(f.Root, "JourneyMotor"); Field(motor, "journey", f.Session);
                var entry = GameObject.CreatePrimitive(PrimitiveType.Cube); entry.SetActive(false);
                entry.name = "driver entry test geometry"; entry.transform.SetParent(f.Root.transform, false);
                UnityEngine.Object.DestroyImmediate(entry.GetComponent<Collider>());
                entry.transform.position = new Vector3(4000, 4000, 4000);
                var player = new GameObject("driver test walker"); player.SetActive(false); player.transform.SetParent(f.Root.transform, false);
                var walker = player.AddComponent<CharacterController>();
                player.transform.position = entry.transform.position + (withinReach ? Vector3.zero : Vector3.right * 10);
                Field(motor, "walker", walker); Field(motor, "entryStep", entry.transform);
                Field(motor, "vehicle", entry.transform); Field(f.Actions, "motor", motor); Field(f.Actions, "interaction", 4);
                Physics.SyncTransforms(); Call(f.Actions, "Interact");
                Assert.That(Get(f.State, "Control").ToString(), Is.EqualTo(withinReach ? "Driving" : "OnFoot"));
                if (withinReach) f.AssertCancelled();
                else
                {
                    Assert.That(Get(f.Actions, "ReloadRemaining"), Is.EqualTo(.85f));
                    Assert.That(f.Voice.clip, Is.SameAs(f.TestClip)); f.AssertNoAmmoOrEpochChange();
                }
            }
        }
    }
}

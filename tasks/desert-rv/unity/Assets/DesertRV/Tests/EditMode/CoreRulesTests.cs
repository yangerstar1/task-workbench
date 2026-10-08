using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.ExceptionServices;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    // Invoke the production Assembly-CSharp, not a copied model or a stub.
    // This preserves existing MonoBehaviour assembly identity and serialized assets.
    internal static class Production
    {
        public static Type Type(string name) => System.Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        public static object New(string name, params object[] args) => Activator.CreateInstance(Type(name), args);
        public static object Enum(string name, string value) => System.Enum.Parse(Type(name), value);
        public static object Get(object target, string name)
        {
            var property = target.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.Instance);
            Assert.That(property, Is.Not.Null, "Missing production property: " + name);
            return property.GetValue(target);
        }
        public static T Get<T>(object target, string name) => (T)Get(target, name);
        public static object Call(object target, string name, params object[] args)
        {
            var method = target.GetType().GetMethod(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            Assert.That(method, Is.Not.Null, "Missing production method: " + name);
            try { return method.Invoke(target, args); }
            catch (TargetInvocationException exception)
            {
                ExceptionDispatchInfo.Capture(exception.InnerException ?? exception).Throw();
                throw;
            }
        }
        public static void Yes(object target, string name, params object[] args) => Assert.That(Call(target, name, args), Is.EqualTo(true), name);
        public static void No(object target, string name, params object[] args) => Assert.That(Call(target, name, args), Is.EqualTo(false), name);
        public static void Status(object target, string value) => Assert.That(Get(target, "Status").ToString(), Is.EqualTo(value));
        public static object Session(double front = -40, double speed = 2, double damage = 4)
        {
            var state = New("SessionState");
            Yes(state, "ConfigureStorm", front, speed, damage);
            Yes(state, "Start");
            return state;
        }
        public static void Install(object state, string part, string id)
        {
            var component = Enum("ComponentPart", part);
            Yes(state, "TryCollect", id, component);
            Yes(state, "TryInstall", component);
        }
        public static void Advance(object state, string part, string id)
        {
            Install(state, part, id);
            Yes(state, "SetObjectivesResolved", true);
            Yes(state, "TryAdvance");
            Yes(state, "CompleteLoading");
        }
    }

    public sealed class SessionRulesTests
    {
        [Test] public void PauseFreezesStormDamageAmmoAndProgression()
        {
            var s = Production.Session(0);
            Production.Call(s, "DamageVehicle", 20);
            Production.Call(s, "TryFire");
            Production.Call(s, "Pause");
            Production.Call(s, "AdvanceStorm", 100d, -10d, -10d);
            Production.Call(s, "DamagePlayer", 100);
            Production.Call(s, "DamageVehicle", 300);
            Production.Call(s, "Reload");
            Production.No(s, "TryFire");
            Production.No(s, "TryRepair");
            Production.No(s, "SetObjectivesResolved", true);
            Assert.That(Production.Get<double>(s, "StormElapsedSeconds"), Is.Zero);
            Assert.That(Production.Get<int>(s, "PlayerHealth"), Is.EqualTo(100));
            Assert.That(Production.Get<int>(s, "VehicleHealth"), Is.EqualTo(280));
            Assert.That(Production.Get<int>(s, "LoadedAmmo"), Is.EqualTo(11));
            Assert.That(Production.Get<int>(s, "ReserveAmmo"), Is.EqualTo(96));
            Production.Call(s, "Resume");
            Production.Call(s, "AdvanceStorm", 1d, -10d, -10d);
            Assert.That(Production.Get<int>(s, "PlayerHealth"), Is.EqualTo(96));
        }

        [TestCase(false)] [TestCase(true)]
        public void FailureRestartsWholeJourneyWithoutPersistentGrowth(bool vehicleFailure)
        {
            var s = Production.Session();
            Production.Advance(s, "RamPart", "ram");
            Production.Advance(s, "Coil", "coil");
            Production.Call(s, "TryFire"); Production.Call(s, "Reload");
            Production.Call(s, "DamageVehicle", 20); Production.Call(s, "TryRepair");
            Production.Call(s, "SetGateOpen", true); Production.Call(s, "SetPowerConnected", true);
            Production.Call(s, "SetObjectivesResolved", true);
            Production.Call(s, "SetControl", Production.Enum("ControlMode", "OnFoot"));
            Production.Call(s, "AdvanceStorm", 10d, 1000d, 1000d);
            Production.Call(s, vehicleFailure ? "DamageVehicle" : "DamagePlayer", vehicleFailure ? 300 : 100);
            Production.Status(s, "Failed"); Production.Yes(s, "RestartJourney");
            Production.Status(s, "Playing");
            foreach (var item in new Dictionary<string, int> { {"SceneId",1}, {"PlayerHealth",100}, {"VehicleHealth",300}, {"LoadedAmmo",12}, {"ReserveAmmo",96}, {"RepairKits",2} })
                Assert.That(Production.Get<int>(s, item.Key), Is.EqualTo(item.Value), item.Key);
            Assert.That(Production.Get(s, "Upgrades").ToString(), Is.EqualTo("None"));
            Assert.That(Production.Get(s, "Control").ToString(), Is.EqualTo("Driving"));
            foreach (var property in new[] { "GateOpen", "PowerConnected", "ObjectivesResolved" })
                Assert.That(Production.Get<bool>(s, property), Is.False, property);
            Assert.That(Production.Get<double>(s, "StormElapsedSeconds"), Is.Zero);
            Assert.That(Production.Get<double>(s, "StormFrontProgress"), Is.EqualTo(-40));
            Production.Yes(s, "TryCollect", "ram", Production.Enum("ComponentPart", "RamPart"));
        }

        [Test] public void LivingJourneyCannotResetForFreeSupplies() => Production.No(Production.Session(), "RestartJourney");

        [Test] public void RegionTransitionPreservesSuppliesAndStorm()
        {
            var s = Production.Session();
            Production.Call(s, "DamagePlayer", 9); Production.Call(s, "DamageVehicle", 40);
            Production.Call(s, "TryFire"); Production.Call(s, "AdvanceStorm", 17d, 1000d, 1000d);
            Production.Advance(s, "RamPart", "ram");
            Assert.That(Production.Get<int>(s, "SceneId"), Is.EqualTo(2));
            Assert.That(Production.Get<int>(s, "PlayerHealth"), Is.EqualTo(91));
            Assert.That(Production.Get<int>(s, "VehicleHealth"), Is.EqualTo(260));
            Assert.That(Production.Get<int>(s, "LoadedAmmo"), Is.EqualTo(11));
            Assert.That(Production.Get<double>(s, "StormFrontProgress"), Is.EqualTo(-6));
        }

        [Test] public void FixedStormSpeedCannotBeReconfiguredDuringRun()
        {
            var a = Production.Session(); var b = Production.Session();
            Production.Call(a, "AdvanceStorm", 10d, 1000d, 1000d);
            Production.Call(b, "AdvanceStorm", 17d, 1000d, 1000d);
            Assert.That(Production.Get<double>(b, "StormFrontProgress") - Production.Get<double>(a, "StormFrontProgress"), Is.EqualTo(14));
            Production.No(b, "ConfigureStorm", -999d, 1d, 1d);
            Assert.That(Production.Get<double>(b, "StormSpeed"), Is.EqualTo(2));
        }

        [TestCase("Driving")] [TestCase("OnFoot")]
        public void StormHurtsPlayerAndNeverRv(string control)
        {
            var s = Production.Session(0);
            Production.Call(s, "SetControl", Production.Enum("ControlMode", control));
            Production.Call(s, "AdvanceStorm", 2.5d, -10d, -10d);
            Assert.That(Production.Get<int>(s, "PlayerHealth"), Is.EqualTo(90));
            Assert.That(Production.Get<int>(s, "VehicleHealth"), Is.EqualTo(300));
        }

        [Test] public void StormBoundaryCrossingIsFrameIndependent()
        {
            var single = Production.Session(0, 2, 12); var split = Production.Session(0, 2, 12);
            Production.Call(single, "AdvanceStorm", 2d, 10d, -10d);
            Production.Call(split, "AdvanceStorm", 1d, 10d, 0d);
            Production.Call(split, "AdvanceStorm", 1d, 0d, -10d);
            Assert.That(Production.Get<int>(single, "PlayerHealth"), Is.EqualTo(86));
            Assert.That(Production.Get<int>(split, "PlayerHealth"), Is.EqualTo(86));
        }

        [Test] public void FractionalStormDamageSurvivesManyFrames()
        {
            var s = Production.Session(0, 2, 7);
            for (int i = 0; i < 180; i++) Production.Call(s, "AdvanceStorm", 1d / 60, -10d, -10d);
            Assert.That(Production.Get<int>(s, "PlayerHealth"), Is.EqualTo(79));
            Assert.That(Production.Get<double>(s, "StormFrontProgress"), Is.EqualTo(6).Within(1e-7));
        }

        [Test] public void FailedAndCompletedSessionsFreezeStorm()
        {
            var s = Production.Session(0, 2, 100);
            Production.Call(s, "AdvanceStorm", 1d, -10d, -10d);
            Production.Call(s, "AdvanceStorm", 20d, -10d, -10d);
            Production.Status(s, "Failed"); Assert.That(Production.Get<double>(s, "StormElapsedSeconds"), Is.EqualTo(1));
            Production.Yes(s, "RestartJourney");
            Production.Advance(s, "RamPart", "ram"); Production.Advance(s, "Coil", "coil");
            Production.Call(s, "SetObjectivesResolved", true); Production.Call(s, "SetGateOpen", true);
            Production.Yes(s, "TryReachSafety", true); Production.Call(s, "AdvanceStorm", 20d, -10d, -10d);
            Production.Status(s, "Completed"); Assert.That(Production.Get<double>(s, "StormElapsedSeconds"), Is.Zero);
        }

        [Test] public void BackgroundReleaseDoesNotDismissManualPause()
        {
            var s = Production.Session(); var gate = Production.New("PauseGate", s);
            Production.Call(gate, "Set", Production.Enum("PauseReason", "Manual"), true);
            Production.Call(gate, "Set", Production.Enum("PauseReason", "Background"), true);
            Production.Call(gate, "Set", Production.Enum("PauseReason", "Background"), false);
            Production.Status(s, "Paused");
            Production.Call(gate, "Set", Production.Enum("PauseReason", "Manual"), false);
            Production.Status(s, "Playing");
        }

        [Test] public void LoadingCompletionDoesNotUnpauseBackground()
        {
            var s = Production.Session(); var gate = Production.New("PauseGate", s);
            Production.Yes(s, "BeginLoading");
            Production.Call(gate, "Set", Production.Enum("PauseReason", "Background"), true);
            Production.Yes(s, "CompleteLoading"); Production.Status(s, "Paused");
            Production.Call(gate, "Set", Production.Enum("PauseReason", "Background"), false);
            Production.Status(s, "Playing");
        }
    }

    public sealed class TouchRulesTests
    {
        object input;
        [SetUp] public void SetUp() { input = Production.New("TouchInputState"); }
        void Context(string value) => Production.Yes(input, "SetContext", Production.Enum("TouchContext", value));
        void Begin(int id, string value) => Production.Yes(input, "Begin", id, Production.Enum("TouchControl", value));

        [Test] public void PointerReleaseClearsHeldControlsAndMovement()
        {
            Begin(1, "Accelerate"); Begin(2, "Move"); Production.Call(input, "Move", 2, .8f, .5f);
            Production.Call(input, "End", 1); Production.Call(input, "End", 2);
            Assert.That(Production.Get<bool>(input, "AccelerateHeld"), Is.False);
            Assert.That(Production.Get<float>(input, "MoveX"), Is.Zero);
        }
        [Test] public void ContextSwitchSuppressesHeldFingerUntilLift()
        {
            Begin(1, "Accelerate"); Context("OnFoot");
            Production.No(input, "Begin", 1, Production.Enum("TouchControl", "Fire"));
            Assert.That(Production.Get<bool>(input, "AccelerateHeld"), Is.False);
            Production.Call(input, "End", 1); Begin(1, "Fire");
        }
        [Test] public void OverlayRejectsGameplayControls()
        {
            Context("Overlay");
            foreach (var value in new[] {"Move","Look","Accelerate","Brake","Fire","Interact","Reload"})
                Production.No(input, "Begin", 1, Production.Enum("TouchControl", value));
        }
        [Test] public void MissingUpAllowsReplacementPointer()
        {
            Begin(1, "Move"); Production.Call(input, "Move", 1, 1f, 0f);
            Production.Call(input, "ReconcileFingers", new HashSet<int>());
            Assert.That(Production.Get<float>(input, "MoveX"), Is.Zero); Begin(2, "Move");
        }
        [Test] public void CancelRemovesActionEdgeAndRequiresLift()
        {
            Context("OnFoot"); Begin(1, "Fire"); Production.Call(input, "Cancel", 1);
            Assert.That(Production.Get<bool>(input, "FirePressed"), Is.False);
            Assert.That(Production.Get<bool>(input, "FireHeld"), Is.False);
            Production.No(input, "Begin", 1, Production.Enum("TouchControl", "Fire"));
            Production.Call(input, "ReconcileFingers", new HashSet<int>()); Begin(1, "Fire");
        }
        [Test] public void FrameConsumptionPreservesHoldButClearsEdgesAndLook()
        {
            Context("OnFoot"); Begin(1, "Fire"); Production.Call(input, "Move", 1, .2f, .3f);
            Production.Call(input, "ConsumeFrame");
            Assert.That(Production.Get<bool>(input, "FireHeld"), Is.True);
            Assert.That(Production.Get<bool>(input, "FirePressed"), Is.False);
            Assert.That(Production.Get<float>(input, "LookX"), Is.Zero);
        }
        [Test] public void QuickTapRetainsExactlyOneFrameEdge()
        {
            Begin(1, "Interact"); Production.Call(input, "End", 1);
            Assert.That(Production.Get<bool>(input, "InteractPressed"), Is.True);
            Production.Call(input, "ConsumeFrame"); Assert.That(Production.Get<bool>(input, "InteractPressed"), Is.False);
        }
        [Test] public void PointerOwnershipCannotBeStolen()
        {
            Begin(1, "Move");
            Production.No(input, "Begin", 2, Production.Enum("TouchControl", "Move"));
            Production.No(input, "Begin", 1, Production.Enum("TouchControl", "Accelerate"));
            Assert.That(Production.Get<bool>(input, "AccelerateHeld"), Is.False);
        }
    }

    public sealed class JourneyHostRulesTests
    {
        GameObject owner;
        object host, state;
        CursorLockMode oldLock;
        bool oldVisible;
        [SetUp] public void SetUp()
        {
            oldLock = Cursor.lockState; oldVisible = Cursor.visible;
            owner = new GameObject("EditMode journey fixture"); owner.SetActive(false);
            host = owner.AddComponent(Production.Type("JourneySession"));
            // EditMode does not run normal play-loop Awake. Invoke the production lifecycle once.
            if (Production.Get(host, "State") == null) Production.Call(host, "Awake");
            state = Production.Get(host, "State"); Production.Yes(host, "StartJourney");
        }
        [TearDown] public void TearDown()
        {
            if (owner != null) UnityEngine.Object.DestroyImmediate(owner);
            Cursor.lockState = oldLock; Cursor.visible = oldVisible;
        }
        object Ticket(string part, string id)
        {
            Production.Install(state, part, id); Production.Yes(state, "SetObjectivesResolved", true);
            return Production.Call(host, "BeginRegionAdvance");
        }
        [Test] public void DuplicateAndEarlierTransitionCallbacksAreRejected()
        {
            var first = Ticket("RamPart", "ram"); Production.Yes(host, "CompleteRegionLoad", first, 100d);
            Production.No(host, "CompleteRegionLoad", first, 100d);
            var second = Ticket("Coil", "coil"); Production.No(host, "CompleteRegionLoad", first, 100d);
            Production.Status(state, "Loading"); Production.Yes(host, "CompleteRegionLoad", second, 200d);
        }
        [Test] public void PriorJourneyCallbackCannotCompleteNewJourneyLoad()
        {
            var old = Ticket("RamPart", "ram"); Production.Yes(host, "CompleteRegionLoad", old, 100d);
            int generation = Production.Get<int>(host, "Generation");
            Production.Call(state, "DamagePlayer", 100); Production.Yes(host, "RestartJourney");
            Assert.That(Production.Get<int>(host, "Generation"), Is.EqualTo(generation + 1));
            var current = Ticket("RamPart", "ram");
            Production.No(host, "CompleteRegionLoad", old, -999d); Production.Status(state, "Loading");
            Production.Yes(host, "CompleteRegionLoad", current, 100d);
        }
        [TestCase("Generation")] [TestCase("Sequence")] [TestCase("Scene")]
        public void MismatchedLoadTicketFieldIsRejected(string field)
        {
            var valid = Ticket("RamPart", "ram");
            var type = valid.GetType();
            int generation = (int)type.GetField("Generation").GetValue(valid);
            int sequence = (int)type.GetField("Sequence").GetValue(valid);
            int scene = (int)type.GetField("Scene").GetValue(valid);
            var wrong = Activator.CreateInstance(type, new object[] {
                generation + (field == "Generation" ? 1 : 0),
                sequence + (field == "Sequence" ? 1 : 0),
                scene + (field == "Scene" ? 1 : 0) });
            Production.No(host, "CompleteRegionLoad", wrong, -999d);
            Production.Status(state, "Loading");
            Production.Yes(host, "CompleteRegionLoad", valid, 100d);
        }
        [Test] public void HostLoadCompletionPreservesManualPause()
        {
            var ticket = Ticket("RamPart", "ram"); Production.Call(host, "TogglePause");
            Production.Yes(host, "CompleteRegionLoad", ticket, 100d); Production.Status(state, "Paused");
            Production.Call(host, "TogglePause"); Production.Status(state, "Playing");
        }
        [Test] public void GameplayOverlayBlocksInputButDoesNotFreezeStorm()
        {
            Production.Call(host, "SetGameplayOverlay", true);
            var input = Production.Get(Production.Get(host, "Input"), "State");
            Assert.That(Production.Get(input, "Context").ToString(), Is.EqualTo("Overlay"));
            Production.Call(host, "TickStorm", 10d, 1000d);
            Assert.That(Production.Get<double>(state, "StormElapsedSeconds"), Is.EqualTo(10));
        }
    }
}

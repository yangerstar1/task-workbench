#if UNITY_EDITOR
using System;
using System.Collections;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace DesertRV.Tests
{
    public sealed class JourneyReplayInputTests
    {
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Call(object obj, string name, params object[] args) => obj.GetType().GetMethod(name).Invoke(obj, args);
        static object Get(object obj, string name) => obj.GetType().GetProperty(name).GetValue(obj);
        static object E(string type, string value) => Enum.Parse(T(type), value);

        const BindingFlags Instance = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
        static object Invoke(object target, string name, params object[] args) => target.GetType().GetMethod(name, Instance).Invoke(target, args);
        static object Field(object target, string name) => target.GetType().GetField(name, Instance).GetValue(target);
        static void Field(object target, string name, object value) => target.GetType().GetField(name, Instance).SetValue(target, value);

        // Controlled held-key samples exercise the production adapter and motor in native Unity.
        // They are not evidence that OS keyboard events or a rendered player were exercised.
        sealed class KeyboardFixture : IDisposable
        {
            public readonly GameObject Root = new GameObject("keyboard look input fixture");
            public readonly Component Adapter, Session, Motor;
            public readonly object State, Touch;
            readonly CursorLockMode cursorLock = Cursor.lockState;
            readonly bool cursorVisible = Cursor.visible;
            public KeyboardFixture()
            {
                Adapter = Root.AddComponent(T("MobileInputAdapter"));
                Session = Root.AddComponent(T("JourneySession")); ((Behaviour)Session).enabled = false;
                State = Get(Session, "State"); Touch = Get(Adapter, "State");
                Call(Adapter, "Sample"); // Initialize screen/safe-area before fixture input.
                Call(State, "Start"); Call(State, "SetControl", E("ControlMode", "OnFoot"));
                Call(Adapter, "SetContext", E("TouchContext", "OnFoot"));
                var vehicle = Child("fixture vehicle"); vehicle.position = new Vector3(10000,1000,10000);
                var hinge = Child("fixture door hinge"); hinge.SetParent(vehicle, false);
                var view = Child("fixture camera").gameObject.AddComponent<Camera>(); view.enabled = false;
                var motorObject = Child("fixture motor").gameObject; motorObject.SetActive(false);
                Motor = motorObject.AddComponent(T("JourneyMotor"));
                Field(Motor, "journey", Session); Field(Motor, "vehicle", vehicle);
                Field(Motor, "doorHinge", hinge); Field(Motor, "view", view);
                motorObject.SetActive(true); ((Behaviour)Motor).enabled = false;
                view.GetComponent<AudioListener>().enabled = false;
                var walker = (CharacterController)Field(Motor, "walker");
                walker.transform.position = vehicle.position; walker.enabled = true;
                Cursor.lockState = CursorLockMode.None; Cursor.visible = true;
            }
            Transform Child(string name)
            { var child = new GameObject(name).transform; child.SetParent(Root.transform, false); return child; }
            public Vector2 Look => (Vector2)Get(Adapter, "Look");
            public void Configure(float speed = 60) => Call(Adapter, "ConfigureKeyboardLook", true, speed);
            public void Rearm(bool held = false) => Invoke(Adapter, "RearmKeyboardWhenReleased", held);
            public void Sample(float delta, bool left = false, bool right = true, bool up = false, bool down = false,
                bool focused = true, bool touch = false) =>
                Invoke(Adapter, "SampleKeyboardLook", left, right, up, down, focused, touch, delta);
            public void Tick(float delta) { Call(Motor, "Tick", delta); Call(Adapter, "ConsumeFrame"); }
            public void Dispose()
            {
                UnityEngine.Object.DestroyImmediate(Root);
                Cursor.lockState = cursorLock; Cursor.visible = cursorVisible;
            }
        }

        [Test] public void KeyboardLook_RateAndBounds()
        {
            using (var f = new KeyboardFixture())
            {
                f.Configure(); f.Rearm();
                foreach (int fps in new[] { 30, 60, 120 })
                {
                    Field(f.Motor, "yaw", 0f); Field(f.Motor, "pitch", 0f);
                    for (int frame = 0; frame < fps; frame++) { f.Sample(1f / fps); f.Tick(1f / fps); }
                    Assert.That((float)Field(f.Motor, "yaw"), Is.EqualTo(60).Within(.002f), "Look -> Motor must integrate degrees once at " + fps + " FPS.");
                }
                Field(f.Motor, "pitch", 0f);
                for (int frame = 0; frame < 120; frame++) { f.Sample(1f / 60, right:false, up:true); f.Tick(1f / 60); }
                Assert.That((float)Field(f.Motor, "pitch"), Is.EqualTo(-70).Within(.001f));
                for (int frame = 0; frame < 180; frame++) { f.Sample(1f / 60, right:false, down:true); f.Tick(1f / 60); }
                Assert.That((float)Field(f.Motor, "pitch"), Is.EqualTo(70).Within(.001f));
                foreach (float invalidSpeed in new[] { float.NaN, float.PositiveInfinity, float.NegativeInfinity })
                { f.Configure(invalidSpeed); Assert.That(Get(f.Adapter, "KeyboardLookSpeed"), Is.EqualTo(60f)); }
                f.Configure(-100); Assert.That(Get(f.Adapter, "KeyboardLookSpeed"), Is.EqualTo(30f));
                f.Configure(1000); Assert.That(Get(f.Adapter, "KeyboardLookSpeed"), Is.EqualTo(120f)); f.Rearm();
                foreach (float invalidDelta in new[] { 0, -.1f, float.NaN, float.PositiveInfinity, float.NegativeInfinity })
                { f.Sample(invalidDelta); Assert.That(f.Look, Is.EqualTo(Vector2.zero)); }
                f.Sample(10); Assert.That(f.Look.x, Is.EqualTo(12).Within(.0001f), "A stall cannot queue an unbounded turn.");
                f.Sample(.1f, up:true); Assert.That(f.Look.magnitude, Is.EqualTo(12).Within(.0001f));
                f.Sample(.1f, left:true, up:true, down:true); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                f.Sample(.1f, left:true, right:false); Assert.That(f.Look.x, Is.EqualTo(-12).Within(.0001f));
            }
        }

        [Test] public void KeyboardLook_ContextAndRelease()
        {
            using (var f = new KeyboardFixture())
            {
                Assert.That(Get(f.Adapter, "KeyboardLookEnabled"), Is.False);
                Assert.That(Get(f.Adapter, "KeyboardLookSpeed"), Is.EqualTo(60f));
                f.Rearm(); f.Sample(1f / 60); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                f.Configure(); f.Rearm(true); f.Sample(1f / 60); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                f.Rearm(); f.Sample(1f / 60); Assert.That(f.Look.x, Is.EqualTo(1).Within(.0001f));
                Call(f.Session, "TogglePause"); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                f.Sample(1f / 60); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                Call(f.Session, "TogglePause"); f.Rearm(true); f.Sample(1f / 60); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                Cursor.lockState = CursorLockMode.None;
                f.Rearm(); f.Sample(1f / 60); Assert.That(f.Look.x, Is.EqualTo(1).Within(.0001f));
                Invoke(f.Session, "OnApplicationFocus", false); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                Invoke(f.Session, "OnApplicationFocus", true); f.Rearm(true); f.Sample(1f / 60); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                Cursor.lockState = CursorLockMode.None;
                f.Rearm(); f.Sample(1f / 60); Assert.That(f.Look.x, Is.EqualTo(1).Within(.0001f));
                f.Sample(1f / 60, focused:false); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                f.Sample(1f / 60, touch:true); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                f.Sample(1f / 60); Call(f.Adapter, "ConsumeFrame"); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                foreach (string context in new[] { "Driving", "Overlay" })
                {
                    Call(f.Adapter, "SetContext", E("TouchContext", context)); f.Rearm();
                    f.Sample(1f / 60); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                }
                Call(f.Adapter, "SetContext", E("TouchContext", "OnFoot")); f.Rearm(); f.Sample(1f / 60);
                Call(f.State, "DamagePlayer", 100);
                Assert.That(Call(f.Session, "RestartJourney"), Is.True); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                Call(f.State, "SetControl", E("ControlMode", "OnFoot")); Call(f.Adapter, "SetContext", E("TouchContext", "OnFoot"));
                f.Rearm(true); f.Sample(1f / 60); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                f.Rearm(); f.Sample(1f / 60); Assert.That(f.Look.x, Is.EqualTo(1).Within(.0001f));
                f.Configure(120); f.Rearm(true); f.Sample(1f / 60); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                f.Rearm(); f.Sample(1f / 60); Assert.That(f.Look.x, Is.EqualTo(2).Within(.0001f));
                f.Sample(1f / 60, right:false); Assert.That(f.Look, Is.EqualTo(Vector2.zero), "Key-up stops rotation in the next sample.");
                Invoke(f.Adapter, "OnDisable"); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
            }
        }

        [Test] public void KeyboardLook_PreservesExistingSources()
        {
            using (var f = new KeyboardFixture())
            {
                f.Configure(); f.Rearm();
                Call(f.Touch, "Begin", 42001, E("TouchControl", "Look")); Call(f.Touch, "Move", 42001, .02f, -.03f);
                Call(f.Touch, "Begin", 42002, E("TouchControl", "Move")); Call(f.Touch, "Move", 42002, .4f, .6f);
                Call(f.Touch, "Begin", 42003, E("TouchControl", "Fire"));
                Vector2 expectedMovement = Vector2.ClampMagnitude(new Vector2(.4f, .6f) +
                    new Vector2(Input.GetAxisRaw("Horizontal"), Input.GetAxisRaw("Vertical")), 1);
                f.Sample(1f / 60);
                Assert.That(f.Look.x, Is.EqualTo(4).Within(.0001f), "Touch contributes 3 degrees; keyboard contributes 1, without another x150.");
                Assert.That(f.Look.y, Is.EqualTo(-4.5f).Within(.0001f));
                Assert.That((Vector2)Get(f.Adapter, "Movement"), Is.EqualTo(expectedMovement));
                Assert.That(Get(f.Adapter, "Fire"), Is.True);
                Call(f.Adapter, "ConsumeFrame"); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                Assert.That(Get(f.Adapter, "Fire"), Is.True, "Look consumption does not clear held touch fire.");
                Call(f.Adapter, "ConfigureKeyboardLook", false, 60f); f.Rearm();
                Call(f.Touch, "End", 42001); Call(f.Touch, "Begin", 42001, E("TouchControl", "Look"));
                Call(f.Touch, "Move", 42001, .02f, -.03f); f.Sample(1f / 60);
                Assert.That(f.Look.x, Is.EqualTo(3).Within(.0001f)); Assert.That(f.Look.y, Is.EqualTo(-4.5f).Within(.0001f));
            }
        }

        [Test] public void KeyboardLook_EditorReplayIsExclusive()
        {
            using (var f = new KeyboardFixture())
            {
                f.Configure(); f.Rearm(); f.Sample(1f / 60); Assert.That(f.Look.x, Is.EqualTo(1).Within(.0001f));
                Call(f.Adapter, "AttachEditorReplay", f.Root); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
                Call(f.Touch, "Begin", 42011, E("TouchControl", "Look")); Call(f.Touch, "Move", 42011, .02f, -.03f);
                Call(f.Adapter, "SetEditorReplayFingers", f.Root, new[] { 42011 }); Call(f.Adapter, "Sample");
                Assert.That((Vector2)Field(f.Adapter, "keyboardLookDelta"), Is.EqualTo(Vector2.zero));
                Assert.That(Field(f.Adapter, "keyboardArmed"), Is.False);
                Assert.That(f.Look.x, Is.EqualTo(3).Within(.0001f)); Assert.That(f.Look.y, Is.EqualTo(-4.5f).Within(.0001f));
                Call(f.Adapter, "DetachEditorReplay", f.Root); Assert.That(f.Look, Is.EqualTo(Vector2.zero));
            }
        }

        [UnityTest] public IEnumerator HudRegionLabel_TracksSessionAdvanceAndWholeRunRestart()
        {
            // Real Awake/Update and the retained UI Text are exercised in PlayMode.
            // Session tickets are driven directly; this is not an authored-region load or gameplay replay.
            var root = new GameObject("region HUD lifecycle fixture"); root.SetActive(false);
            var originalLock = Cursor.lockState; bool originalCursor = Cursor.visible;
            Component hud = null;
            var sprites = new System.Collections.Generic.HashSet<Sprite>();
            Texture2D roundedTexture = null;
            try
            {
                Assert.That(Application.isPlaying, Is.True);
                Transform Child(string name)
                { var child = new GameObject(name).transform; child.SetParent(root.transform, false); return child; }
                var session = root.AddComponent(T("JourneySession"));
                var vehicle = Child("fixture vehicle"); var door = Child("fixture door"); door.SetParent(vehicle, false);
                var view = Child("fixture camera").gameObject.AddComponent<Camera>(); view.enabled = false;
                var motor = Child("fixture motor").gameObject.AddComponent(T("JourneyMotor"));
                Field(motor, "journey", session); Field(motor, "vehicle", vehicle); Field(motor, "doorHinge", door); Field(motor, "view", view);
                var actions = Child("fixture actions").gameObject.AddComponent(T("JourneyActions"));
                Field(actions, "journey", session); Field(actions, "motor", motor);
                var tracer = UnityEditor.AssetDatabase.LoadAssetAtPath<Material>("Assets/DesertRV/Art/Materials/JourneyNailTrajectory.mat");
                Assert.That(tracer, Is.Not.Null); Field(actions, "nailTrajectoryMaterial", tracer);
                var loader = Child("fixture loader").gameObject.AddComponent(T("RegionLoader"));
                hud = Child("fixture HUD").gameObject.AddComponent(T("JourneyHud"));
                var font = UnityEditor.AssetDatabase.LoadAssetAtPath<Font>("Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf");
                Assert.That(font, Is.Not.Null, "Restore the pinned production font before the native run.");
                var director = root.AddComponent(T("JourneyDirector"));
                Field(director, "journey", session); Field(director, "motor", motor); Field(director, "actions", actions);
                Field(director, "loader", loader); Field(director, "hud", hud);
                Field(hud, "journey", session); Field(hud, "director", director); Field(hud, "motor", motor); Field(hud, "font", font);
                root.SetActive(true); // Run the production lifecycle once, after all serialized dependencies are assigned.
                ((Behaviour)session).enabled = false; // Keep live device input outside this focused HUD test.
                view.GetComponent<AudioListener>().enabled = false;
                Assert.That(Get(director, "OwnsJourney"), Is.True);
                var textType = Type.GetType("UnityEngine.UI.Text, UnityEngine.UI", true);
                const string labelPath = "Safe area/Vehicle status/Journey label";
                var label = hud.transform.Find(labelPath).GetComponent(textType);
                Assert.That(label, Is.Not.Null);
                var state = Get(session, "State");
                void AssertLabel(int scene, string status, string expected)
                {
                    Assert.That(Get(session, "State"), Is.SameAs(state));
                    Assert.That(Get(state, "SceneId"), Is.EqualTo(scene));
                    Assert.That(Get(state, "Status").ToString(), Is.EqualTo(status));
                    Assert.That(hud.transform.Find(labelPath).GetComponent(textType), Is.SameAs(label));
                    Assert.That(((Behaviour)hud).isActiveAndEnabled && hud.GetComponent<Canvas>().enabled && label.gameObject.activeInHierarchy, Is.True);
                    Assert.That(Get(label, "text"), Is.EqualTo(expected));
                }
                Assert.That(Call(session, "StartJourney"), Is.True);
                yield return null; AssertLabel(1, "Playing", "荒漠行路 / 01");
                int generation = (int)Get(session, "Generation");
                string[] parts = { "RamPart", "Coil" }, labels = { "荒漠行路 / 02", "荒漠行路 / 03" };
                for (int step = 0; step < 2; step++)
                {
                    Assert.That(Call(state, "TryCollect", "hud-fixture-" + parts[step], E("ComponentPart", parts[step])), Is.True);
                    Assert.That(Call(state, "TryInstall", E("ComponentPart", parts[step])), Is.True);
                    Assert.That(Call(state, "SetGateOpen", true), Is.True);
                    Assert.That(Call(state, "SetObjectivesResolved", true), Is.True);
                    var ticket = Call(session, "BeginRegionAdvance");
                    Assert.That(Call(session, "IsCurrentLoad", ticket), Is.True);
                    yield return null; AssertLabel(step + 2, "Loading", labels[step]);
                    Assert.That(Call(session, "CompleteRegionLoad", ticket, 0d), Is.True);
                    yield return null; AssertLabel(step + 2, "Playing", labels[step]);
                    Assert.That(Get(session, "Generation"), Is.EqualTo(generation));
                }
                Call(state, "DamagePlayer", 100);
                yield return null; AssertLabel(3, "Failed", "荒漠行路 / 03");
                Assert.That(Call(session, "RestartJourney"), Is.True);
                Assert.That(Get(session, "Generation"), Is.EqualTo(generation + 1));
                var restart = Call(session, "BeginCurrentRegionLoad");
                Assert.That(Call(session, "IsCurrentLoad", restart), Is.True);
                yield return null; AssertLabel(1, "Loading", "荒漠行路 / 01");
                Assert.That(Call(session, "CompleteRegionLoad", restart, 0d), Is.True);
                yield return null; AssertLabel(1, "Playing", "荒漠行路 / 01");
            }
            finally
            {
                // HUD Awake owns four runtime sprites and one texture; do not destroy imported assets or whiteTexture.
                if (hud)
                {
                    var rounded = (Sprite)Field(hud, "rounded");
                    if (rounded) { sprites.Add(rounded); roundedTexture = rounded.texture; }
                    foreach (string field in new[] { "playerBar", "carBar", "actionBar" })
                    { var bar = Field(hud, field); if (bar != null) sprites.Add((Sprite)Get(bar, "sprite")); }
                }
                UnityEngine.Object.DestroyImmediate(root);
                foreach (var sprite in sprites) if (sprite) UnityEngine.Object.DestroyImmediate(sprite);
                if (roundedTexture) UnityEngine.Object.DestroyImmediate(roundedTexture);
                Cursor.lockState = originalLock; Cursor.visible = originalCursor;
            }
        }

        [UnityTest] public IEnumerator HeldFire_SurvivesAdapterSampleWithoutNewPressedEdge()
        {
            var go = new GameObject("replay ownership test"); var adapter = go.AddComponent(T("MobileInputAdapter"));
            try
            {
                Call(adapter, "Sample"); // Initialize screen/safe-area before pressing.
                Call(adapter, "AttachEditorReplay", go);
                Call(adapter, "SetContext", E("TouchContext", "OnFoot"));
                var state = Get(adapter, "State");
                Assert.That(Call(state, "Begin", 41001, E("TouchControl", "Fire")), Is.True);
                Call(state, "Begin", 41003, E("TouchControl", "Move")); Call(state, "Move", 41003, .8f, .3f);
                Call(adapter, "SetEditorReplayFingers", go, new[] { 41001, 41003 });
                Call(adapter, "ConsumeFrame");
                Call(adapter, "Sample");
                Assert.That(Get(state, "FireHeld"), Is.True);
                Assert.That(Get(state, "FirePressed"), Is.False, "Holding is not a new button-down each frame.");
                Assert.That(Get(state, "MoveX"), Is.EqualTo(.8f).Within(.0001));
                Assert.That(Get(state, "MoveY"), Is.EqualTo(.3f).Within(.0001));
                Call(state, "End", 41003);
                Call(state, "End", 41001); Call(adapter, "SetEditorReplayFingers", go, Array.Empty<int>());
                Call(adapter, "Sample"); Assert.That(Get(state, "FireHeld"), Is.False);
                Call(adapter, "DetachEditorReplay", go);
                Assert.That(Get(adapter, "EditorReplayActive"), Is.False);
            }
            finally { UnityEngine.Object.Destroy(go); }
            yield return null;
        }
        [UnityTest] public IEnumerator ContextCancellation_HeldReplayRequiresLiftBeforeRepress()
        {
            var go = new GameObject("replay cancellation test"); var adapter = go.AddComponent(T("MobileInputAdapter"));
            try
            {
                Call(adapter, "Sample"); Call(adapter, "AttachEditorReplay", go);
                Call(adapter, "SetContext", E("TouchContext", "OnFoot")); var state = Get(adapter, "State");
                Call(state, "Begin", 41002, E("TouchControl", "Fire"));
                Call(adapter, "SetEditorReplayFingers", go, new[] { 41002 });
                Call(adapter, "SetContext", E("TouchContext", "Overlay"));
                Call(adapter, "SetContext", E("TouchContext", "OnFoot")); Call(adapter, "Sample");
                Assert.That(Get(state, "FireHeld"), Is.False);
                Assert.That(Call(state, "Begin", 41002, E("TouchControl", "Fire")), Is.False);
                Call(state, "End", 41002); Call(adapter, "SetEditorReplayFingers", go, Array.Empty<int>()); Call(adapter, "Sample");
                Assert.That(Call(state, "Begin", 41002, E("TouchControl", "Fire")), Is.True);
                Call(adapter, "DetachEditorReplay", go);
            }
            finally { UnityEngine.Object.Destroy(go); }
            yield return null;
        }
        [UnityTest] public IEnumerator ScopeRequestHashChange_InvalidatesAndCloseClearsCapability()
        {
            // Deliberately corrupt only the diagnostic capability fixture, never gameplay state.
            var type = T("Editor.JourneyDiagnosticScope");
            string path = System.IO.Path.Combine(Application.temporaryCachePath, "diagnostic-scope-" + Guid.NewGuid() + ".json");
            try
            {
                System.IO.File.WriteAllText(path, "changed request");
                type.GetField("request", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, Activator.CreateInstance(type.GetNestedType("Request")));
                type.GetField("requestPath", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, path);
                type.GetField("requestHash", BindingFlags.Static | BindingFlags.NonPublic).SetValue(null, new string('0', 64));
                object[] args = { null };
                LogAssert.Expect(LogType.Error, "EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT INVALIDATED: Diagnostic lifetime or request hash changed.");
                Assert.That(type.GetMethod("ValidateCurrent").Invoke(null, args), Is.False);
                Assert.That(type.GetProperty("InvalidReason").GetValue(null), Is.Not.Null);
            }
            finally
            {
                type.GetMethod("Close").Invoke(null, null);
                if (System.IO.File.Exists(path)) System.IO.File.Delete(path);
            }
            Assert.That(type.GetProperty("Active").GetValue(null), Is.False);
            yield return null;
        }
    }
}
#endif

using System.Collections.Generic;
using UnityEngine;

namespace DesertRV
{
    // Pixel hit areas are shared with the HUD. Ownership is fixed at pointer-down;
    // a drag across another button never activates that other control.
    public sealed class MobileInputAdapter : MonoBehaviour
    {
        public TouchInputState State { get; } = new TouchInputState();
        readonly Dictionary<TouchControl, Rect> regions = new Dictionary<TouchControl, Rect>();
        readonly Dictionary<int, Vector2> origins = new Dictionary<int, Vector2>();
        readonly Dictionary<int, TouchControl> owners = new Dictionary<int, TouchControl>();
        readonly HashSet<int> active = new HashSet<int>();
        const int MouseId = int.MaxValue;
        Vector2 lastMouse;
        int screenWidth, screenHeight;
        Rect safeArea;
        bool keyboardArmed;
        bool keyboardLookEnabled;
        float keyboardLookSpeed = 60;
        Vector2 keyboardLookDelta;
        public bool KeyboardLookEnabled => keyboardLookEnabled;
        public float KeyboardLookSpeed => keyboardLookSpeed;
        public float StickRadius { get; set; } = 70;
        public Rect SafeArea => Screen.safeArea;
        public bool IsTouch => Application.isMobilePlatform || Input.touchCount > 0;

        public void SetRegion(TouchControl control, Rect screenPixels) => regions[control] = screenPixels;
        public void ClearRegions() => regions.Clear();

        // Session-local accessibility settings. Mouse and touch retain their own sensitivities.
        public void ConfigureKeyboardLook(bool enabled, float degreesPerSecond)
        {
            float speed = float.IsNaN(degreesPerSecond) || float.IsInfinity(degreesPerSecond) ?
                60 : Mathf.Clamp(degreesPerSecond, 30, 120);
            if (keyboardLookEnabled == enabled && keyboardLookSpeed == speed) return;
            keyboardLookEnabled = enabled; keyboardLookSpeed = speed;
            ReleaseAll(); // A held key cannot become a fresh input after a setting change.
        }

        public void SetContext(TouchContext context)
        {
            if (State.Context == context) return;
            State.SetContext(context);
            origins.Clear(); owners.Clear(); keyboardArmed = false; keyboardLookDelta = Vector2.zero;
        }

        public void ReleaseAll()
        {
            State.CancelAll(); origins.Clear(); owners.Clear(); keyboardArmed = false; keyboardLookDelta = Vector2.zero;
        }

        void OnDisable() => ReleaseAll();

#if UNITY_EDITOR
        UnityEngine.Object editorReplayOwner;
        readonly HashSet<int> editorReplayFingers = new HashSet<int>();
        public bool EditorReplayActive => editorReplayOwner;
        public void AttachEditorReplay(UnityEngine.Object owner)
        {
            if (!Application.isPlaying || !owner || editorReplayOwner)
                throw new System.InvalidOperationException("One explicit Editor replay owner is required.");
            ReleaseAll(); editorReplayOwner = owner; editorReplayFingers.Clear();
        }
        public void SetEditorReplayFingers(UnityEngine.Object owner, IEnumerable<int> fingers)
        {
            if (!owner || owner != editorReplayOwner) throw new System.InvalidOperationException("Replay owner mismatch.");
            editorReplayFingers.Clear();
            foreach (int id in fingers) editorReplayFingers.Add(id);
        }
        public void DetachEditorReplay(UnityEngine.Object owner)
        {
            if (owner != editorReplayOwner) return;
            ReleaseAll(); editorReplayFingers.Clear(); editorReplayOwner = null;
        }
#endif

        // Called exactly once by the journey simulation, before reading controls.
        // Does not own the game's pause policy or consume action edges itself.
        public void Sample()
        {
            keyboardLookDelta = Vector2.zero;
            if (screenWidth != Screen.width || screenHeight != Screen.height || safeArea != Screen.safeArea)
            {
                ReleaseAll(); screenWidth = Screen.width; screenHeight = Screen.height; safeArea = Screen.safeArea;
            }
#if UNITY_EDITOR
            if (editorReplayOwner)
            {
                keyboardArmed = false;
                State.ReconcileFingers(editorReplayFingers);
                return; // Only the explicit replay source owns pointers; no real/synthetic mixing.
            }
#endif
            active.Clear();
            for (int i = 0; i < Input.touchCount; i++)
            {
                Touch touch = Input.GetTouch(i);
                if (touch.phase != TouchPhase.Ended && touch.phase != TouchPhase.Canceled) active.Add(touch.fingerId);
                if (touch.phase == TouchPhase.Ended) End(touch.fingerId, false);
                else if (touch.phase == TouchPhase.Canceled) End(touch.fingerId, true);
            }
            if (!Application.isMobilePlatform && Input.touchCount == 0 && Input.GetMouseButton(0)) active.Add(MouseId);
            // A missing Up event must release its owner before a replacement pointer begins.
            State.ReconcileFingers(active);
            // Release old owners before new downs, independent of OS touch array order.
            for (int i = 0; i < Input.touchCount; i++)
            {
                Touch touch = Input.GetTouch(i);
                if (touch.phase == TouchPhase.Began) Begin(touch.fingerId, touch.position);
                else if (touch.phase == TouchPhase.Moved || touch.phase == TouchPhase.Stationary)
                    Move(touch.fingerId, touch.position, touch.deltaPosition);
            }
            // Ignore synthetic mouse events generated by real mobile touches.
            if (!Application.isMobilePlatform && Input.touchCount == 0)
            {
                Vector2 mouse = Input.mousePosition;
                if (Input.GetMouseButton(0)) active.Add(MouseId);
                if (Input.GetMouseButtonDown(0)) Begin(MouseId, mouse);
                else if (Input.GetMouseButtonUp(0)) End(MouseId, false);
                else if (Input.GetMouseButton(0)) Move(MouseId, mouse, mouse - lastMouse);
                lastMouse = mouse;
                RearmKeyboardWhenReleased(AnyGameplayKeyHeld());
            }
            SampleKeyboardLook(Input.GetKey(KeyCode.J), Input.GetKey(KeyCode.L),
                Input.GetKey(KeyCode.I), Input.GetKey(KeyCode.K), Application.isFocused, IsTouch, Time.deltaTime);
            State.ReconcileFingers(active);
            // Forget a missing-up finger's adapter bookkeeping as well.
            var expired = new List<int>();
            foreach (int id in owners.Keys) if (!active.Contains(id)) expired.Add(id);
            foreach (int id in expired) { owners.Remove(id); origins.Remove(id); }
        }

        void Begin(int id, Vector2 point)
        {
            if (!SafeArea.Contains(point)) return;
            // Explicit priority prevents large look area stealing action buttons.
            TouchControl[] order = { TouchControl.Interact, TouchControl.Reload, TouchControl.Fire,
                TouchControl.Accelerate, TouchControl.Brake, TouchControl.Move, TouchControl.Look };
            foreach (var control in order)
                if (regions.TryGetValue(control, out Rect bounds) && bounds.Contains(point))
                {
                    if (State.Begin(id, control))
                    {
                        owners[id] = control;
                        origins[id] = control == TouchControl.Move ? bounds.center : point;
                        Move(id, point, Vector2.zero);
                    }
                    return;
                }
        }

        void Move(int id, Vector2 point, Vector2 delta)
        {
            if (!owners.TryGetValue(id, out var control)) return;
            if (control == TouchControl.Move)
            {
                Vector2 offset = (point - origins[id]) / Mathf.Max(1, StickRadius);
                State.Move(id, offset.x, offset.y);
            }
            else State.Move(id, delta.x / Mathf.Max(1, SafeArea.height), delta.y / Mathf.Max(1, SafeArea.height));
        }

        void End(int id, bool canceled)
        {
            if (canceled) State.Cancel(id); else State.End(id);
            origins.Remove(id); owners.Remove(id);
        }

        bool AnyGameplayKeyHeld() => Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.A) ||
            Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.E) ||
            Input.GetKey(KeyCode.R) || Input.GetKey(KeyCode.Space) || Input.GetMouseButton(0) ||
            Input.GetKey(KeyCode.UpArrow) || Input.GetKey(KeyCode.DownArrow) ||
            Input.GetKey(KeyCode.LeftArrow) || Input.GetKey(KeyCode.RightArrow) ||
            (keyboardLookEnabled && (Input.GetKey(KeyCode.I) || Input.GetKey(KeyCode.J) ||
                Input.GetKey(KeyCode.K) || Input.GetKey(KeyCode.L)));

        void RearmKeyboardWhenReleased(bool anyGameplayKeyHeld)
        { if (!anyGameplayKeyHeld) keyboardArmed = true; }

        void SampleKeyboardLook(bool left, bool right, bool up, bool down, bool focused, bool touch, float delta)
        {
            keyboardLookDelta = Vector2.zero;
            if (!keyboardLookEnabled || !keyboardArmed || !focused || touch || State.Context != TouchContext.OnFoot ||
                float.IsNaN(delta) || float.IsInfinity(delta) || delta <= 0) return;
            var direction = new Vector2((right ? 1 : 0) - (left ? 1 : 0), (up ? 1 : 0) - (down ? 1 : 0));
            // Look is degrees this frame, not a rate or the touch viewport displacement.
            // Cap stall catch-up; ordinary frame rates integrate the same angular speed.
            keyboardLookDelta = Vector2.ClampMagnitude(direction, 1) * keyboardLookSpeed * Mathf.Min(delta, .1f);
        }

        bool KeyboardEnabled => keyboardArmed && !IsTouch && State.Context != TouchContext.Overlay;
        public Vector2 Movement => Vector2.ClampMagnitude(new Vector2(State.MoveX, State.MoveY) +
            (KeyboardEnabled ? new Vector2(Input.GetAxisRaw("Horizontal"), Input.GetAxisRaw("Vertical")) : Vector2.zero), 1);
        public float Throttle => (State.AccelerateHeld ? 1 : 0) - (State.BrakeHeld ? 1 : 0) +
            (KeyboardEnabled ? Input.GetAxisRaw("Vertical") : 0);
        public Vector2 Look => new Vector2(State.LookX, State.LookY) * 150 +
            (KeyboardEnabled && Cursor.lockState == CursorLockMode.Locked ? new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y")) * 1.7f : Vector2.zero) +
            keyboardLookDelta;
        public bool Fire => State.FirePressed || State.FireHeld ||
            (KeyboardEnabled && Input.GetMouseButton(0) && Cursor.lockState == CursorLockMode.Locked);
        public bool Interact => State.InteractPressed || (KeyboardEnabled && Input.GetKeyDown(KeyCode.E));
        public bool Reload => State.ReloadPressed || (KeyboardEnabled && Input.GetKeyDown(KeyCode.R));
        public void ConsumeFrame() { State.ConsumeFrame(); keyboardLookDelta = Vector2.zero; }
    }
}

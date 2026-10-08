using System;
using System.Collections.Generic;

namespace DesertRV
{
    public enum TouchContext { Driving, OnFoot, Overlay }
    public enum TouchControl { Move, Look, Accelerate, Brake, Fire, Interact, Reload }

    // Pure input ownership, independent of screen resolution and Unity UI technology.
    // UI hit testing supplies a control ONLY on pointer-down. A pointer never changes
    // owners when it drags across another button. Finger IDs, not array indices, are used.
    public sealed class TouchInputState
    {
        readonly Dictionary<int, TouchControl> pointers = new Dictionary<int, TouchControl>();
        readonly HashSet<int> suppressed = new HashSet<int>();
        readonly Dictionary<int, long> pressIds = new Dictionary<int, long>();
        readonly HashSet<long> interactEdges = new HashSet<long>();
        readonly HashSet<long> reloadEdges = new HashSet<long>();
        readonly HashSet<long> fireEdges = new HashSet<long>();
        long nextPressId;
        public TouchContext Context { get; private set; } = TouchContext.Driving;
        public float MoveX { get; private set; }
        public float MoveY { get; private set; }
        public float LookX { get; private set; }
        public float LookY { get; private set; }
        public bool FireHeld => pointers.ContainsValue(TouchControl.Fire);
        public bool AccelerateHeld => pointers.ContainsValue(TouchControl.Accelerate);
        public bool BrakeHeld => pointers.ContainsValue(TouchControl.Brake);
        public bool InteractPressed => interactEdges.Count > 0;
        public bool ReloadPressed => reloadEdges.Count > 0;
        public bool FirePressed => fireEdges.Count > 0;

        public bool SetContext(TouchContext context)
        {
            if (!Enum.IsDefined(typeof(TouchContext), context)) return false;
            if (Context == context) return true;
            CancelAll();
            Context = context;
            return true;
        }

        bool Allowed(TouchControl control)
        {
            if (!Enum.IsDefined(typeof(TouchControl), control) || Context == TouchContext.Overlay) return false;
            if (Context == TouchContext.Driving)
                return control == TouchControl.Move || control == TouchControl.Accelerate ||
                    control == TouchControl.Brake || control == TouchControl.Interact;
            return control != TouchControl.Accelerate && control != TouchControl.Brake;
        }

        public bool Begin(int fingerId, TouchControl control)
        {
            if (fingerId < 0 || suppressed.Contains(fingerId) || pointers.ContainsKey(fingerId) ||
                pointers.ContainsValue(control) || !Allowed(control)) return false;
            pointers.Add(fingerId, control);
            long pressId = ++nextPressId;
            pressIds.Add(fingerId, pressId);
            if (control == TouchControl.Interact) interactEdges.Add(pressId);
            if (control == TouchControl.Reload) reloadEdges.Add(pressId);
            if (control == TouchControl.Fire) fireEdges.Add(pressId);
            return true;
        }

        // For Move: normalized stick displacement. For Look/Fire: frame delta in
        // normalized viewport units. Pixel conversion and sensitivity belong to the adapter.
        public bool Move(int fingerId, float x, float y)
        {
            if (!pointers.TryGetValue(fingerId, out var control)) return false;
            if (!Finite(x) || !Finite(y)) { Cancel(fingerId); return false; }
            if (control == TouchControl.Move)
            {
                x = Clamp(x); y = Clamp(y);
                double length = Math.Sqrt(x * x + y * y);
                if (length > 1) { x /= (float)length; y /= (float)length; }
                MoveX = x; MoveY = Context == TouchContext.Driving ? 0 : y;
            }
            else if (control == TouchControl.Look || control == TouchControl.Fire)
            {
                LookX = Clamp(LookX + Clamp(x)); LookY = Clamp(LookY + Clamp(y));
            }
            return true;
        }

        public void End(int fingerId)
        {
            suppressed.Remove(fingerId);
            if (!pointers.TryGetValue(fingerId, out var control)) return;
            pointers.Remove(fingerId);
            pressIds.Remove(fingerId);
            if (control == TouchControl.Move) { MoveX = 0; MoveY = 0; }
        }

        public void Cancel(int fingerId)
        {
            if (!pointers.TryGetValue(fingerId, out var control)) return;
            long pressId = pressIds[fingerId];
            End(fingerId);
            interactEdges.Remove(pressId); reloadEdges.Remove(pressId); fireEdges.Remove(pressId);
            suppressed.Add(fingerId);
        }

        public void CancelAll()
        {
            foreach (int id in pointers.Keys) suppressed.Add(id);
            pointers.Clear();
            pressIds.Clear();
            MoveX = MoveY = LookX = LookY = 0;
            interactEdges.Clear(); reloadEdges.Clear(); fireEdges.Clear();
        }

        // Call after consuming per-frame inputs; held movement/buttons persist.
        public void ConsumeFrame()
        {
            LookX = LookY = 0;
            interactEdges.Clear(); reloadEdges.Clear(); fireEdges.Clear();
        }

        // On app resume, the adapter supplies the OS's current active finger IDs.
        // Released fingers can be reused; still-held fingers require a real lift first.
        public void ReconcileFingers(ISet<int> activeFingerIds)
        {
            if (activeFingerIds == null) throw new ArgumentNullException(nameof(activeFingerIds));
            foreach (int id in new List<int>(pointers.Keys))
                if (!activeFingerIds.Contains(id)) End(id);
            suppressed.RemoveWhere(id => !activeFingerIds.Contains(id));
        }

        static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
        static float Clamp(float value) => Math.Max(-1, Math.Min(1, value));
    }
}

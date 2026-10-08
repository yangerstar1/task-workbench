using UnityEngine;

namespace DesertRV
{
    [DisallowMultipleComponent]
    public sealed class BeastWeakPointPresentation : MonoBehaviour
    {
        public BeastActor actor;
        public Renderer weakPointRenderer;
        public int materialSlot;
        public Material openMaterial;
        public Transform armorPlate;
        public Vector3 openLocalEuler = new Vector3(-28, 0, 0);
        Material[] original;
        Quaternion closedRotation;
        bool owns, open;
        public bool ValidateBindings(out string reason)
        {
            reason = null;
            if (!actor || !actor.armored || !weakPointRenderer || !openMaterial || !armorPlate ||
                !weakPointRenderer.transform.IsChildOf(actor.transform) || !armorPlate.IsChildOf(actor.transform) ||
                materialSlot < 0 || materialSlot >= weakPointRenderer.sharedMaterials.Length)
                reason = "Weakpoint needs independent armored mesh/material slot and actual armor plate.";
            else if (weakPointRenderer.sharedMaterials[materialSlot] == openMaterial) reason = "Open and closed materials must differ.";
            return reason == null;
        }
        void OnEnable()
        {
            if (!ValidateBindings(out var error)) { Debug.LogError(error, this); enabled = false; return; }
            if (!PresentationOwnership.Acquire(actor, this, "weakpoint")) { Debug.LogError("Duplicate weakpoint presenter.", this); enabled = false; return; }
            owns = true; original = weakPointRenderer.sharedMaterials; closedRotation = armorPlate.localRotation;
            Apply(false);
        }
        void OnDisable()
        {
            if (!owns) return;
            Apply(false); PresentationOwnership.Release(actor, this, "weakpoint"); owns = false;
        }
        void Apply(bool visible)
        {
            open = visible;
            if (weakPointRenderer && original != null)
            {
                var materials = (Material[])original.Clone();
                if (visible) materials[materialSlot] = openMaterial;
                weakPointRenderer.sharedMaterials = materials;
            }
            if (armorPlate) armorPlate.localRotation = closedRotation * (visible ? Quaternion.Euler(openLocalEuler) : Quaternion.identity);
        }
        void LateUpdate()
        {
            if (!owns) return;
            // Read the real combat window, not a guessed animation normalized time.
            bool visible = actor && actor.WeakPointExposed;
            if (visible != open) Apply(visible);
            // Plate is a dedicated presentation child, never a bone keyed by the combat animator.
            if (armorPlate) armorPlate.localRotation = closedRotation * (open ? Quaternion.Euler(openLocalEuler) : Quaternion.identity);
        }
    }
}

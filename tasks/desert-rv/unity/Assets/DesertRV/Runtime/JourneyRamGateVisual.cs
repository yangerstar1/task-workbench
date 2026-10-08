using UnityEngine;
namespace DesertRV
{
    // Presentation only. Director's swept ram contact owns Collider.enabled and progression.
    public sealed class JourneyRamGateVisual : MonoBehaviour
    {
        public Collider gate;
        public GameObject intact, damaged;
        bool lastBroken, observed;
        public bool ValidateBindings(out string reason)
        {
            reason=null;
            if(!gate || !intact || !damaged || intact==damaged ||
                !intact.transform.IsChildOf(transform) || !damaged.transform.IsChildOf(transform) ||
                intact==gameObject || damaged==gameObject || gate.transform.IsChildOf(intact.transform) || gate.transform.IsChildOf(damaged.transform))
                reason="Gate requires its real collider and separate decoration-only child roots.";
            else if(intact.GetComponentsInChildren<Collider>(true).Length!=0 || damaged.GetComponentsInChildren<Collider>(true).Length!=0 ||
                intact.GetComponentsInChildren<MonoBehaviour>(true).Length!=0 || damaged.GetComponentsInChildren<MonoBehaviour>(true).Length!=0)
                reason="Gate visual roots must never contain gameplay scripts or colliders.";
            return reason==null;
        }
        void OnEnable() { observed=false; RefreshFromGate(); }
        void OnDisable() { observed=false; }
        void LateUpdate() => RefreshFromGate();
        public void RefreshFromGate()
        {
            if(!isActiveAndEnabled || !ValidateBindings(out _)) return;
            bool broken=!gate.enabled;
            if(observed && broken==lastBroken) return;
            lastBroken=broken;observed=true;
            intact.SetActive(!broken);damaged.SetActive(broken);
        }
    }
}

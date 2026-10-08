using UnityEngine;

namespace DesertRV
{
    // Keep every world collider, including the RV. Only the caller's exact body
    // collider is excluded; sharing a parent/layer/name never grants an exemption.
    public static class JourneyRaycast
    {
        public static bool TryFirstHit(Vector3 origin, Vector3 direction, float distance,
            Collider self, out RaycastHit hit)
        {
            hit = default;
            if (distance <= 0 || direction.sqrMagnitude <= 0) return false;
            // All hits avoids a fixed NonAlloc buffer silently dropping a closer wall
            // or enemy. Unity does not guarantee the returned array's ordering.
            return TrySelectFirst(Physics.RaycastAll(origin, direction.normalized, distance,
                ~0, QueryTriggerInteraction.Ignore), self, out hit);
        }

        public static bool CanReachPoint(Vector3 origin, Vector3 point, Collider self, Collider targetSurface)
        {
            Vector3 direction = point - origin;
            if (!TryFirstHit(origin, direction, direction.magnitude, self, out var hit)) return true;
            // The authored anchor may sit just inside its own bench. This small
            // allowance belongs only to that exact surface, never a nearby wall/RV.
            return targetSurface && hit.collider == targetSurface &&
                Vector3.Distance(hit.point, point) < .35f;
        }

        public static bool TrySelectFirst(RaycastHit[] hits, Collider self, out RaycastHit hit)
        {
            hit = default;
            bool found = false;
            foreach (var candidate in hits)
            {
                if (!candidate.collider || candidate.collider == self) continue;
                if (found && candidate.distance >= hit.distance) continue;
                hit = candidate;
                found = true;
            }
            return found;
        }
    }
}

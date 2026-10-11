using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV
{
    // Added only by real-region integration. The imported model/STRICT preview has no mover.
    // The authored root is the support datum, not the bottom of the elevated hurt capsule.
    [DisallowMultipleComponent]
    public sealed class PouncerGroundSupport : MonoBehaviour, PouncerPawContactConstraint.ISceneSupport
    {
        public BeastActor actor;
        public PouncerPawContactConstraint paws;
        public RegionBinding region;
        public string LastFailure { get; private set; }
        public Vector3 RootBeforeLastReconcile { get; private set; }
        public Vector3 RootAfterLastReconcile { get; private set; }
        readonly Collider[] pawSupports = new Collider[4];
        static int LegIndex(string id) => id == "fore.L" ? 0 : id == "fore.R" ? 1 : id == "hind.L" ? 2 : id == "hind.R" ? 3 : -1;
        public Collider LastPawSupport(string id) { int index = LegIndex(id); return index < 0 ? null : pawSupports[index]; }
        public void RecordPawSupport(string id, Collider surface) { int index = LegIndex(id); if (index >= 0) pawSupports[index] = surface; }
        public const float MinimumSupportNormalY = .9f; // Same slope limit as authored spawn grounding.
        // A non-jumping beast can negotiate a step/drop up to half its capsule radius.
        // This is a body-relative movement limit, independent of road heights and IK budgets.
        const float StepRadiusFraction = .5f, SampleRadiusFraction = .25f;
        const float Clearance = .04f, PositionTolerance = .0001f;
        readonly List<Vector3> footprint = new List<Vector3>();
        readonly List<Vector3> path = new List<Vector3>();
        readonly RaycastHit[] hits = new RaycastHit[32];
        readonly Collider[] overlaps = new Collider[32];
        struct SupportBox { internal BoxCollider collider; internal Vector3 center, extents; internal Quaternion rotation, inverse; }
        readonly SupportBox[] boxes = new SupportBox[2];

        public bool ValidateBindings(out string reason)
        {
            reason = null;
            var scene = gameObject.scene;
            if (!scene.IsValid() || !scene.isLoaded || !scene.GetPhysicsScene().IsValid())
            { reason = "Pouncer support requires a valid loaded actor PhysicsScene."; return false; }
            if (!actor || actor.gameObject != gameObject || actor.armored || !paws || paws.gameObject != gameObject || paws.actor != actor ||
                !region || region.gameObject.scene != gameObject.scene || region.pouncerSupportSurfaces == null || region.pouncerSupportSurfaces.Length != 2)
            { reason = "Pouncer requires its real same-scene region and explicit foundation/road supports."; return false; }
            bool foundation = false, road = false;
            foreach (var floor in region.pouncerSupportSurfaces)
            {
                if (!floor || floor.gameObject.scene != gameObject.scene || floor.transform.parent != region.transform ||
                    !floor.enabled || !floor.gameObject.activeInHierarchy || floor.isTrigger || floor.attachedRigidbody ||
                    floor.GetComponentInParent<BeastActor>() || floor.GetComponentInParent<JourneyMotor>() ||
                    !TwoBoneArmSolver.Finite(floor.bounds.min) || !TwoBoneArmSolver.Finite(floor.bounds.max) ||
                    floor.size.x <= 0 || floor.size.y <= 0 || floor.size.z <= 0 || !Unskewed(floor.transform))
                { reason = "Support must be an enabled static authored region box, never a prop, actor or vehicle."; return false; }
                if (floor.name == "Route foundation" && !foundation) foundation = true;
                else if (floor.name == "Road surface" && !road) road = true;
                else { reason = "Support inventory must contain the distinct authored foundation and road."; return false; }
            }
            if (!foundation || !road) { reason = "Missing authored foundation/road."; return false; }
            return true;
        }

        static bool Unskewed(Transform t)
        {
            var matrix = t.localToWorldMatrix;
            var x = matrix.MultiplyVector(Vector3.right); var y = matrix.MultiplyVector(Vector3.up); var z = matrix.MultiplyVector(Vector3.forward);
            return x.sqrMagnitude > 0 && y.sqrMagnitude > 0 && z.sqrMagnitude > 0 &&
                Mathf.Abs(Vector3.Dot(x.normalized, y.normalized)) < .00001f &&
                Mathf.Abs(Vector3.Dot(x.normalized, z.normalized)) < .00001f && Mathf.Abs(Vector3.Dot(y.normalized, z.normalized)) < .00001f;
        }
        void CacheSupportBoxes()
        {
            for (int i = 0; i < boxes.Length; i++)
            {
                var floor = region.pouncerSupportSurfaces[i]; var scale = floor.transform.lossyScale;
                boxes[i] = new SupportBox { collider = floor, center = floor.transform.TransformPoint(floor.center),
                    extents = Vector3.Scale(floor.size, new Vector3(Mathf.Abs(scale.x), Mathf.Abs(scale.y), Mathf.Abs(scale.z))) * .5f,
                    rotation = floor.transform.rotation, inverse = Quaternion.Inverse(floor.transform.rotation) };
            }
        }
        // Exact vertical ray/OBB intersection against the two authored BoxCollider shapes.
        // This avoids per-vertex Physics queries and never extends a tangent plane off a box.
        // Unity boxes use rotation plus lossyScale; sheared hierarchies are rejected below.
        public bool TrySampleSupport(Vector3 point, out PouncerPawContactConstraint.SurfaceHit support)
        {
            support = default; bool found = false;
            foreach (var box in boxes)
            {
                var local = box.inverse * (point - box.center);
                var direction = box.inverse * Vector3.down;
                float near = float.NegativeInfinity, far = float.PositiveInfinity; Vector3 normal = Vector3.zero;
                bool intersects = true;
                for (int axis = 0; axis < 3; axis++)
                {
                    if (Mathf.Abs(direction[axis]) < .000001f)
                    {
                        if (local[axis] < -box.extents[axis] || local[axis] > box.extents[axis]) { intersects = false; break; }
                        continue;
                    }
                    float a = (-box.extents[axis] - local[axis]) / direction[axis];
                    float b = ( box.extents[axis] - local[axis]) / direction[axis];
                    float entry = Mathf.Min(a, b), leave = Mathf.Max(a, b);
                    if (entry > near) { near = entry; normal = Vector3.zero; normal[axis] = direction[axis] > 0 ? -1 : 1; }
                    far = Mathf.Min(far, leave);
                    if (near > far) { intersects = false; break; }
                }
                if (!intersects) continue;
                var worldNormal = box.rotation * normal; var hit = point + Vector3.down * near;
                if (worldNormal.y < MinimumSupportNormalY || !TwoBoneArmSolver.Finite(hit)) continue;
                if (!found || hit.y > support.point.y)
                { support = new PouncerPawContactConstraint.SurfaceHit { collider = box.collider, point = hit, normal = worldNormal }; found = true; }
            }
            return found;
        }

        bool RootHeight(Vector3 displacement, out float height, out string reason)
        {
            height = float.NegativeInfinity; reason = null;
            // Every sample must have a real eligible surface. The highest actual sample wins;
            // averaging mixed low/high support would push feet into the high side.
            foreach (var point in footprint)
            {
                if (!TrySampleSupport(point + displacement, out var hit))
                { reason = "No eligible authored support under the root or complete paw footprint."; return false; }
                height = Mathf.Max(height, hit.point.y);
            }
            return true;
        }

        void AddWaypoint(Vector3 point, Vector3 origin)
        {
            var last = path.Count == 0 ? origin : path[path.Count - 1]; var next = point - last;
            if (next.sqrMagnitude <= PositionTolerance * PositionTolerance) return;
            if (path.Count > 0)
            {
                var before = path.Count == 1 ? origin : path[path.Count - 2]; var prior = last - before;
                // Coalesce only collinear, same-direction travel. A full cast still covers
                // every point; step/rise/fall corners remain explicit waypoints.
                if (Vector3.Dot(prior, next) > 0 && Vector3.Cross(prior, next).sqrMagnitude <= 1e-12f * prior.sqrMagnitude * next.sqrMagnitude)
                { path[path.Count - 1] = point; return; }
            }
            path.Add(point);
        }

        bool ClearAt(Vector3 position, Vector3 origin, Vector3 bottom, Vector3 top, float radius, out Collider contact, out string reason)
        {
            contact = null; reason = null; var offset = position - origin;
            var physics = gameObject.scene.GetPhysicsScene();
            int count = physics.OverlapCapsule(bottom + offset, top + offset, radius, overlaps, ~0, QueryTriggerInteraction.Ignore);
            if (count == overlaps.Length) { reason = "Capsule overlap buffer saturated; movement rejected."; return false; }
            var capsule = GetComponent<CapsuleCollider>();
            for (int i = 0; i < count; i++)
            {
                var other = overlaps[i];
                if (!other || other.transform.IsChildOf(transform)) continue;
                if (Physics.ComputePenetration(capsule, position, transform.rotation, other, other.transform.position, other.transform.rotation, out _, out float depth) && depth > PositionTolerance)
                { contact = other; reason = "Capsule would penetrate " + other.name + "."; return false; }
            }
            return true;
        }

        bool ClearSegment(Vector3 from, Vector3 to, Vector3 origin, Vector3 bottom, Vector3 top, float radius, out Collider contact, out string reason)
        {
            contact = null; reason = null; var delta = to - from; float length = delta.magnitude;
            if (length <= PositionTolerance) return true;
            {
                int count = gameObject.scene.GetPhysicsScene().CapsuleCast(bottom + from - origin, top + from - origin, radius,
                    delta / length, hits, length + (Mathf.Abs(delta.y) > PositionTolerance ? PositionTolerance : Clearance), ~0, QueryTriggerInteraction.Ignore);
                if (count == hits.Length) { reason = "Capsule sweep buffer saturated; movement rejected."; return false; }
                float nearest = float.PositiveInfinity;
                for (int i = 0; i < count; i++)
                {
                    var hit = hits[i];
                    if (!hit.collider || hit.collider.transform.IsChildOf(transform)) continue;
                    // No normal-based exclusion: floors, low props, walls and overhead cover
                    // all remain solid along the entire rising/horizontal/falling capsule path.
                    if (hit.distance < nearest) { nearest = hit.distance; contact = hit.collider; }
                }
                if (contact) { reason = "Capsule path blocked by " + contact.name + "."; return false; }
            }
            return ClearAt(to, origin, bottom, top, radius, out contact, out reason);
        }

        public bool TryMove(Vector3 displacement, out Collider contact, out string reason)
        {
            // Explicit movement queries need current obstacle transforms. Stationary paw
            // reconciliation reuses the paw constraint's existing pre-query synchronization.
            Physics.SyncTransforms();
            return TryMoveSynchronized(displacement, out contact, out reason);
        }

        public bool ReconcileSynchronized(out string reason)
        {
            RootBeforeLastReconcile = RootAfterLastReconcile = transform.position;
            Array.Clear(pawSupports, 0, pawSupports.Length);
            // Death deliberately disables the hurt capsule. Keep the original Death paw
            // validation on the explicit floors, without moving the corpse or re-enabling it.
            if (actor && actor.Dead)
            {
                if (!ValidateBindings(out reason)) { LastFailure = reason; return false; }
                CacheSupportBoxes(); LastFailure = null; return true;
            }
            bool valid = TryMoveSynchronized(Vector3.zero, out _, out reason);
            RootAfterLastReconcile = transform.position;
            return valid;
        }

        bool TryMoveSynchronized(Vector3 displacement, out Collider contact, out string reason)
        {
            contact = null; reason = null;
            if (!TwoBoneArmSolver.Finite(displacement) || Mathf.Abs(displacement.y) > PositionTolerance ||
                !ValidateBindings(out reason) || !actor.TryGetSweepCapsule(out var bottom, out var top, out var radius) ||
                Vector3.Dot(transform.up, Vector3.up) < .99999f)
            { LastFailure = reason = reason ?? "Ground following requires a finite horizontal request and upright unit-scale capsule."; return false; }
            CacheSupportBoxes();
            footprint.Clear(); footprint.Add(transform.position);
            if (!paws.TryGetSupportFootprint(footprint, out reason)) { LastFailure = reason; return false; }
            var origin = transform.position;
            float step = radius * StepRadiusFraction;
            int count = Mathf.CeilToInt(displacement.magnitude / (radius * SampleRadiusFraction));
            // Path length is bounded by the production dt cap/speed. Reject malformed callers
            // rather than allocate or silently undersample an arbitrary teleport request.
            if (count > 128) { LastFailure = reason = "Ground movement request exceeds the bounded sweep path."; return false; }
            path.Clear(); var previous = origin;
            for (int i = 0; i <= count; i++)
            {
                var horizontal = count == 0 ? Vector3.zero : displacement * ((float)i / count);
                if (!RootHeight(horizontal, out float height, out reason)) { LastFailure = reason; return false; }
                if (Mathf.Abs(height - previous.y) > step + PositionTolerance)
                { LastFailure = reason = "Authored support exceeds the body-relative step/drop limit; no snap or fall."; return false; }
                var next = new Vector3(origin.x + horizontal.x, height, origin.z + horizontal.z);
                // Rise before translating; translate before falling. All segments are checked
                // before any root write, so a later blocked segment rolls back the whole move.
                if (next.y > previous.y) AddWaypoint(new Vector3(previous.x, next.y, previous.z), origin);
                else if (next.y < previous.y) AddWaypoint(new Vector3(next.x, previous.y, next.z), origin);
                AddWaypoint(next, origin); previous = next;
            }
            // A stationary support validation is not a new overlap/contact test. Existing
            // contact must not latch paw failure when there is no root movement to perform.
            if (path.Count == 0) { LastFailure = null; return true; }
            if (!ClearAt(origin, origin, bottom, top, radius, out contact, out reason)) { LastFailure = reason; return false; }
            previous = origin;
            foreach (var point in path)
            {
                if (!ClearSegment(previous, point, origin, bottom, top, radius, out contact, out reason)) { LastFailure = reason; return false; }
                previous = point;
            }
            if ((previous - origin).sqrMagnitude > 0)
            {
                transform.position = previous;
                // Keep the real capsule current for the next actor and the vehicle. This
                // additional sync is conditional on an actual successful root displacement.
                Physics.SyncTransforms();
            }
            LastFailure = null; return true;
        }
    }
}

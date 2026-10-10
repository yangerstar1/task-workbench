using UnityEngine;

namespace DesertRV
{
    public sealed class JourneyMotor : MonoBehaviour
    {
        public JourneySession journey;
        public Transform vehicle;
        public Camera view;
        public Transform doorHinge, entryStep;
        public GameObject ram, arc, roofCargo;
        public Vector3 localForward = Vector3.forward;
        public float topSpeed = 11;
        public float Speed { get; private set; }
        public float DamageCueRemaining { get; private set; }
        public Vector3 DamageSource { get; private set; }
        public int DamageAmount { get; private set; }
        public bool DamageToVehicle { get; private set; }
        // Presentation only: callers supply the health actually lost at a real contact.
        internal void ShowContactDamage(Vector3 source, int amount, bool toVehicle)
        {
            if (amount <= 0) return;
            DamageSource = source; DamageAmount = amount; DamageToVehicle = toVehicle;
            DamageCueRemaining = .8f;
        }
        internal void AdvanceDamageCue(float delta) => DamageCueRemaining = Mathf.Max(0, DamageCueRemaining - delta);
        public Vector2 DamageBearing
        {
            get
            {
                Vector3 to = DamageSource - PlayerPosition; to.y = 0;
                Vector3 forward = view.transform.forward; forward.y = 0; forward.Normalize();
                return new Vector2(Vector3.Dot(to, Vector3.Cross(Vector3.up, forward)), Vector3.Dot(to, forward)).normalized;
            }
        }
        public event System.Action<RaycastHit, float> ObstacleContact;
        public Transform Walker => walker.transform;
        public Vector3 PlayerPosition => journey.State.Control == ControlMode.Driving ? vehicle.position : walker.transform.position;
        public Vector3 EntryPosition => entryStep.GetComponent<Renderer>().bounds.center;
        public bool InsideCabin => journey.State.Control == ControlMode.OnFoot &&
            Mathf.Abs(Vector3.Dot(PlayerPosition - vehicle.position, Vector3.Cross(Vector3.up, Forward))) < 1.2f &&
            Mathf.Abs(Vector3.Dot(PlayerPosition - vehicle.position, Forward)) < 3.0f &&
            PlayerPosition.y > vehicle.position.y + .5f && PlayerPosition.y < vehicle.position.y + 1.4f;
        public Vector3 Forward => vehicle.TransformDirection(localForward).normalized;
        CharacterController walker;
        Quaternion closedDoor;
        Vector3 hingeAxis;
        float recoil;
        public void AddRecoil(float amount) => recoil = Mathf.Min(7, recoil + amount);
        float yaw, pitch, verticalSpeed, doorAngle, impactCooldown;
        bool doorOpen;
        Vector3 initialPosition;
        Quaternion initialRotation;
        readonly System.Collections.Generic.HashSet<BeastActor> rammed = new System.Collections.Generic.HashSet<BeastActor>();
        readonly RaycastHit[] carHits = new RaycastHit[32];
        readonly Collider[] rotationHits = new Collider[32];
        readonly float[] capsuleBoxTimes = new float[8];

        void Awake()
        {
            initialPosition = vehicle.position; initialRotation = vehicle.rotation;
            closedDoor = doorHinge.localRotation; hingeAxis = doorHinge.InverseTransformDirection(Vector3.up);
            walker = new GameObject("Journey walker").AddComponent<CharacterController>();
            walker.transform.SetParent(transform, true);
            walker.height = 1.62f; walker.radius = .19f; walker.center = Vector3.up * .81f;
            walker.stepOffset = .38f; walker.skinWidth = .025f; walker.enabled = false;
            view.nearClipPlane = .045f;
            if (!view.GetComponent<AudioListener>()) view.gameObject.AddComponent<AudioListener>();
        }
        public void ResetVehicle()
        {
            DamageCueRemaining = 0;
            walker.enabled = false;
            vehicle.SetPositionAndRotation(initialPosition, initialRotation);
            Speed = verticalSpeed = doorAngle = impactCooldown = 0; doorOpen = false;
            doorHinge.localRotation = closedDoor; RefreshModules(); Physics.SyncTransforms();
        }
        // Placement never changes health, ammunition, inventory, or the storm clock.
        public void PlaceForRegion(Vector3 position, Quaternion rotation)
        {
            DamageCueRemaining = 0;
            walker.enabled = false;
            vehicle.SetPositionAndRotation(position, rotation);
            walker.transform.position = position;
            Speed = verticalSpeed = doorAngle = impactCooldown = recoil = 0;
            doorOpen = false; doorHinge.localRotation = closedDoor;
            RefreshModules(); Physics.SyncTransforms();
        }
        public void RefreshModules()
        {
            var upgrades = journey.State.Upgrades;
            if (ram) ram.SetActive((upgrades & VehicleUpgrades.Ram) != 0);
            if (arc) arc.SetActive((upgrades & VehicleUpgrades.Arc) != 0);
            if (roofCargo) roofCargo.SetActive((upgrades & VehicleUpgrades.Arc) == 0);
        }
        public void Tick(float delta)
        {
            if (journey.State.Status != SessionStatus.Playing) return;
            AdvanceDamageCue(delta);
            recoil = Mathf.MoveTowards(recoil, 0, delta * 8);
            impactCooldown = Mathf.Max(0, impactCooldown - delta);
            float oldAngle = doorAngle;
            doorAngle = Mathf.MoveTowards(doorAngle, doorOpen ? -100 : 0, delta * 155);
            doorHinge.localRotation = closedDoor * Quaternion.AngleAxis(doorAngle, hingeAxis);
            if (journey.State.Control == ControlMode.Driving) Drive(delta);
            else Walk(delta);
            if (Mathf.Abs(Speed) > .01f || oldAngle != doorAngle) Physics.SyncTransforms();
        }
        void Drive(float delta)
        {
            if (journey.State.PowerConnected) { Speed = 0; return; }
            float throttle = Mathf.Clamp(journey.Input.Throttle, -1, 1);
            float target = throttle >= 0 ? throttle * topSpeed : throttle * topSpeed * .38f;
            Speed = Mathf.MoveTowards(Speed, target, delta * (Mathf.Abs(throttle) < .05f ? 7 : 4.5f));
            float steering = journey.Input.Movement.x;
            Quaternion oldRotation = vehicle.rotation;
            vehicle.Rotate(Vector3.up, steering * Speed * delta * 7, Space.World);
            if (Mathf.Abs(steering * Speed) > .01f)
            {
                int overlaps = Physics.OverlapBoxNonAlloc(vehicle.position + Vector3.up * 1.45f,
                    new Vector3(1.05f,1.12f,2.7f), rotationHits, Quaternion.LookRotation(Forward), ~0, QueryTriggerInteraction.Ignore);
                bool blocked = overlaps == rotationHits.Length;
                for (int i = 0; i < overlaps; i++)
                    if (rotationHits[i] && !rotationHits[i].transform.IsChildOf(vehicle) && rotationHits[i] != walker &&
                        rotationHits[i].bounds.max.y > vehicle.position.y + .34f) blocked = true;
                if (blocked) vehicle.rotation = oldRotation;
            }
            Vector3 displacement = Forward * Speed * delta;
            float distance = displacement.magnitude;
            if (distance > .001f)
            {
                // A swept proxy avoids tunnelling. Detailed static cabin colliders stay available
                // for walking; no dynamic Rigidbody is attached to non-convex imported meshes.
                Quaternion heading = Quaternion.LookRotation(Forward);
                Vector3 center = vehicle.position + Vector3.up * 1.45f;
                int count = Physics.BoxCastNonAlloc(center, new Vector3(1.05f, 1.12f, 2.7f),
                    displacement.normalized, carHits, heading, distance + .10f, ~0, QueryTriggerInteraction.Ignore);
                // A full buffer may contain only our own cabin colliders, or omit
                // the nearest wall. Recover the complete set before filtering.
                RaycastHit[] hits = carHits;
                if (count == carHits.Length)
                {
                    hits = Physics.BoxCastAll(center, new Vector3(1.05f, 1.12f, 2.7f),
                        displacement.normalized, heading, distance + .10f, ~0, QueryTriggerInteraction.Ignore);
                    count = hits.Length;
                }
                // Physics non-alloc casts are not ordered. A wall must stop processing
                // before a beast behind it; never damage through the nearest obstruction.
                System.Array.Sort(hits, 0, count, System.Collections.Generic.Comparer<RaycastHit>.Create((a,b) => a.distance.CompareTo(b.distance)));
                float allowed = distance;
                Vector3 impactPoint = vehicle.position;
                rammed.Clear();
                for (int i = 0; i < count; i++)
                {
                    var hit = hits[i];
                    if (hit.distance > allowed + .10f) break;
                    if (!hit.collider || hit.collider.transform.IsChildOf(vehicle) || hit.collider == walker || hit.normal.y > .65f) continue;
                    var beast = hit.collider.GetComponentInParent<BeastActor>();
                    if (beast && !beast.Dead && hit.distance == 0 &&
                        CanLeaveInitialBeastOverlap(beast, hit.collider, center, heading, Speed * delta)) continue;
                    if (beast && !beast.Dead && Speed > 3 &&
                        Vector3.Dot(hit.point - vehicle.position, Forward) > 1.8f &&
                        Vector3.Dot(-hit.normal, Forward) > .45f &&
                        (journey.State.Upgrades & VehicleUpgrades.Ram) != 0)
                    {
                        if (rammed.Add(beast)) beast.TakeHit(Mathf.CeilToInt(Mathf.Abs(Speed) * 30), displacement.normalized, true);
                        if (beast.Dead) continue;
                    }
                    ObstacleContact?.Invoke(hit, Speed);
                    if (hit.distance - .10f < allowed) impactPoint = hit.distance > 0 ? hit.point : hit.collider.bounds.center;
                    allowed = Mathf.Min(allowed, Mathf.Max(0, hit.distance - .10f));
                }
                vehicle.position += displacement.normalized * allowed;
                if (allowed + .005f < distance)
                {
                    vehicle.rotation = oldRotation;
                    if (impactCooldown <= 0 && Mathf.Abs(Speed) > 3)
                    {
                        int before = journey.State.VehicleHealth;
                        journey.State.DamageVehicle(Mathf.CeilToInt(Mathf.Abs(Speed) * 1.4f)); impactCooldown = .6f;
                        ShowContactDamage(impactPoint, before - journey.State.VehicleHealth, true);
                    }
                    Speed = 0;
                }
            }
        }
        // Initial-overlap casts return a synthetic normal opposite either travel
        // direction. Only independently proved capsule separation can bypass one.
        // The capsule axis must still be outside the box; deep embedding stays
        // blocked. No helper collider or world/actor displacement is introduced.
        bool CanLeaveInitialBeastOverlap(BeastActor beast, Collider hit, Vector3 center, Quaternion heading, float travel)
        {
            if (!beast || beast.Dead || travel == 0 || hit != beast.GetComponent<CapsuleCollider>() ||
                !beast.TryGetSweepCapsule(out var bottom, out var top, out float radius)) return false;
            var inverse = Quaternion.Inverse(heading);
            Vector3 a = inverse * (bottom - center), b = inverse * (top - center);
            if (!Finite(a) || !Finite(b) || float.IsNaN(travel) || float.IsInfinity(travel)) return false;
            Vector3 separation = CapsuleBoxVector(a, b);
            float squared = separation.sqrMagnitude;
            if (squared <= 1e-10f || squared >= radius * radius) return false;
            // Drive translates exactly along the query box's local Z axis.
            // Keep the initial supporting direction: an endpoint-only check could
            // allow a long step through a beast and out its opposite side.
            // Squared distance between these convex shapes is convex under
            // translation. This closest vector makes its initial derivative
            // nonnegative, hence distance cannot decrease anywhere in the step.
            if (Mathf.Sign(travel) * separation.z > 0) return false;
            Vector3 offset = Vector3.forward * travel;
            return CapsuleBoxVector(a - offset, b - offset).sqrMagnitude + 1e-10f >= squared;
        }
        static bool Finite(Vector3 value) =>
            !float.IsNaN(value.x) && !float.IsInfinity(value.x) &&
            !float.IsNaN(value.y) && !float.IsInfinity(value.y) &&
            !float.IsNaN(value.z) && !float.IsInfinity(value.z);

        // Exact segment-to-AABB closest vector. Each slab crossing changes which
        // coordinates contribute to squared distance; each interval is quadratic.
        Vector3 CapsuleBoxVector(Vector3 a, Vector3 b)
        {
            Vector3 extents = new Vector3(1.05f, 1.12f, 2.7f), direction = b - a;
            int count = 2; capsuleBoxTimes[0] = 0; capsuleBoxTimes[1] = 1;
            for (int axis = 0; axis < 3; axis++)
            {
                if (direction[axis] == 0) continue;
                for (int side = -1; side <= 1; side += 2)
                {
                    float t = (side * extents[axis] - a[axis]) / direction[axis];
                    if (t > 0 && t < 1) capsuleBoxTimes[count++] = t;
                }
            }
            System.Array.Sort(capsuleBoxTimes, 0, count);
            Vector3 best = Vector3.zero; float bestSquared = float.PositiveInfinity;
            for (int interval = 0; interval < count - 1; interval++)
            {
                float lo = capsuleBoxTimes[interval], hi = capsuleBoxTimes[interval + 1];
                Vector3 middle = a + direction * ((lo + hi) * .5f);
                float quadratic = 0, linear = 0;
                for (int axis = 0; axis < 3; axis++)
                {
                    float edge = middle[axis] < -extents[axis] ? -extents[axis] : extents[axis];
                    if (middle[axis] >= -extents[axis] && middle[axis] <= extents[axis]) continue;
                    quadratic += direction[axis] * direction[axis];
                    linear += direction[axis] * (a[axis] - edge);
                }
                float t = quadratic > 0 ? Mathf.Clamp(-linear / quadratic, lo, hi) : lo;
                Vector3 point = a + direction * t;
                Vector3 delta = point - Vector3.Min(Vector3.Max(point, -extents), extents);
                if (delta.sqrMagnitude < bestSquared) { best = delta; bestSquared = delta.sqrMagnitude; }
            }
            return best;
        }
        void Walk(float delta)
        {
            Vector2 look = journey.Input.Look;
            yaw += look.x; pitch = Mathf.Clamp(pitch - look.y, -70, 70);
            Vector2 movement = journey.Input.Movement;
            Vector3 velocity = Quaternion.Euler(0, yaw, 0) * new Vector3(movement.x, 0, movement.y) * 3.1f;
            // Long moves can span both RV risers before the controller settles on one.
            // At the configured 1/3-second frame cap, each move is at most 1/60 second.
            // Keep all elapsed time even for larger deltas; bound collision work to 20 moves.
            int steps = delta > 0 && !float.IsInfinity(delta)
                ? Mathf.Clamp(Mathf.CeilToInt(Mathf.Min(delta, 1f / 3) * 60), 1, 20) : 1;
            float step = delta / steps;
            for (int i = 0; i < steps; i++)
            {
                verticalSpeed = walker.isGrounded ? -1 : Mathf.Max(-24, verticalSpeed - 18 * step);
                walker.Move((velocity + Vector3.up * verticalSpeed) * step);
            }
        }
        public bool TryExitVehicle()
        {
            if (journey.State.Control != ControlMode.Driving || Mathf.Abs(Speed) > .6f || journey.State.Status != SessionStatus.Playing) return false;
            var stepRenderer = entryStep.GetComponent<Renderer>();
            Vector3 entry = stepRenderer.bounds.center;
            Vector3 right = Vector3.Cross(Vector3.up, Forward);
            Vector3 outward = right * Mathf.Sign(Vector3.Dot(entry - vehicle.position, right));
            Vector3 exit = entry + outward * .95f; exit.y = vehicle.position.y + .04f;
            // Never place the player into an obstacle when parked against a wall.
            var overlaps = Physics.OverlapCapsule(exit + Vector3.up * .25f, exit + Vector3.up * 1.38f, .20f, ~0, QueryTriggerInteraction.Ignore);
            foreach (var collider in overlaps)
                if (!collider.transform.IsChildOf(vehicle) && collider != walker) return false;
            Speed = verticalSpeed = 0; doorOpen = true;
            walker.enabled = false; walker.transform.position = exit; walker.enabled = true;
            yaw = Quaternion.LookRotation(-outward).eulerAngles.y; pitch = 0;
            journey.State.SetControl(ControlMode.OnFoot); journey.ApplyContext();
            Cursor.lockState = Application.isMobilePlatform ? CursorLockMode.None : CursorLockMode.Locked;
            Cursor.visible = Application.isMobilePlatform; return true;
        }
        public string DriverEntryBlockReason()
        {
            if (journey.State.Status != SessionStatus.Playing) return "旅程暂停，暂时无法上车。";
            if (journey.State.Control != ControlMode.OnFoot) return "已经在驾驶位。";
            if (Vector3.Distance(PlayerPosition, EntryPosition) > 2.8f) return "靠近车门后再上车。";
            if (journey.State.PowerConnected) return "先拔除电缆，再上车。";
            Vector3 eye = walker.transform.position + Vector3.up * 1.52f;
            Vector3 doorTarget = EntryPosition + Vector3.up * 1.15f;
            if (Physics.Linecast(eye, doorTarget, out var obstacle, ~0, QueryTriggerInteraction.Ignore) &&
                Vector3.Distance(obstacle.point, doorTarget) > .35f) return "门前受阻，请绕到车门。";
            return null;
        }
        public bool TryEnterDriver()
        {
            if (DriverEntryBlockReason() != null) return false;
            journey.State.SetControl(ControlMode.Driving); walker.enabled = false; Speed = 0; doorOpen = false;
            journey.ApplyContext(); Cursor.lockState = CursorLockMode.None; Cursor.visible = true; return true;
        }
        void LateUpdate()
        {
            if (!journey || !view || !walker) return;
            if (journey.State.Control == ControlMode.OnFoot)
            { view.fieldOfView = 66; view.transform.SetPositionAndRotation(walker.transform.position + Vector3.up * 1.52f, Quaternion.Euler(pitch - recoil, yaw, 0)); }
            else
            {
                view.fieldOfView = 44;
                Vector3 center = vehicle.position + Vector3.up * 1.3f + Forward * 2.2f;
                Quaternion rotation = Quaternion.Euler(74, Quaternion.LookRotation(Forward).eulerAngles.y, 0);
                view.transform.SetPositionAndRotation(center + rotation * new Vector3(0, 0, -26), rotation);
            }
        }
    }
}

using UnityEngine;

namespace DesertRV
{
    public enum BeastPhase { Idle, Stalk, Windup, Attack, Recover, Hit, Dead }
    public sealed class BeastActor : MonoBehaviour
    {
        public JourneySession journey;
        public JourneyMotor player;
        public bool armored;
        public Animator animator;
        public int Health { get; private set; }
        public BeastPhase Phase { get; private set; }
        public bool Dead => Phase == BeastPhase.Dead;
        // Exposes the real fenced recovery window; pause freezes its visible pose.
        public bool WeakPointExposed => armored && !Dead && Phase == BeastPhase.Recover &&
            combat != null && combat.WeakPointOpen && journey && journey.State != null &&
            combatRegion == journey.State.SceneId && combatGeneration == journey.Generation &&
            (journey.State.Status == SessionStatus.Playing || journey.State.Status == SessionStatus.Paused);
        public bool KilledByRam { get; private set; }
        Vector3 home, attackDirection;
        float phaseTime, lastHit, attackClock;
        bool initialized;
        BeastCombatState combat;
        int combatRegion, combatGeneration, chargeId;
        Collider hurtbox;
        readonly RaycastHit[] hits = new RaycastHit[16];

        void Awake() => EnsureInitialized();
        void EnsureInitialized()
        {
            if (initialized) return;
            initialized = true; home = transform.position; Health = armored ? 160 : 65;
            hurtbox = GetComponent<Collider>(); SetPhase(BeastPhase.Idle);
        }
        public void ResetActor()
        {
            EnsureInitialized();
            var pawContact=GetComponent<PouncerPawContactConstraint>();if(pawContact)pawContact.ResetContactState();
            transform.position = home; Health = armored ? 160 : 65;
            KilledByRam = false; combat = null; chargeId = 0; lastHit = 0; attackClock = 0;
            EnsureCombat(); if (hurtbox) hurtbox.enabled = true;
            var footContact=GetComponent<ArmoredFootContactConstraint>();if(footContact)footContact.ResetContactState();
            SetPhase(BeastPhase.Idle);
        }
        bool EnsureCombat()
        {
            if (!journey || journey.State == null || journey.State.Generation <= 0) return false;
            if (combat == null)
            {
                combatRegion = journey.State.SceneId; combatGeneration = journey.State.Generation;
                combat = new BeastCombatState(journey.State, combatRegion, combatGeneration);
            }
            return combatRegion == journey.State.SceneId && combatGeneration == journey.State.Generation;
        }
        void SetPhase(BeastPhase phase)
        {
            Phase = phase; phaseTime = 0;
            if (phase == BeastPhase.Recover && combat != null)
                combat.TryBeginRecovery(combatRegion, combatGeneration, chargeId, armored ? 2.0 : 1.3);
            if (animator) animator.CrossFade(phase == BeastPhase.Stalk ? "Walk" : phase == BeastPhase.Dead ? "Death" : phase.ToString(), .12f);
        }
        void Update()
        {
            if (!EnsureCombat() || journey.State.Status != SessionStatus.Playing || !player)
            { if (animator) animator.speed = 0; return; }
            if (animator) animator.speed = 1;
            if (Dead) return;
            float dt = Mathf.Min(Time.deltaTime, .1f); phaseTime += dt; lastHit -= dt; combat.Tick(dt);
            Vector3 target = player.PlayerPosition; Vector3 to = target - transform.position; to.y = 0;
            float distance = to.magnitude;
            if (Phase == BeastPhase.Idle)
            { if (distance < 19) SetPhase(BeastPhase.Stalk); return; }
            if (Phase == BeastPhase.Stalk)
            {
                if (distance > 34) { MoveToward(home, 2, dt); return; }
                Face(to, dt * 7);
                if (distance < (armored ? 8 : 5.2f) && ClearAttackLine(target))
                {
                    chargeId = combat.TryBeginCharge(combatRegion, combatGeneration);
                    if (chargeId != 0) { attackDirection = to.normalized; SetPhase(BeastPhase.Windup); }
                }
                else MoveToward(target, armored ? 2.1f : 2.7f, dt);
            }
            else if (Phase == BeastPhase.Windup)
            {
                // Direction locks at the start of the readable tell; dodging has meaning.
                Face(attackDirection, dt * 10);
                if (phaseTime >= (armored ? 1.1f : .78f)) { attackClock = 0; SetPhase(BeastPhase.Attack); }
            }
            else if (Phase == BeastPhase.Attack)
            {
                attackClock += dt;
                bool blocked = !MoveSwept(attackDirection * (armored ? 10 : 8) * dt, out var contact);
                bool touchedVehicle = contact && contact.transform.IsChildOf(player.vehicle);
                bool touchedPlayer = contact && contact.transform == player.Walker;
                // Damage follows an actual swept contact, never proximity through cover.
                if ((touchedVehicle || touchedPlayer) && combat.TryRegisterChargeHit(combatRegion, combatGeneration, chargeId))
                {
                    ApplyContactDamage(touchedVehicle);
                    SetPhase(BeastPhase.Recover);
                }
                else if (blocked || attackClock > (armored ? 1.2f : .8f)) SetPhase(BeastPhase.Recover);
            }
            else if (phaseTime > (Phase == BeastPhase.Hit ? .28f : armored ? 2.0f : 1.3f)) SetPhase(BeastPhase.Stalk);
        }
        void ApplyContactDamage(bool touchedVehicle)
        {
            int before = touchedVehicle ? journey.State.VehicleHealth : journey.State.PlayerHealth;
            if (touchedVehicle) journey.State.DamageVehicle(armored ? 38 : 19);
            else journey.State.DamagePlayer(armored ? 27 : 15);
            player.ShowContactDamage(transform.position,
                before - (touchedVehicle ? journey.State.VehicleHealth : journey.State.PlayerHealth), touchedVehicle);
        }
        // Read the live actor, its existing attack range/line and current binding. Never activates an enemy.
        public bool IsCloseRearThreat(JourneyMotor observer)
        {
            if (!isActiveAndEnabled || !observer || player != observer || journey != observer.journey ||
                !journey || journey.State == null || journey.State.Status != SessionStatus.Playing ||
                combat == null || combatRegion != journey.State.SceneId || combatGeneration != journey.Generation ||
                (Phase != BeastPhase.Stalk && Phase != BeastPhase.Windup && Phase != BeastPhase.Attack)) return false;
            Vector3 to = transform.position - observer.PlayerPosition; to.y = 0;
            Vector3 forward = observer.view.transform.forward; forward.y = 0;
            return to.sqrMagnitude < (armored ? 8 * 8 : 5.2f * 5.2f) &&
                Vector3.Dot(to.normalized, forward.normalized) < -.35f && ClearAttackLine(observer.PlayerPosition);
        }
        bool ClearAttackLine(Vector3 target)
        {
            Vector3 from = transform.position + Vector3.up * .6f;
            Vector3 to = target + Vector3.up * .7f - from;
            if (!Physics.Raycast(from, to.normalized, out var hit, to.magnitude, ~0, QueryTriggerInteraction.Ignore)) return true;
            return hit.collider.transform.IsChildOf(player.vehicle) || hit.collider.transform == player.Walker;
        }
        void Face(Vector3 direction, float amount)
        {
            if (direction.sqrMagnitude > .001f) transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(direction), amount);
        }
        void MoveToward(Vector3 target, float speed, float dt)
        {
            Vector3 to = target - transform.position; to.y = 0;
            if (to.magnitude < .3f) return;
            if (!MoveSwept(to.normalized * speed * dt))
            {
                Vector3 tangent = Vector3.Cross(Vector3.up, to.normalized);
                MoveSwept(tangent * speed * .6f * dt);
            }
        }
        // Candidate roots use unit world scale and a Y-axis root capsule. Reject unsupported
        // shapes instead of silently sweeping a different volume from the actual collider.
        internal bool TryGetSweepCapsule(out Vector3 bottomSphere, out Vector3 topSphere, out float radius)
        {
            bottomSphere=topSphere=Vector3.zero; radius=0;
            var capsule=GetComponent<CapsuleCollider>();
            if(!capsule || capsule.direction!=1 || !capsule.enabled || capsule.isTrigger ||
                (transform.lossyScale-Vector3.one).sqrMagnitude>1e-10f ||
                (float.IsNaN(capsule.radius) || float.IsInfinity(capsule.radius)) || (float.IsNaN(capsule.height) || float.IsInfinity(capsule.height)) ||
                (float.IsNaN(capsule.center.x) || float.IsInfinity(capsule.center.x)) || (float.IsNaN(capsule.center.y) || float.IsInfinity(capsule.center.y)) || (float.IsNaN(capsule.center.z) || float.IsInfinity(capsule.center.z)) ||
                capsule.radius<=0 || capsule.height<2*capsule.radius)return false;
            radius=capsule.radius;
            var center=transform.TransformPoint(capsule.center);
            var half=transform.TransformDirection(Vector3.up)*(capsule.height*.5f-radius);
            bottomSphere=center-half; topSphere=center+half;
            return true;
        }
        bool MoveSwept(Vector3 displacement) => MoveSwept(displacement, out _);
        bool MoveSwept(Vector3 displacement, out Collider contact)
        {
            contact = null;
            float length = displacement.magnitude;
            if (length < .0001f) return true;
            if(!TryGetSweepCapsule(out var bottomSphere,out var topSphere,out var radius))
            { Debug.LogError("Beast sweep requires an enabled non-trigger Y capsule on a unit-scale root.",this); return false; }
            int count = Physics.CapsuleCastNonAlloc(bottomSphere,
                topSphere, radius, displacement / length,
                hits, length + .04f, ~0, QueryTriggerInteraction.Ignore);
            float nearest = float.PositiveInfinity;
            for (int i = 0; i < count; i++)
                if (hits[i].collider && !hits[i].collider.transform.IsChildOf(transform) && hits[i].normal.y < .65f && hits[i].distance < nearest)
                { contact = hits[i].collider; nearest = hits[i].distance; }
            if (contact) return false;
            transform.position += displacement;
            return true;
        }
        public int TakeHit(int damage, Vector3 direction, bool ramHit = false)
        {
            EnsureInitialized();
            if (!EnsureCombat() || Dead || journey.State.Status != SessionStatus.Playing || damage <= 0) return 0;
            int applied = damage;
            if (armored && !ramHit && !combat.WeakPointOpen) applied = Mathf.Max(1, damage / 5);
            Health = Mathf.Max(0, Health - applied);
            if (Health == 0)
            { KilledByRam = ramHit; if (hurtbox) hurtbox.enabled = false; SetPhase(BeastPhase.Dead); }
            else if (!armored && Phase == BeastPhase.Stalk && lastHit <= 0)
            { SetPhase(BeastPhase.Hit); lastHit = 1; }
            return applied;
        }
    }
}

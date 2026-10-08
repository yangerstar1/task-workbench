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
        public bool KilledByRam { get; private set; }
        Vector3 home, attackDirection;
        float phaseTime, lastHit, attackClock;
        bool dealtDamage, initialized;
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
            transform.position = home; Health = armored ? 160 : 65;
            KilledByRam = false; if (hurtbox) hurtbox.enabled = true;
            SetPhase(BeastPhase.Idle);
        }
        void SetPhase(BeastPhase phase)
        {
            Phase = phase; phaseTime = 0;
            if (animator) animator.CrossFade(phase == BeastPhase.Stalk ? "Walk" : phase == BeastPhase.Dead ? "Death" : phase.ToString(), .12f);
        }
        void Update()
        {
            if (!journey || journey.State.Status != SessionStatus.Playing)
            { if (animator) animator.speed = 0; return; }
            if (animator) animator.speed = 1;
            if (Dead) return;
            float dt = Mathf.Min(Time.deltaTime, .1f); phaseTime += dt; lastHit -= dt;
            Vector3 target = player.PlayerPosition; Vector3 to = target - transform.position; to.y = 0;
            float distance = to.magnitude;
            if (Phase == BeastPhase.Idle)
            { if (distance < 19) SetPhase(BeastPhase.Stalk); return; }
            if (Phase == BeastPhase.Stalk)
            {
                if (distance > 34) { MoveToward(home, 2, dt); return; }
                Face(to, dt * 7);
                if (distance < (armored ? 8 : 5.2f) && ClearAttackLine(target))
                { attackDirection = to.normalized; dealtDamage = false; SetPhase(BeastPhase.Windup); }
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
                if (!dealtDamage && (touchedVehicle || touchedPlayer))
                {
                    if (touchedVehicle) journey.State.DamageVehicle(armored ? 38 : 19);
                    else journey.State.DamagePlayer(armored ? 27 : 15);
                    dealtDamage = true; SetPhase(BeastPhase.Recover);
                }
                else if (blocked || attackClock > (armored ? 1.2f : .8f)) SetPhase(BeastPhase.Recover);
            }
            else if (phaseTime > (Phase == BeastPhase.Hit ? .28f : armored ? 2.0f : 1.3f)) SetPhase(BeastPhase.Stalk);
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
        bool MoveSwept(Vector3 displacement) => MoveSwept(displacement, out _);
        bool MoveSwept(Vector3 displacement, out Collider contact)
        {
            contact = null;
            float length = displacement.magnitude;
            if (length < .0001f) return true;
            int count = Physics.CapsuleCastNonAlloc(transform.position + Vector3.up * .45f,
                transform.position + Vector3.up * 1.0f, armored ? .5f : .36f, displacement / length,
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
            if (Dead || journey.State.Status != SessionStatus.Playing) return 0;
            int applied = damage;
            if (armored && !ramHit && Phase != BeastPhase.Recover) applied = Mathf.Max(1, damage / 5);
            Health = Mathf.Max(0, Health - applied);
            if (Health == 0)
            { KilledByRam = ramHit; if (hurtbox) hurtbox.enabled = false; SetPhase(BeastPhase.Dead); }
            else if (!armored && Phase == BeastPhase.Stalk && lastHit <= 0)
            { SetPhase(BeastPhase.Hit); lastHit = 1; }
            return applied;
        }
    }
}

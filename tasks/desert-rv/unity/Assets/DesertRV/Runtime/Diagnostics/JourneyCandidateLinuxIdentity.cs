#if UNITY_EDITOR || (DESERTRV_CANDIDATE_LINUX && UNITY_STANDALONE_LINUX && DEVELOPMENT_BUILD)
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DesertRV
{
    // Serialized only into build-time scene copies. Never added to a saved source scene.
    [DefaultExecutionOrder(-10000), DisallowMultipleComponent]
    public sealed class JourneyCandidateLinuxIdentity : MonoBehaviour
    {
        public const string Define = "DESERTRV_CANDIDATE_LINUX";
        public const string Bootstrap = "Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity";
        public static readonly string[] Regions = { "Assets/DesertRV/Scenes/Journey/FirstStation.unity", "Assets/DesertRV/Scenes/Journey/Scrapyard.unity", "Assets/DesertRV/Scenes/Journey/NightBeacon.unity" };
        public string sourceCommit, producerRunUrl, generatedReceiptSha256;
        public JourneyContentManifest content;
        public JourneyDirector director;
        public RegionBinding region;
        static JourneyCandidateLinuxIdentity owner;
        bool bornInBootstrap;
        public static bool Active
        {
            get
            {
#if DESERTRV_CANDIDATE_LINUX && UNITY_STANDALONE_LINUX && DEVELOPMENT_BUILD && !UNITY_EDITOR
                return Application.platform == RuntimePlatform.LinuxPlayer && Debug.isDebugBuild && owner;
#else
                return false;
#endif
            }
        }
        void Awake()
        {
#if DESERTRV_CANDIDATE_LINUX && UNITY_STANDALONE_LINUX && DEVELOPMENT_BUILD && !UNITY_EDITOR
            // Capture before the existing Director moves its root to DontDestroyOnLoad.
            bornInBootstrap = gameObject.scene.path == Bootstrap;
#endif
        }
        void Start()
        {
#if DESERTRV_CANDIDATE_LINUX && UNITY_STANDALONE_LINUX && DEVELOPMENT_BUILD && !UNITY_EDITOR
            if (!director || owner || !bornInBootstrap || !director.OwnsJourney || !ValidIdentity() ||
                !ValidateBootstrap(director, content, out _)) return;
            owner = this;
#endif
        }
        void OnDestroy() { if (owner == this) owner = null; }
        public bool ValidIdentity() => Regex.IsMatch(sourceCommit ?? "", "^[a-f0-9]{40}$") &&
            Regex.IsMatch(generatedReceiptSha256 ?? "", "^[a-f0-9]{64}$") &&
            Regex.IsMatch(producerRunUrl ?? "", "^https://github\\.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*$");
        public static bool UnapprovedContent(JourneyContentManifest m) => m && m.pouncer != null && m.armored != null && m.weapon != null &&
            m.pouncer.prefab && m.armored.prefab && m.weapon.prefab && m.pouncer.prefab != m.armored.prefab && m.weapon.prefab != m.pouncer.prefab && m.weapon.prefab != m.armored.prefab &&
            !m.pouncer.accepted && !m.armored.accepted && !m.weapon.accepted &&
            string.IsNullOrEmpty(m.pouncer.visualEvidence) && string.IsNullOrEmpty(m.pouncer.motionEvidence) &&
            string.IsNullOrEmpty(m.armored.visualEvidence) && string.IsNullOrEmpty(m.armored.motionEvidence) &&
            string.IsNullOrEmpty(m.weapon.visualEvidence) && string.IsNullOrEmpty(m.weapon.motionEvidence) &&
            string.IsNullOrEmpty(m.bootstrapEvidence) && string.IsNullOrEmpty(m.combatIntegrationEvidence) &&
            m.environmentEvidence != null && m.environmentEvidence.Length == 3 && m.environmentEvidence.All(string.IsNullOrEmpty);
        static HashSet<Mesh> Meshes(GameObject root) => new HashSet<Mesh>(root.GetComponentsInChildren<Renderer>(true)
            .Where(r => r is MeshRenderer || r is SkinnedMeshRenderer).Select(BeastWeakPointPresentation.MeshOf));
        static bool RealGeometry(GameObject instance, GameObject prefab)
        {
            if (!instance || !prefab) return false;
            var expected = Meshes(prefab); var actual = Meshes(instance);
            return expected.Count > 0 && expected.All(m => m && m.vertexCount >= 3) && expected.SetEquals(actual) &&
                instance.GetComponentsInChildren<Renderer>(true).All(r => r.sharedMaterials.Length > 0 && r.sharedMaterials.All(m => m && m.shader));
        }
        public static bool ValidateBootstrap(JourneyDirector d, JourneyContentManifest m, out string reason)
        {
            reason = "Candidate Linux bootstrap identity or real content is invalid.";
            if (!UnapprovedContent(m) || !d || d.transform.parent || !d.journey || !d.motor || !d.actions || !d.loader || !d.hud ||
                !d.motor.vehicle || !d.motor.view || !d.motor.arc || !d.motor.ram || !d.hud.font ||
                d.actions.journey != d.journey || d.actions.motor != d.motor || d.motor.journey != d.journey || d.hud.director != d ||
                !d.actions.cabinWorkbench || !d.actions.workbenchSurface || !d.actions.cabinWorkbench.IsChildOf(d.motor.vehicle) ||
                !d.actions.workbenchSurface.transform.IsChildOf(d.motor.vehicle)) return false;
            foreach (var c in new Component[] { d.journey, d.motor, d.actions, d.loader, d.hud, d.motor.vehicle, d.motor.view })
                if (!c.transform.IsChildOf(d.transform)) return false;
            if (d.loader.regionScenes == null || !d.loader.regionScenes.SequenceEqual(new[] { "FirstStation", "Scrapyard", "NightBeacon" })) return false;
            var weapons = d.GetComponentsInChildren<WeaponPresentation>(true); var arcs = d.GetComponentsInChildren<ArcPresentation>(true);
            if (weapons.Length != 1 || arcs.Length != 1 || !weapons[0].enabled || !arcs[0].enabled ||
                weapons[0].actions != d.actions || arcs[0].actions != d.actions ||
                !weapons[0].ValidateBindings(out reason) || !arcs[0].ValidateBindings(out reason) ||
                !weapons[0].animator || !RealGeometry(weapons[0].animator.gameObject, m.weapon.prefab)) return false;
            var original = m.weapon.prefab.GetComponentInChildren<Animator>(true);
            if (!original || original.runtimeAnimatorController != weapons[0].animator.runtimeAnimatorController) return false;
            reason = null; return true;
        }
        public static bool ValidateRegionContent(RegionBinding b, JourneyContentManifest m, out string reason)
        {
            reason = "Candidate Linux region identity or real content is invalid.";
            if (!b || !UnapprovedContent(m) || b.combatAssetsVerified || b.environmentVerified || !b.ValidateStructure(out reason)) return false;
            var roots = b.gameObject.scene.GetRootGameObjects();
            if (roots.SelectMany(r => r.GetComponentsInChildren<RegionBinding>(true)).Count() != 1 ||
                roots.Any(r => r.GetComponentInChildren<JourneyDirector>(true) || r.GetComponentInChildren<JourneySession>(true) ||
                    r.GetComponentInChildren<JourneyMotor>(true) || r.GetComponentInChildren<JourneyHud>(true) ||
                    r.GetComponentInChildren<Camera>(true) || r.GetComponentInChildren<AudioListener>(true))) return false;
            var enemies = b.AllEnemies().ToArray();
            var actual = b.gameObject.scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<BeastActor>(true)).ToArray();
            if (enemies.Length == 0 || enemies.Distinct().Count() != enemies.Length || !new HashSet<BeastActor>(actual).SetEquals(enemies)) return false;
            foreach (var enemy in enemies)
            {
                var prefab = enemy.armored ? m.armored.prefab : m.pouncer.prefab;
                var expected = prefab.GetComponent<BeastActor>(); var collider = enemy.GetComponent<Collider>();
                if (!expected || expected.armored != enemy.armored || !collider || !collider.enabled || collider.isTrigger ||
                    !enemy.animator || !expected.animator || !enemy.animator.runtimeAnimatorController ||
                    enemy.animator.runtimeAnimatorController != expected.animator.runtimeAnimatorController || !RealGeometry(enemy.gameObject, prefab)) return false;
                if (enemy.armored)
                {
                    var weak = enemy.GetComponentsInChildren<BeastWeakPointPresentation>(true);
                    if (weak.Length != 1 || !weak[0].enabled || !weak[0].ValidateBindings(out reason)) return false;
                }
            }
            reason = null; return true;
        }
        public static bool ValidateForLoad(RegionBinding b, out string reason)
        {
            reason = "Explicit prepared Linux Development identity is absent or stale.";
            if (!Active || !owner || !owner.director || !owner.director.OwnsJourney || !owner.ValidIdentity() ||
                !ValidateBootstrap(owner.director, owner.content, out reason) || !b || b.region < 1 || b.region > 3 || b.gameObject.scene.path != Regions[b.region - 1]) return false;
            var stamps = b.gameObject.scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<JourneyCandidateLinuxIdentity>(true)).ToArray();
            if (stamps.Length != 1 || stamps[0].region != b || stamps[0].director || stamps[0].content != owner.content ||
                stamps[0].sourceCommit != owner.sourceCommit || stamps[0].producerRunUrl != owner.producerRunUrl ||
                stamps[0].generatedReceiptSha256 != owner.generatedReceiptSha256 || !stamps[0].ValidIdentity()) return false;
            return ValidateRegionContent(b, owner.content, out reason);
        }
    }
}
#endif

using System;
using UnityEngine;

namespace DesertRV
{
    // Evidence is entered only after a real visual/action review. Authoring never grants approval.
    [Serializable] public sealed class JourneyAssetReview
    {
        public GameObject prefab;
        public string dependencyHash;
        public UnityEngine.Object sourceModel;
        public string reviewedDependencySha256, generationRunUrl;
        public string visualEvidence, motionEvidence;
        public bool accepted;
    }

    [CreateAssetMenu(menuName = "Desert RV/Journey Content Manifest")]
    public sealed class JourneyContentManifest : ScriptableObject
    {
        public JourneyAssetReview pouncer = new JourneyAssetReview();
        public JourneyAssetReview armored = new JourneyAssetReview();
        public JourneyAssetReview weapon = new JourneyAssetReview();
        public string[] environmentDependencyHashes = new string[3];
        public string[] environmentEvidence = new string[3];
        public string bootstrapDependencyHash, bootstrapEvidence;
        // Must reference implemented prefab components, not empty approval flags.
        public MonoBehaviour weaponPresentation;
        public MonoBehaviour arcPresentation;
        public MonoBehaviour armoredWeakpointPresentation;
        public string combatIntegrationEvidence;
    }
}

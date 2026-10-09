"""Exact current CandidateArt assembly inventory, shared by all result gates.

Historical XML remains immutable and cannot satisfy this current 26-case gate.
This list is a contract, never evidence that the tests actually ran.
"""
from foot_contact_output import NATIVE_NAMES as ARMORED_NATIVE_NAMES
from paw_contact_output import NATIVE_NAMES as POUNCER_NATIVE_NAMES
BASE_NATIVE_NAMES=frozenset(('DesertRV.Tests.CandidateArtImportTests.ExecutePinnedDiscoveryOrBindingDiagnostics', 'DesertRV.Tests.CandidateAnimationPolicyTests.OnlyArmoredAttackGetsTheSourceLoopException', 'DesertRV.Tests.CandidateAnimationPolicyTests.EqualKeyValuesDoNotExcuseUnsafeTangents', 'DesertRV.Tests.CandidateAnimationPolicyTests.MissingNativeAnimatorGetsCreatedAndReused', 'DesertRV.Tests.CandidateAnimationPolicyTests.OpenCoreEmissionSurvivesRealSaveReimportAndReload', 'DesertRV.Tests.CandidateAnimationPolicyTests.RenderTargetCleanupDetachesCameraBeforeDestroy', 'DesertRV.Tests.CandidateMaterialIdentityTests.PersistedWeaponMaterialIdentitySurvivesNeutralSamplingAndRejectsImpostors', 'DesertRV.Tests.CandidateMeshMeasurementTests.ScaledTranslatedRotatedHierarchyMatchesIndependentSkinning', 'DesertRV.Tests.CandidateMeshMeasurementTests.RejectsBlendShapesAndTruncatedSkinQuality', 'DesertRV.Tests.CandidateMeshMeasurementTests.StaticMeshesAndFourMillimetreGateUseWorldVertices'))
NATIVE_NAMES=BASE_NATIVE_NAMES|ARMORED_NATIVE_NAMES|POUNCER_NATIVE_NAMES
NATIVE_COUNT=len(NATIVE_NAMES)
assert len(BASE_NATIVE_NAMES)==10 and len(ARMORED_NATIVE_NAMES)==7 and len(POUNCER_NATIVE_NAMES)==9 and NATIVE_COUNT==26

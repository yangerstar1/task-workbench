"""Host-only merge guards; no claim of C# semantic compilation or native execution."""
import hashlib
from pathlib import Path
import re
import tempfile
import unittest
import candidate_native_cases as inventory
import failed_capture_output as failed
import paw_contact_output as paw
import foot_contact_output as foot
import pouncer_output as pouncer
import strict_output as strict
import weapon_output as weapon

ROOT=Path(__file__).parents[2]
UNITY=ROOT/'unity/Assets/DesertRV'
CAPTURE=(UNITY/'Editor/JourneyCandidateArtCapture.cs').read_text()

class DualContactIntegrationTests(unittest.TestCase):
 def test_exact_native_inventory_is_shared_by_every_result_gate(self):
  self.assertEqual(inventory.NATIVE_COUNT,26)
  self.assertEqual(len(inventory.BASE_NATIVE_NAMES),10)
  self.assertEqual(len(foot.NATIVE_NAMES),7);self.assertEqual(len(paw.NATIVE_NAMES),9)
  self.assertEqual(strict.CURRENT_NATIVE_NAMES,inventory.NATIVE_NAMES)
  self.assertEqual(pouncer.NATIVE_NAMES,inventory.NATIVE_NAMES)
  self.assertEqual(failed.NATIVE_NAMES,inventory.NATIVE_NAMES)
  self.assertEqual(weapon.NATIVE_CASES,26)
 def test_native_inventory_matches_actual_candidate_art_test_sources(self):
  names=set()
  for file in (UNITY/'Tests/CandidateArt').glob('*.cs'):
   source=file.read_text();classes=re.findall(r'public (?:sealed )?class (\w+)',source)
   methods=re.findall(r'\[Test\]\s+public void (\w+)\(',source)
   if methods:
    self.assertEqual(len(classes),1,file.name)
    names.update('DesertRV.Tests.'+classes[0]+'.'+method for method in methods)
  self.assertEqual(names,inventory.NATIVE_NAMES)
 def test_both_runtime_components_bound_and_applied_exactly_once(self):
  for name,method in [('ArmoredFootContactConstraint','ApplyFootContact'),('PouncerPawContactConstraint','ApplyPawContact')]:
   self.assertEqual(CAPTURE.count('subject.GetComponent<'+name+'>()'),1)
   self.assertEqual(CAPTURE.count('.'+method+'(out var '),1)
  self.assertEqual(CAPTURE.count('new GameObject(groundName)'),1)
  self.assertEqual(CAPTURE.count('MoveGameObjectToScene(groundObject,scene)'),1)
 def test_contact_locals_never_leak_into_unrelated_capture_methods(self):
  tail=CAPTURE[CAPTURE.index('        static void ReleaseCandidateRenderTarget'):]
  for local in ('pawContact','footContact','pawEvidence','footEvidence','contract.kind','groundName','groundLayer'):
   self.assertNotIn(local,tail)
 def test_original_probe_and_measurement_helpers_are_byte_unchanged(self):
  tail=CAPTURE[CAPTURE.index('        static void LogSkinProbe(string phase,GameObject subject,Renderer[] renderers)'):]
  self.assertEqual(hashlib.sha256(tail.encode()).hexdigest(),'57d74f024b1e715ddfdf99330fa90bff939fb7c72a448b738f49abec2e218682')
  measurement=(UNITY/'Editor/JourneyCandidateMeshMeasurement.cs').read_bytes()
  self.assertEqual(hashlib.sha256(measurement).hexdigest(),'7df82cae4ae36af8163cd16013a23fdc2a17717d8174b8b69a0003bcf3ee60d6')
 def test_original_full_mesh_gate_and_animator_schedule_are_preserved(self):
  gate='if(frame.groundDiagnosticApplicable && frame.worldMinY<frame.groundReferenceY-.004f)\n                        throw new InvalidOperationException("Ground penetration exceeds 0.004m:'
  self.assertEqual(CAPTURE.count(gate),1)
  calls=re.findall(r'animator\.(?:Rebind|Update|Play|CrossFade)\([^;\n]*',CAPTURE)
  self.assertEqual(hashlib.sha256('\n'.join(calls).encode()).hexdigest(),'112471693f59f8e25f7bc80b06234e9a434915385f79e4bdf196e24a7c3d0c78')
 def test_reports_remain_kind_specific(self):
  self.assertIn('if(contract.kind=="armored")File.WriteAllText("JourneyEvidence/CandidateArt/foot-contact-report.json"',CAPTURE)
  self.assertIn('if(contract.kind=="pouncer")File.WriteAllText("JourneyEvidence/CandidateArt/paw-contact-report.json"',CAPTURE)
  self.assertIn('public ArmoredFootContactConstraint.Report solve;',CAPTURE)
  self.assertIn('public PouncerPawContactConstraint.Report solve;',CAPTURE)
 def test_actor_reset_clears_both_real_components(self):
  source=(UNITY/'Runtime/BeastActor.cs').read_text();reset=source[source.index('public void ResetActor()'):source.index('bool EnsureCombat()')]
  self.assertEqual(reset.count('GetComponent<ArmoredFootContactConstraint>()'),1)
  self.assertEqual(reset.count('GetComponent<PouncerPawContactConstraint>()'),1)
  self.assertEqual(reset.count('.ResetContactState()'),2)
 def test_historical_native_subset_cannot_pass_current_acceptance(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);p=root/'artifacts/candidate-art/result.xml';p.parent.mkdir(parents=True)
   for names in (inventory.BASE_NATIVE_NAMES,inventory.BASE_NATIVE_NAMES|foot.NATIVE_NAMES,inventory.BASE_NATIVE_NAMES|paw.NATIVE_NAMES):
    p.write_text('<test-run result="Passed">'+''.join('<test-case fullname="'+n+'" result="Passed"/>' for n in names)+'</test-run>')
    with self.assertRaisesRegex(strict.StrictError,'STRICT_NATIVE_FAILED'):strict.native_report(root)
 def test_exact_current_synthetic_xml_is_admitted_without_claiming_native_execution(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);p=root/'artifacts/candidate-art/result.xml';p.parent.mkdir(parents=True)
   p.write_text('<test-run result="Passed">'+''.join('<test-case fullname="'+n+'" result="Passed"/>' for n in inventory.NATIVE_NAMES)+'</test-run>')
   self.assertEqual(strict.native_report(root),hashlib.sha256(p.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main()

#!/usr/bin/env python3
"""Synthetic observations only: no license files, credentials, Unity or authentication calls."""
import json,pathlib,tempfile,unittest
import license_observation as obs
import startup_diagnostic as diag
class LicenseObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.logs=self.root/'logs';self.logs.mkdir();self.project=self.root/'project'
        (self.project/'Assets/DesertRV').mkdir(parents=True)
    def tearDown(self):self.tmp.cleanup()
    def parse(self,text,stdout=None):
        (self.logs/'editor.log').write_text(text)
        if stdout is not None:(self.logs/'rendered.log').write_text(stdout)
        return diag.classify(self.logs,self.project,143,1,'SIGTERM_ON_CAPTURE_FAILURE')
    def test_signature_error_then_connection_is_not_latched_final_failure(self):
        r=self.parse('[Licensing::Client] Error: Code 10 while verifying Licensing Client signature PRIVATE_PATH\n[Licensing::Module] Successfully connected to LicensingClient on channel PRIVATE_USER\n')
        self.assertEqual(r['licenseStatus'],'ERROR_THEN_SUCCESS_REPORTED');s=r['licenseObservations']['editor'];self.assertEqual(s['sequenceState'],'ERROR_THEN_SUCCESS');self.assertEqual([e['kind'] for e in s['events']],['SIGNATURE_ERROR','IPC_CONNECTED']);self.assertNotIn('PRIVATE',json.dumps(r))
    def test_literal_error_code_200_with_updated_status_is_success_event(self):
        r=self.parse('[LicensingClient] Error: Code 200 while updating license in client (status: Licenses updated.)\n');item=r['licenseObservations']['editor']['events'][0];self.assertEqual(item,dict(kind='LICENSE_UPDATED',codeNamespace='EDITOR_MESSAGE',code=200));self.assertEqual(r['licenseStatus'],'SUCCESS_EVENT_REPORTED')
    def test_success_then_real_entitlement_failure_is_retained(self):
        r=self.parse('[Licensing::Client] Successfully resolved entitlements\n[Licensing::Module] Error: License is not active (PRIVATE_ENTITLEMENT)\n');self.assertEqual(r['licenseStatus'],'LATER_ERROR_AFTER_SUCCESS');self.assertEqual(r['licenseObservations']['editor']['lastObservedEvent'],'LICENSE_NOT_ACTIVE')
    def test_token_success_never_emits_token_value(self):
        r=self.parse('[Licensing::Module] Error: Access token is unavailable; failed to update licenses\n[Licensing::Client] Successfully updated the access token PRIVATE_TOKEN_CANARY\n');self.assertEqual(r['licenseObservations']['editor']['sequenceState'],'ERROR_THEN_SUCCESS');self.assertNotIn('PRIVATE_TOKEN_CANARY',json.dumps(r))
    def test_missing_ulf_retains_only_category(self):
        r=self.parse('[Licensing::Client] Error: Could not find /home/PRIVATE/Unity_lic.ulf\n');self.assertEqual(r['licenseObservations']['editor']['lastObservedEvent'],'ULF_MISSING');self.assertNotIn('/home',json.dumps(r))
    def test_request_timeout_code1500_has_message_namespace(self):
        r=self.parse('[Licensing::Client] Error: Code 1500 while processing request (TimeoutPolicy did not complete within the timeout.)\n');self.assertEqual(r['licenseObservations']['editor']['events'][0],dict(kind='REQUEST_TIMEOUT',codeNamespace='EDITOR_MESSAGE',code=1500))
    def test_message_code10_not_interpreted_as_client_exit10(self):
        a=obs.event('[Licensing::Client] Error: Code 10 while verifying Licensing Client signature');b=obs.event('[Licensing::Module] Licensing Client exited with code 10');self.assertEqual(a['codeNamespace'],'EDITOR_MESSAGE');self.assertEqual(b['codeNamespace'],'CLIENT_EXIT');self.assertNotEqual(a['kind'],b['kind'])
    def test_unknown_numeric_code_redacted_to_other(self):
        r=self.parse('[Licensing::Client] Error: Code 987654 private cause\n');self.assertEqual(r['licenseObservations']['editor']['events'][0]['code'],'OTHER');self.assertNotIn('987654',json.dumps(r))
    def test_explicit_wait_is_distinct_from_error_or_inferred_thread_state(self):
        r=self.parse('[Licensing::Module] Waiting for IPC handshake PRIVATE_CHANNEL\n');s=r['licenseObservations']['editor'];self.assertEqual(s['lastExplicitWait'],'WAIT_IPC');self.assertEqual(s['sequenceState'],'PROGRESS_ONLY');self.assertEqual(r['terminationRequest'],'SIGTERM_ON_CAPTURE_FAILURE')
    def test_wait_then_success_does_not_remain_last_wait(self):
        r=self.parse('[Licensing::Module] Waiting for license update\n[Licensing::Client] Successfully updated the license\n');self.assertEqual(r['licenseObservations']['editor']['lastExplicitWait'],'NONE')
    def test_streams_are_never_falsely_merged_into_chronological_recovery(self):
        r=self.parse('[Licensing::Client] Error: Code 10 while verifying Licensing Client signature\n','[Licensing::Module] Successfully connected to LicensingClient\n');self.assertEqual(r['licenseStatus'],'MULTIPLE_STREAM_HISTORIES');self.assertEqual(r['licenseObservations']['editor']['sequenceState'],'ERROR_ONLY');self.assertEqual(r['licenseObservations']['stdout']['sequenceState'],'SUCCESS_ONLY')
    def test_tail_bound_is_explicit_not_silent(self):
        text=''.join('[Licensing::Client] Error: Code 10 while verifying Licensing Client signature\n[Licensing::Module] Successfully connected to LicensingClient\n' for _ in range(10));r=self.parse(text);s=r['licenseObservations']['editor'];self.assertTrue(s['truncated']);self.assertEqual(len(s['events']),obs.MAX_EVENTS)
    def test_same_repeated_fact_collapses_without_secret_or_pid_values(self):
        text=''.join('[Licensing::Module] Successfully connected to LicensingClient on channel PRIVATE_'+str(i)+'\n' for i in range(30));r=self.parse(text);self.assertEqual(len(r['licenseObservations']['editor']['events']),1);self.assertNotIn('PRIVATE',json.dumps(r))
    def test_malicious_original_line_or_unknown_kind_rejected(self):
        for item in (dict(kind='PRIVATE',codeNamespace='NONE',code=None),dict(kind='CLIENT_ERROR',codeNamespace='EDITOR_MESSAGE',code=123456),dict(kind='CLIENT_ERROR',codeNamespace='NONE',code=None,raw='PRIVATE')):
            value=obs.empty();value['editor']=obs.summarize([item]) if item['kind'] in obs.KINDS else dict(events=[item],truncated=False,sequenceState='ERROR_ONLY',lastObservedEvent='PRIVATE',lastExplicitWait='NONE')
            with self.assertRaises(Exception):obs.validate_streams(value)
    def test_tampered_derived_sequence_summary_rejected(self):
        value=obs.empty();value['editor']=obs.add(value['editor'],obs.event('[Licensing::Client] Error: Code 10 while verifying Licensing Client signature'));value['editor']['sequenceState']='SUCCESS_ONLY'
        with self.assertRaises(Exception):obs.validate_streams(value)
    def test_activation_and_return_are_still_never_scanned(self):
        (self.logs/'activation.log').write_text('[Licensing::Client] Error: Code 10 while verifying Licensing Client signature PRIVATE\n');(self.logs/'return.log').write_text('PRIVATE');r=diag.classify(self.logs,self.project);self.assertEqual(r['licenseObservations'],obs.empty())
if __name__=='__main__':unittest.main()

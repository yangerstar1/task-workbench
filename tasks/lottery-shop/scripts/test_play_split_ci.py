#!/usr/bin/env python3
"""Synthetic partition/receipt boundaries only. No Docker/Unity is invoked."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import play_split_ci as split
import safe_project_ci as safe

IDENT=dict(scope=split.visual.SCOPE,sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='12345',runAttempt='1')
ROOT=Path(__file__).resolve().parents[3]



def sync_suite_counts(tree):
    # Synthetic fixture writer only. Never used by a production validator or
    # on exported native XML; negative tests mutate after this construction.
    for suite in tree.iter('test-suite'):
        children=list(suite.iter('test-case'));passed=sum(c.get('result')=='Passed' for c in children)
        counts=dict(total=len(children),passed=passed,failed=len(children)-passed,skipped=0,inconclusive=0)
        for key,value in counts.items():suite.set(key,str(value))
        suite.set('result','Failed' if counts['failed'] else 'Passed')


def seed(root, ident=IDENT):
    split.visual.write(split.visual.outdir(root)/'source-receipt.json',ident)
    for name in ('g2-test-contract.json','g3-test-contract.json'):
        target=root/split.visual.TASK/'ci'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/split.visual.TASK/'ci'/name,target)
    trees={}
    for shard in split.SHARDS:
        record=safe.process_receipt(ident,split.PHASES[shard])
        record.update(nativeStartedAtNs=time.time_ns(),nativeExitCode=0,dockerExitCode=0,nativeExitMarkerCount=1,status='NATIVE_SUCCEEDED')
        split.visual.write(safe.file(root,split.PHASES[shard]),record)
        count=len(split.names(shard));tree=ET.Element('test-run',result='Passed',total=str(count),passed=str(count),failed='0',skipped='0',inconclusive='0')
        for assembly,names in split.expected(shard).items():
            suite=ET.SubElement(tree,'test-suite',type='Assembly',name=assembly,result='Passed')
            fixture_name=names[0].rsplit('.',1)[0]
            fixture=ET.SubElement(suite,'test-suite',type='TestFixture',name=fixture_name.rsplit('.',1)[1],fullname=fixture_name,classname=fixture_name,result='Passed')
            for name in names:ET.SubElement(fixture,'test-case',fullname=name,classname=fixture_name,methodname=name.rsplit('.',1)[1],name=name.rsplit('.',1)[1],result='Passed')
        source,target=split.paths(root,shard);source.mkdir(parents=True,exist_ok=True)
        sync_suite_counts(tree)
        (source/'playmode-results.xml').write_bytes(ET.tostring(tree));trees[shard]=tree
    return trees


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,GITHUB_SHA=IDENT['sourceCommit'],GITHUB_RUN_ID=IDENT['runId'],GITHUB_RUN_ATTEMPT='1');self.env.start();self.addCleanup(self.env.stop)
        self.trees=seed(self.root)
    def save(self,shard): (split.paths(self.root,shard)[0]/'playmode-results.xml').write_bytes(ET.tostring(self.trees[shard]))
    def reject(self):
        with self.assertRaises(ValueError):split.aggregate(self.root)
        self.assertFalse(split.visual.read_json(split.visual.outdir(self.root)/'regression-play-summary.json')['allExpectedPassed'])
    def test_fixed_disjoint_union_and_exact_regex_filters(self):
        split.contract(self.root)
        self.assertEqual(len(split.names('core')),34);self.assertEqual(len(split.names('world')),3)
        all_names=split.names('core')+split.names('world')
        for shard in split.SHARDS:
            filters=split.selection(shard).split(';')
            selected=[name for name in all_names if any(re.search(f,name) for f in filters)]
            self.assertEqual(set(selected),set(split.names(shard)))
            for name in split.names(shard):
                self.assertFalse(any(re.search(f,'prefix'+name) or re.search(f,name+'Suffix') for f in filters))
        self.assertNotIn('regression-play',safe.PHASES)
    def test_contract_mutation_cannot_silently_change_selection(self):
        p=self.root/split.visual.TASK/'ci/g3-test-contract.json';v=json.loads(p.read_text());v['profiles']['play']['Lottery.G3.PlayMode.Tests.dll'][-1]+='Mutant';split.visual.write(p,v)
        with self.assertRaises(ValueError):split.contract(self.root)
    def test_success_two_raw_xmls_no_merged_native_xml(self):
        value=split.aggregate(self.root)
        self.assertTrue(value['allExpectedPassed']);self.assertTrue(value['exactDisjointUnionVerified'])
        self.assertEqual(len(value['cases']),37);self.assertEqual(value['totalPlayProcessEnvelopeSeconds'],960)
        for shard in split.SHARDS:
            source,target=split.paths(self.root,shard)
            self.assertEqual((target/'raw-test-results.xml').read_bytes(),(source/'playmode-results.xml').read_bytes())
        self.assertFalse((split.visual.outdir(self.root)/'regression-play/raw-test-results.xml').exists())
    def test_each_shard_missing_renamed_duplicate_extra_or_wrong_owner_rejected(self):
        original=copy.deepcopy(self.trees)
        for shard in split.SHARDS:
            for mode in ('missing','renamed','duplicate','extra','wrong-owner','orphan','wrong-fixture','wrong-classname'):
                self.trees=copy.deepcopy(original);tree=self.trees[shard];suite=tree.find(".//test-suite[@type='TestFixture']");case=suite.find('test-case')
                if mode=='missing':suite.remove(case)
                elif mode=='renamed':case.set('fullname',case.get('fullname')+'Wrong')
                elif mode=='duplicate':suite.append(copy.deepcopy(case))
                elif mode=='extra':ET.SubElement(suite,'test-case',fullname='Unreviewed.Case',result='Passed')
                elif mode=='wrong-owner':tree.find('test-suite').set('name','Arbitrary.dll')
                elif mode=='wrong-fixture':suite.set('fullname','Wrong.Fixture')
                elif mode=='wrong-classname':case.set('classname','Wrong.Class')
                else:suite.remove(case);tree.append(case)
                self.save(shard);self.reject();self.trees=copy.deepcopy(original);self.save(shard)
    def test_sibling_failure_preserved_and_aggregate_failed(self):
        tree=self.trees['world'];tree.find('.//test-case').set('result','Failed');tree.set('result','Failed');tree.set('passed','2');tree.set('failed','1');sync_suite_counts(tree);self.save('world')
        p=safe.file(self.root,split.PHASES['world']);v=json.loads(p.read_text());v.update(status='NATIVE_FAILED',nativeExitCode=2,dockerExitCode=2);split.visual.write(p,v)
        self.reject();self.assertTrue((split.paths(self.root,'world')[1]/'raw-test-results.xml').exists())
        self.assertTrue(split.inspect(self.root,'core')['allExpectedPassed'])
    def test_every_suite_counter_missing_or_contradictory_is_rejected(self):
        original=copy.deepcopy(self.trees['core'])
        # Include the native namespace-style wrapper, with a discovery count
        # deliberately different from execution total.
        namespace=ET.Element('test-suite',type='TestSuite',name='Lottery',fullname='Lottery',testcasecount='39')
        for child in list(original):original.remove(child);namespace.append(child)
        original.append(namespace);sync_suite_counts(original)
        for suite_type in ('Assembly','TestFixture','TestSuite'):
            for field in ('total','passed','failed','skipped','inconclusive'):
                for mutation in ('missing','contradictory'):
                    self.trees['core']=copy.deepcopy(original)
                    suite=self.trees['core'].find(".//test-suite[@type='"+suite_type+"']")
                    if mutation=='missing':del suite.attrib[field]
                    else:suite.set(field,str(int(suite.get(field))+1))
                    self.save('core')
                    with self.subTest(suite=suite_type,field=field,mutation=mutation):self.reject()
        # Preserve the specific independently reported root-passing false-pass.
        self.trees['core']=copy.deepcopy(original)
        suite=self.trees['core'].find(".//test-suite[@type='Assembly']")
        suite.set('failed','1');suite.set('passed','7');suite.set('total','8');self.save('core');self.reject()

    def test_suite_results_must_match_descendant_failures(self):
        original=copy.deepcopy(self.trees['world'])
        wrapper=ET.Element('test-suite',type='TestSuite',name='Lottery',fullname='Lottery')
        for child in list(original):original.remove(child);wrapper.append(child)
        original.append(wrapper)
        original.find('.//test-case').set('result','Failed')
        original.set('result','Failed(Child)');original.set('passed','2');original.set('failed','1');sync_suite_counts(original)
        p=safe.file(self.root,split.PHASES['world']);value=json.loads(p.read_text());value.update(status='NATIVE_FAILED',nativeExitCode=2,dockerExitCode=2);split.visual.write(p,value)
        for suite_type in ('Assembly','TestFixture','TestSuite'):
            self.trees['world']=copy.deepcopy(original)
            self.trees['world'].find(".//test-suite[@type='"+suite_type+"']").set('result','Passed')
            self.save('world');self.reject()
            with self.assertRaisesRegex(ValueError,'PLAY_SUITE_RESULT_REJECTED'):split.inspect(self.root,'world')
        self.trees['world']=original;self.save('world')
        receipt=split.inspect(self.root,'world');self.assertFalse(receipt['allExpectedPassed']);self.assertEqual(receipt['counts']['failed'],1)

    def test_failure_child_of_passed_case_rejected_even_with_failed_sibling(self):
        tree=self.trees['world'];cases=list(tree.iter('test-case'));cases[0].set('result','Failed');ET.SubElement(cases[1],'failure')
        tree.set('result','Failed');tree.set('passed','2');tree.set('failed','1');sync_suite_counts(tree);self.save('world')
        with self.assertRaisesRegex(ValueError,'PLAY_PASSED_CASE_FAILURE_REJECTED'):split.inspect(self.root,'world')
        self.reject()

    def test_discovery_testcasecount_is_not_an_execution_counter(self):
        tree=self.trees['core']
        for suite in tree.iter('test-suite'):suite.set('testcasecount','999')
        self.save('core');self.assertTrue(split.aggregate(self.root)['allExpectedPassed'])

    def test_passed_namespace_failure_node_cannot_hide_in_failed_shard(self):
        tree=self.trees['core'];assembly=tree.find('test-suite')
        wrapper=ET.Element('test-suite',type='TestSuite',name='Lottery',fullname='Lottery')
        for child in list(assembly):assembly.remove(child);wrapper.append(child)
        assembly.append(wrapper);sync_suite_counts(tree);ET.SubElement(wrapper,'failure');self.save('core');self.reject()

    def test_mixed_source_run_attempt_shard_filter_pin_or_budget_rejected(self):
        p=safe.file(self.root,split.PHASES['world']);original=json.loads(p.read_text())
        for key,value in [('sourceCommit','3'*40),('reviewedCandidateCommit','4'*40),('runId','999'),('runAttempt','2'),('phase','regression-play-core'),('shard','core'),('testSelectionSha256','f'*64),('plannedCaseCount',37),('processBudgetSeconds',960),('mechanismSourcePin','bad'),('image','bad')]:
            with self.subTest(key=key):split.visual.write(p,dict(original,**{key:value}));self.reject()
        split.visual.write(p,original)
    def test_native_timeout_missing_exit_wrong_exit_boolean_exit_rejected(self):
        p=safe.file(self.root,split.PHASES['core']);original=json.loads(p.read_text())
        for changed in [dict(status='PROCESS_TIMEOUT'),dict(nativeExitMarkerCount=0),dict(nativeExitMarkerCount=True),dict(nativeExitCode=None),dict(nativeExitCode=False),dict(dockerExitCode=2),dict(status='NATIVE_FAILED')]:
            split.visual.write(p,dict(original,**changed));self.reject()
    def test_skip_inconclusive_count_fabrication_parent_failure_rejected(self):
        original=copy.deepcopy(self.trees['core'])
        for mode in ('Skipped','Inconclusive','count','parent','failure'):
            tree=copy.deepcopy(original);self.trees['core']=tree
            if mode in ('Skipped','Inconclusive'):tree.find('.//test-case').set('result',mode)
            elif mode=='count':tree.set('passed','37')
            elif mode=='parent':tree.find('test-suite').set('result','Failed')
            else:ET.SubElement(tree.find('.//test-case'),'failure')
            self.save('core');self.reject()
    def test_stale_xml_missing_shard_and_stale_pass_receipt_do_not_pass(self):
        split.aggregate(self.root)
        p=split.paths(self.root,'world')[0]/'playmode-results.xml';os.utime(p,ns=(1,1));self.reject()
        p.unlink();self.reject()
    def test_unsafe_xml_rejected_without_raw_export(self):
        p=split.paths(self.root,'world')[0]/'playmode-results.xml';raw=p.read_bytes()
        for value in [b'<!DOCTYPE test-run>'+raw,raw.replace(b'</test-run>',b'<output>UNITY_PASSWORD SECRET</output></test-run>'),raw.decode().encode('utf-16')]:
            p.write_bytes(value);self.reject();self.assertFalse((split.paths(self.root,'world')[1]/'raw-test-results.xml').exists())
    def test_native_failure_stays_blocked_and_return_never_claimed(self):
        value=dict(IDENT,status='READY',activationSucceeded=True,stagesStarted=[],cleanup=None);safe.private.write(safe.file(self.root,'session'),value)
        with patch.object(safe,'identity',return_value=IDENT),patch.object(safe,'compiler_assets',return_value=()),patch.object(safe.private,'cleanup',return_value=dict(status='ABSENCE_VERIFIED',removalExitCode=0)),patch.object(safe,'native',side_effect=lambda *args:args[3].update(status='PROCESS_TIMEOUT')):
            self.assertEqual(safe.test(self.root,'regression-play-core'),1)
        with patch.object(safe,'identity',return_value=IDENT),patch.object(safe.private,'cleanup',return_value=dict(status='ABSENCE_VERIFIED',removalExitCode=0)),patch.object(safe,'native') as native:
            self.assertEqual(safe.test(self.root,'regression-play-world'),1);native.assert_not_called()
            self.assertEqual(safe.finish(self.root),1);native.assert_not_called()
        self.assertEqual(json.loads(safe.file(self.root,'finish').read_text())['returnStatus'],'RETURN_NOT_RUN_SESSION_BLOCKED')
    def test_both_arguments_keep_resolution_gpu_worker_and_each_480(self):
        for shard in split.SHARDS:
            phase=split.PHASES[shard];argv=safe.project_argv(phase,IDENT)
            self.assertEqual(safe.PHASES[phase][3],480)
            for k,v in [('-screen-width','1280'),('-screen-height','720'),('-job-worker-count','2'),('-g3RegressionShard',shard),('-testFilter',split.selection(shard)),('-probeRunAttempt','1')]:self.assertEqual(argv[argv.index(k)+1],v)
            for item in ('-quit','-nographics','-runSynchronously','-testCategory','-repeat','-retry'):self.assertNotIn(item,argv)
            self.assertIn('-force-glcore',argv)
    def test_workflow_keeps_timeout_sidecars_exact_upload_and_no_continue(self):
        text=(ROOT/split.visual.WORKFLOW).read_text()
        self.assertIn('timeout-minutes: 75',text);self.assertNotIn('continue-on-error',text)
        for shard in split.SHARDS:
            self.assertIn('safe_project_ci.py '+split.PHASES[shard],text)
            self.assertIn('visual_candidate_ci.py tests --stage '+split.PHASES[shard],text)
            self.assertIn('visual_candidate_ci.py regression-progress --shard '+shard,text)
        self.assertIn('visual_candidate_ci.py play-summary',text)
        block=text.split('      - name: Preserve bounded WORLD route and ray sidecar even on timeout',1)[1].split('      - name:',1)[0]
        self.assertIn("always()",block);self.assertIn("steps.regressionplayworld.outcome != 'skipped'",block)
        self.assertIn('world_progress_ci.py',block);self.assertIn('/world-progress.json',text)
        self.assertNotIn('/world-progress.jsonl',text);self.assertNotIn('*.log',text)

if __name__=='__main__':unittest.main()

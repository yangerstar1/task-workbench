"""Narrow synthetic phase-schema checks. No Unity, native logs or network."""
import json
import re
import unittest
from pathlib import Path
import world_progress_ci as world
from test_world_progress_ci import record, route, ray, encode, IDENT, KEY, SEGMENT

FIELDS = ('frequency intervals frame wallTicks yieldTicks resumeTicks pumpCalls pumpTicks diagnosticCalls diagnosticTicks pollCalls pollTicks '
          'glyphCalls glyphTicks atlasNotifications updateCalls updateTicks showCalls showTicks gcMax gc0 gc1 gc2 incomplete overflow cpuAvailable processCpuTicks').split()

def phase(segment=SEGMENT, **updates):
    v = dict.fromkeys(FIELDS, 0)
    v.update(frequency=10000000, intervals=1, frame=1, wallTicks=593432000,
             yieldTicks=593400000, resumeTicks=32000, pumpCalls=1, pumpTicks=10000,
             diagnosticCalls=1, diagnosticTicks=1000, pollCalls=1, pollTicks=16000, glyphCalls=2, glyphTicks=1000,
             updateCalls=1, updateTicks=8000, gcMax=2)
    v.update(updates)
    return 'WORLD_PHASE_V1 segment='+segment+''.join(' '+k+'='+str(v[k]) for k in FIELDS)

def rows(sample=None, end='ABORTED', frames=1):
    return [record(), record(route(phase=end,elapsed='66.0000',frames=frames),sequence=2), record(sample or phase(),sequence=3)]

class WorldPhaseTests(unittest.TestCase):
    def check(self, values):return world.decode_records(encode(values), IDENT)
    def test_cpu_extension_and_legacy_records(self):
        self.check(rows(phase(cpuAvailable=1,processCpuTicks=1200000000)))
        self.check(rows(phase(cpuAvailable=1,processCpuTicks=0)))
        self.check(rows(phase().replace(" cpuAvailable=0 processCpuTicks=0", "")))
        for sample in (phase(cpuAvailable=0,processCpuTicks=1),phase(cpuAvailable=2),phase(processCpuTicks=-1),phase(processCpuTicks=1000000000000001),phase()+" processCpuTicks=0"):
            with self.subTest(sample=sample),self.assertRaises(ValueError):self.check(rows(sample))
    def test_positive_native_shaped_record(self):
        data=rows();got=self.check(data)
        self.assertEqual(got['observations'],data)
        self.assertEqual(got['status'],'OBSERVATIONS_ONLY_NOT_TEST_PASS')
        self.assertNotIn('allExpectedPassed',got)
    def test_zero_frame_and_pending_first_frame(self):
        values=dict.fromkeys(FIELDS,0);values.update(frequency=10000000,gcMax=2)
        self.check(rows(phase(**values),frames=0))
        self.check(rows(phase(incomplete=1),frames=0))
        for sample in [phase(intervals=0,frame=0),phase(intervals=1,frame=0),phase(intervals=0,frame=1)]:
            with self.subTest(sample=sample),self.assertRaises(ValueError):self.check(rows(sample,frames=0))
        with self.assertRaises(ValueError):self.check(rows(phase(incomplete=1),end='REACHED',frames=0))
    def test_wrong_sequence_duplicate_and_wrong_case(self):
        bads=[[record(phase())],[record(),record(phase(),sequence=2)],rows()+[record(phase(),sequence=4)],
              rows()[:2]+[record(ray(),sequence=3),record(phase(),sequence=4)]]
        other=next(k for k in world.CASE_SEGMENTS if k!=KEY)
        wrong=rows();wrong[-1]['caseKey']=other;bads.append(wrong)
        for data in bads:
            with self.subTest(data=data),self.assertRaises(ValueError):self.check(data)
    def test_numbers_fields_and_injection_rejected(self):
        bads=[phase()+' secret=PRIVATE',phase()+'\n',phase().replace('pumpTicks=10000','pumpTicks=NaN'),
              phase().replace('pumpTicks=10000','pumpTicks=-1'),phase().replace('pumpTicks=10000','pumpTicks=1e8'),
              phase().replace('pumpTicks=10000','pumpTicks=10000 pumpTicks=10000'),phase(frequency=0),
              phase(pumpTicks=1000000000000001),phase(incomplete=2),phase(overflow=2),phase(gcMax=3),
              phase(wallTicks=3),phase(intervals=1000001),phase(frame=2),phase(gcMax=0,gc1=1),phase(gcMax=1,gc2=1)]
        for sample in bads:
            with self.subTest(sample=sample),self.assertRaises(ValueError):self.check(rows(sample))
    def test_overflow_is_explicit_not_accepted_as_timing_evidence(self):
        self.check(rows(phase(overflow=1,wallTicks=1000000000000000)))
    def test_truncated_last_phase_preserves_terminal_route_only(self):
        prefix=encode(rows()[:2]);last=encode([rows()[-1]])
        for cut in (1,len(last)//2,len(last)-1):
            got=world.decode_records(prefix+last[:cut],IDENT)
            self.assertEqual(got['observations'],rows()[:2]);self.assertTrue(got['partialFinalRecordDiscarded'])
    def test_all_maximum_routes_and_phases_fit_existing_limits(self):
        data=[]
        for key,segments in world.CASE_SEGMENTS.items():
            for segment in segments:
                data.append(record(route(segment),key,len(data)+1))
                for i in range(1,9):data.append(record(route(segment,'SAMPLE',f'{i*5}.0000',i),key,len(data)+1))
                data.append(record(route(segment,'REACHED','44.0000',9),key,len(data)+1))
                data.append(record(phase(segment,intervals=9),key,len(data)+1))
            for _ in range(3 if 'ENTRY_TO_INVENTORY' in segments else 2):data.append(record(ray(),key,len(data)+1))
        encoded=encode(data)
        self.assertEqual(len(data),117);self.assertLess(len(encoded),world.LIMIT)
        self.assertTrue(all(len(x)+1<=world.MAX_RECORD_BYTES for x in encoded.splitlines()))
        self.assertEqual(len(self.check(data)['observations']),117)
    def test_source_grammar_and_fixed_gate_match(self):
        root=Path(__file__).resolve().parents[3]
        g3=root/'tasks/lottery-shop/unity/Assets/G3'
        writer=(g3/'Tests/PlayMode/G3WorldProgress.cs').read_text()
        self.assertEqual(re.search('const string PhasePattern=@"([^"]+)";',writer).group(1),world.PHASE_PATTERN)
        self.assertIn('public static bool PhaseTimingEnabled=>Enabled;',writer)
        self.assertIn('MaximumBytes=262144, MaximumRecords=128, MaximumRecordBytes=4096',writer)
        source=(g3/'Tests/PlayMode/G3WorldInteractionTests.cs').read_text()
        self.assertIn('if(G3WorldProgress.PhaseTimingEnabled)',source)
        self.assertIn('try{phases?.EndFrame(true);}',source)
        self.assertIn('finally{phases?.End();sample.Workload?.End();}',source)
        self.assertIn('if(!(elapsed<45))Assert.That(elapsed,Is.LessThan(45)',source)
        self.assertEqual(source.count('WriteWorldDiagnostic(phases.Summary(segment))'),1)
        self.assertEqual(source.count('[UnityTest,Timeout(180000)]'),3)
        self.assertIn('finally{activeWorldPhase?.ObserveDiagnostic(System.Diagnostics.Stopwatch.GetTimestamp()-started);}',source)
        begin=source.index('activeWorldPhase?.BeforeYield(sample.Frames+1)')
        body=source[begin:source.index('// Arrival on a slow frame',begin)]
        self.assertLess(body.index('sample.Observe('),body.index('WriteWorldDiagnostic(WorldWalkDiagnostic(sample,"SAMPLE"))'))
        self.assertLess(body.index('WriteWorldDiagnostic(WorldWalkDiagnostic(sample,"SAMPLE"))'),body.index('activeWorldPhase?.EndFrame()'))
        actual=re.findall(r'" ([A-Za-z0-9]+)="',source[source.index('public string Summary(string segment)'):source.index('public void End(){G3SceneView')])
        self.assertEqual(actual,FIELDS)

if __name__=='__main__':unittest.main(verbosity=2)


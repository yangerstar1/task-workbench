using System;
using System.IO;
using NUnit.Framework;
using UnityEngine;
namespace DesertRV.Tests
{
    public sealed class CandidateArtImportTests
    {
        [Serializable] sealed class Mode { public string mode; }
        static void RequireNestedWeaponDiagnosticsJsonRoundTrip()
        {
            // Exercise the actual nested Sample through Unity's serializer. A custom
            // diagnostics struct without [Serializable] silently loses these fields.
            var sampleType=Type.GetType("DesertRV.Editor.CandidateWeaponDiagnostics+Sample, Assembly-CSharp-Editor",true);
            var sample=Activator.CreateInstance(sampleType);
            var diagnosticsType=sampleType.GetField("left").FieldType;
            Assert.That(diagnosticsType.GetFields(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public).Length,Is.EqualTo(12));
            string[] measures={"upperLength","foreLength","wristGap","shoulderDrift","targetDrift","targetDistance","expectedUpperLength","expectedForeLength"};
            foreach(string side in new[]{"left","right"})
            {
                var diagnostics=Activator.CreateInstance(diagnosticsType);
                diagnosticsType.GetField("solved").SetValue(diagnostics,side=="left");
                diagnosticsType.GetField("measured").SetValue(diagnostics,true);
                diagnosticsType.GetField("measurementsFinite").SetValue(diagnostics,true);
                diagnosticsType.GetField("reason").SetValue(diagnostics,side+"-serialization-probe");
                for(int i=0;i<measures.Length;i++)diagnosticsType.GetField(measures[i]).SetValue(diagnostics,(side=="left"?.01f:.02f)*(i+1));
                sampleType.GetField(side).SetValue(sample,diagnostics);
            }
            string json=JsonUtility.ToJson(sample);
            var restored=JsonUtility.FromJson(json,sampleType);
            foreach(string side in new[]{"left","right"})
            {
                Assert.That(json,Does.Contain("\""+side+"\":"),"Actual nested arm diagnostics must be serialized.");
                var expected=sampleType.GetField(side).GetValue(sample);var actual=sampleType.GetField(side).GetValue(restored);
                foreach(var field in diagnosticsType.GetFields(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public))
                    Assert.That(field.GetValue(actual),Is.EqualTo(field.GetValue(expected)),"Nested diagnostics round-trip: "+side+"."+field.Name);
            }
            Debug.Log("CANDIDATE_WEAPON_SAMPLE_SERIALIZATION sides=2 measuredFieldsPerSide=12 roundTrip=true");
        }
        [Test] public void ExecutePinnedDiscoveryOrBindingDiagnostics()
        {
            RequireNestedWeaponDiagnosticsJsonRoundTrip();
            var scan=Type.GetType("DesertRV.Editor.JourneyCandidateArtDiscovery, Assembly-CSharp-Editor",true).GetMethod("ContainsStrictRootFields");
            Assert.That(scan.Invoke(null,new object[]{"{\"mode\":\"DISCOVERY_ONLY\",\"files\":[]}"}),Is.False);
            Assert.That(scan.Invoke(null,new object[]{"{\"note\":\"bindings\",\"nested\":{\"clips\":null}}"}),Is.False);
            foreach(string key in new[]{"bindings","clips","materials","weapon"})
                foreach(string value in new[]{"null","[]","{}"})
                    Assert.That(scan.Invoke(null,new object[]{"{\""+key+"\":"+value+"}"}),Is.True);
            Assert.That(scan.Invoke(null,new object[]{"{\"\\u0062indings\":null}"}),Is.True);
            var mode=JsonUtility.FromJson<Mode>(File.ReadAllText("CandidateImportInput/contract.json")).mode;
            Assert.That(mode,Is.EqualTo("DISCOVERY_ONLY").Or.EqualTo("STRICT_BINDING"));
            string type=mode=="DISCOVERY_ONLY"?"JourneyCandidateArtDiscovery":"JourneyCandidateArtCapture";
            string method=mode=="DISCOVERY_ONLY"?"Discover":"ImportAndCapture";
            Type.GetType("DesertRV.Editor."+type+", Assembly-CSharp-Editor",true).GetMethod(method).Invoke(null,null);
        }
    }
}

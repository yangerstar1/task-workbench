using System;
using System.IO;
using NUnit.Framework;
using UnityEngine;
namespace DesertRV.Tests
{
    public sealed class CandidateArtImportTests
    {
        [Serializable] sealed class Mode { public string mode; }
        [Test] public void ExecutePinnedDiscoveryOrBindingDiagnostics()
        {
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

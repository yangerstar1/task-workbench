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
            var mode=JsonUtility.FromJson<Mode>(File.ReadAllText("CandidateImportInput/contract.json")).mode;
            Assert.That(mode,Is.EqualTo("DISCOVERY_ONLY").Or.EqualTo("STRICT_BINDING"));
            string type=mode=="DISCOVERY_ONLY"?"JourneyCandidateArtDiscovery":"JourneyCandidateArtCapture";
            string method=mode=="DISCOVERY_ONLY"?"Discover":"ImportAndCapture";
            Type.GetType("DesertRV.Editor."+type+", Assembly-CSharp-Editor",true).GetMethod(method).Invoke(null,null);
        }
    }
}

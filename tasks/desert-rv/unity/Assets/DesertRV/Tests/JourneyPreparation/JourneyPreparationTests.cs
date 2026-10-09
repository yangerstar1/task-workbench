using System;
using NUnit.Framework;
namespace DesertRV.Tests
{
    public sealed class JourneyPreparationTests
    {
        [Test] public void PrepareVerifiedSameWorkspaceJourney()
        {
            Type.GetType("DesertRV.Editor.JourneyCandidatePreparation, Assembly-CSharp-Editor", true)
                .GetMethod("PrepareVerifiedSameWorkspace").Invoke(null, null);
        }
    }
}

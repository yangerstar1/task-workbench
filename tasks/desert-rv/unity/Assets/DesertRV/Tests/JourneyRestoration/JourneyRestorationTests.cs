using System;
using System.Reflection;
using NUnit.Framework;

namespace DesertRV.Tests
{
    // A separate single-case gate; original strict/preparation/boundary case inventories stay unchanged.
    public sealed class JourneyRestorationTests
    {
        [Test, Timeout(600000)]
        public void RevalidatePinnedRestoredJourney()
        {
            var type = Type.GetType("DesertRV.Editor.JourneyCandidateRestoration, Assembly-CSharp-Editor", true);
            var method = type.GetMethod("RevalidatePinnedRestoredJourney", BindingFlags.Public | BindingFlags.Static);
            Assert.That(method, Is.Not.Null);
            try { method.Invoke(null, null); }
            catch (TargetInvocationException error) when (error.InnerException != null)
            {
                System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(error.InnerException).Throw();
                throw;
            }
        }
    }
}

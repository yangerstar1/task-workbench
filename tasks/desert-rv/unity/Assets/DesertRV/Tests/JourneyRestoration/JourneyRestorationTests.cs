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
            var parser = type.GetMethod("ParseConsumerRunId", BindingFlags.Public | BindingFlags.Static);
            Assert.That(parser, Is.Not.Null);
            const string expected = "https://github.com/yangerstar1/task-workbench/actions/runs/123";
            Assert.That(parser.Invoke(null, new object[] { new[] { "Unity", "-journeyRestorationRunId", "123", "-batchmode" }, expected }), Is.EqualTo("123"));
            foreach (var args in new[] {
                Array.Empty<string>(), new[] { "-journeyRestorationRunId" },
                new[] { "-journeyRestorationRunId", "123", "-journeyRestorationRunId", "123" },
                new[] { "-journeyRestorationRunId", "0" }, new[] { "-journeyRestorationRunId", "-1" },
                new[] { "-journeyRestorationRunId", "123/other" }, new[] { "-journeyRestorationRunId", "124" } })
            {
                var error = Assert.Throws<TargetInvocationException>(() => parser.Invoke(null, new object[] { args, expected }));
                Assert.That(error.InnerException, Is.TypeOf<InvalidOperationException>());
            }
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

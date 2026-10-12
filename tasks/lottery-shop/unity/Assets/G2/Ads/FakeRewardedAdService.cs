using System;
using System.Collections.Generic;
using System.Linq;
using Lottery.G2.Core;
namespace Lottery.G2.Ads
{
    public enum AdEventKind { Closed, Reward, NoFill, NotShown, NoRewardTerminal }
    public sealed class FakeAdEvent { public string EventId, RequestId, RunId; public AdEventKind Kind; }
    public interface IRewardedAdService
    {
        bool IsAvailable { get; }
        CommandResult Show(string requestId, string runId);
        IReadOnlyList<FakeAdEvent> ReadEvents(string requestId);
    }
    // Explicit development receipt source. Events survive restart because they share the durable store.
    public sealed class FakeRewardedAdService : IRewardedAdService
    {
        readonly IStateStore store;
        public static bool DevelopmentEnabled
        {
            get
            {
#if UNITY_EDITOR || DEVELOPMENT_BUILD || LOTTERY_G2_TEST_FIXTURE
                return true;
#else
                return false;
#endif
            }
        }
        public bool IsAvailable => DevelopmentEnabled;
        public FakeRewardedAdService(IStateStore store) { this.store = store ?? throw new ArgumentNullException(nameof(store)); }
        public CommandResult Show(string requestId, string runId)
        {
            RequireDevelopment(); var snapshot = store.Read(); string id = "fake-show:" + requestId;
            return store.Execute(id, CommandDigest.Create(runId, "FAKE_SHOW", w => w.Write(requestId ?? "")), snapshot.Revision, s =>
            {
                if (runId != s.RunId || s.Ad == null || s.Ad.RequestId != requestId || s.Ad.Phase != AdPhase.SHOWING) throw new RuleViolation("AD_REQUEST_MISMATCH");
                if (s.FakeShownRequests.Contains(requestId)) throw new RuleViolation("NO_CHANGE");
                s.FakeShownRequests.Add(requestId); return new CommandReceipt { Kind = "FAKE_SHOW" };
            });
        }
        public CommandResult QueueEvent(string requestId, string runId, AdEventKind kind)
            => QueueEvent(requestId, runId, kind, requestId + ":" + kind);
        public CommandResult QueueEvent(string requestId, string runId, AdEventKind kind, string eventId)
        {
            RequireDevelopment(); var snapshot = store.Read();
            return store.Execute("fake-event:" + eventId, CommandDigest.Create(snapshot.RunId, "FAKE_EVENT", w => { w.Write(eventId ?? ""); w.Write(requestId ?? ""); w.Write(runId ?? ""); w.Write((int)kind); }), snapshot.Revision, s =>
            {
                if (string.IsNullOrEmpty(eventId) || string.IsNullOrEmpty(requestId) || string.IsNullOrEmpty(runId) || !Enum.IsDefined(typeof(AdEventKind), kind)) throw new RuleViolation("INVALID_REQUEST");
                s.FakeEvents.Add(new FakeAdEvent { EventId = eventId, RequestId = requestId, RunId = runId, Kind = kind });
                return new CommandReceipt { Kind = "FAKE_EVENT" };
            });
        }
        public IReadOnlyList<FakeAdEvent> ReadEvents(string requestId)
        { RequireDevelopment(); return store.Read().FakeEvents.Where(e => e.RequestId == requestId).ToArray(); }
        static void RequireDevelopment() { if (!DevelopmentEnabled) throw new InvalidOperationException("Fake rewarded advertising is disabled in non-development candidates"); }
    }
}

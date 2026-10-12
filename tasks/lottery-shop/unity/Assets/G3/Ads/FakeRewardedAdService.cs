using System;
using System.Collections.Generic;
using System.Linq;
using Lottery.G3.Core;

namespace Lottery.G3.Ads
{
    public enum AdEventKind { Closed, Reward, NoFill, NotShown, NoRewardTerminal }
    public sealed class FakeAdEvent
    {
        public string EventId = "", RequestId = "", RunId = "";
        public AdEventKind Kind;
    }
    public interface IRewardedAdService
    {
        bool IsAvailable { get; }
        CommandResult Show(string requestId, string runId);
        IReadOnlyList<FakeAdEvent> ReadEvents(string requestId);
    }

    // A deliberately synthetic, durable receipt source, never a production ad provider.
    // Both a development build and a separately marked initial fixture are required.
    public sealed class FakeRewardedAdService : IRewardedAdService
    {
        readonly IStateStore store;
        public static bool DevelopmentEnabled
        {
            get
            {
#if UNITY_EDITOR || DEVELOPMENT_BUILD || LOTTERY_G3_TEST_FIXTURE
                return true;
#else
                return false;
#endif
            }
        }
        public bool IsAvailable => DevelopmentEnabled && store.Read().FixtureLabel == SyntheticAdFixture.Label;
        public FakeRewardedAdService(IStateStore store) { this.store = store ?? throw new ArgumentNullException(nameof(store)); }

        public CommandResult Show(string requestId, string runId)
        {
            var snapshot = store.Read();
            if (!DevelopmentEnabled || snapshot.FixtureLabel != SyntheticAdFixture.Label) return Rejection("AD_SERVICE_UNAVAILABLE");
            return store.Execute("fake-show:" + requestId,
                CommandDigest.Create(runId, "FAKE_SHOW", w => w.Write(requestId ?? "")), snapshot.Revision, s =>
                {
                    RequireFixture(s);
                    if (runId != s.RunId || s.Ad == null || s.Ad.RequestId != requestId || s.Ad.RunId != runId || s.Ad.Phase != AdPhase.SHOWING)
                        throw new RuleViolation("AD_REQUEST_MISMATCH");
                    if (s.FakeShownRequests.Contains(requestId)) throw new RuleViolation("NO_CHANGE");
                    s.FakeShownRequests.Add(requestId);
                    return new CommandReceipt { Kind = "FAKE_SHOW" };
                });
        }
        public CommandResult QueueEvent(string requestId, string runId, AdEventKind kind)
            => QueueEvent(requestId, runId, kind, requestId + ":" + kind);
        public CommandResult QueueEvent(string requestId, string runId, AdEventKind kind, string eventId)
        {
            var snapshot = store.Read();
            if (!DevelopmentEnabled || snapshot.FixtureLabel != SyntheticAdFixture.Label) return Rejection("AD_SERVICE_UNAVAILABLE");
            return store.Execute("fake-event:" + eventId,
                CommandDigest.Create(snapshot.RunId, "FAKE_EVENT", w =>
                { w.Write(eventId ?? ""); w.Write(requestId ?? ""); w.Write(runId ?? ""); w.Write((int)kind); }), snapshot.Revision, s =>
                {
                    RequireFixture(s);
                    if (!ValidId(eventId, 220) || !ValidId(requestId) || !ValidId(runId) || !Enum.IsDefined(typeof(AdEventKind), kind))
                        throw new RuleViolation("INVALID_REQUEST");
                    if (s.AdEvents.Any(e => e.EventId == eventId)) throw new RuleViolation("AD_EVENT_ID_REUSED");
                    // Wrong-run/request test receipts may be injected, but cannot be applied to an ad.
                    s.AdEvents.Add(new AdEventRecord { EventId = eventId, RequestId = requestId, RunId = runId, Kind = kind.ToString() });
                    return new CommandReceipt { Kind = "FAKE_EVENT" };
                });
        }
        public IReadOnlyList<FakeAdEvent> ReadEvents(string requestId)
        {
            var snapshot = store.Read();
            if (!DevelopmentEnabled || snapshot.FixtureLabel != SyntheticAdFixture.Label) return new FakeAdEvent[0];
            var events = new List<FakeAdEvent>();
            foreach (var e in snapshot.AdEvents.Where(e => e.RequestId == requestId))
            {
                AdEventKind kind;
                if (!Enum.TryParse(e.Kind, out kind) || !Enum.IsDefined(typeof(AdEventKind), kind))
                    throw new InvalidOperationException("Invalid persisted synthetic ad receipt");
                events.Add(new FakeAdEvent { EventId = e.EventId, RequestId = e.RequestId, RunId = e.RunId, Kind = kind });
            }
            return events;
        }
        internal static bool ValidId(string value, int maximum = 128) => !string.IsNullOrWhiteSpace(value) && value.Length <= maximum && !value.Any(char.IsControl);
        static void RequireFixture(RunState s)
        { if (!DevelopmentEnabled || s.FixtureLabel != SyntheticAdFixture.Label) throw new RuleViolation("AD_SERVICE_UNAVAILABLE"); }
        CommandResult Rejection(string code) => new CommandResult
        { CommitStatus = store.CanMutate ? CommitStatus.PROVEN_NOT_COMMITTED : CommitStatus.COMMIT_UNKNOWN, Code = code, State = store.Read() };
    }
}

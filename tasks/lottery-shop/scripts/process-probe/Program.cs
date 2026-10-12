// Real Linux/.NET process fixture over the same Core source. Not Unity/Android evidence.
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Text.Json;
using System.Threading;
using Lottery.G2.Core;
using Lottery.G2.Persistence;
using Lottery.G2.Ads;
static class Program
{
    static string check = "ARGUMENTS";
    const string Attempt = "kill-attempt", Request = "fake-request";
    const string WaitingScenario = "ad_waiting", WaitingPoint = "ClosedAwaitingReward";
    static int Main(string[] args)
    {
        try
        {
            if (args.Length != 4) throw new InvalidOperationException();
            string mode = args[0], scenario = args[1], point = args[2], directory = args[3];
            if (scenario == WaitingScenario)
            {
                if (point != WaitingPoint) throw new InvalidOperationException();
                if (mode == "prepare") PrepareWaiting(directory);
                else if (mode == "crash") CrashWaiting(directory);
                else if (mode == "verify") VerifyWaiting(directory);
                else throw new InvalidOperationException();
                return 0;
            }
            if (!new[] {"buy", "scratch", "claim", "ad"}.Contains(scenario)) throw new InvalidOperationException();
            if (mode == "prepare") Prepare(scenario, directory);
            else if (mode == "crash")
            {
                check = "CRASH_APPLY";
                using (var store = new FileStateStore(Path.Combine(directory, "actual"), Initial(scenario), new PauseAt(point, Path.Combine(directory, "ready"))))
                    MustCommit(Apply(scenario, store, store.Read().Revision));
                check = "KILL_POINT_NOT_REACHED";
                throw new InvalidOperationException("Expected kill point was not hit");
            }
            else if (mode == "verify") Verify(scenario, point, directory);
            else throw new InvalidOperationException();
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine("G2_PROBE_ERROR " + check + " " + error.GetType().Name); return 1; }
    }
    static RunState Initial(string scenario)
    {
        var s = RunState.CreateNew("synthetic-process-" + scenario, "g2-process-fixed-seed");
        if (scenario == "ad" || scenario == WaitingScenario) { s.FixtureLabel = "SYNTHETIC_AD_FIXTURE"; s.DayNumber = 2; s.FixtureBaseSettlements = s.SettledTicketCount = 12; }
        return s;
    }
    static void Setup(string scenario, FileStateStore store)
    {
        var tickets = new TicketService(store);
        if (scenario == "scratch" || scenario == "claim") { check = "SETUP_BUY"; MustCommit(tickets.BuyNumberTicket("setup-buy", store.Read().Revision)); }
        if (scenario == "claim")
        {
            var strokes = new List<ScratchStroke>();
            for (int y = 0; y <= 16; y++) strokes.Add(new ScratchStroke(0, y / 16.0, 1, y / 16.0, true, 16));
            check = "SETUP_SCRATCH";
            MustCommit(tickets.ApplyScratch(store.Read().CurrentTicket.Id, "setup-reveal", store.Read().Revision, strokes.ToArray()));
            check = "SETUP_REVEAL";
            if (!store.Read().CurrentTicket.Scratch.IsFullyRevealed) throw new InvalidOperationException();
        }
        if (scenario == "ad")
        {
            var fake = new FakeRewardedAdService(store); var ads = new AdPurchaseService(store, fake);
            check = "AD_BEGIN";
            MustCommit(ads.BeginAd(Request, "setup-begin", store.Read().Revision, 60));
            check = "AD_REWARD";
            MustCommit(fake.QueueEvent(Request, store.Read().RunId, AdEventKind.Reward));
            check = "AD_RECORD";
            MustCommit(ads.RecordEvent(fake.ReadEvents(Request)[0], "setup-reward", store.Read().Revision));
            check = "AD_COMMITTING";
            MustCommit(ads.MarkCommitting(Request, "setup-committing", store.Read().Revision));
        }
    }
    static CommandResult Apply(string scenario, FileStateStore store, long revision)
    {
        var service = new TicketService(store); var state = store.Read();
        if (scenario == "buy") return service.BuyNumberTicket(Attempt, revision);
        if (scenario == "scratch") return service.ApplyScratch(state.CurrentTicket.Id, Attempt, revision,
            new[] { new ScratchStroke(.1, .25, .45, .25, true, 12) });
        if (scenario == "claim") return service.Claim(state.CurrentTicket.Id, Attempt, revision);
        return new AdPurchaseService(store, new FakeRewardedAdService(store)).CommitAd(Request, Attempt, revision);
    }
    static void MustCommit(CommandResult result) { if (!result.Committed) throw new InvalidOperationException("Expected committed setup"); }
    static string Hash(RunState state) => StateCodec.HashBytes(StateCodec.SerializeCanonical(state));
    static void Prepare(string scenario, string directory)
    {
        check = "PREPARE_DIRECTORY";
        if (Directory.Exists(directory)) throw new InvalidOperationException("Refuse fixture reuse");
        Directory.CreateDirectory(directory);
        string before, expected;
        using (var store = new FileStateStore(Path.Combine(directory, "actual"), Initial(scenario))) { Setup(scenario, store); before = Hash(store.Read()); }
        using (var store = new FileStateStore(Path.Combine(directory, "expected"), Initial(scenario)))
        {
            Setup(scenario, store); check = "PREPARE_EQUAL"; if (Hash(store.Read()) != before) throw new InvalidOperationException();
            check = "PREPARE_APPLY";
            MustCommit(Apply(scenario, store, store.Read().Revision)); expected = Hash(store.Read());
        }
        File.WriteAllText(Path.Combine(directory, "expected.json"), JsonSerializer.Serialize(new { before, expected }));
    }
    static void Verify(string scenario, string point, string directory)
    {
        check = "RECOVERY_BOUNDARY";
        using (var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(directory, "expected.json"))))
        using (var store = new FileStateStore(Path.Combine(directory, "actual"), Initial(scenario)))
        {
            string before = doc.RootElement.GetProperty("before").GetString(), expected = doc.RootElement.GetProperty("expected").GetString();
            var recovered = store.Recover(Attempt); bool published = point == "AfterPublish" || point == "BeforeResponse";
            string recoveredHash = Hash(store.Read());
            if (recovered.CommitStatus != (published ? CommitStatus.COMMITTED : CommitStatus.PROVEN_NOT_COMMITTED) ||
                recoveredHash != (published ? expected : before) || !store.CanMutate) throw new InvalidOperationException("Wrong recovery boundary");
            check = "RECOVERY_REPLAY";
            MustCommit(Apply(scenario, store, store.Read().Revision));
            string finalHash = Hash(store.Read());
            check = "STALE_REPLAY";
            MustCommit(Apply(scenario, store, -999)); // Committed lookup must precede stale-revision rejection.
            check = "STATE_INVARIANTS";
            var state = store.Read(); StateInvariants.Validate(state);
            check = "EXACTLY_ONCE";
            if (Hash(state) != finalHash || finalHash != expected || state.Commands.Count(c => c.CommandId == Attempt) != 1)
                throw new InvalidOperationException("Replay duplicated or changed a committed result");
            check = "WALLET_STOCK";
            long expectedCash = NumberTicketRules.InitialCashMinor - (scenario == "ad" ? NumberTicketRules.AdPriceMinor : NumberTicketRules.PriceMinor);
            if (scenario == "claim") expectedCash += state.CurrentTicket.RawPrizeMinor;
            if (state.CashMinor != expectedCash || (scenario == "ad" && (state.Ad.Phase != AdPhase.COMMITTED || state.StockAvailable || state.Drawers.Count(x => x != null) != 1)))
                throw new InvalidOperationException("Independent wallet/stock invariant failed");
            check = "RESULT_WRITE";
            File.WriteAllText(Path.Combine(directory, "result.json"), JsonSerializer.Serialize(new {
                status = "PASS", scenario, point, recoveryStatus = recovered.CommitStatus.ToString(), beforeHash = before,
                expectedHash = expected, recoveredHash, finalHash, finalCashMinor = state.CashMinor,
                finalCommands = state.Commands.Count, attemptCommandOccurrences = 1, staleRevisionReplayUnchanged = true }));
        }
    }
    static void BeginWaiting(FileStateStore store)
    {
        check = "WAITING_BEGIN";
        MustCommit(new AdPurchaseService(store, new FakeRewardedAdService(store)).BeginAd(Request, "setup-begin", store.Read().Revision, 60));
    }
    static void CloseWaiting(FileStateStore store)
    {
        check = "WAITING_CLOSE";
        var fake = new FakeRewardedAdService(store); var ads = new AdPurchaseService(store, fake);
        MustCommit(fake.QueueEvent(Request, store.Read().RunId, AdEventKind.Closed));
        MustCommit(ads.PollAd(Request, "waiting-poll", store.Read().Revision));
        AssertWaiting(store.Read());
    }
    static void AssertReservation(RunState state)
    {
        check = "WAITING_RESERVATION";
        var ad = state.Ad;
        if (state.RunId != "synthetic-process-ad_waiting" || state.FixtureLabel != "SYNTHETIC_AD_FIXTURE" ||
            state.DayNumber != 2 || state.SettledTicketCount != 12 || ad == null || ad.RunId != state.RunId || ad.RequestId != Request ||
            ad.StockId != NumberTicketRules.StockId || ad.ItemId != NumberTicketRules.StockItemId || ad.Quality != NumberTicketRules.StockQuality ||
            ad.ReservedPriceMinor != NumberTicketRules.AdPriceMinor || ad.ReservedDrawerSlot != 0 || ad.DayNumber != 2 ||
            ad.CreateCommandId != "setup-begin" || ad.ReserveCommandId != "setup-begin:reserve" || ad.ShowingCommandId != "setup-begin:showing" ||
            ad.CommittingCommandId != Request + ":committing" || ad.CommitCommandId != Request + ":commit")
            throw new InvalidOperationException("Original waiting reservation changed");
    }
    static void AssertWaiting(RunState state)
    {
        AssertReservation(state); check = "WAITING_STATE"; StateInvariants.Validate(state);
        if (state.Ad.Phase != AdPhase.CLOSED_AWAITING_REWARD || state.Ad.RewardRecorded || !AdPurchaseService.HasReservation(state.Ad) ||
            state.CashMinor != NumberTicketRules.InitialCashMinor || !state.StockAvailable || state.Drawers.Any(x => x != null) ||
            state.AdSuccessesToday != 0 || state.SettledCountAtLastAdSuccess != -1 || state.Commands.Count != 6 || state.Revision != 6 ||
            state.FakeShownRequests.Count != 1 || state.FakeShownRequests[0] != Request || state.FakeEvents.Count != 1 ||
            state.FakeEvents[0].Kind != AdEventKind.Closed || state.FakeEvents[0].RequestId != Request || state.FakeEvents[0].RunId != state.RunId)
            throw new InvalidOperationException("Waiting state has consumed or lost a reservation");
    }
    static void ReleaseLateReward(FileStateStore store)
    {
        check = "WAITING_LATE_REWARD";
        var fake = new FakeRewardedAdService(store); var ads = new AdPurchaseService(store, fake);
        MustCommit(fake.QueueEvent(Request, store.Read().RunId, AdEventKind.Reward));
        MustCommit(ads.PollAd(Request, "late-reward-poll", store.Read().Revision));
    }
    static void PrepareWaiting(string directory)
    {
        check = "PREPARE_DIRECTORY";
        if (Directory.Exists(directory)) throw new InvalidOperationException("Refuse fixture reuse");
        Directory.CreateDirectory(directory);
        string seeded, before, expected;
        using (var store = new FileStateStore(Path.Combine(directory, "actual"), Initial(WaitingScenario)))
        { BeginWaiting(store); seeded = Hash(store.Read()); }
        using (var store = new FileStateStore(Path.Combine(directory, "expected"), Initial(WaitingScenario)))
        {
            BeginWaiting(store); check = "PREPARE_EQUAL";
            if (Hash(store.Read()) != seeded) throw new InvalidOperationException();
            CloseWaiting(store); before = Hash(store.Read());
            ReleaseLateReward(store); expected = Hash(store.Read());
        }
        File.WriteAllText(Path.Combine(directory, "expected.json"), JsonSerializer.Serialize(new { seeded, before, expected }));
    }
    static void CrashWaiting(string directory)
    {
        using (var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(directory, "expected.json"))))
        using (var store = new FileStateStore(Path.Combine(directory, "actual"), Initial(WaitingScenario)))
        {
            check = "WAITING_SEEDED";
            if (!store.CanMutate || Hash(store.Read()) != doc.RootElement.GetProperty("seeded").GetString()) throw new InvalidOperationException();
            // This child durably enters CLOSED_AWAITING_REWARD itself. No reward
            // exists in this save and its writer remains open when SIGKILL lands.
            CloseWaiting(store); check = "WAITING_CHECKPOINT";
            if (Hash(store.Read()) != doc.RootElement.GetProperty("before").GetString()) throw new InvalidOperationException();
            PauseForKill(Path.Combine(directory, "ready"), WaitingPoint);
        }
    }
    static object WaitingObservation(RunState state) => new {
        phase = state.Ad.Phase.ToString(), cashMinor = state.CashMinor, stockAvailable = state.StockAvailable,
        drawerCount = state.Drawers.Count(x => x != null), adSuccessesToday = state.AdSuccessesToday,
        lastAdSettlementCount = state.SettledCountAtLastAdSuccess, rewardRecorded = state.Ad.RewardRecorded,
        rewardEventCount = state.FakeEvents.Count(e => e.Kind == AdEventKind.Reward), shownRequestCount = state.FakeShownRequests.Count,
        commandCount = state.Commands.Count, revision = state.Revision };
    static void VerifyWaiting(string directory)
    {
        using (var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(directory, "expected.json"))))
        using (var store = new FileStateStore(Path.Combine(directory, "actual"), Initial(WaitingScenario)))
        {
            check = "WAITING_RECOVERY";
            string before = doc.RootElement.GetProperty("before").GetString(), expected = doc.RootElement.GetProperty("expected").GetString();
            var recovered = store.Recover("ad-event:" + Request + ":Closed");
            string recoveredHash = Hash(store.Read());
            if (!recovered.Committed || !store.CanMutate || recoveredHash != before) throw new InvalidOperationException();
            var waiting = store.Read(); AssertWaiting(waiting);
            var fake = new FakeRewardedAdService(store); var ads = new AdPurchaseService(store, fake);
            // Polling after restart cannot infer no-reward, consume resources,
            // show another ad, or lose the original waiting request.
            check = "WAITING_REPOLL";
            MustCommit(ads.PollAd(Request, "restart-poll", store.Read().Revision));
            if (Hash(store.Read()) != before) throw new InvalidOperationException();
            AssertWaiting(store.Read());
            check = "WAITING_RESOURCE_LOCK";
            var blocked = ads.BuyNormally("waiting-normal-buy", store.Read().Revision);
            if (blocked.CommitStatus != CommitStatus.PROVEN_NOT_COMMITTED || blocked.Code != "RESOURCE_RESERVED" || Hash(store.Read()) != before)
                throw new InvalidOperationException();
            ReleaseLateReward(store);
            string finalHash = Hash(store.Read());
            check = "WAITING_DUPLICATE_REWARD";
            MustCommit(fake.QueueEvent(Request, store.Read().RunId, AdEventKind.Reward));
            MustCommit(ads.PollAd(Request, "duplicate-poll", -999));
            MustCommit(ads.CommitAd(Request, Request + ":commit", -999));
            var state = store.Read(); AssertReservation(state); StateInvariants.Validate(state);
            check = "WAITING_EXACTLY_ONCE";
            if (Hash(state) != finalHash || finalHash != expected || state.Ad.Phase != AdPhase.COMMITTED || !state.Ad.RewardRecorded ||
                state.CashMinor != NumberTicketRules.InitialCashMinor - NumberTicketRules.AdPriceMinor || state.StockAvailable ||
                state.Drawers.Count(x => x != null) != 1 || state.Drawers[waiting.Ad.ReservedDrawerSlot] == null ||
                state.AdSuccessesToday != 1 || state.SettledCountAtLastAdSuccess != 12 || state.Commands.Count != 10 || state.Revision != 10 ||
                state.Commands.Count(c => c.CommandId == Request + ":commit" && c.Kind == "AD_COMMIT" && c.CashDeltaMinor == -NumberTicketRules.AdPriceMinor) != 1 ||
                state.FakeEvents.Count(e => e.Kind == AdEventKind.Reward) != 1 || state.FakeShownRequests.Count != 1)
                throw new InvalidOperationException("Late or duplicate reward did not commit exactly once");
            check = "RESULT_WRITE";
            File.WriteAllText(Path.Combine(directory, "result.json"), JsonSerializer.Serialize(new {
                status = "PASS", scenario = WaitingScenario, point = WaitingPoint, recoveryStatus = recovered.CommitStatus.ToString(),
                beforeHash = before, expectedHash = expected, recoveredHash, finalHash, finalCashMinor = state.CashMinor,
                finalCommands = state.Commands.Count, attemptCommandOccurrences = 1, staleRevisionReplayUnchanged = true,
                requestId = state.Ad.RequestId, runId = state.RunId, waiting = WaitingObservation(waiting), final = WaitingObservation(state),
                waitingPollUnchanged = true, reservedPurchaseBlocked = true, duplicateRewardReplayUnchanged = true,
                originalReservationUnchanged = true }));
        }
    }
    static void PauseForKill(string marker, string point)
    {
        File.WriteAllText(marker, point);
        // Parent must actually SIGKILL this process, not ask it to throw/dispose.
        while (true) Thread.Sleep(100);
    }
    sealed class PauseAt : IStoreFaultInjector
    {
        readonly StoreFaultPoint target; readonly string marker;
        public PauseAt(string point, string marker) { target = (StoreFaultPoint)Enum.Parse(typeof(StoreFaultPoint), point); this.marker = marker; }
        public void OnPoint(StoreFaultPoint point)
        {
            if (point != target) return;
            PauseForKill(marker, point.ToString());
        }
    }
}

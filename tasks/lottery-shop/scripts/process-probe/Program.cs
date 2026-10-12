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
    const string Attempt = "kill-attempt", Request = "fake-request";
    static int Main(string[] args)
    {
        try
        {
            if (args.Length != 4) throw new InvalidOperationException();
            string mode = args[0], scenario = args[1], point = args[2], directory = args[3];
            if (!new[] {"buy", "scratch", "claim", "ad"}.Contains(scenario)) throw new InvalidOperationException();
            if (mode == "prepare") Prepare(scenario, directory);
            else if (mode == "crash")
            {
                using (var store = new FileStateStore(Path.Combine(directory, "actual"), Initial(scenario), new PauseAt(point, Path.Combine(directory, "ready"))))
                    MustCommit(Apply(scenario, store, store.Read().Revision));
                throw new InvalidOperationException("Expected kill point was not hit");
            }
            else if (mode == "verify") Verify(scenario, point, directory);
            else throw new InvalidOperationException();
            return 0;
        }
        catch { Console.Error.WriteLine("Bounded G2 process fixture failed."); return 1; }
    }
    static RunState Initial(string scenario)
    {
        var s = RunState.CreateNew("synthetic-process-" + scenario, "g2-process-fixed-seed");
        if (scenario == "ad") { s.FixtureLabel = "SYNTHETIC_AD_FIXTURE"; s.DayNumber = 2; s.FixtureBaseSettlements = s.SettledTicketCount = 12; }
        return s;
    }
    static void Setup(string scenario, FileStateStore store)
    {
        var tickets = new TicketService(store);
        if (scenario == "scratch" || scenario == "claim") MustCommit(tickets.BuyNumberTicket("setup-buy", store.Read().Revision));
        if (scenario == "claim")
        {
            var strokes = new List<ScratchStroke>();
            for (int y = 0; y <= 16; y++) strokes.Add(new ScratchStroke(0, y / 16.0, 1, y / 16.0, true, 16));
            MustCommit(tickets.ApplyScratch(store.Read().CurrentTicket.Id, "setup-reveal", store.Read().Revision, strokes.ToArray()));
            if (!store.Read().CurrentTicket.Scratch.IsFullyRevealed) throw new InvalidOperationException();
        }
        if (scenario == "ad")
        {
            var fake = new FakeRewardedAdService(store); var ads = new AdPurchaseService(store, fake);
            MustCommit(ads.BeginAd(Request, "setup-begin", store.Read().Revision, 60));
            MustCommit(fake.QueueEvent(Request, store.Read().RunId, AdEventKind.Reward));
            MustCommit(ads.RecordEvent(fake.ReadEvents(Request)[0], "setup-reward", store.Read().Revision));
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
        if (Directory.Exists(directory)) throw new InvalidOperationException("Refuse fixture reuse");
        Directory.CreateDirectory(directory);
        string before, expected;
        using (var store = new FileStateStore(Path.Combine(directory, "actual"), Initial(scenario))) { Setup(scenario, store); before = Hash(store.Read()); }
        using (var store = new FileStateStore(Path.Combine(directory, "expected"), Initial(scenario)))
        {
            Setup(scenario, store); if (Hash(store.Read()) != before) throw new InvalidOperationException();
            MustCommit(Apply(scenario, store, store.Read().Revision)); expected = Hash(store.Read());
        }
        File.WriteAllText(Path.Combine(directory, "expected.json"), JsonSerializer.Serialize(new { before, expected }));
    }
    static void Verify(string scenario, string point, string directory)
    {
        using (var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(directory, "expected.json"))))
        using (var store = new FileStateStore(Path.Combine(directory, "actual"), Initial(scenario)))
        {
            string before = doc.RootElement.GetProperty("before").GetString(), expected = doc.RootElement.GetProperty("expected").GetString();
            var recovered = store.Recover(Attempt); bool published = point == "AfterPublish" || point == "BeforeResponse";
            string recoveredHash = Hash(store.Read());
            if (recovered.CommitStatus != (published ? CommitStatus.COMMITTED : CommitStatus.PROVEN_NOT_COMMITTED) ||
                recoveredHash != (published ? expected : before) || !store.CanMutate) throw new InvalidOperationException("Wrong recovery boundary");
            MustCommit(Apply(scenario, store, store.Read().Revision));
            string finalHash = Hash(store.Read());
            MustCommit(Apply(scenario, store, -999)); // Committed lookup must precede stale-revision rejection.
            var state = store.Read(); StateInvariants.Validate(state);
            if (Hash(state) != finalHash || finalHash != expected || state.Commands.Count(c => c.CommandId == Attempt) != 1)
                throw new InvalidOperationException("Replay duplicated or changed a committed result");
            long expectedCash = NumberTicketRules.InitialCashMinor - (scenario == "ad" ? NumberTicketRules.AdPriceMinor : NumberTicketRules.PriceMinor);
            if (scenario == "claim") expectedCash += state.CurrentTicket.RawPrizeMinor;
            if (state.CashMinor != expectedCash || (scenario == "ad" && (state.Ad.Phase != AdPhase.COMMITTED || state.StockAvailable || state.Drawers.Count(x => x != null) != 1)))
                throw new InvalidOperationException("Independent wallet/stock invariant failed");
            File.WriteAllText(Path.Combine(directory, "result.json"), JsonSerializer.Serialize(new {
                status = "PASS", scenario, point, recoveryStatus = recovered.CommitStatus.ToString(), beforeHash = before,
                expectedHash = expected, recoveredHash, finalHash, finalCashMinor = state.CashMinor,
                finalCommands = state.Commands.Count, attemptCommandOccurrences = 1, staleRevisionReplayUnchanged = true }));
        }
    }
    sealed class PauseAt : IStoreFaultInjector
    {
        readonly StoreFaultPoint target; readonly string marker;
        public PauseAt(string point, string marker) { target = (StoreFaultPoint)Enum.Parse(typeof(StoreFaultPoint), point); this.marker = marker; }
        public void OnPoint(StoreFaultPoint point)
        {
            if (point != target) return;
            File.WriteAllText(marker, point.ToString());
            // Parent must actually SIGKILL this process, not ask it to throw/dispose.
            while (true) Thread.Sleep(100);
        }
    }
}

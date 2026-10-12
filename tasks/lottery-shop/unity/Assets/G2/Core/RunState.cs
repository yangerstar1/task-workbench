using System;
using System.Collections.Generic;
using System.Linq;
namespace Lottery.G2.Core
{
    public enum TicketPhase { ACTIVE, REVEALED_UNCLAIMED, SETTLED }
    public enum CommitStatus { COMMITTED, PROVEN_NOT_COMMITTED, COMMIT_UNKNOWN }
    public enum AdPhase { CREATED, RESERVED, SHOWING, CLOSED_AWAITING_REWARD, REWARD_CONFIRMED, COMMITTING, COMMITTED, ABORTED_NO_REWARD, RECOVERY_CONFLICT }
    public sealed class TicketState
    {
        public string Id, TicketType = "number", PreviousSettledTicketType = "", EconomicAlgorithm = "lottery-sha256-stream-v1";
        public TicketPhase Phase;
        public NumberFace Face;
        public long RawPrizeMinor, PriceMinor, CashAfterPurchaseMinor;
        public int PurchasedPosition;
        public ulong EconomicCounterBefore, EconomicCounterAfter;
        public string[] ConfigurationSnapshot = Array.Empty<string>();
        public int SettledCountSnapshot;
        public ScratchMask Scratch = new ScratchMask();
    }
    public sealed class CommandReceipt
    {
        public string CommandId, RequestDigest, Kind, TicketId = "", Code = "SUCCESS";
        public long Revision, CashDeltaMinor;
    }
    public sealed class SettlementRecord
    {
        public string TicketId;
        public long RawPrizeMinor, AdditionMinor, TotalMinor, TicketPriceMinor, NetMinor;
    }
    public sealed class AdTransaction
    {
        public string RequestId, RunId, StockId, ItemId, Quality, Version = "g2-fake-ad-transaction-v1";
        public AdPhase Phase;
        public long ReservedPriceMinor;
        public int ReservedDrawerSlot, DayNumber;
        public bool RewardRecorded;
        public string Conflict = "", CreateCommandId, ReserveCommandId, ShowingCommandId, CommittingCommandId, CommitCommandId;
    }
    public sealed class DrawerItem { public string StockId, ItemId, Quality; }
    public sealed class RunState
    {
        public const int CurrentSchema = 1;
        public int SchemaVersion = CurrentSchema;
        public string RulesHash = NumberTicketRules.RulesSha256, RunId, Seed, FixtureLabel = "";
        public long Revision, InitialCashMinor = NumberTicketRules.InitialCashMinor, CashMinor = NumberTicketRules.InitialCashMinor;
        public int DayNumber = 1, TicketsPurchasedToday, SettledTicketCount, FixtureBaseSettlements, AdSuccessesToday, SettledCountAtLastAdSuccess = -1;
        public ulong EconomicCounter;
        public bool StockAvailable = true;
        public List<TicketState> Tickets = new List<TicketState>();
        public List<SettlementRecord> Settlements = new List<SettlementRecord>();
        public List<CommandReceipt> Commands = new List<CommandReceipt>();
        public DrawerItem[] Drawers = new DrawerItem[NumberTicketRules.DrawerSlots];
        public AdTransaction Ad;
        public List<Ads.FakeAdEvent> FakeEvents = new List<Ads.FakeAdEvent>();
        public List<string> FakeShownRequests = new List<string>();
        // Read-only observations supplied by the store; not part of committed ledger bytes.
        public string PendingCommandId = "";
        public bool RecoveryRequired;
        public TicketState CurrentTicket => Tickets.Count == 0 ? null : Tickets[Tickets.Count - 1];
        public static RunState CreateNew(string runId, string seed)
        {
            if (string.IsNullOrWhiteSpace(runId) || string.IsNullOrWhiteSpace(seed)) throw new ArgumentException("Run identity and seed are required");
            return new RunState { RunId = runId, Seed = seed };
        }
        public RunState Copy()
        {
            var copy = StateCodec.DeserializeCanonical(StateCodec.SerializeCanonical(this));
            copy.PendingCommandId = PendingCommandId; copy.RecoveryRequired = RecoveryRequired; return copy;
        }
    }
    public sealed class CommandResult
    {
        public CommitStatus CommitStatus;
        public string Code;
        public CommandReceipt Receipt;
        public RunState State;
        public CommitStatus Status => CommitStatus;
        public bool Committed => CommitStatus == Lottery.G2.Core.CommitStatus.COMMITTED;
    }
    public interface IStateStore
    {
        RunState Read();
        bool CanMutate { get; }
        string ConfirmedHash { get; }
        CommandResult Execute(string commandId, string requestDigest, long expectedRevision, Func<RunState, CommandReceipt> apply);
        CommandResult Recover(string commandId);
    }
    public sealed class RuleViolation : Exception { public string Code { get; } public RuleViolation(string code) : base(code) { Code = code; } }
    public static class StateInvariants
    {
        public static void Validate(RunState state)
        {
            if (state == null || state.SchemaVersion != RunState.CurrentSchema || state.RulesHash != NumberTicketRules.RulesSha256) throw new InvalidOperationException("Unsupported state schema or rules");
            if (string.IsNullOrEmpty(state.RunId) || string.IsNullOrEmpty(state.Seed) || state.Revision < 0 || state.CashMinor < 0 || state.InitialCashMinor < 0 || state.DayNumber < 1) throw new InvalidOperationException("Invalid run header");
            if (state.FixtureLabel != "" && state.FixtureLabel != "SYNTHETIC_AD_FIXTURE") throw new InvalidOperationException("Unknown fixture");
            if (state.FixtureLabel == "" && (state.InitialCashMinor != NumberTicketRules.InitialCashMinor || state.FixtureBaseSettlements != 0 || state.DayNumber != 1)) throw new InvalidOperationException("Unexpected normal-run baseline");
            if (state.TicketsPurchasedToday != state.Tickets.Count || state.Tickets.Count > NumberTicketRules.DailyTicketLimit) throw new InvalidOperationException("Ticket count mismatch");
            var ids = new HashSet<string>(); int active = 0; ulong counter = 0;
            foreach (var ticket in state.Tickets)
            {
                if (ticket == null || !ids.Add(ticket.Id) || ticket.PriceMinor != NumberTicketRules.PriceMinor || ticket.TicketType != "number" || ticket.PurchasedPosition != ids.Count || ticket.ConfigurationSnapshot == null || ticket.ConfigurationSnapshot.Length != 0 || ticket.CashAfterPurchaseMinor < 0 || ticket.SettledCountSnapshot != state.FixtureBaseSettlements + ids.Count - 1) throw new InvalidOperationException("Invalid locked ticket snapshot");
                if (ticket.EconomicAlgorithm != "lottery-sha256-stream-v1" || ticket.EconomicCounterBefore != counter) throw new InvalidOperationException("Wrong economic checkpoint");
                var economic = new DeterministicStream(state.Seed, NumberTicketRules.EconomicDomain, counter);
                if (ticket.RawPrizeMinor != NumberTicketRules.PrizeForSample(economic.Next(NumberTicketRules.ProbabilityDenominator)) || ticket.EconomicCounterAfter != economic.Counter) throw new InvalidOperationException("Locked award mismatch");
                counter = economic.Counter;
                NumberTicketRules.ValidateFace(ticket.Face, ticket.RawPrizeMinor);
                var expectedFace = NumberTicketRules.BuildFace(state.Seed, ticket.Id, ticket.RawPrizeMinor);
                if (expectedFace.WinningNumber != ticket.Face.WinningNumber || expectedFace.Cells.Where((c, i) => c.Number != ticket.Face.Cells[i].Number || c.PrizeMinor != ticket.Face.Cells[i].PrizeMinor).Any()) throw new InvalidOperationException("Locked display mismatch");
                if (ticket.Scratch == null || !Enum.IsDefined(typeof(TicketPhase), ticket.Phase)) throw new InvalidOperationException("Invalid ticket state");
                if (ticket.Phase == TicketPhase.ACTIVE && ticket.Scratch.IsFullyRevealed) throw new InvalidOperationException("Revealed ticket marked active");
                if (ticket.Phase != TicketPhase.ACTIVE && !ticket.Scratch.IsFullyRevealed) throw new InvalidOperationException("Unrevealed settlement");
                if (ticket.Phase != TicketPhase.SETTLED) { active++; if (!ReferenceEquals(ticket, state.CurrentTicket)) throw new InvalidOperationException("Occupied older ticket"); }
            }
            if (active > 1 || counter != state.EconomicCounter) throw new InvalidOperationException("Ticket slot/economic count mismatch");
            var settledIds = new HashSet<string>();
            foreach (var settlement in state.Settlements)
            {
                var ticket = state.Tickets.SingleOrDefault(t => t.Id == settlement.TicketId);
                if (ticket == null || ticket.Phase != TicketPhase.SETTLED || !settledIds.Add(settlement.TicketId) || settlement.RawPrizeMinor != ticket.RawPrizeMinor || settlement.AdditionMinor != 0 || settlement.TotalMinor != ticket.RawPrizeMinor || settlement.TicketPriceMinor != ticket.PriceMinor || settlement.NetMinor != settlement.TotalMinor - settlement.TicketPriceMinor) throw new InvalidOperationException("Invalid settlement ledger");
            }
            if (state.Tickets.Count(t => t.Phase == TicketPhase.SETTLED) != state.Settlements.Count || state.SettledTicketCount != state.FixtureBaseSettlements + state.Settlements.Count) throw new InvalidOperationException("Settlement count mismatch");
            var commandIds = new HashSet<string>(); long wallet = state.InitialCashMinor; long revision = 0;
            foreach (var c in state.Commands)
            {
                if (c == null || string.IsNullOrEmpty(c.CommandId) || !commandIds.Add(c.CommandId) || c.RequestDigest == null || c.RequestDigest.Length != 64 || c.Revision != ++revision || c.Code != "SUCCESS") throw new InvalidOperationException("Invalid command journal");
                wallet = checked(wallet + c.CashDeltaMinor); if (wallet < 0) throw new InvalidOperationException("Negative wallet ledger");
            }
            foreach (var c in state.Commands)
            {
                switch (c.Kind)
                {
                    case "BUY_TICKET": case "CLAIM": break;
                    case "BUY_STOCK": if (c.CashDeltaMinor != -NumberTicketRules.StockPriceMinor) throw new InvalidOperationException("Wrong stock debit"); break;
                    case "AD_COMMIT": if (c.CashDeltaMinor != -NumberTicketRules.AdPriceMinor) throw new InvalidOperationException("Wrong ad debit"); break;
                    case "SCRATCH": case "AD_CREATE": case "AD_RESERVE": case "AD_SHOWING": case "AD_EVENT": case "AD_COMMITTING": case "AD_CONFLICT": case "FAKE_SHOW": case "FAKE_EVENT":
                        if (c.CashDeltaMinor != 0) throw new InvalidOperationException("Unexpected money movement"); break;
                    default: throw new InvalidOperationException("Unknown command kind");
                }
            }
            if (wallet != state.CashMinor || revision != state.Revision) throw new InvalidOperationException("Wallet or revision mismatch");
            if (state.Commands.Count(c => c.Kind == "BUY_TICKET") != state.Tickets.Count || state.Commands.Count(c => c.Kind == "CLAIM") != state.Settlements.Count) throw new InvalidOperationException("Ticket command mismatch");
            foreach (var t in state.Tickets)
            {
                var buy = state.Commands.SingleOrDefault(c => c.Kind == "BUY_TICKET" && c.TicketId == t.Id);
                if (buy == null || buy.CashDeltaMinor != -t.PriceMinor || t.CashAfterPurchaseMinor != state.InitialCashMinor + state.Commands.Where(c => c.Revision <= buy.Revision).Sum(c => c.CashDeltaMinor) || t.PreviousSettledTicketType != (t.PurchasedPosition == 1 ? "" : "number")) throw new InvalidOperationException("Missing purchase debit");
                var claim = state.Commands.SingleOrDefault(c => c.Kind == "CLAIM" && c.TicketId == t.Id);
                if ((t.Phase == TicketPhase.SETTLED) != (claim != null) || (claim != null && claim.CashDeltaMinor != t.RawPrizeMinor)) throw new InvalidOperationException("Missing unique credit");
            }
            if (state.Drawers == null || state.Drawers.Length != NumberTicketRules.DrawerSlots || state.AdSuccessesToday < 0 || state.AdSuccessesToday > 1) throw new InvalidOperationException("Invalid shop state");
            var stock = state.Drawers.Where(d => d != null).ToArray();
            if (stock.Length > 1 || (stock.Length == 1) != !state.StockAvailable || stock.Any(d => d.StockId != NumberTicketRules.StockId || d.ItemId != NumberTicketRules.StockItemId || d.Quality != NumberTicketRules.StockQuality)) throw new InvalidOperationException("Invalid fixed stock");
            if (state.Commands.Count(c => c.Kind == "BUY_STOCK" || c.Kind == "AD_COMMIT") != stock.Length || state.Commands.Count(c => c.Kind == "AD_COMMIT") != state.AdSuccessesToday || state.Commands.Count(c => c.Kind == "FAKE_EVENT") != state.FakeEvents.Count || state.Commands.Count(c => c.Kind == "FAKE_SHOW") != state.FakeShownRequests.Count) throw new InvalidOperationException("Shop/provider ledger mismatch");
            if (state.FakeEvents.Select(e => e.EventId).Distinct().Count() != state.FakeEvents.Count || state.FakeShownRequests.Distinct().Count() != state.FakeShownRequests.Count) throw new InvalidOperationException("Duplicate provider receipt");
            if (state.Ad != null)
            {
                var ad = state.Ad;
                if (string.IsNullOrEmpty(ad.CreateCommandId) || string.IsNullOrEmpty(ad.ReserveCommandId) || string.IsNullOrEmpty(ad.ShowingCommandId) || string.IsNullOrEmpty(ad.CommittingCommandId) || string.IsNullOrEmpty(ad.CommitCommandId) || ad.RunId != state.RunId || string.IsNullOrEmpty(ad.RequestId) || !Enum.IsDefined(typeof(AdPhase), ad.Phase) || ad.StockId != NumberTicketRules.StockId || ad.ItemId != NumberTicketRules.StockItemId || ad.Quality != NumberTicketRules.StockQuality || ad.ReservedPriceMinor != NumberTicketRules.AdPriceMinor || ad.ReservedDrawerSlot < 0 || ad.ReservedDrawerSlot >= 2 || ad.DayNumber != state.DayNumber) throw new InvalidOperationException("Invalid ad commitment");
                if (Ads.AdPurchaseService.HasReservation(ad) && ad.Phase != AdPhase.RECOVERY_CONFLICT && (!state.StockAvailable || state.Drawers[ad.ReservedDrawerSlot] != null || state.CashMinor < ad.ReservedPriceMinor)) throw new InvalidOperationException("Lost ad reservation");
                if (ad.Phase == AdPhase.COMMITTED && (!ad.RewardRecorded || state.StockAvailable || state.AdSuccessesToday != 1)) throw new InvalidOperationException("Invalid rewarded purchase");
            }
        }
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Lottery.G2.Core;

namespace Lottery.G3.Core
{
    public enum DayPhase { DAY_OPEN, CLOSING_PREP, NIGHT_BILL, DAY_COMPLETE, RUN_FAILED }
    public enum TicketPhase { ACTIVE, REVEALED_UNCLAIMED, SETTLED }
    public enum CommitStatus { COMMITTED, PROVEN_NOT_COMMITTED, COMMIT_UNKNOWN }
    public enum AdPhase { CREATED, RESERVED, SHOWING, CLOSED_AWAITING_REWARD, REWARD_CONFIRMED, COMMITTING, COMMITTED, ABORTED_NO_REWARD, RECOVERY_CONFLICT }
    public sealed class RuleViolation : Exception { public string Code { get; } public RuleViolation(string code) : base(code) { Code = code; } }
    public interface IStateStore
    {
        RunState Read(); bool CanMutate { get; } string ConfirmedHash { get; }
        CommandResult Execute(string commandId, string requestDigest, long expectedRevision, Func<RunState, CommandReceipt> apply);
        CommandResult Recover(string commandId);
    }
    public sealed class CommandReceipt
    {
        public string CommandId = "", RequestDigest = "", Kind = "", TicketId = "", Code = "";
        public long Revision, CashDeltaMinor;
    }
    public sealed class CommandResult
    {
        public CommitStatus CommitStatus; public string Code = ""; public CommandReceipt Receipt; public RunState State;
        public bool Success => CommitStatus == CommitStatus.COMMITTED;
    }
    public sealed class ToolSnapshot { public string ItemId = ""; public int Level; }
    public sealed class OwnedTool { public string ItemId = ""; public int Level; public long InitialPaymentMinor; }
    public sealed class ToolCounter { public string ItemId = ""; public int UsedToday, ClipTicks; }
    public sealed class StockItem
    {
        public string StockId = "", ItemId = "", Quality = "common"; public bool IsConsumable;
        public long PriceMinor; public int Quantity = 1;
    }
    public sealed class DrawerItem { public string StockId = "", ItemId = "", Quality = "common"; public long PurchasePriceMinor; }
    public sealed class LoanRecord
    {
        public string LoanId = "", ContactId = ""; public long BorrowedMinor, RemainingMinor; public int BorrowedDay, DueNight;
    }
    public sealed class ContactState { public string ContactId = ""; public long BorrowedLifetimeMinor; }
    public sealed class PhoneEvent { public string EventId = "", ContactId = "", Kind = "", LoanId = ""; public long AmountMinor; public int Day, DueNight; }
    public sealed class LedgerEntry { public string CommandId = "", Kind = "", ReferenceId = ""; public long DeltaMinor, BalanceMinor; }
    public sealed class PayoutEntry { public string Source = ""; public long AmountMinor; }
    public sealed class SettlementRecord
    {
        public string TicketId = ""; public long RawPrizeMinor, TotalMinor, TicketPriceMinor, ConsumableCostMinor, NetMinor;
        public List<PayoutEntry> Entries = new List<PayoutEntry>();
    }
    public sealed class AdTransaction
    {
        public string RequestId = "", RunId = "", StockId = "", ItemId = "", Quality = "", Version = "g3-fake-ad-v1", Conflict = "";
        public string CreateCommandId = "", ReserveCommandId = "", ShowingCommandId = "", CommittingCommandId = "", CommitCommandId = "";
        public AdPhase Phase; public long ReservedPriceMinor; public int ReservedDrawerSlot, DayNumber; public bool RewardRecorded;
    }
    public sealed class AdEventRecord { public string EventId = "", RequestId = "", RunId = "", Kind = ""; }
    public sealed class ConsumableUse { public string ItemId = "", Quality = "", StockId = ""; public long PurchasePriceMinor, LockedAmountMinor; public int[] TargetCells = new int[0]; }
    public sealed class TicketState
    {
        public string Id = "", PurchaseCommandId = "", TicketType = "number", PreviousSettledTicketType = "", SelectionId = "", InformationSource = "";
        public TicketPhase Phase; public long PriceMinor = 1000, RawPrizeMinor, CashAfterPurchaseMinor, CopyMinor, ProtectionMinor, ConsumableCostMinor;
        public int PurchasedPosition, SelectedCell = -1, SafeCount, EconomicDrawCount = 1; public bool Busted, LampUsed;
        public ToolSnapshot[] ConfigurationSnapshot = new ToolSnapshot[0]; public NumberFace Face;
        public TicketMask Scratch; public bool[] ChallengeSafe = new bool[0], RevealedCells = new bool[0], PeekedCells = new bool[0];
        public List<string> UsedConsumableTypes = new List<string>();
        public List<ConsumableUse> ConsumableUses = new List<ConsumableUse>();
        public ulong EconomicCounterBefore, EconomicCounterAfter, ChallengeCounterBefore, ChallengeCounterAfter;
    }
    public sealed class ClaimBuyIntent { public string IntentId = "", TicketId = "", NextTicketType = "", ClaimCommandId = "", BuyCommandId = ""; public int BoostDrawerSlot; public bool Cancelled; }
    public sealed class NightBill
    {
        public long PrincipalDueMinor, InterestUnpaidMinor, TotalDueMinor, AvailableCashMinor, ShortfallMinor, NextDayInterestMinor;
        public int RemainingOpportunities;
    }
    public sealed class RunState
    {
        public const int CurrentSchema = 1;
        public int SchemaVersion = CurrentSchema; public string RulesHash = NumberTicketRules.RulesSha256, RunId = "", Seed = "", FixtureLabel = "";
        public long Revision, InitialCashMinor = 30000, CashMinor = 30000, PrincipalMinor = 300000, PrincipalAtOpenMinor = 300000, PrincipalRepaidMinor, InterestDueMinor = 1500, InterestPaidMinor;
        public int DayNumber = 1, TicketsPurchasedToday, SettledTicketCount, LifetimeEffectiveTickets, LifetimeEffectiveAtOpen;
        public DayPhase Phase; public ulong EconomicCounter, ChallengeCounter, ShopCounter;
        public List<TicketState> Tickets = new List<TicketState>(); public List<StockItem> Stock = new List<StockItem>(); public List<OwnedTool> Tools = new List<OwnedTool>();
        public string[] NextToolIds = { "", "", "" }; public DrawerItem[] Drawers = new DrawerItem[2]; public List<ToolCounter> ToolCounters = new List<ToolCounter>();
        public List<LoanRecord> Loans = new List<LoanRecord>(); public List<ContactState> Contacts = new List<ContactState>();
        public List<ClaimBuyIntent> ClaimBuyIntents = new List<ClaimBuyIntent>();
        public List<SettlementRecord> Settlements = new List<SettlementRecord>(); public List<CommandReceipt> Commands = new List<CommandReceipt>();
        public List<LedgerEntry> Ledger = new List<LedgerEntry>(); public List<PhoneEvent> PhoneEvents = new List<PhoneEvent>();
        public string[] ConsumableBatch = new string[4]; public AdTransaction Ad;
        public int AdSuccessesToday, SettledCountAtLastAdSuccess, FixtureBaseSettlements; public long FirstLaunchElapsedSeconds;
        public List<AdEventRecord> AdEvents = new List<AdEventRecord>(); public List<string> FakeShownRequests = new List<string>();
        // Diagnostic arrangements are admitted only during creation. Normal saves contain no overrides.
        public List<bool[]> DiagnosticChallengeArrangements = new List<bool[]>();
        public bool RecoveryRequired; public string PendingCommandId = "";
        public TicketState CurrentTicket => Tickets.Count == 0 ? null : Tickets[Tickets.Count - 1];
        public bool HasUnsettledTicket => CurrentTicket != null && CurrentTicket.Phase != TicketPhase.SETTLED;
        public long AvailableCashMinor => CashMinor - (AdReservations.HasReservation(Ad) ? Ad.ReservedPriceMinor : 0);
        public RunState Copy() => StateCodec.DeserializeCanonical(StateCodec.SerializeCanonical(this));
    }
    public static class AdReservations
    {
        public static bool HasReservation(AdTransaction a) => a != null && a.Phase != AdPhase.CREATED && a.Phase != AdPhase.COMMITTED && a.Phase != AdPhase.ABORTED_NO_REWARD;
        public static bool HasPending(AdTransaction a) => a != null && a.Phase != AdPhase.COMMITTED && a.Phase != AdPhase.ABORTED_NO_REWARD;
        public static bool DrawerReserved(RunState s, int slot) => HasReservation(s.Ad) && s.Ad.ReservedDrawerSlot == slot;
        public static bool StockReserved(RunState s, string id) => HasReservation(s.Ad) && s.Ad.StockId == id;
    }
    public static class CommandDigest
    {
        public static string Create(string runId, string kind, Action<BinaryWriter> fields = null)
        {
            using (var stream = new MemoryStream()) using (var writer = new BinaryWriter(stream))
            { writer.Write(runId ?? ""); writer.Write(kind); fields?.Invoke(writer); writer.Flush(); return StateCodec.HashBytes(stream.ToArray()); }
        }
    }
}

using System;
using System.Linq;
using Lottery.G2.Core;
namespace Lottery.G2.Ads
{
    public sealed class AdAvailability
    {
        public bool CanBuyNormally, CanWatchAd;
        public string Reason, StockId = NumberTicketRules.StockId, Quality = NumberTicketRules.StockQuality;
        public long FullPriceMinor = NumberTicketRules.StockPriceMinor, DiscountPriceMinor = NumberTicketRules.AdPriceMinor;
        public int FreeDrawerSlots;
    }
    public sealed class AdPurchaseService
    {
        readonly IStateStore store;
        readonly IRewardedAdService ads;
        public AdPurchaseService(IStateStore store, IRewardedAdService ads) { this.store = store ?? throw new ArgumentNullException(nameof(store)); this.ads = ads ?? throw new ArgumentNullException(nameof(ads)); }
        public static bool HasReservation(AdTransaction ad) => ad != null && ad.Phase != AdPhase.CREATED && ad.Phase != AdPhase.COMMITTED && ad.Phase != AdPhase.ABORTED_NO_REWARD;
        public AdAvailability GetAvailability(long elapsedSeconds)
        {
            var s = store.Read(); string reason = Eligibility(s, elapsedSeconds);
            if (!store.CanMutate) reason = s.RecoveryRequired ? "RECOVERY_REQUIRED" : "COMMIT_UNKNOWN";
            else if (!ads.IsAvailable) reason = "AD_SERVICE_UNAVAILABLE";
            return new AdAvailability { FreeDrawerSlots = s.Drawers.Count(x => x == null) - (HasReservation(s.Ad) ? 1 : 0), CanBuyNormally = store.CanMutate && s.StockAvailable && !HasReservation(s.Ad) && s.Drawers.Any(x => x == null) && s.CashMinor >= NumberTicketRules.StockPriceMinor,
                CanWatchAd = reason == "", Reason = reason };
        }
        static string Eligibility(RunState s, long seconds)
        {
            if (s.Ad != null) return s.Ad.Phase == AdPhase.RECOVERY_CONFLICT ? "RECOVERY_REQUIRED" : "AD_TRANSACTION_EXISTS";
            if (s.DayNumber == 1) return "AD_TUTORIAL_DAY";
            if (seconds < NumberTicketRules.AdMinimumSeconds) return "AD_FIRST_LAUNCH_DELAY";
            if (s.SettledTicketCount < NumberTicketRules.AdMinimumSettlements) return "AD_MINIMUM_SETTLEMENTS";
            if (s.AdSuccessesToday >= NumberTicketRules.AdDailySuccessCap) return "AD_DAILY_CAP";
            if (s.SettledCountAtLastAdSuccess >= 0 && s.SettledTicketCount - s.SettledCountAtLastAdSuccess < NumberTicketRules.AdCooldownSettlements) return "AD_COOLDOWN";
            if (!s.StockAvailable) return "STOCK_UNAVAILABLE";
            if (!s.Drawers.Any(x => x == null)) return "DRAWER_FULL";
            if (s.CashMinor < NumberTicketRules.AdPriceMinor) return "INSUFFICIENT_CASH";
            return "";
        }
        public CommandResult BuyNormally(string commandId, long expectedRevision)
        {
            return store.Execute(commandId, CommandDigest.Create(store.Read().RunId, "BUY_STOCK"), expectedRevision, s =>
            {
                if (!s.StockAvailable) throw new RuleViolation("STOCK_UNAVAILABLE");
                if (HasReservation(s.Ad)) throw new RuleViolation("RESOURCE_RESERVED");
                int slot = Array.FindIndex(s.Drawers, x => x == null); if (slot < 0) throw new RuleViolation("DRAWER_FULL");
                if (s.CashMinor < NumberTicketRules.StockPriceMinor) throw new RuleViolation("INSUFFICIENT_CASH");
                s.CashMinor -= NumberTicketRules.StockPriceMinor; s.StockAvailable = false; s.Drawers[slot] = NewItem();
                return new CommandReceipt { Kind = "BUY_STOCK", CashDeltaMinor = -NumberTicketRules.StockPriceMinor };
            });
        }
        public CommandResult CreateAd(string requestId, string commandId, long expectedRevision, long elapsedSeconds)
        {
            return store.Execute(commandId, CommandDigest.Create(store.Read().RunId, "AD_CREATE", w => { w.Write(requestId ?? ""); w.Write(elapsedSeconds); }), expectedRevision, s =>
            {
                if (!ads.IsAvailable) throw new RuleViolation("AD_SERVICE_UNAVAILABLE");
                if (string.IsNullOrWhiteSpace(requestId) || requestId.Length > 128 || requestId.Any(char.IsControl) || commandId.Length > 220) throw new RuleViolation("INVALID_REQUEST");
                string reason = Eligibility(s, elapsedSeconds); if (reason != "") throw new RuleViolation(reason);
                s.Ad = new AdTransaction { RequestId = requestId, RunId = s.RunId, StockId = NumberTicketRules.StockId, ItemId = NumberTicketRules.StockItemId, Quality = NumberTicketRules.StockQuality,
                    CreateCommandId = commandId, ReserveCommandId = commandId + ":reserve", ShowingCommandId = commandId + ":showing", CommittingCommandId = requestId + ":committing", CommitCommandId = requestId + ":commit",
                    ReservedPriceMinor = NumberTicketRules.AdPriceMinor, ReservedDrawerSlot = Array.FindIndex(s.Drawers, x => x == null), DayNumber = s.DayNumber, Phase = AdPhase.CREATED };
                return new CommandReceipt { Kind = "AD_CREATE" };
            });
        }
        public CommandResult ReserveAd(string requestId, string commandId, long expectedRevision)
        {
            return Step(requestId, commandId, expectedRevision, "AD_RESERVE", s =>
            {
                if (s.Ad.Phase != AdPhase.CREATED) throw new RuleViolation("AD_WRONG_PHASE");
                if (!ResourcesIntact(s)) { s.Ad.Phase = AdPhase.RECOVERY_CONFLICT; s.Ad.Conflict = "Reservation target changed before reserve"; }
                else s.Ad.Phase = AdPhase.RESERVED;
            });
        }
        public CommandResult MarkShowing(string requestId, string commandId, long expectedRevision)
        { return Step(requestId, commandId, expectedRevision, "AD_SHOWING", s => { if (s.Ad.Phase != AdPhase.RESERVED) throw new RuleViolation("AD_WRONG_PHASE"); s.Ad.Phase = AdPhase.SHOWING; }); }
        public CommandResult BeginAd(string requestId, string commandId, long expectedRevision, long elapsedSeconds)
        {
            var result = CreateAd(requestId, commandId, expectedRevision, elapsedSeconds); if (!result.Committed) return result;
            result = ReserveAd(requestId, commandId + ":reserve", result.State.Revision); if (!result.Committed) return result;
            if (result.State.Ad.Phase == AdPhase.RECOVERY_CONFLICT) return result;
            result = MarkShowing(requestId, commandId + ":showing", result.State.Revision); if (!result.Committed) return result;
            return ads.Show(requestId, result.State.RunId);
        }
        public CommandResult RecordEvent(FakeAdEvent receipt, string commandId, long expectedRevision)
        {
            if (receipt == null) return Rejection("INVALID_REQUEST");
            return store.Execute(commandId, CommandDigest.Create(store.Read().RunId, "AD_EVENT", w => { w.Write(receipt.EventId ?? ""); w.Write(receipt.RequestId ?? ""); w.Write(receipt.RunId ?? ""); w.Write((int)receipt.Kind); }), expectedRevision, s =>
            {
                var ad = s.Ad;
                if (ad == null || receipt.RequestId != ad.RequestId || receipt.RunId != ad.RunId) throw new RuleViolation("AD_REQUEST_MISMATCH");
                // The callback must be backed by the persistent provider receipt source.
                if (!ads.ReadEvents(ad.RequestId).Any(e => e.EventId == receipt.EventId && e.RequestId == receipt.RequestId && e.RunId == receipt.RunId && e.Kind == receipt.Kind)) throw new RuleViolation("AD_RECEIPT_UNVERIFIED");
                if (ad.Phase == AdPhase.RECOVERY_CONFLICT) throw new RuleViolation("RECOVERY_REQUIRED");
                if (receipt.Kind == AdEventKind.Reward)
                {
                    if (ad.Phase == AdPhase.ABORTED_NO_REWARD || !ResourcesIntact(s) && ad.Phase != AdPhase.COMMITTED || ad.Phase == AdPhase.CREATED)
                    { ad.Phase = AdPhase.RECOVERY_CONFLICT; ad.Conflict = "Reward conflicts with terminal state or original reservation"; }
                    else if (ad.Phase != AdPhase.COMMITTED && ad.Phase != AdPhase.COMMITTING) { ad.RewardRecorded = true; ad.Phase = AdPhase.REWARD_CONFIRMED; }
                }
                else if (receipt.Kind == AdEventKind.Closed)
                {
                    if (ad.Phase == AdPhase.SHOWING) ad.Phase = AdPhase.CLOSED_AWAITING_REWARD;
                    // A close after reward or commit never reverses it.
                }
                else if (receipt.Kind == AdEventKind.NoFill || receipt.Kind == AdEventKind.NotShown || receipt.Kind == AdEventKind.NoRewardTerminal)
                {
                    if (ad.RewardRecorded || ad.Phase == AdPhase.COMMITTED) { ad.Phase = AdPhase.RECOVERY_CONFLICT; ad.Conflict = "No-reward terminal conflicts with verified reward"; }
                    else ad.Phase = AdPhase.ABORTED_NO_REWARD;
                }
                else throw new RuleViolation("INVALID_REQUEST");
                return new CommandReceipt { Kind = "AD_EVENT" };
            });
        }
        public CommandResult MarkCommitting(string requestId, string commandId, long expectedRevision)
        { return Step(requestId, commandId, expectedRevision, "AD_COMMITTING", s => { if (s.Ad.Phase != AdPhase.REWARD_CONFIRMED || !s.Ad.RewardRecorded) throw new RuleViolation("AD_WRONG_PHASE"); s.Ad.Phase = AdPhase.COMMITTING; }); }
        public CommandResult CommitAd(string requestId, string commandId, long expectedRevision)
        {
            return store.Execute(commandId, CommandDigest.Create(store.Read().RunId, "AD_COMMIT", w => w.Write(requestId ?? "")), expectedRevision, s =>
            {
                RequireAd(s, requestId);
                if (s.Ad.Phase != AdPhase.COMMITTING || !s.Ad.RewardRecorded) throw new RuleViolation("AD_WRONG_PHASE");
                s.Ad.CommitCommandId = commandId;
                if (!ResourcesIntact(s)) { s.Ad.Phase = AdPhase.RECOVERY_CONFLICT; s.Ad.Conflict = "Original reservation cannot be committed"; return new CommandReceipt { Kind = "AD_CONFLICT" }; }
                s.CashMinor -= s.Ad.ReservedPriceMinor; s.StockAvailable = false; s.Drawers[s.Ad.ReservedDrawerSlot] = NewItem();
                s.AdSuccessesToday++; s.SettledCountAtLastAdSuccess = s.SettledTicketCount; s.Ad.Phase = AdPhase.COMMITTED;
                return new CommandReceipt { Kind = "AD_COMMIT", CashDeltaMinor = -s.Ad.ReservedPriceMinor };
            });
        }
        public CommandResult PollAd(string requestId, string commandId, long expectedRevision)
        {
            var state = store.Read(); if (state.Ad == null || state.Ad.RequestId != requestId) return Rejection("AD_REQUEST_MISMATCH");
            CommandResult result = null;
            // Resume the original durable request after restart, using its stored step IDs.
            if (state.Ad.Phase == AdPhase.CREATED)
            { result = ReserveAd(requestId, state.Ad.ReserveCommandId, state.Revision); if (!result.Committed) return result; state = store.Read(); }
            if (state.Ad.Phase == AdPhase.RESERVED)
            { result = MarkShowing(requestId, state.Ad.ShowingCommandId, state.Revision); if (!result.Committed) return result; state = store.Read(); }
            if (state.Ad.Phase == AdPhase.SHOWING)
            { result = ads.Show(requestId, state.RunId); if (!result.Committed) return result; }
            foreach (var e in ads.ReadEvents(requestId))
            {
                if (e.RunId != state.RunId) continue;
                result = RecordEvent(e, "ad-event:" + e.EventId, store.Read().Revision); if (!result.Committed) return result;
            }
            state = store.Read();
            if (state.Ad.Phase == AdPhase.REWARD_CONFIRMED)
            { result = MarkCommitting(requestId, state.Ad.CommittingCommandId, state.Revision); if (!result.Committed) return result; }
            state = store.Read();
            if (state.Ad.Phase == AdPhase.COMMITTING) return CommitAd(requestId, state.Ad.CommitCommandId, state.Revision);
            if (state.Ad.Phase == AdPhase.COMMITTED) return store.Recover(state.Ad.CommitCommandId);
            return result ?? Rejection(state.Ad.Phase == AdPhase.RECOVERY_CONFLICT ? "RECOVERY_REQUIRED" : "AD_AWAITING_REWARD");
        }
        CommandResult Step(string request, string id, long revision, string kind, Action<RunState> action)
        { return store.Execute(id, CommandDigest.Create(store.Read().RunId, kind, w => w.Write(request ?? "")), revision, s => { RequireAd(s, request); if (kind == "AD_RESERVE") s.Ad.ReserveCommandId = id; else if (kind == "AD_SHOWING") s.Ad.ShowingCommandId = id; else if (kind == "AD_COMMITTING") s.Ad.CommittingCommandId = id; action(s); return new CommandReceipt { Kind = kind }; }); }
        static void RequireAd(RunState state, string request) { if (state.Ad == null || state.Ad.RequestId != request || state.Ad.RunId != state.RunId) throw new RuleViolation("AD_REQUEST_MISMATCH"); }
        static bool ResourcesIntact(RunState s) => s.StockAvailable && s.Ad != null && s.CashMinor >= s.Ad.ReservedPriceMinor && s.Drawers[s.Ad.ReservedDrawerSlot] == null && s.AdSuccessesToday < NumberTicketRules.AdDailySuccessCap;
        static DrawerItem NewItem() => new DrawerItem { StockId = NumberTicketRules.StockId, ItemId = NumberTicketRules.StockItemId, Quality = NumberTicketRules.StockQuality };
        CommandResult Rejection(string code) => new CommandResult { CommitStatus = store.CanMutate ? CommitStatus.PROVEN_NOT_COMMITTED : CommitStatus.COMMIT_UNKNOWN, Code = code, State = store.Read() };
    }
}

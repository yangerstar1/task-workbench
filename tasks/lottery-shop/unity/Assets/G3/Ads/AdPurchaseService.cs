using System;
using System.Linq;
using Lottery.G3.Core;

namespace Lottery.G3.Ads
{
    public sealed class AdAvailability
    {
        public bool CanBuyNormally, CanWatchAd;
        public string Reason = "", StockId = "", Quality = "";
        public long FullPriceMinor, DiscountPriceMinor;
        public int FreeDrawerSlots;
    }

    public sealed class AdPurchaseService
    {
        readonly IStateStore store;
        readonly IRewardedAdService ads;
        public AdPurchaseService(IStateStore store, IRewardedAdService ads)
        { this.store = store ?? throw new ArgumentNullException(nameof(store)); this.ads = ads ?? throw new ArgumentNullException(nameof(ads)); }

        public AdAvailability GetAvailability(string stockId, long elapsedSeconds)
        {
            var s = store.Read(); var stock = FindStock(s, stockId);
            string reason = Eligibility(s, stockId, elapsedSeconds);
            if (!store.CanMutate) reason = s.RecoveryRequired ? "RECOVERY_REQUIRED" : "COMMIT_UNKNOWN";
            else if (reason == "" && !ads.IsAvailable) reason = "AD_SERVICE_UNAVAILABLE";
            int slots = Enumerable.Range(0, s.Drawers.Length).Count(i => s.Drawers[i] == null && !AdReservations.DrawerReserved(s, i));
            return new AdAvailability
            {
                StockId = stockId ?? "", Quality = stock == null ? "" : stock.Quality,
                FullPriceMinor = stock == null ? 0 : stock.PriceMinor, DiscountPriceMinor = stock == null ? 0 : Discount(stock.PriceMinor),
                FreeDrawerSlots = slots,
                CanBuyNormally = store.CanMutate && (s.Phase == DayPhase.DAY_OPEN || s.Phase == DayPhase.CLOSING_PREP) && stock != null && stock.IsConsumable && stock.Quantity == 1
                    && !AdReservations.StockReserved(s, stock.StockId) && slots > 0 && s.AvailableCashMinor >= stock.PriceMinor,
                CanWatchAd = reason == "", Reason = reason
            };
        }
        static string Eligibility(RunState s, string stockId, long seconds)
        {
            if (s.FixtureLabel != SyntheticAdFixture.Label)
                return s.DayNumber == 1 ? "AD_TUTORIAL_DAY" : "AD_SYNTHETIC_FIXTURE_REQUIRED";
            if (s.Phase != DayPhase.DAY_OPEN) return "DAY_NOT_OPEN";
            if (s.Ad != null) return s.Ad.Phase == AdPhase.RECOVERY_CONFLICT ? "RECOVERY_REQUIRED" : "AD_TRANSACTION_EXISTS";
            if (seconds < SyntheticAdFixture.MinimumSeconds) return "AD_FIRST_LAUNCH_DELAY";
            if (s.SettledTicketCount < SyntheticAdFixture.MinimumSettlements) return "AD_MINIMUM_SETTLEMENTS";
            if (s.AdSuccessesToday >= SyntheticAdFixture.DailySuccessCap) return "AD_DAILY_CAP";
            if (s.SettledCountAtLastAdSuccess >= 0 && s.SettledTicketCount - s.SettledCountAtLastAdSuccess < SyntheticAdFixture.CooldownSettlements) return "AD_COOLDOWN";
            var stock = FindStock(s, stockId);
            if (stock == null || stock.Quantity != 1) return "STOCK_UNAVAILABLE";
            if (!stock.IsConsumable) return "AD_CONSUMABLE_ONLY";
            if (!s.Drawers.Any(x => x == null)) return "DRAWER_FULL";
            if (stock.PriceMinor <= 0 || s.AvailableCashMinor < Discount(stock.PriceMinor)) return "INSUFFICIENT_CASH";
            return "";
        }
        public CommandResult CreateAd(string requestId, string stockId, long elapsedSeconds, string commandId, long expectedRevision)
        {
            return store.Execute(commandId, CommandDigest.Create(store.Read().RunId, "AD_CREATE", w =>
            { w.Write(requestId ?? ""); w.Write(stockId ?? ""); w.Write(elapsedSeconds); }), expectedRevision, s =>
            {
                if (!FakeRewardedAdService.ValidId(requestId) || string.IsNullOrEmpty(commandId) || commandId.Length > 220) throw new RuleViolation("INVALID_REQUEST");
                string reason = Eligibility(s, stockId, elapsedSeconds); if (reason != "") throw new RuleViolation(reason);
                if (!ads.IsAvailable) throw new RuleViolation("AD_SERVICE_UNAVAILABLE");
                var stock = FindStock(s, stockId);
                s.FirstLaunchElapsedSeconds = Math.Max(s.FirstLaunchElapsedSeconds, elapsedSeconds);
                s.Ad = new AdTransaction
                {
                    RequestId = requestId, RunId = s.RunId, StockId = stock.StockId, ItemId = stock.ItemId, Quality = stock.Quality,
                    CreateCommandId = commandId, ReserveCommandId = commandId + ":reserve", ShowingCommandId = commandId + ":showing",
                    CommittingCommandId = requestId + ":committing", CommitCommandId = requestId + ":commit",
                    ReservedPriceMinor = Discount(stock.PriceMinor), ReservedDrawerSlot = Array.FindIndex(s.Drawers, x => x == null),
                    DayNumber = s.DayNumber, Phase = AdPhase.CREATED
                };
                return new CommandReceipt { Kind = "AD_CREATE" };
            });
        }
        public CommandResult ReserveAd(string requestId, string commandId, long expectedRevision)
            => Step(requestId, commandId, expectedRevision, "AD_RESERVE", s =>
            {
                if (s.Ad.Phase != AdPhase.CREATED) throw new RuleViolation("AD_WRONG_PHASE");
                if (!ResourcesIntact(s)) Conflict(s, "Original target changed before reservation");
                else s.Ad.Phase = AdPhase.RESERVED;
            });
        public CommandResult MarkShowing(string requestId, string commandId, long expectedRevision)
            => Step(requestId, commandId, expectedRevision, "AD_SHOWING", s =>
            {
                if (s.Ad.Phase != AdPhase.RESERVED) throw new RuleViolation("AD_WRONG_PHASE");
                if (!ResourcesIntact(s)) Conflict(s, "Original reservation changed before showing");
                else s.Ad.Phase = AdPhase.SHOWING;
            });
        public CommandResult BeginAd(string requestId, string stockId, long elapsedSeconds, string commandId, long expectedRevision)
        {
            var result = CreateAd(requestId, stockId, elapsedSeconds, commandId, expectedRevision);
            if (!CanContinue(result)) return result;
            result = ReserveAd(requestId, commandId + ":reserve", result.State.Revision);
            if (!CanContinue(result)) return result;
            result = MarkShowing(requestId, commandId + ":showing", result.State.Revision);
            if (!CanContinue(result)) return result;
            return ads.Show(requestId, result.State.RunId);
        }
        public CommandResult RecordEvent(FakeAdEvent receipt, string commandId, long expectedRevision)
        {
            if (receipt == null) return Rejection("INVALID_REQUEST");
            return store.Execute(commandId, CommandDigest.Create(store.Read().RunId, "AD_EVENT", w =>
            { w.Write(receipt.EventId ?? ""); w.Write(receipt.RequestId ?? ""); w.Write(receipt.RunId ?? ""); w.Write((int)receipt.Kind); }), expectedRevision, s =>
            {
                RequireAd(s, receipt.RequestId);
                var ad = s.Ad;
                if (receipt.RunId != ad.RunId) throw new RuleViolation("AD_REQUEST_MISMATCH");
                if (!Enum.IsDefined(typeof(AdEventKind), receipt.Kind)) throw new RuleViolation("INVALID_REQUEST");
                if (!ads.ReadEvents(ad.RequestId).Any(e => e.EventId == receipt.EventId && e.RequestId == receipt.RequestId && e.RunId == receipt.RunId && e.Kind == receipt.Kind))
                    throw new RuleViolation("AD_RECEIPT_UNVERIFIED");
                if (ad.Phase == AdPhase.RECOVERY_CONFLICT) throw new RuleViolation("RECOVERY_REQUIRED");
                if (receipt.Kind == AdEventKind.Reward)
                {
                    if (ad.Phase == AdPhase.ABORTED_NO_REWARD || ad.Phase == AdPhase.CREATED || (ad.Phase != AdPhase.COMMITTED && !ResourcesIntact(s)))
                        Conflict(s, "Verified reward conflicts with terminal state or original reservation");
                    else if (ad.Phase != AdPhase.COMMITTED && ad.Phase != AdPhase.COMMITTING)
                    { ad.RewardRecorded = true; ad.Phase = AdPhase.REWARD_CONFIRMED; }
                }
                else if (receipt.Kind == AdEventKind.Closed)
                {
                    if (ad.Phase == AdPhase.SHOWING) ad.Phase = AdPhase.CLOSED_AWAITING_REWARD;
                    // Closing is never evidence of no reward; reward/commit phases are monotonic.
                }
                else
                {
                    // Only a verified explicit no-reward terminal receipt can release a reservation.
                    if (ad.RewardRecorded || ad.Phase == AdPhase.COMMITTED || ad.Phase == AdPhase.COMMITTING)
                        Conflict(s, "Verified no-reward terminal contradicts verified reward");
                    else ad.Phase = AdPhase.ABORTED_NO_REWARD;
                }
                return new CommandReceipt { Kind = ad.Phase == AdPhase.RECOVERY_CONFLICT ? "AD_CONFLICT" : "AD_EVENT" };
            });
        }
        public CommandResult MarkCommitting(string requestId, string commandId, long expectedRevision)
            => Step(requestId, commandId, expectedRevision, "AD_COMMITTING", s =>
            {
                if (s.Ad.Phase != AdPhase.REWARD_CONFIRMED || !s.Ad.RewardRecorded) throw new RuleViolation("AD_WRONG_PHASE");
                if (!ResourcesIntact(s)) Conflict(s, "Original reservation changed before commit intent");
                else s.Ad.Phase = AdPhase.COMMITTING;
            });
        public CommandResult CommitAd(string requestId, string commandId, long expectedRevision)
        {
            return store.Execute(commandId, CommandDigest.Create(store.Read().RunId, "AD_COMMIT", w => w.Write(requestId ?? "")), expectedRevision, s =>
            {
                RequireAd(s, requestId);
                if (s.Ad.Phase != AdPhase.COMMITTING || !s.Ad.RewardRecorded) throw new RuleViolation("AD_WRONG_PHASE");
                s.Ad.CommitCommandId = commandId;
                if (!ResourcesIntact(s))
                { Conflict(s, "Original reservation cannot be committed"); return new CommandReceipt { Kind = "AD_CONFLICT" }; }
                var stock = FindStock(s, s.Ad.StockId);
                s.CashMinor -= s.Ad.ReservedPriceMinor;
                stock.Quantity = 0;
                s.Drawers[s.Ad.ReservedDrawerSlot] = new DrawerItem
                { StockId = stock.StockId, ItemId = stock.ItemId, Quality = stock.Quality, PurchasePriceMinor = s.Ad.ReservedPriceMinor };
                s.Ledger.Add(new LedgerEntry
                { CommandId = commandId, Kind = "AD_PURCHASE", ReferenceId = stock.StockId, DeltaMinor = -s.Ad.ReservedPriceMinor, BalanceMinor = s.CashMinor });
                s.AdSuccessesToday++;
                s.SettledCountAtLastAdSuccess = s.SettledTicketCount;
                s.Ad.Phase = AdPhase.COMMITTED;
                return new CommandReceipt { Kind = "AD_COMMIT", CashDeltaMinor = -s.Ad.ReservedPriceMinor };
            });
        }
        public CommandResult PollAd(string requestId, string commandId, long expectedRevision)
        {
            var state = store.Read();
            if (!store.CanMutate) return Rejection(state.RecoveryRequired ? "RECOVERY_REQUIRED" : "COMMIT_UNKNOWN");
            if (string.IsNullOrWhiteSpace(commandId) || commandId.Length > 256 || commandId.Any(char.IsControl)) return Rejection("INVALID_REQUEST");
            if (state.Revision != expectedRevision) return Rejection("STALE_REVISION");
            if (state.Ad == null || state.Ad.RequestId != requestId || state.Ad.RunId != state.RunId) return Rejection("AD_REQUEST_MISMATCH");
            CommandResult result = null;
            if (state.Ad.Phase == AdPhase.CREATED)
            {
                result = ReserveAd(requestId, state.Ad.ReserveCommandId, state.Revision);
                if (!CanContinue(result)) return result;
                state = result.State;
            }
            if (state.Ad.Phase == AdPhase.RESERVED)
            {
                result = MarkShowing(requestId, state.Ad.ShowingCommandId, state.Revision);
                if (!CanContinue(result)) return result;
                state = result.State;
            }
            if (state.Ad.Phase == AdPhase.SHOWING)
            {
                result = ads.Show(requestId, state.RunId);
                if (!CanContinue(result)) return result;
            }
            foreach (var e in ads.ReadEvents(requestId))
            {
                if (e.RunId != state.RunId) continue;
                result = RecordEvent(e, "ad-event:" + e.EventId, store.Read().Revision);
                if (!CanContinue(result)) return result;
            }
            state = store.Read();
            if (state.Ad.Phase == AdPhase.REWARD_CONFIRMED)
            {
                result = MarkCommitting(requestId, state.Ad.CommittingCommandId, state.Revision);
                if (!CanContinue(result)) return result;
                state = result.State;
            }
            if (state.Ad.Phase == AdPhase.COMMITTING) return CommitAd(requestId, state.Ad.CommitCommandId, state.Revision);
            if (state.Ad.Phase == AdPhase.COMMITTED) return store.Recover(state.Ad.CommitCommandId);
            // Replaying an old provider/show receipt is not progress or a new reward confirmation.
            if (state.Revision == expectedRevision) return Rejection("AD_AWAITING_REWARD");
            return result ?? Rejection(state.Ad.Phase == AdPhase.RECOVERY_CONFLICT ? "RECOVERY_REQUIRED" : "AD_AWAITING_REWARD");
        }
        CommandResult Step(string requestId, string commandId, long revision, string kind, Action<RunState> action)
            => store.Execute(commandId, CommandDigest.Create(store.Read().RunId, kind, w => w.Write(requestId ?? "")), revision, s =>
            {
                RequireAd(s, requestId);
                if (kind == "AD_RESERVE") s.Ad.ReserveCommandId = commandId;
                else if (kind == "AD_SHOWING") s.Ad.ShowingCommandId = commandId;
                else if (kind == "AD_COMMITTING") s.Ad.CommittingCommandId = commandId;
                action(s);
                return new CommandReceipt { Kind = s.Ad.Phase == AdPhase.RECOVERY_CONFLICT ? "AD_CONFLICT" : kind };
            });
        static bool CanContinue(CommandResult result) => result.Success && result.State != null && result.State.Ad != null && result.State.Ad.Phase != AdPhase.RECOVERY_CONFLICT;
        static void RequireAd(RunState s, string requestId)
        {
            if (s.FixtureLabel != SyntheticAdFixture.Label) throw new RuleViolation("AD_SYNTHETIC_FIXTURE_REQUIRED");
            if (s.Ad == null || s.Ad.RequestId != requestId || s.Ad.RunId != s.RunId) throw new RuleViolation("AD_REQUEST_MISMATCH");
        }
        static bool ResourcesIntact(RunState s)
        {
            var ad = s.Ad;
            if (ad == null || ad.RunId != s.RunId || ad.DayNumber != s.DayNumber || ad.Version != "g3-fake-ad-v1" || s.Phase == DayPhase.DAY_COMPLETE || s.Phase == DayPhase.RUN_FAILED
                || ad.ReservedDrawerSlot < 0 || ad.ReservedDrawerSlot >= s.Drawers.Length || s.Drawers[ad.ReservedDrawerSlot] != null
                || ad.ReservedPriceMinor <= 0 || s.CashMinor < ad.ReservedPriceMinor || s.AdSuccessesToday >= SyntheticAdFixture.DailySuccessCap) return false;
            var stock = FindStock(s, ad.StockId);
            return stock != null && stock.IsConsumable && stock.Quantity == 1 && stock.ItemId == ad.ItemId && stock.Quality == ad.Quality
                && Discount(stock.PriceMinor) == ad.ReservedPriceMinor;
        }
        static StockItem FindStock(RunState s, string stockId) => s.Stock.FirstOrDefault(x => x.StockId == stockId);
        static long Discount(long fullPriceMinor) => fullPriceMinor / 2 + fullPriceMinor % 2;
        static void Conflict(RunState s, string reason) { s.Ad.Phase = AdPhase.RECOVERY_CONFLICT; s.Ad.Conflict = reason; }
        CommandResult Rejection(string code) => new CommandResult
        { CommitStatus = store.CanMutate ? CommitStatus.PROVEN_NOT_COMMITTED : CommitStatus.COMMIT_UNKNOWN, Code = code, State = store.Read() };
    }
}

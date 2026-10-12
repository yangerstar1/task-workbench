using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Lottery.G3.Ads;
using Lottery.G3.Core;
using Lottery.G3.Persistence;
using NUnit.Framework;

namespace Lottery.G3.EditMode.Tests
{
    public sealed class AdTests
    {
        string root;
        readonly List<FileStateStore> stores = new List<FileStateStore>();
        [SetUp] public void SetUp()
        {
            root = Path.Combine(Path.GetTempPath(), "lottery-g3-ad-tests-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            Assert.That(FakeRewardedAdService.DevelopmentEnabled, Is.True, "Synthetic tests require a development/test build, never production admission.");
        }
        [TearDown] public void TearDown()
        {
            foreach (var store in stores) store.Dispose();
            stores.Clear();
            if (Directory.Exists(root)) Directory.Delete(root, true);
        }
        static RunState Fixture() => SyntheticAdFixture.Create("ad-run");
        FileStateStore Open(string name = "fixture", RunState initial = null, IStoreFaultInjector faults = null)
        {
            var store = new FileStateStore(Path.Combine(root, name), initial ?? Fixture(), faults);
            stores.Add(store);
            Assert.That(store.CanMutate, Is.True, "Fixture must be valid under the production G3 state validator.");
            return store;
        }
        static StockItem Stock(IStateStore store) => store.Read().Stock.First(s => s.IsConsumable);
        static AdPurchaseService Service(IStateStore store) => new AdPurchaseService(store, new FakeRewardedAdService(store));
        static void Ok(CommandResult result) { Assert.That(result.CommitStatus, Is.EqualTo(CommitStatus.COMMITTED), result.Code); }
        static void Begin(IStateStore store, AdPurchaseService service, string request = "request", string command = "begin")
            => Ok(service.BeginAd(request, Stock(store).StockId, 60, command, store.Read().Revision));
        static void Queue(IStateStore store, FakeRewardedAdService fake, AdEventKind kind, string eventId = null)
        {
            if (eventId == null) Ok(fake.QueueEvent("request", store.Read().RunId, kind));
            else Ok(fake.QueueEvent("request", store.Read().RunId, kind, eventId));
        }
        static CommandResult Poll(IStateStore store, AdPurchaseService service) => service.PollAd("request", "poll", store.Read().Revision);
        static void RewardReady(IStateStore store, FakeRewardedAdService fake, AdPurchaseService service)
        {
            Queue(store, fake, AdEventKind.Reward);
            Ok(service.RecordEvent(fake.ReadEvents("request").Single(), "record-reward", store.Read().Revision));
            Ok(service.MarkCommitting("request", "mark-commit", store.Read().Revision));
        }

        [Test] public void NormalFirstDayAndDiagnosticFirstDayNeverAdmitSyntheticAds()
        {
            foreach (var initial in new[] { RunFactory.Create("normal", "seed"), RunFactory.CreateDiagnostic("diagnostic") })
            {
                var store = Open(initial.RunId, initial); var fake = new FakeRewardedAdService(store); var ad = Service(store);
                var before = store.ConfirmedHash;
                Assert.That(ad.GetAvailability(Stock(store).StockId, long.MaxValue).Reason, Is.EqualTo("AD_TUTORIAL_DAY"));
                Assert.That(ad.GetAvailability(Stock(store).StockId, long.MaxValue).CanBuyNormally, Is.True);
                Assert.That(ad.BeginAd("request", Stock(store).StockId, long.MaxValue, "begin", 0).Code, Is.EqualTo("AD_TUTORIAL_DAY"));
                Assert.That(fake.IsAvailable, Is.False);
                Assert.That(fake.Show("request", initial.RunId).Code, Is.EqualTo("AD_SERVICE_UNAVAILABLE"));
                Assert.That(fake.QueueEvent("request", initial.RunId, AdEventKind.Reward).Code, Is.EqualTo("AD_SERVICE_UNAVAILABLE"));
                Assert.That(store.ConfirmedHash, Is.EqualTo(before));
                Assert.That(store.Read().DayNumber, Is.EqualTo(1));
                Assert.That(store.Read().Ad, Is.Null);
            }
        }
        [Test] public void ExplicitFixtureEmulatesQualificationsWithoutDayTwoOrLifetimeProgress()
        {
            var s = Fixture(); var store = Open(initial: s);
            Assert.That(s.FixtureLabel, Is.EqualTo("SYNTHETIC_AD_FIXTURE"));
            Assert.That(s.DayNumber, Is.EqualTo(1));
            Assert.That(s.SettledTicketCount, Is.EqualTo(12));
            Assert.That(s.FixtureBaseSettlements, Is.EqualTo(12));
            Assert.That(s.LifetimeEffectiveTickets, Is.Zero);
            Assert.That(s.LifetimeEffectiveAtOpen, Is.Zero);
            Assert.That(s.Settlements, Is.Empty);
            Assert.That(Service(store).GetAvailability(Stock(store).StockId, 60).CanWatchAd, Is.True);
        }
        [Test] public void ElapsedTimeAndSettlementThresholdsAreCheckedAtCreation()
        {
            var store = Open(); var ad = Service(store);
            Assert.That(ad.GetAvailability(Stock(store).StockId, 59).Reason, Is.EqualTo("AD_FIRST_LAUNCH_DELAY"));
            Assert.That(ad.CreateAd("request", Stock(store).StockId, 59, "early", 0).Code, Is.EqualTo("AD_FIRST_LAUNCH_DELAY"));
            Assert.That(store.Read().Ad, Is.Null);
            var initial = Fixture(); initial.SettledTicketCount = initial.FixtureBaseSettlements = 11;
            var low = Open("too-few", initial); var lowAd = Service(low);
            Assert.That(lowAd.GetAvailability(Stock(low).StockId, 60).Reason, Is.EqualTo("AD_MINIMUM_SETTLEMENTS"));
            Assert.That(lowAd.CreateAd("request", Stock(low).StockId, 60, "early", 0).Code, Is.EqualTo("AD_MINIMUM_SETTLEMENTS"));
        }
        [Test] public void QualificationRejectsCooldownCapFullDrawerPhaseAndInsufficientCash()
        {
            CheckAvailability(s => s.SettledCountAtLastAdSuccess = 1, "AD_COOLDOWN");
            CheckAvailability(s => s.AdSuccessesToday = 1, "AD_DAILY_CAP");
            CheckAvailability(s => s.Phase = DayPhase.CLOSING_PREP, "DAY_NOT_OPEN");
            CheckAvailability(s => s.CashMinor = 0, "INSUFFICIENT_CASH");
            CheckAvailability(s => { s.Drawers[0] = new DrawerItem(); s.Drawers[1] = new DrawerItem(); }, "DRAWER_FULL");
            CheckAvailability(s => s.Stock.First(x => x.IsConsumable).Quantity = 0, "STOCK_UNAVAILABLE");
        }
        static void CheckAvailability(Action<RunState> arrange, string code)
        {
            // Isolated invalid/negative input snapshots exercise availability, not persisted-state acceptance.
            var initial = Fixture(); arrange(initial); var view = new SnapshotOnlyStore(initial);
            Assert.That(Service(view).GetAvailability(Stock(view).StockId, 60).Reason, Is.EqualTo(code));
        }
        [Test] public void ToolStockWrongStockAndUnavailableProviderCannotCreateAd()
        {
            var store = Open(); var ad = Service(store);
            Assert.That(ad.CreateAd("request", "missing", 60, "missing", 0).Code, Is.EqualTo("STOCK_UNAVAILABLE"));
            Assert.That(ad.CreateAd("request", store.Read().Stock.First(s => !s.IsConsumable).StockId, 60, "tool", 0).Code, Is.EqualTo("AD_CONSUMABLE_ONLY"));
            var unavailable = new AdPurchaseService(store, new UnavailableProvider());
            Assert.That(unavailable.GetAvailability(Stock(store).StockId, 60).Reason, Is.EqualTo("AD_SERVICE_UNAVAILABLE"));
            Assert.That(unavailable.BeginAd("request", Stock(store).StockId, 60, "begin", 0).Code, Is.EqualTo("AD_SERVICE_UNAVAILABLE"));
            Assert.That(store.Read().Ad, Is.Null);
        }
        [Test] public void CreateReserveShowAreSeparateDurableStepsWithOriginalResources()
        {
            var store = Open(); var ad = Service(store); var stock = Stock(store); long cash = store.Read().CashMinor;
            Ok(ad.CreateAd("request", stock.StockId, 60, "create", 0));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.CREATED));
            Assert.That(AdReservations.HasReservation(store.Read().Ad), Is.False);
            Ok(ad.ReserveAd("request", "reserve", store.Read().Revision));
            var reserved = store.Read();
            Assert.That(reserved.Ad.Phase, Is.EqualTo(AdPhase.RESERVED));
            Assert.That(reserved.AvailableCashMinor, Is.EqualTo(cash - stock.PriceMinor / 2));
            Assert.That(AdReservations.StockReserved(reserved, stock.StockId), Is.True);
            Assert.That(AdReservations.DrawerReserved(reserved, reserved.Ad.ReservedDrawerSlot), Is.True);
            Assert.That(reserved.Ad.Quality, Is.EqualTo(stock.Quality));
            Assert.That(reserved.CashMinor, Is.EqualTo(cash));
            Assert.That(Stock(store).Quantity, Is.EqualTo(1));
            Ok(ad.MarkShowing("request", "showing", reserved.Revision));
            Ok(new FakeRewardedAdService(store).Show("request", reserved.RunId));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.SHOWING));
            Assert.That(store.Read().FakeShownRequests, Is.EquivalentTo(new[] { "request" }));
        }
        [Test] public void CloseThenLateRewardRetainsReservationAndPurchasesOriginalStockOnce()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store);
            var original = Stock(store); var allStock = store.Read().Stock.Select(x => x.StockId).ToArray(); long cash = store.Read().CashMinor;
            Begin(store, ad); Queue(store, fake, AdEventKind.Closed); Ok(Poll(store, ad));
            var closed = store.Read();
            Assert.That(closed.Ad.Phase, Is.EqualTo(AdPhase.CLOSED_AWAITING_REWARD));
            Assert.That(closed.CashMinor, Is.EqualTo(cash));
            Assert.That(closed.AvailableCashMinor, Is.EqualTo(cash - original.PriceMinor / 2));
            Assert.That(AdReservations.HasReservation(closed.Ad), Is.True);
            Assert.That(new DayGameService(store).BuyStock(original.StockId, "", "steal-stock", closed.Revision).Success, Is.False);
            Queue(store, fake, AdEventKind.Reward); Ok(Poll(store, ad)); Ok(Poll(store, ad));
            var done = store.Read(); var drawer = done.Drawers.Single(x => x != null); var ledger = done.Ledger.Single(x => x.Kind == "AD_PURCHASE");
            Assert.That(done.Ad.Phase, Is.EqualTo(AdPhase.COMMITTED));
            Assert.That(done.CashMinor, Is.EqualTo(cash - original.PriceMinor / 2));
            Assert.That(done.AdSuccessesToday, Is.EqualTo(1));
            Assert.That(done.Stock.Select(x => x.StockId), Is.EquivalentTo(allStock), "An ad must never replenish or replace stock.");
            Assert.That(done.Stock.Single(x => x.StockId == original.StockId).Quantity, Is.Zero);
            Assert.That(drawer.StockId, Is.EqualTo(original.StockId));
            Assert.That(drawer.ItemId, Is.EqualTo(original.ItemId));
            Assert.That(drawer.Quality, Is.EqualTo(original.Quality));
            Assert.That(drawer.PurchasePriceMinor, Is.EqualTo(original.PriceMinor / 2));
            Assert.That(ledger.ReferenceId, Is.EqualTo(original.StockId));
            Assert.That(ledger.DeltaMinor, Is.EqualTo(-original.PriceMinor / 2));
            Assert.That(ledger.BalanceMinor, Is.EqualTo(done.CashMinor));
            Assert.That(done.Commands.Count(c => c.Kind == "AD_COMMIT"), Is.EqualTo(1));
            Assert.That(done.LifetimeEffectiveTickets, Is.Zero);
        }
        [Test] public void ReservedCoinsCannotFundAnOrdinaryTicket()
        {
            var initial = Fixture(); long price = initial.Stock.First(s => s.IsConsumable).PriceMinor / 2;
            initial.InitialCashMinor = initial.CashMinor = price + DayRules.TicketPriceMinor - 1;
            var store = Open(initial: initial); Begin(store, Service(store));
            var result = new DayGameService(store).BuyNumberTicket("spend-reservation", store.Read().Revision);
            Assert.That(result.Code, Is.EqualTo("INSUFFICIENT_CASH"));
            Assert.That(store.Read().CashMinor, Is.EqualTo(initial.CashMinor));
            Assert.That(store.Read().CurrentTicket, Is.Null);
            Assert.That(AdReservations.HasReservation(store.Read().Ad), Is.True);
        }
        [Test] public void PendingAdCanResolveAtNightButCannotBeDiscardedByPaymentOrRestart()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); var game = new DayGameService(store);
            Begin(store, ad); Ok(game.BeginClosing("closing", store.Read().Revision)); Ok(game.EnterNightBill("night", store.Read().Revision));
            Assert.That(game.PayNightBill(false, "pay-too-early", store.Read().Revision).Code, Is.EqualTo("AD_RESOLUTION_REQUIRED"));
            Assert.That(game.RestartDay("new-run", "new-seed", "restart-too-early", store.Read().Revision).Success, Is.False);
            Queue(store, fake, AdEventKind.Reward); Ok(Poll(store, ad));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTED));
            Assert.That(store.Read().Phase, Is.EqualTo(DayPhase.NIGHT_BILL));
            Ok(game.PayNightBill(false, "pay", store.Read().Revision));
            Assert.That(store.Read().Phase, Is.EqualTo(DayPhase.DAY_COMPLETE));
        }
        [Test] public void RewardThenCloseAndDifferentDuplicateRewardCannotDoubleSpend()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); Begin(store, ad);
            Queue(store, fake, AdEventKind.Reward); Ok(Poll(store, ad)); long cash = store.Read().CashMinor;
            Queue(store, fake, AdEventKind.Closed); Queue(store, fake, AdEventKind.Reward, "duplicate-reward"); Ok(Poll(store, ad));
            Assert.That(store.Read().CashMinor, Is.EqualTo(cash));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTED));
            Assert.That(store.Read().Ledger.Count(x => x.Kind == "AD_PURCHASE"), Is.EqualTo(1));
        }
        [Test] public void WrongRequestWrongRunAndUnverifiedCallbacksNeverReward()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); Begin(store, ad);
            Ok(fake.QueueEvent("wrong-request", store.Read().RunId, AdEventKind.Reward));
            Ok(fake.QueueEvent("request", "wrong-run", AdEventKind.Reward, "wrong-run-event"));
            Ok(Poll(store, ad));
            var forged = new FakeAdEvent { EventId = "forged", RequestId = "request", RunId = store.Read().RunId, Kind = AdEventKind.Reward };
            Assert.That(ad.RecordEvent(forged, "forged", store.Read().Revision).Code, Is.EqualTo("AD_RECEIPT_UNVERIFIED"));
            Assert.That(ad.RecordEvent(fake.ReadEvents("wrong-request").Single(), "wrong-request", store.Read().Revision).Code, Is.EqualTo("AD_REQUEST_MISMATCH"));
            Assert.That(ad.RecordEvent(fake.ReadEvents("request").Single(), "wrong-run", store.Read().Revision).Code, Is.EqualTo("AD_REQUEST_MISMATCH"));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.SHOWING));
            Assert.That(store.Read().CashMinor, Is.EqualTo(30000));
            Assert.That(store.Read().Ledger, Is.Empty);
        }
        [TestCase(AdEventKind.NoFill)] [TestCase(AdEventKind.NotShown)] [TestCase(AdEventKind.NoRewardTerminal)]
        public void OnlyVerifiedNoRewardTerminalReleasesReservation(AdEventKind terminal)
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); Begin(store, ad);
            Queue(store, fake, terminal); Ok(Poll(store, ad)); var state = store.Read();
            Assert.That(state.Ad.Phase, Is.EqualTo(AdPhase.ABORTED_NO_REWARD));
            Assert.That(AdReservations.HasReservation(state.Ad), Is.False);
            Assert.That(state.AvailableCashMinor, Is.EqualTo(state.CashMinor));
            Assert.That(Stock(store).Quantity, Is.EqualTo(1));
            Assert.That(state.Drawers.All(x => x == null), Is.True);
            Assert.That(state.Ledger, Is.Empty);
        }
        [Test] public void NoRewardThenLateRewardFailsClosedWithoutRestocking()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); Begin(store, ad);
            Queue(store, fake, AdEventKind.NoRewardTerminal); Ok(Poll(store, ad));
            Ok(new DayGameService(store).BuyStock(Stock(store).StockId, "", "ordinary-after-abort", store.Read().Revision));
            var before = store.Read(); Queue(store, fake, AdEventKind.Reward); Ok(Poll(store, ad));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.RECOVERY_CONFLICT));
            Assert.That(store.CanMutate, Is.False);
            Assert.That(store.Read().CashMinor, Is.EqualTo(before.CashMinor));
            Assert.That(Stock(store).Quantity, Is.Zero);
            Assert.That(store.Read().Drawers.Count(x => x != null), Is.EqualTo(1));
            Assert.That(store.Read().Ledger.Count(x => x.Kind == "AD_PURCHASE"), Is.Zero);
        }
        [Test] public void RewardThenContradictoryTerminalReceiptFailsClosed()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); Begin(store, ad);
            Queue(store, fake, AdEventKind.Reward); Queue(store, fake, AdEventKind.NoRewardTerminal); Ok(Poll(store, ad));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.RECOVERY_CONFLICT));
            Assert.That(store.CanMutate, Is.False);
            Assert.That(store.Read().CashMinor, Is.EqualTo(30000));
            Assert.That(store.Read().Ledger, Is.Empty);
        }
        [Test] public void CommitThenContradictoryTerminalReceiptCannotRefundOrSpendAgain()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); Begin(store, ad);
            Queue(store, fake, AdEventKind.Reward); Ok(Poll(store, ad));
            Ok(new DayGameService(store).RepayPrincipal(store.Read().CashMinor, "spend-after-commit", store.Read().Revision));
            Queue(store, fake, AdEventKind.NotShown); Ok(Poll(store, ad));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.RECOVERY_CONFLICT));
            Assert.That(store.Read().CashMinor, Is.Zero, "Conflict must persist even after legitimately spending the remaining unreserved cash.");
            Assert.That(store.Read().Ledger.Count(x => x.Kind == "AD_PURCHASE"), Is.EqualTo(1));
            Assert.That(store.CanMutate, Is.False);
        }
        [Test] public void ChangedOriginalStockBeforeReservationBecomesConflictWithoutReplacement()
        {
            var store = Open(); var ad = Service(store); string original = Stock(store).StockId;
            Ok(ad.CreateAd("request", original, 60, "create", 0));
            Ok(new DayGameService(store).BuyStock(original, "", "ordinary", store.Read().Revision)); long cash = store.Read().CashMinor;
            Ok(ad.ReserveAd("request", "reserve", store.Read().Revision));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.RECOVERY_CONFLICT));
            Assert.That(store.Read().CashMinor, Is.EqualTo(cash));
            Assert.That(Stock(store).Quantity, Is.Zero);
            Assert.That(store.Read().Drawers.Count(x => x != null), Is.EqualTo(1));
            Assert.That(store.CanMutate, Is.False);
        }
        [Test] public void RewardWhileCreatedConflictsButVerifiedReservedRewardCanResume()
        {
            foreach (bool reserve in new[] { false, true })
            {
                var store = Open("reserved-" + reserve); var fake = new FakeRewardedAdService(store); var ad = Service(store);
                Ok(ad.CreateAd("request", Stock(store).StockId, 60, "create", 0));
                if (reserve) Ok(ad.ReserveAd("request", "reserve", store.Read().Revision));
                Queue(store, fake, AdEventKind.Reward);
                Ok(ad.RecordEvent(fake.ReadEvents("request").Single(), "record", store.Read().Revision));
                Assert.That(store.Read().Ad.Phase, Is.EqualTo(reserve ? AdPhase.REWARD_CONFIRMED : AdPhase.RECOVERY_CONFLICT));
                Assert.That(store.Read().CashMinor, Is.EqualTo(30000));
            }
        }
        [TestCase(false)] [TestCase(true)]
        public void CreatedAndReservedTransactionsResumeOriginalPersistedStepIds(bool reserve)
        {
            var store = Open(); var ad = Service(store);
            Ok(ad.CreateAd("request", Stock(store).StockId, 60, "original-create", 0));
            if (reserve) Ok(ad.ReserveAd("request", "original-reserve", store.Read().Revision));
            store.Dispose(); var reload = Open(); var restored = Service(reload);
            Ok(Poll(reload, restored)); Ok(Poll(reload, restored));
            Assert.That(reload.Read().Ad.Phase, Is.EqualTo(AdPhase.SHOWING));
            Assert.That(reload.Read().FakeShownRequests.Count, Is.EqualTo(1));
            Assert.That(reload.Read().Ad.CreateCommandId, Is.EqualTo("original-create"));
            Assert.That(reload.Read().Ad.ReserveCommandId, Is.EqualTo(reserve ? "original-reserve" : "original-create:reserve"));
        }
        [Test] public void ClosedReservationAndUndeliveredProviderRewardSurviveRebuild()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); Begin(store, ad);
            Queue(store, fake, AdEventKind.Closed); Ok(Poll(store, ad)); Queue(store, fake, AdEventKind.Reward);
            long discount = store.Read().Ad.ReservedPriceMinor;
            store.Dispose(); var reload = Open();
            Assert.That(reload.Read().Ad.Phase, Is.EqualTo(AdPhase.CLOSED_AWAITING_REWARD));
            Assert.That(reload.Read().AdEvents.Count, Is.EqualTo(2));
            Ok(Poll(reload, Service(reload)));
            Assert.That(reload.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTED));
            Assert.That(reload.Read().CashMinor, Is.EqualTo(30000 - discount));
        }
        [Test] public void PersistedCommitIntentResumesAndStaleDuplicateCommitDoesNotSpendTwice()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); Begin(store, ad); RewardReady(store, fake, ad);
            long discount = store.Read().Ad.ReservedPriceMinor; store.Dispose(); var reload = Open(); var restored = Service(reload);
            Assert.That(reload.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTING));
            long revision = reload.Read().Revision;
            Ok(restored.CommitAd("request", "final", revision)); Ok(restored.CommitAd("request", "final", revision));
            Assert.That(reload.Read().CashMinor, Is.EqualTo(30000 - discount));
            Assert.That(reload.Read().Commands.Count(c => c.Kind == "AD_COMMIT"), Is.EqualTo(1));
            Assert.That(restored.CommitAd("different", "final", revision).Code, Is.EqualTo("COMMAND_ID_REUSED"));
        }
        [Test] public void CommitUnknownRetainsConfirmedReservationUntilAuthoritativeRecovery()
        {
            var faults = new Faults(); var store = Open(faults: faults); var fake = new FakeRewardedAdService(store); var ad = Service(store);
            Begin(store, ad); RewardReady(store, fake, ad); long discount = store.Read().Ad.ReservedPriceMinor;
            faults.Point = StoreFaultPoint.AfterPublish; faults.ReadBlocked = true;
            var result = ad.CommitAd("request", "final", store.Read().Revision);
            Assert.That(result.CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN));
            Assert.That(result.State.Ad.Phase, Is.EqualTo(AdPhase.COMMITTING));
            Assert.That(result.State.CashMinor, Is.EqualTo(30000));
            Assert.That(result.State.AvailableCashMinor, Is.EqualTo(30000 - discount));
            Assert.That(result.State.Drawers.All(x => x == null), Is.True);
            Assert.That(store.CanMutate, Is.False);
            Assert.That(Poll(store, ad).CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN));
            faults.ReadBlocked = false; Ok(store.Recover("final")); Ok(Poll(store, ad));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTED));
            Assert.That(store.Read().CashMinor, Is.EqualTo(30000 - discount));
            Assert.That(store.Read().Ledger.Count(x => x.Kind == "AD_PURCHASE"), Is.EqualTo(1));
        }
        [TestCase(StoreFaultPoint.BeforeWrite)] [TestCase(StoreFaultPoint.TempHalfWritten)]
        [TestCase(StoreFaultPoint.TempFlushed)] [TestCase(StoreFaultPoint.BeforePublish)]
        [TestCase(StoreFaultPoint.AfterPublish)] [TestCase(StoreFaultPoint.BeforeResponse)]
        public void CommitFaultWindowsRecoverToExactlyOneEconomicEffect(StoreFaultPoint point)
        {
            var faults = new Faults(); var store = Open(faults: faults); var fake = new FakeRewardedAdService(store); var ad = Service(store);
            Begin(store, ad); RewardReady(store, fake, ad); long discount = store.Read().Ad.ReservedPriceMinor;
            faults.Point = point; var result = ad.CommitAd("request", "final", store.Read().Revision);
            Assert.That(result.CommitStatus, Is.Not.EqualTo(CommitStatus.COMMIT_UNKNOWN));
            if (!result.Success) Ok(ad.CommitAd("request", "final", store.Read().Revision));
            store.Dispose(); var reload = Open();
            Assert.That(reload.Read().CashMinor, Is.EqualTo(30000 - discount));
            Assert.That(reload.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTED));
            Assert.That(reload.Read().Ledger.Count(x => x.Kind == "AD_PURCHASE"), Is.EqualTo(1));
            Assert.That(reload.Read().Drawers.Count(x => x != null), Is.EqualTo(1));
        }
        [Test] public void InvalidEventsIdentityReuseAndOutOfOrderCommandsAreRejected()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store);
            Assert.That(ad.CreateAd("", Stock(store).StockId, 60, "empty", 0).Code, Is.EqualTo("INVALID_REQUEST"));
            Ok(ad.CreateAd("request", Stock(store).StockId, 60, "create", 0));
            Assert.That(ad.MarkShowing("request", "out-of-order", store.Read().Revision).Code, Is.EqualTo("AD_WRONG_PHASE"));
            Assert.That(ad.MarkCommitting("request", "unrewarded", store.Read().Revision).Code, Is.EqualTo("AD_WRONG_PHASE"));
            Assert.That(ad.CommitAd("request", "unrewarded-commit", store.Read().Revision).Code, Is.EqualTo("AD_WRONG_PHASE"));
            Assert.That(fake.QueueEvent("request", store.Read().RunId, (AdEventKind)999, "invalid").Code, Is.EqualTo("INVALID_REQUEST"));
            Ok(fake.QueueEvent("request", store.Read().RunId, AdEventKind.Closed, "identity"));
            Assert.That(fake.QueueEvent("request", store.Read().RunId, AdEventKind.Reward, "identity").Code, Is.EqualTo("COMMAND_ID_REUSED"));
            Assert.That(ad.RecordEvent(null, "null", store.Read().Revision).Code, Is.EqualTo("INVALID_REQUEST"));
            Assert.That(ad.PollAd("request", "stale", 0).Code, Is.EqualTo("STALE_REVISION"));
            Assert.That(store.Read().CashMinor, Is.EqualTo(30000));
        }
        [Test] public void MaximumRequestIdSupportsDefaultEventIdsAndProviderReturnsDetachedReceipts()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = Service(store); string request = new string('r', 128);
            Begin(store, ad, request); Ok(fake.QueueEvent(request, store.Read().RunId, AdEventKind.Reward));
            var receipt = fake.ReadEvents(request).Single(); receipt.Kind = AdEventKind.NoRewardTerminal;
            Assert.That(fake.ReadEvents(request).Single().Kind, Is.EqualTo(AdEventKind.Reward));
            Assert.That(ad.RecordEvent(receipt, "modified", store.Read().Revision).Code, Is.EqualTo("AD_RECEIPT_UNVERIFIED"));
            Ok(ad.PollAd(request, "poll", store.Read().Revision));
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTED));
        }

        sealed class Faults : IStoreFaultInjector
        {
            public StoreFaultPoint? Point;
            public bool ReadBlocked;
            public void OnPoint(StoreFaultPoint point)
            {
                if (point == StoreFaultPoint.BeforeRecoveryRead && ReadBlocked) throw new IOException("SYNTHETIC read unavailable");
                if (Point == point) { Point = null; throw new IOException("SYNTHETIC fault at " + point); }
            }
        }
        sealed class SnapshotOnlyStore : IStateStore
        {
            readonly RunState state;
            public SnapshotOnlyStore(RunState state) { this.state = state; }
            public bool CanMutate => true;
            public string ConfirmedHash => "";
            public RunState Read() => state.Copy();
            public CommandResult Execute(string id, string digest, long revision, Func<RunState, CommandReceipt> apply) => throw new InvalidOperationException("Availability-only test store");
            public CommandResult Recover(string id) => throw new InvalidOperationException("Availability-only test store");
        }
        sealed class UnavailableProvider : IRewardedAdService
        {
            public bool IsAvailable => false;
            public CommandResult Show(string requestId, string runId) => throw new InvalidOperationException("Unavailable provider cannot be shown");
            public IReadOnlyList<FakeAdEvent> ReadEvents(string requestId) => new FakeAdEvent[0];
        }
    }
}

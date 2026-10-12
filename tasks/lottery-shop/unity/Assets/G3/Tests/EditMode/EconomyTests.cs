using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Lottery.G3.Core;
using Lottery.G3.Persistence;
using NUnit.Framework;

namespace Lottery.G3.EditMode.Tests
{
    // Frozen rules oracle: G1 e959108cb2a4ef080862565de5b87814ccdfae14026204227e767d049bbdf668.
    // Every economic action uses DayGameService + FileStateStore. Synthetic stock/carried
    // inventory is created BEFORE opening a run, is labelled, and pays the frozen price.
    // Inspecting the saved challenge arrangement below is a synthetic unit-test driver,
    // never a player-visible hint, a forced prize, or evidence of natural play quality.
    public sealed class EconomyTests
    {
        static readonly string[] ToolIds = { "small_prize_box", "ticket_clip", "large_prize_stamp", "loss_mat", "inspection_lamp", "cashout_stamp", "alternating_stamp", "last_tickets_stamp" };
        static readonly long[] Prices = { 6000, 4500, 7500, 3000, 4000, 4500, 14000, 14000 };
        static readonly long[][] Upgrades = { new long[] { 9000, 13500 }, new long[] { 6750, 10500 }, new long[] { 12000, 18000 }, new long[] { 4500, 7000 }, new long[] { 6000, 9000 }, new long[] { 6500, 10000 }, new long[0], new long[0] };
        static readonly string[] Goods = { "reveal_film", "seal_sticker", "copy_paper", "boost_coupon" };
        static readonly string[] Qualities = { "common", "rare", "precious" };
        static readonly long[][] GoodsPrices = { new long[] { 1000, 3000, 6000 }, new long[] { 500, 1000, 2000 }, new long[] { 3000, 4500, 6000 }, new long[] { 800, 1600, 3200 } };
        static readonly long[] ChallengePrizes = { 1000, 2000, 3000, 5000, 9000, 18000 };
        const string DefaultSeed = "g3-economy-positive-116";
        string root;
        int command;
        readonly List<FileStateStore> stores = new List<FileStateStore>();

        [SetUp] public void SetUp()
        { root = Path.Combine(Path.GetTempPath(), "g3-economy-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root); command = 0; }
        [TearDown] public void TearDown()
        { foreach (var store in stores) store.Dispose(); stores.Clear(); if (Directory.Exists(root)) Directory.Delete(root, true); }
        string Id() => "economy_" + (++command);
        static long Price(string id) => Prices[Array.IndexOf(ToolIds, id)];
        static long GoodsPrice(string id, string quality) => GoodsPrices[Array.IndexOf(Goods, id)][Array.IndexOf(Qualities, quality)];
        static long Round(long value, long numerator, long denominator) => (value * numerator + denominator / 2) / denominator;
        DayGameService Open(RunState initial)
        {
            var store = new FileStateStore(Path.Combine(root, stores.Count.ToString()), initial); stores.Add(store);
            Assert.That(store.CanMutate, Is.True, "Labelled fixture must pass production invariants");
            AssertIndependent(store.Read()); return new DayGameService(store);
        }
        static RunState Initial(string[] toolStock = null, string goods = "copy_paper", string quality = "common", string seed = DefaultSeed)
        {
            var state = RunFactory.Create("economy_run", seed);
            state.FixtureLabel = "SYNTHETIC_CONSUMABLE_BOUNDARY_FIXTURE";
            state.Stock = new List<StockItem>();
            foreach (string id in toolStock ?? new string[0]) state.Stock.Add(RunFactory.ToolStock(state.RunId, id));
            state.Stock.Add(RunFactory.ConsumableStock(state.RunId, goods, quality));
            state.ConsumableBatch = new[] { goods }.Concat(Goods.Where(x => x != goods)).ToArray();
            return state;
        }
        static void CarryDrawer(RunState initial, int slot, string id, string quality)
        {
            long price = GoodsPrice(id, quality); string stockId = "fixture_prior_drawer_" + slot;
            initial.Drawers[slot] = new DrawerItem { StockId = stockId, ItemId = id, Quality = quality, PurchasePriceMinor = price };
            initial.CashMinor -= price;
            initial.Ledger.Add(new LedgerEntry { CommandId = "fixture-purchase:drawer:" + slot, Kind = "FIXTURE_PRIOR_PURCHASE", ReferenceId = id, DeltaMinor = -price, BalanceMinor = initial.CashMinor });
        }
        static void CarryTool(RunState initial, string id)
        {
            initial.Tools.Add(new OwnedTool { ItemId = id, Level = 1, InitialPaymentMinor = Price(id) }); initial.CashMinor -= Price(id);
            initial.Ledger.Add(new LedgerEntry { CommandId = "fixture-purchase:" + id, Kind = "FIXTURE_PRIOR_PURCHASE", ReferenceId = id, DeltaMinor = -Price(id), BalanceMinor = initial.CashMinor });
        }
        void Ok(DayGameService game, CommandResult result, long delta = 0)
        {
            Assert.That(result.CommitStatus, Is.EqualTo(CommitStatus.COMMITTED), result.Code);
            Assert.That(result.Code, Is.EqualTo("SUCCESS")); Assert.That(result.Receipt.CashDeltaMinor, Is.EqualTo(delta));
            Assert.That(StateCodec.SerializeCanonical(result.State), Is.EqualTo(StateCodec.SerializeCanonical(game.Snapshot)));
            AssertIndependent(game.Snapshot);
        }
        void Reject(DayGameService game, string code, Func<CommandResult> action)
        {
            byte[] before = StateCodec.SerializeCanonical(game.Snapshot); var result = action();
            Assert.That(result.CommitStatus, Is.EqualTo(CommitStatus.PROVEN_NOT_COMMITTED)); Assert.That(result.Code, Is.EqualTo(code));
            Assert.That(StateCodec.SerializeCanonical(game.Snapshot), Is.EqualTo(before), "Failed command changed confirmed state");
            Assert.That(StateCodec.SerializeCanonical(result.State), Is.EqualTo(before)); AssertIndependent(game.Snapshot);
        }
        void BuyTool(DayGameService game, string id)
        { var stock = game.Snapshot.Stock.Single(x => x.ItemId == id); Ok(game, game.BuyStock(stock.StockId, "", Id(), game.Snapshot.Revision), -Price(id)); }
        void BuyGoods(DayGameService game)
        { var stock = game.Snapshot.Stock.Single(x => x.IsConsumable); Ok(game, game.BuyStock(stock.StockId, "", Id(), game.Snapshot.Revision), -GoodsPrice(stock.ItemId, stock.Quality)); }
        void Equip(DayGameService game, string id, int slot = 0)
        { Ok(game, game.EquipTool(id, slot, Id(), game.Snapshot.Revision)); }
        void Fund(DayGameService game)
        { Ok(game, game.Borrow("mother", 50000, Id(), game.Snapshot.Revision), 50000); }
        void Upgrade(DayGameService game, string id)
        { int level = game.Snapshot.Tools.Single(x => x.ItemId == id).Level; Ok(game, game.UpgradeTool(id, Id(), game.Snapshot.Revision), -Upgrades[Array.IndexOf(ToolIds, id)][level - 1]); }
        void BuyTicket(DayGameService game, string type, int boost = -1)
        { Ok(game, game.BuyTicket(type, boost, Id(), game.Snapshot.Revision), -1000); }
        void RevealNumber(DayGameService game)
        { Ok(game, game.QuickReveal(game.Snapshot.CurrentTicket.Id, Id(), game.Snapshot.Revision)); }
        void RevealCell(DayGameService game, int cell)
        {
            string ticket = game.Snapshot.CurrentTicket.Id;
            Ok(game, game.SelectChallengeCell(ticket, cell, Id(), game.Snapshot.Revision));
            Ok(game, game.QuickReveal(ticket, Id(), game.Snapshot.Revision));
        }
        void SafeCells(DayGameService game, int count)
        {
            for (int n = 0; n < count; n++)
            { var ticket = game.Snapshot.CurrentTicket; int cell = Enumerable.Range(0, 8).First(i => ticket.ChallengeSafe[i] && !ticket.RevealedCells[i]); RevealCell(game, cell); }
        }
        void Bust(DayGameService game)
        { var ticket = game.Snapshot.CurrentTicket; RevealCell(game, Enumerable.Range(0, 8).First(i => !ticket.ChallengeSafe[i] && !ticket.RevealedCells[i])); }
        SettlementRecord Claim(DayGameService game)
        {
            var before = game.Snapshot; byte[] bytes = StateCodec.SerializeCanonical(before); var preview = game.PreviewSettlement();
            Assert.That(preview, Is.Not.Null); Assert.That(StateCodec.SerializeCanonical(game.Snapshot), Is.EqualTo(bytes));
            var expected = ExpectedEntries(before.CurrentTicket, ClipTicksBefore(before, before.CurrentTicket));
            AssertEntries(preview, expected); AssertEntries(game.PreviewSettlement(), expected);
            Ok(game, game.Claim(before.CurrentTicket.Id, Id(), before.Revision), expected.Values.Sum());
            var settlement = game.Snapshot.Settlements.Last(); AssertEntries(settlement, expected); return settlement;
        }
        void Use(DayGameService game, int slot, int[] cells = null)
        { Ok(game, game.UseConsumable(game.Snapshot.CurrentTicket.Id, slot, cells ?? new int[0], Id(), game.Snapshot.Revision)); }
        static long Entry(SettlementRecord record, string source) => record.Entries.Where(x => x.Source == source).Sum(x => x.AmountMinor);
        DayGameService ToolGame(string id, int level, string seed = DefaultSeed)
        {
            var initial = Initial(new[] { id }, seed: seed); initial.FixtureLabel = "SYNTHETIC_INVENTORY_BOUNDARY_FIXTURE";
            var game = Open(initial); Fund(game); BuyTool(game, id); Equip(game, id);
            for (int l = 1; l < level; l++) Upgrade(game, id);
            Assert.That(game.Snapshot.Tools.Single().InitialPaymentMinor, Is.EqualTo(Price(id)));
            return game;
        }
        static IEnumerable ToolLevels
        {
            get
            {
                for (int t = 0; t < ToolIds.Length; t++) for (int level = 1; level <= (t < 6 ? 3 : 1); level++)
                    yield return new TestCaseData(ToolIds[t], level).SetName("ToolEffects_" + ToolIds[t] + "_Level" + level);
            }
        }
        [TestCaseSource(nameof(ToolLevels))]
        public void EveryInitiallyOfferableToolUsesFrozenEffects(string id, int level)
        {
            string seed = id == "small_prize_box" ? "g3-economy-small-205" : id == "large_prize_stamp" ? "g3-economy-large-137803" : id == "loss_mat" ? "g3-economy-loss-3" : DefaultSeed;
            var game = ToolGame(id, level, seed); int l = level - 1;
            if (id == "small_prize_box" || id == "large_prize_stamp" || id == "loss_mat")
            {
                long[] raw = id == "small_prize_box" ? new long[] { 2000, 0, 5000 } : id == "large_prize_stamp" ? new long[] { 20000, 5000, 2000 } : new long[] { 0, 2000, 1000 };
                for (int i = 0; i < raw.Length; i++)
                {
                    BuyTicket(game, "number"); Assert.That(game.Snapshot.CurrentTicket.RawPrizeMinor, Is.EqualTo(raw[i]), "Natural seed vector changed");
                    Assert.That(game.Snapshot.CurrentTicket.ConfigurationSnapshot.Single().Level, Is.EqualTo(level)); RevealNumber(game); var record = Claim(game);
                    long expected = id == "small_prize_box" ? (i == 0 ? new long[] { 300, 700, 1500 }[l] : 0) : id == "large_prize_stamp" ? (i == 0 ? new long[] { 3000, 6000, 12000 }[l] : i == 1 ? new long[] { 2500, 5000, 10000 }[l] : 0) : (i == 0 ? new long[] { 200, 350, 500 }[l] : 0);
                    Assert.That(Entry(record, id), Is.EqualTo(expected));
                }
                BuyTicket(game, "challenge"); if (id == "loss_mat") Bust(game); else SafeCells(game, 5);
                Assert.That(Entry(Claim(game), id), Is.EqualTo(id == "loss_mat" ? new long[] { 200, 350, 500 }[l] : 0));
            }
            else if (id == "ticket_clip")
            {
                for (int i = 1; i <= 4; i++)
                {
                    BuyTicket(game, "challenge"); if (i == 2) Bust(game); else SafeCells(game, 1);
                    Assert.That(Entry(Claim(game), id), Is.EqualTo(i == 4 ? new long[] { 750, 1500, 3000 }[l] : 0));
                    Assert.That(game.Snapshot.ToolCounters.Single(x => x.ItemId == id).ClipTicks, Is.EqualTo(i == 1 || i == 2 ? 1 : i == 3 ? 2 : 0));
                }
            }
            else if (id == "inspection_lamp")
            {
                for (int i = 0; i <= level; i++)
                {
                    BuyTicket(game, "challenge"); string ticket = game.Snapshot.CurrentTicket.Id;
                    if (i < level)
                    {
                        Ok(game, game.UseLamp(ticket, 0, Id(), game.Snapshot.Revision));
                        Assert.That(game.Snapshot.CurrentTicket.PeekedCells.Count(x => x), Is.EqualTo(1));
                        Assert.That(game.Snapshot.CurrentTicket.RevealedCells.Any(x => x), Is.False);
                        Reject(game, "INFORMATION_SOURCE_USED", () => game.UseLamp(ticket, 1, Id(), game.Snapshot.Revision));
                    }
                    else Reject(game, "LAMP_DAILY_LIMIT", () => game.UseLamp(ticket, 0, Id(), game.Snapshot.Revision));
                    SafeCells(game, 1); Assert.That(Entry(Claim(game), id), Is.Zero);
                }
                Assert.That(game.Snapshot.ToolCounters.Single(x => x.ItemId == id).UsedToday, Is.EqualTo(level));
            }
            else if (id == "cashout_stamp")
            {
                foreach (int safe in new[] { 1, 2, 3, 4, 6 })
                { BuyTicket(game, "challenge"); SafeCells(game, safe); Assert.That(Entry(Claim(game), id), Is.EqualTo(safe == 2 || safe == 3 ? new long[] { 400, 800, 1500 }[l] : 0)); }
                BuyTicket(game, "challenge"); SafeCells(game, 2); Bust(game); Assert.That(Entry(Claim(game), id), Is.Zero);
            }
            else if (id == "alternating_stamp")
            {
                BuyTicket(game, "number"); RevealNumber(game); Assert.That(Entry(Claim(game), id), Is.Zero);
                BuyTicket(game, "challenge"); SafeCells(game, 5); Assert.That(Entry(Claim(game), id), Is.EqualTo(6000));
                BuyTicket(game, "challenge"); SafeCells(game, 2); Assert.That(Entry(Claim(game), id), Is.Zero);
                BuyTicket(game, "number"); RevealNumber(game); Assert.That(Entry(Claim(game), id), Is.EqualTo(750));
            }
            else
            {
                for (int position = 1; position <= 12; position++)
                {
                    BuyTicket(game, "challenge"); SafeCells(game, position == 11 ? 6 : position == 12 ? 2 : 1);
                    Assert.That(game.Snapshot.CurrentTicket.PurchasedPosition, Is.EqualTo(position));
                    Assert.That(Entry(Claim(game), id), Is.EqualTo(position < 10 ? 0 : position == 10 ? 2000 : position == 11 ? 30000 : 4000));
                }
                Assert.That(game.Snapshot.Phase, Is.EqualTo(DayPhase.CLOSING_PREP));
            }
            if (level == (Array.IndexOf(ToolIds, id) < 6 ? 3 : 1)) Reject(game, "MAX_LEVEL", () => game.UpgradeTool(id, Id(), game.Snapshot.Revision));
        }
        static IEnumerable SnapshotCases
        { get { foreach (string id in ToolIds.Take(6)) yield return new TestCaseData(id).SetName("SnapshotUpgrade_" + id); } }
        [TestCaseSource(nameof(SnapshotCases))]
        public void UpgradeAndUnequipAffectOnlyNextPurchase(string id)
        {
            for (int oldLevel = 1; oldLevel <= 2; oldLevel++)
            {
                string seed = id == "large_prize_stamp" ? "g3-economy-large-137803" : id == "loss_mat" ? "g3-economy-loss-3" : "g3-economy-small-205";
                var game = ToolGame(id, oldLevel, seed);
                if (id == "ticket_clip") for (int i = 0; i < 2; i++) { BuyTicket(game, "challenge"); SafeCells(game, 1); Claim(game); }
                string type = id == "small_prize_box" || id == "large_prize_stamp" || id == "loss_mat" ? "number" : "challenge";
                BuyTicket(game, type); var original = game.Snapshot.CurrentTicket; Upgrade(game, id); Equip(game, "");
                Assert.That(game.Snapshot.CurrentTicket.ConfigurationSnapshot.Single().ItemId, Is.EqualTo(id));
                Assert.That(game.Snapshot.CurrentTicket.ConfigurationSnapshot.Single().Level, Is.EqualTo(oldLevel));
                Assert.That(game.Snapshot.CurrentTicket.ChallengeSafe, Is.EqualTo(original.ChallengeSafe));
                Reject(game, "CURRENT_TICKET_TOOL_LOCKED", () => game.SellTool(id, Id(), game.Snapshot.Revision));
                if (id == "inspection_lamp") Ok(game, game.UseLamp(game.Snapshot.CurrentTicket.Id, 0, Id(), game.Snapshot.Revision));
                if (type == "number") RevealNumber(game); else SafeCells(game, 2);
                long[] expectedBonus = oldLevel == 1 ? new long[] { 300, 750, 3000, 200, 0, 400 } : new long[] { 700, 1500, 6000, 350, 0, 800 };
                Assert.That(Entry(Claim(game), id), Is.EqualTo(expectedBonus[Array.IndexOf(ToolIds, id)]));
                Equip(game, id); BuyTicket(game, type);
                Assert.That(game.Snapshot.CurrentTicket.ConfigurationSnapshot.Single().Level, Is.EqualTo(oldLevel + 1));
                if (id == "inspection_lamp") Ok(game, game.UseLamp(game.Snapshot.CurrentTicket.Id, 0, Id(), game.Snapshot.Revision));
                if (type == "number") RevealNumber(game); else SafeCells(game, 2); Claim(game);
                long cash = game.Snapshot.CashMinor; Ok(game, game.SellTool(id, Id(), game.Snapshot.Revision), Price(id) / 2);
                Assert.That(game.Snapshot.CashMinor, Is.EqualTo(cash + Price(id) / 2), "Upgrade expense must not be refunded");
            }
        }
        static IEnumerable ConsumableCases
        { get { foreach (string id in Goods) foreach (string quality in Qualities) yield return new TestCaseData(id, quality).SetName("ConsumableEffects_" + id + "_" + quality); } }
        [TestCaseSource(nameof(ConsumableCases))]
        public void AllConsumableQualitiesPayAndApplyExactlyOnce(string id, string quality)
        {
            int q = Array.IndexOf(Qualities, quality); var game = Open(Initial(goods: id, quality: quality, seed: "g3-economy-copy_cap-846")); BuyGoods(game);
            Assert.That(game.Snapshot.Drawers.Count(x => x != null), Is.EqualTo(1)); Assert.That(game.Snapshot.Tickets, Is.Empty);
            Reject(game, "OUT_OF_STOCK", () => game.BuyStock(game.Snapshot.Stock.Single().StockId, "", Id(), game.Snapshot.Revision));
            if (id == "boost_coupon")
            {
                Reject(game, "BOOST_NUMBER_ONLY", () => game.BuyTicket("challenge", 0, Id(), game.Snapshot.Revision));
                BuyTicket(game, "number", 0); Assert.That(game.Snapshot.CurrentTicket.EconomicDrawCount, Is.EqualTo(new[] { 2, 3, 5 }[q]));
                RevealNumber(game); Claim(game); BuyTicket(game, "number"); Assert.That(game.Snapshot.CurrentTicket.EconomicDrawCount, Is.EqualTo(1)); RevealNumber(game); Claim(game);
            }
            else if (id == "copy_paper")
            {
                BuyTicket(game, "number"); Reject(game, "COPY_REQUIRES_REVEALED_NUMBER", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, new int[0], Id(), game.Snapshot.Revision));
                RevealNumber(game); Use(game, 0); Assert.That(game.Snapshot.CurrentTicket.CopyMinor, Is.EqualTo(new long[] { 10000, 15000, 20000 }[q]));
                Assert.That(Entry(Claim(game), id), Is.EqualTo(new long[] { 10000, 15000, 20000 }[q]));
                var ratio = Open(Initial(new[] { "large_prize_stamp" }, id, quality, "g3-economy-copy_ratio-59")); BuyGoods(ratio); BuyTool(ratio, "large_prize_stamp"); Equip(ratio, "large_prize_stamp");
                BuyTicket(ratio, "number"); RevealNumber(ratio); Use(ratio, 0); var record = Claim(ratio);
                Assert.That(Entry(record, id), Is.EqualTo(new long[] { 5000, 7500, 10000 }[q])); Assert.That(Entry(record, "large_prize_stamp"), Is.EqualTo(2500));
            }
            else if (id == "reveal_film")
            {
                BuyTicket(game, "challenge"); var before = game.Snapshot.CurrentTicket; int[] targets = Enumerable.Range(0, q + 1).ToArray(); Use(game, 0, targets);
                var after = game.Snapshot.CurrentTicket; Assert.That(after.ChallengeSafe, Is.EqualTo(before.ChallengeSafe)); Assert.That(after.RevealedCells.Any(x => x), Is.False);
                Assert.That(after.PeekedCells.Select((value, index) => new { value, index }).Where(x => x.value).Select(x => x.index), Is.EqualTo(targets));
                Assert.That(after.InformationSource, Is.EqualTo(id)); SafeCells(game, 1); Assert.That(Entry(Claim(game), id), Is.Zero);
            }
            else
            {
                BuyTicket(game, "challenge"); Reject(game, "NEED_SAFE_CELL", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, new int[0], Id(), game.Snapshot.Revision));
                SafeCells(game, 5); Use(game, 0); Assert.That(game.Snapshot.CurrentTicket.ProtectionMinor, Is.EqualTo(new long[] { 3000, 6000, 9000 }[q]));
                Bust(game); Assert.That(Entry(Claim(game), id), Is.EqualTo(new long[] { 3000, 6000, 9000 }[q]));
            }
            Assert.That(game.Snapshot.Drawers.All(x => x == null), Is.True);
            var used = game.Snapshot.Tickets.First(x => x.UsedConsumableTypes.Contains(id)); Assert.That(used.ConsumableCostMinor, Is.EqualTo(GoodsPrice(id, quality)));
            Assert.That(used.ConsumableUses.Single().Quality, Is.EqualTo(quality)); Assert.That(used.ConsumableUses.Single().PurchasePriceMinor, Is.EqualTo(GoodsPrice(id, quality)));
        }
        [TestCase(TestName = "CatalogMatchesEightInitiallyOfferableFrozenTools")]
        public void CatalogMatchesEightInitiallyOfferableFrozenTools()
        {
            Assert.That(DayRules.Tools.Select(x => x.Id), Is.EqualTo(ToolIds));
            for (int i = 0; i < ToolIds.Length; i++)
            {
                var rule = DayRules.Tool(ToolIds[i]); Assert.That(rule.PriceMinor, Is.EqualTo(Prices[i])); Assert.That(rule.UpgradePricesMinor, Is.EqualTo(Upgrades[i]));
                Assert.That(rule.LevelCap, Is.EqualTo(i < 6 ? 3 : 1)); Assert.That(rule.Rarity, Is.EqualTo(i < 6 ? "common" : i == 6 ? "rare" : "precious"));
            }
            foreach (string id in Goods) foreach (string quality in Qualities) Assert.That(DayRules.ConsumablePrice(id, quality), Is.EqualTo(GoodsPrice(id, quality)));
        }
        [TestCase(TestName = "SixOwnedToolsRequireExplicitSeventhReplacement")]
        public void SixOwnedToolsRequireExplicitSeventhReplacement()
        {
            var game = Open(RunFactory.CreateInventoryBoundaryFixture("economy_run"));
            Assert.That(game.Snapshot.CashMinor, Is.EqualTo(500)); Assert.That(game.Snapshot.Tools.Count, Is.EqualTo(6));
            Assert.That(game.Snapshot.NextToolIds.Count(x => x != ""), Is.EqualTo(3));
            string stock = game.Snapshot.Stock.First(x => x.ItemId == "alternating_stamp").StockId;
            Fund(game); Reject(game, "SELECT_REPLACEMENT", () => game.BuyStock(stock, "", Id(), game.Snapshot.Revision));
            Reject(game, "RESERVE_FULL", () => game.EquipTool("", 0, Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "SeventhReplacementAtomicallySellsInitialBasisAndBuys")]
        public void SeventhReplacementAtomicallySellsInitialBasisAndBuys()
        {
            var game = Open(RunFactory.CreateInventoryBoundaryFixture("economy_run")); Fund(game); Upgrade(game, "small_prize_box");
            string stock = game.Snapshot.Stock.First(x => x.ItemId == "alternating_stamp").StockId;
            long before = game.Snapshot.CashMinor; string commandId = Id(); long revision = game.Snapshot.Revision;
            Ok(game, game.BuyStock(stock, "small_prize_box", commandId, revision), -11000);
            Assert.That(game.Snapshot.CashMinor, Is.EqualTo(before - 11000)); Assert.That(game.Snapshot.Tools.Count, Is.EqualTo(6));
            Assert.That(game.Snapshot.Tools.Any(x => x.ItemId == "small_prize_box"), Is.False);
            Assert.That(game.Snapshot.NextToolIds.Count(x => x != ""), Is.EqualTo(3));
            Assert.That(game.Snapshot.Tools.Single(x => x.ItemId == "alternating_stamp").InitialPaymentMinor, Is.EqualTo(14000));
            byte[] committed = StateCodec.SerializeCanonical(game.Snapshot); Ok(game, game.BuyStock(stock, "small_prize_box", commandId, revision), -11000);
            Assert.That(StateCodec.SerializeCanonical(game.Snapshot), Is.EqualTo(committed));
        }
        [TestCase(TestName = "UnaffordableReplacementPreservesOriginalToolAndStock")]
        public void UnaffordableReplacementPreservesOriginalToolAndStock()
        {
            var game = Open(RunFactory.CreateInventoryBoundaryFixture("economy_run")); string stock = game.Snapshot.Stock.First(x => x.ItemId == "alternating_stamp").StockId;
            Reject(game, "INSUFFICIENT_CASH", () => game.BuyStock(stock, "small_prize_box", Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "CurrentSnapshotToolCannotFundAtomicReplacement")]
        public void CurrentSnapshotToolCannotFundAtomicReplacement()
        {
            var game = Open(RunFactory.CreateInventoryBoundaryFixture("economy_run")); Fund(game); BuyTicket(game, "challenge");
            string stock = game.Snapshot.Stock.First(x => x.ItemId == "alternating_stamp").StockId;
            Reject(game, "CURRENT_TICKET_TOOL_LOCKED", () => game.BuyStock(stock, "small_prize_box", Id(), game.Snapshot.Revision));
            string reserve = "loss_mat"; Ok(game, game.SellTool(reserve, Id(), game.Snapshot.Revision), 1500);
            Assert.That(game.Snapshot.CurrentTicket.ConfigurationSnapshot.Any(x => x.ItemId == reserve), Is.False);
        }
        [TestCase(TestName = "TableSwapPreservesThreeTableThreeReservePartition")]
        public void TableSwapPreservesThreeTableThreeReservePartition()
        {
            var game = Open(RunFactory.CreateInventoryBoundaryFixture("economy_run")); string displaced = game.Snapshot.NextToolIds[0];
            Equip(game, "loss_mat", 0); Assert.That(game.Snapshot.NextToolIds[0], Is.EqualTo("loss_mat")); Assert.That(game.Snapshot.NextToolIds.Contains(displaced), Is.False);
            string second = game.Snapshot.NextToolIds[1]; Equip(game, "loss_mat", 1);
            Assert.That(game.Snapshot.NextToolIds[0], Is.EqualTo(second)); Assert.That(game.Snapshot.NextToolIds[1], Is.EqualTo("loss_mat"));
            Reject(game, "NO_CHANGE", () => game.EquipTool("loss_mat", 1, Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "DuplicateOwnedToolCannotBeBoughtAgain")]
        public void DuplicateOwnedToolCannotBeBoughtAgain()
        {
            var initial = Initial(new[] { "ticket_clip" }); CarryTool(initial, "ticket_clip"); var game = Open(initial);
            Reject(game, "ALREADY_OWNED", () => game.BuyStock(game.Snapshot.Stock.First(x => !x.IsConsumable).StockId, "ticket_clip", Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "DrawerSecondSlotReceivesSinglePaidNonstackingItem")]
        public void DrawerSecondSlotReceivesSinglePaidNonstackingItem()
        {
            var initial = Initial(goods: "copy_paper"); CarryDrawer(initial, 0, "copy_paper", "rare"); var game = Open(initial); BuyGoods(game);
            Assert.That(game.Snapshot.Drawers.Count(x => x != null), Is.EqualTo(2)); Assert.That(game.Snapshot.Drawers[0].Quality, Is.EqualTo("rare"));
            Assert.That(game.Snapshot.Drawers[1].Quality, Is.EqualTo("common")); Assert.That(game.Snapshot.Drawers[0].StockId, Is.Not.EqualTo(game.Snapshot.Drawers[1].StockId));
        }
        [TestCase(TestName = "FullDrawerPurchaseRejectsWithoutSpendingOrRestocking")]
        public void FullDrawerPurchaseRejectsWithoutSpendingOrRestocking()
        {
            var initial = Initial(); CarryDrawer(initial, 0, "boost_coupon", "common"); CarryDrawer(initial, 1, "seal_sticker", "common"); var game = Open(initial);
            Reject(game, "DRAWER_FULL", () => game.BuyStock(game.Snapshot.Stock.Single().StockId, "", Id(), game.Snapshot.Revision));
            Reject(game, "INVALID_REPLACEMENT", () => game.BuyStock(game.Snapshot.Stock.Single().StockId, "ticket_clip", Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "SameConsumableTypeCannotConsumeSecondDrawerOnSameTicket")]
        public void SameConsumableTypeCannotConsumeSecondDrawerOnSameTicket()
        {
            var initial = Initial(goods: "copy_paper"); CarryDrawer(initial, 0, "copy_paper", "rare"); var game = Open(initial); BuyGoods(game); BuyTicket(game, "number"); RevealNumber(game); Use(game, 0);
            Reject(game, "CONSUMABLE_TYPE_ALREADY_USED", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 1, new int[0], Id(), game.Snapshot.Revision));
            Assert.That(game.Snapshot.Drawers[1], Is.Not.Null); Claim(game);
        }
        [TestCase(TestName = "BoostAndCopyUseTwoDistinctTypesWithSeparatePaidCosts")]
        public void BoostAndCopyUseTwoDistinctTypesWithSeparatePaidCosts()
        {
            var initial = Initial(goods: "copy_paper", quality: "rare"); CarryDrawer(initial, 0, "boost_coupon", "precious"); var game = Open(initial); BuyGoods(game); BuyTicket(game, "number", 0); RevealNumber(game); Use(game, 1);
            var ticket = game.Snapshot.CurrentTicket; Assert.That(ticket.UsedConsumableTypes, Is.EqualTo(new[] { "boost_coupon", "copy_paper" })); Assert.That(ticket.ConsumableCostMinor, Is.EqualTo(7700));
            var result = Claim(game); Assert.That(result.NetMinor, Is.EqualTo(result.TotalMinor - 1000 - 7700));
        }
        [TestCase(TestName = "PreciousFilmUsesAllThreeRemainingUnopenedCells")]
        public void PreciousFilmUsesAllThreeRemainingUnopenedCells()
        {
            // A live challenge has at least three unopened cells after five safe results.
            // Precious film therefore reaches the exact minimum-three boundary in G3.
            var game = Open(Initial(goods: "reveal_film", quality: "precious")); BuyGoods(game); BuyTicket(game, "challenge"); SafeCells(game, 5);
            int[] remaining = Enumerable.Range(0, 8).Where(i => !game.Snapshot.CurrentTicket.RevealedCells[i]).ToArray(); Assert.That(remaining.Length, Is.EqualTo(3));
            Use(game, 0, remaining); Assert.That(game.Snapshot.CurrentTicket.PeekedCells.Count(x => x), Is.EqualTo(3)); Claim(game);
        }
        [TestCase(TestName = "FilmInvalidDuplicateRevealedAndOutOfRangeTargetsAreAtomic")]
        public void FilmInvalidDuplicateRevealedAndOutOfRangeTargetsAreAtomic()
        {
            var game = Open(Initial(goods: "reveal_film", quality: "rare")); BuyGoods(game); BuyTicket(game, "challenge"); SafeCells(game, 1);
            int revealed = Array.FindIndex(game.Snapshot.CurrentTicket.RevealedCells, x => x); int hidden = Array.FindIndex(game.Snapshot.CurrentTicket.RevealedCells, x => !x);
            foreach (var cells in new[] { new int[0], new[] { hidden }, new[] { hidden, hidden }, new[] { revealed, hidden }, new[] { -1, hidden }, new[] { 8, hidden } })
                Reject(game, "INVALID_INFORMATION_TARGETS", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, cells, Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "LampThenFilmRejectsSecondInformationSource")]
        public void LampThenFilmRejectsSecondInformationSource()
        {
            var game = Open(Initial(new[] { "inspection_lamp" }, "reveal_film")); BuyTool(game, "inspection_lamp"); Equip(game, "inspection_lamp"); BuyGoods(game); BuyTicket(game, "challenge");
            Ok(game, game.UseLamp(game.Snapshot.CurrentTicket.Id, 0, Id(), game.Snapshot.Revision));
            Reject(game, "INFORMATION_SOURCE_USED", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, new[] { 1 }, Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "FilmThenLampRejectsSecondInformationSourceWithoutDailyUse")]
        public void FilmThenLampRejectsSecondInformationSourceWithoutDailyUse()
        {
            var game = Open(Initial(new[] { "inspection_lamp" }, "reveal_film")); BuyTool(game, "inspection_lamp"); Equip(game, "inspection_lamp"); BuyGoods(game); BuyTicket(game, "challenge"); Use(game, 0, new[] { 0 });
            Reject(game, "INFORMATION_SOURCE_USED", () => game.UseLamp(game.Snapshot.CurrentTicket.Id, 1, Id(), game.Snapshot.Revision));
            Assert.That(game.Snapshot.ToolCounters.Single(x => x.ItemId == "inspection_lamp").UsedToday, Is.Zero);
        }
        [TestCase("common", TestName = "SealLockedAmount_common")]
        [TestCase("rare", TestName = "SealLockedAmount_rare")]
        [TestCase("precious", TestName = "SealLockedAmount_precious")]
        public void SealLocksEarlierPrizeAndPaysOnlyOnBust(string quality)
        {
            int q = Array.IndexOf(Qualities, quality);
            foreach (bool bust in new[] { false, true })
            {
                var game = Open(Initial(goods: "seal_sticker", quality: quality)); BuyGoods(game); BuyTicket(game, "challenge"); SafeCells(game, 1); Use(game, 0); SafeCells(game, 3);
                Assert.That(game.Snapshot.CurrentTicket.ProtectionMinor, Is.EqualTo(new long[] { 500, 750, 1000 }[q]));
                if (bust) Bust(game); Assert.That(Entry(Claim(game), "seal_sticker"), Is.EqualTo(bust ? new long[] { 500, 750, 1000 }[q] : 0));
            }
        }
        [TestCase(TestName = "CopyRejectsZeroRawAndNeverUsesLossRefundAsPositivePrize")]
        public void CopyRejectsZeroRawAndNeverUsesLossRefundAsPositivePrize()
        {
            var game = Open(Initial(new[] { "loss_mat", "ticket_clip" }, "copy_paper", "common", "g3-economy-zero-0"));
            BuyTool(game, "loss_mat"); BuyTool(game, "ticket_clip"); Equip(game, "loss_mat"); Equip(game, "ticket_clip", 1); BuyGoods(game); BuyTicket(game, "number"); RevealNumber(game);
            Reject(game, "COPY_REQUIRES_POSITIVE_PRIZE", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, new int[0], Id(), game.Snapshot.Revision));
            var record = Claim(game); Assert.That(record.TotalMinor, Is.EqualTo(200)); Assert.That(game.Snapshot.ToolCounters.Single(x => x.ItemId == "ticket_clip").ClipTicks, Is.Zero);
        }
        [TestCase(TestName = "BoostCannotRedrawExistingTicketOrConsumeOnFailedPurchase")]
        public void BoostCannotRedrawExistingTicketOrConsumeOnFailedPurchase()
        {
            var game = Open(Initial(goods: "boost_coupon")); BuyGoods(game); BuyTicket(game, "number");
            Reject(game, "BOOST_REQUIRES_NEXT_PURCHASE", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, new int[0], Id(), game.Snapshot.Revision));
            Reject(game, "TICKET_OCCUPIED", () => game.BuyTicket("number", 0, Id(), game.Snapshot.Revision));
            Assert.That(game.Snapshot.Drawers[0], Is.Not.Null); Assert.That(game.Snapshot.CurrentTicket.EconomicDrawCount, Is.EqualTo(1));
            RevealNumber(game); Claim(game); long drain = game.Snapshot.CashMinor - 999;
            Ok(game, game.RepayPrincipal(drain, Id(), game.Snapshot.Revision), -drain);
            Reject(game, "INSUFFICIENT_CASH", () => game.BuyTicket("number", 0, Id(), game.Snapshot.Revision));
            Assert.That(game.Snapshot.Drawers[0], Is.Not.Null);
        }
        [TestCase(TestName = "TicketClipTicksSurviveUnequipUpgradeSaleAndReacquisition")]
        public void TicketClipTicksSurviveUnequipUpgradeSaleAndReacquisition()
        {
            var initial = Initial(new[] { "ticket_clip" }); CarryTool(initial, "ticket_clip"); var game = Open(initial); Fund(game); Equip(game, "ticket_clip");
            BuyTicket(game, "challenge"); SafeCells(game, 1); Claim(game); Equip(game, ""); Upgrade(game, "ticket_clip");
            BuyTicket(game, "challenge"); SafeCells(game, 1); Claim(game); Assert.That(game.Snapshot.ToolCounters.Single(x => x.ItemId == "ticket_clip").ClipTicks, Is.EqualTo(1));
            Ok(game, game.SellTool("ticket_clip", Id(), game.Snapshot.Revision), 2250); BuyTool(game, "ticket_clip"); Equip(game, "ticket_clip");
            Assert.That(game.Snapshot.Tools.Single().Level, Is.EqualTo(1));
            BuyTicket(game, "challenge"); SafeCells(game, 1); Assert.That(Entry(Claim(game), "ticket_clip"), Is.Zero);
            BuyTicket(game, "challenge"); SafeCells(game, 1); Assert.That(Entry(Claim(game), "ticket_clip"), Is.EqualTo(750));
        }
        [TestCase(TestName = "LampCapacityUpgradeSubtractsUsedCountAndSaleDoesNotReset")]
        public void LampCapacityUpgradeSubtractsUsedCountAndSaleDoesNotReset()
        {
            var initial = Initial(new[] { "inspection_lamp" }); CarryTool(initial, "inspection_lamp"); var game = Open(initial); Fund(game); Equip(game, "inspection_lamp");
            BuyTicket(game, "challenge"); Ok(game, game.UseLamp(game.Snapshot.CurrentTicket.Id, 0, Id(), game.Snapshot.Revision)); SafeCells(game, 1); Claim(game); Upgrade(game, "inspection_lamp");
            BuyTicket(game, "challenge"); Ok(game, game.UseLamp(game.Snapshot.CurrentTicket.Id, 0, Id(), game.Snapshot.Revision)); SafeCells(game, 1); Claim(game);
            BuyTicket(game, "challenge"); Upgrade(game, "inspection_lamp");
            Reject(game, "LAMP_DAILY_LIMIT", () => game.UseLamp(game.Snapshot.CurrentTicket.Id, 0, Id(), game.Snapshot.Revision)); SafeCells(game, 1); Claim(game);
            Ok(game, game.SellTool("inspection_lamp", Id(), game.Snapshot.Revision), 2000); BuyTool(game, "inspection_lamp"); Equip(game, "inspection_lamp"); BuyTicket(game, "challenge");
            Reject(game, "LAMP_DAILY_LIMIT", () => game.UseLamp(game.Snapshot.CurrentTicket.Id, 0, Id(), game.Snapshot.Revision));
            Assert.That(game.Snapshot.ToolCounters.Single(x => x.ItemId == "inspection_lamp").UsedToday, Is.EqualTo(2));
        }
        [TestCase(TestName = "InvalidEquipmentDrawerAndInformationSlotsDoNotMutate")]
        public void InvalidEquipmentDrawerAndInformationSlotsDoNotMutate()
        {
            var game = ToolGame("inspection_lamp", 1);
            foreach (int slot in new[] { -1, 3 }) Reject(game, "INVALID_SLOT", () => game.EquipTool("inspection_lamp", slot, Id(), game.Snapshot.Revision));
            BuyTicket(game, "challenge");
            foreach (int slot in new[] { -1, 2 }) Reject(game, "INVALID_DRAWER_SLOT", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, slot, new int[0], Id(), game.Snapshot.Revision));
            Reject(game, "DRAWER_EMPTY", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, new int[0], Id(), game.Snapshot.Revision));
            foreach (int cell in new[] { -1, 8 }) Reject(game, "INVALID_CELL", () => game.UseLamp(game.Snapshot.CurrentTicket.Id, cell, Id(), game.Snapshot.Revision));
            SafeCells(game, 1); int revealed = Array.FindIndex(game.Snapshot.CurrentTicket.RevealedCells, x => x);
            Reject(game, "INVALID_CELL", () => game.UseLamp(game.Snapshot.CurrentTicket.Id, revealed, Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "UnownedUnknownAndUnaffordableShoppingActionsRejectAtomically")]
        public void UnownedUnknownAndUnaffordableShoppingActionsRejectAtomically()
        {
            var game = Open(Initial(new[] { "large_prize_stamp" }));
            Reject(game, "TOOL_NOT_OWNED", () => game.EquipTool("large_prize_stamp", 0, Id(), game.Snapshot.Revision));
            Reject(game, "TOOL_NOT_OWNED", () => game.UpgradeTool("large_prize_stamp", Id(), game.Snapshot.Revision));
            Reject(game, "TOOL_NOT_OWNED", () => game.SellTool("large_prize_stamp", Id(), game.Snapshot.Revision));
            Reject(game, "STOCK_NOT_FOUND", () => game.BuyStock("absent", "", Id(), game.Snapshot.Revision));
            BuyTool(game, "large_prize_stamp"); Ok(game, game.RepayPrincipal(game.Snapshot.CashMinor, Id(), game.Snapshot.Revision), -22500);
            Reject(game, "INSUFFICIENT_CASH", () => game.UpgradeTool("large_prize_stamp", Id(), game.Snapshot.Revision));
            Reject(game, "INSUFFICIENT_CASH", () => game.BuyStock(game.Snapshot.Stock.Single(x => x.IsConsumable).StockId, "", Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "BuyingAndEquippingAfterPurchaseDoesNotAddCurrentSnapshotTool")]
        public void BuyingAndEquippingAfterPurchaseDoesNotAddCurrentSnapshotTool()
        {
            var game = Open(Initial(new[] { "small_prize_box" }, seed: "g3-economy-small-205")); BuyTicket(game, "number"); BuyTool(game, "small_prize_box"); Equip(game, "small_prize_box");
            Assert.That(game.Snapshot.CurrentTicket.ConfigurationSnapshot, Is.Empty); RevealNumber(game); Assert.That(Entry(Claim(game), "small_prize_box"), Is.Zero);
            BuyTicket(game, "number"); Assert.That(game.Snapshot.CurrentTicket.ConfigurationSnapshot.Single().ItemId, Is.EqualTo("small_prize_box"));
        }
        [TestCase(TestName = "PendingChallengeSelectionBlocksShoppingInformationAndConsumables")]
        public void PendingChallengeSelectionBlocksShoppingInformationAndConsumables()
        {
            var game = Open(Initial(new[] { "inspection_lamp" }, "reveal_film")); BuyTool(game, "inspection_lamp"); Equip(game, "inspection_lamp"); BuyGoods(game); BuyTicket(game, "challenge");
            string ticket = game.Snapshot.CurrentTicket.Id; Ok(game, game.SelectChallengeCell(ticket, 0, Id(), game.Snapshot.Revision));
            Reject(game, "REVEAL_PENDING", () => game.UpgradeTool("inspection_lamp", Id(), game.Snapshot.Revision));
            Reject(game, "REVEAL_PENDING", () => game.EquipTool("", 0, Id(), game.Snapshot.Revision));
            Reject(game, "REVEAL_PENDING", () => game.UseLamp(ticket, 1, Id(), game.Snapshot.Revision));
            Reject(game, "REVEAL_PENDING", () => game.UseConsumable(ticket, 0, new[] { 1 }, Id(), game.Snapshot.Revision));
        }
        [TestCase(TestName = "ThirdConsumableTypeCannotExceedPerTicketLimit")]
        public void ThirdConsumableTypeCannotExceedPerTicketLimit()
        {
            var initial = Initial(goods: "copy_paper"); CarryDrawer(initial, 0, "reveal_film", "common"); CarryDrawer(initial, 1, "seal_sticker", "common");
            var game = Open(initial); BuyTicket(game, "challenge"); Use(game, 0, new[] { 0 }); SafeCells(game, 1); Use(game, 1); BuyGoods(game);
            Assert.That(game.Snapshot.CurrentTicket.UsedConsumableTypes.Count, Is.EqualTo(2));
            Reject(game, "CONSUMABLE_TYPE_LIMIT", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, new int[0], Id(), game.Snapshot.Revision));
            Assert.That(game.Snapshot.Drawers[0].ItemId, Is.EqualTo("copy_paper"));
        }
        [TestCase(TestName = "WrongTicketTypesAndUnexpectedTargetsLeaveConsumablesIntact")]
        public void WrongTicketTypesAndUnexpectedTargetsLeaveConsumablesIntact()
        {
            foreach (string goods in new[] { "reveal_film", "seal_sticker", "copy_paper" })
            {
                var game = Open(Initial(goods: goods)); BuyGoods(game); BuyTicket(game, goods == "copy_paper" ? "challenge" : "number");
                int[] targets = goods == "reveal_film" ? new[] { 0 } : new int[0];
                Reject(game, goods == "copy_paper" ? "COPY_REQUIRES_REVEALED_NUMBER" : "CHALLENGE_ONLY", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, targets, Id(), game.Snapshot.Revision));
                if (goods != "reveal_film") Reject(game, "UNEXPECTED_TARGETS", () => game.UseConsumable(game.Snapshot.CurrentTicket.Id, 0, new[] { 0 }, Id(), game.Snapshot.Revision));
            }
        }
        [TestCase(TestName = "ReopenPreservesLockedSnapshotOutcomesWalletAndPersistentCounters")]
        public void ReopenPreservesLockedSnapshotOutcomesWalletAndPersistentCounters()
        {
            var initial = Initial(new[] { "ticket_clip", "inspection_lamp" }); var game = Open(initial); Fund(game);
            BuyTool(game, "ticket_clip"); BuyTool(game, "inspection_lamp"); Equip(game, "ticket_clip"); Equip(game, "inspection_lamp", 1);
            BuyTicket(game, "challenge"); Ok(game, game.UseLamp(game.Snapshot.CurrentTicket.Id, 0, Id(), game.Snapshot.Revision)); SafeCells(game, 1); Claim(game);
            Upgrade(game, "ticket_clip"); BuyTicket(game, "challenge"); Upgrade(game, "ticket_clip"); Equip(game, "");
            byte[] expected = StateCodec.SerializeCanonical(game.Snapshot); int directoryIndex = stores.Count - 1; stores[directoryIndex].Dispose();
            var reopenedStore = new FileStateStore(Path.Combine(root, directoryIndex.ToString()), initial); stores.Add(reopenedStore);
            Assert.That(reopenedStore.CanMutate, Is.True); var reopened = new DayGameService(reopenedStore);
            Assert.That(StateCodec.SerializeCanonical(reopened.Snapshot), Is.EqualTo(expected)); AssertIndependent(reopened.Snapshot);
            Assert.That(reopened.Snapshot.Tools.Single(x => x.ItemId == "ticket_clip").Level, Is.EqualTo(3));
            Assert.That(reopened.Snapshot.CurrentTicket.ConfigurationSnapshot.Single(x => x.ItemId == "ticket_clip").Level, Is.EqualTo(2));
            Reject(reopened, "LAMP_DAILY_LIMIT", () => reopened.UseLamp(reopened.Snapshot.CurrentTicket.Id, 0, Id(), reopened.Snapshot.Revision));
            SafeCells(reopened, 1); Claim(reopened); Assert.That(reopened.Snapshot.ToolCounters.Single(x => x.ItemId == "ticket_clip").ClipTicks, Is.EqualTo(2));
        }
        [TestCase(TestName = "RareBonusesRequirePositiveRawAtOtherwiseEligibleTriggers")]
        public void RareBonusesRequirePositiveRawAtOtherwiseEligibleTriggers()
        {
            var alternating = ToolGame("alternating_stamp", 1); BuyTicket(alternating, "number"); RevealNumber(alternating); Claim(alternating);
            BuyTicket(alternating, "challenge"); Bust(alternating); Assert.That(Entry(Claim(alternating), "alternating_stamp"), Is.Zero);
            var last = ToolGame("last_tickets_stamp", 1);
            for (int position = 1; position <= 12; position++)
            {
                BuyTicket(last, "challenge"); if (position == 10 || position == 12) Bust(last); else SafeCells(last, 1);
                Assert.That(Entry(Claim(last), "last_tickets_stamp"), Is.EqualTo(position == 11 ? 2000 : 0));
            }
        }
        static int ClipTicksBefore(RunState state, TicketState ticket)
        {
            int ticks = 0;
            foreach (var previous in state.Tickets)
            {
                if (previous.Id == ticket.Id) break;
                if (previous.Phase == TicketPhase.SETTLED && previous.RawPrizeMinor > 0 && previous.ConfigurationSnapshot.Any(x => x.ItemId == "ticket_clip")) ticks = (ticks + 1) % 3;
            }
            return ticks;
        }
        static Dictionary<string, long> ExpectedEntries(TicketState ticket, int clipTicks)
        {
            var expected = new Dictionary<string, long> { { "raw_prize", ticket.RawPrizeMinor } };
            foreach (var tool in ticket.ConfigurationSnapshot)
            {
                long amount = 0; int l = tool.Level - 1; long raw = ticket.RawPrizeMinor;
                if (tool.ItemId == "small_prize_box" && ticket.TicketType == "number" && raw >= 1 && raw <= 2000) amount = new long[] { 300, 700, 1500 }[l];
                if (tool.ItemId == "ticket_clip" && raw > 0 && clipTicks == 2) amount = new long[] { 750, 1500, 3000 }[l];
                if (tool.ItemId == "large_prize_stamp" && ticket.TicketType == "number" && raw >= 5000) amount = Math.Min(Round(raw, new long[] { 1, 1, 2 }[l], new long[] { 2, 1, 1 }[l]), new long[] { 3000, 6000, 12000 }[l]);
                if (tool.ItemId == "loss_mat" && raw == 0) amount = new long[] { 200, 350, 500 }[l];
                if (tool.ItemId == "cashout_stamp" && ticket.TicketType == "challenge" && !ticket.Busted && (ticket.SafeCount == 2 || ticket.SafeCount == 3)) amount = new long[] { 400, 800, 1500 }[l];
                if (tool.ItemId == "alternating_stamp" && raw > 0 && ticket.PreviousSettledTicketType != "" && ticket.PreviousSettledTicketType != ticket.TicketType) amount = Math.Min(Round(raw, 3, 4), 6000);
                if (tool.ItemId == "last_tickets_stamp" && raw > 0 && ticket.PurchasedPosition >= 10 && ticket.PurchasedPosition <= 12) amount = Math.Min(raw * 2, 30000);
                if (amount != 0) expected.Add(tool.ItemId, amount);
            }
            var copy = ticket.ConsumableUses.SingleOrDefault(x => x.ItemId == "copy_paper");
            if (copy != null)
            {
                int q = Array.IndexOf(Qualities, copy.Quality); long value = Math.Min(Round(ticket.RawPrizeMinor, new long[] { 1, 3, 2 }[q], new long[] { 1, 2, 1 }[q]), new long[] { 10000, 15000, 20000 }[q]);
                Assert.That(ticket.CopyMinor, Is.EqualTo(value)); Assert.That(copy.LockedAmountMinor, Is.EqualTo(value)); expected.Add("copy_paper", value);
            }
            else Assert.That(ticket.CopyMinor, Is.Zero);
            if (ticket.Busted && ticket.ProtectionMinor > 0) expected.Add("seal_sticker", ticket.ProtectionMinor);
            return expected;
        }
        static void AssertEntries(SettlementRecord record, Dictionary<string, long> expected)
        {
            Assert.That(record.Entries.Select(x => x.Source), Is.EquivalentTo(expected.Keys)); Assert.That(record.Entries.Count, Is.EqualTo(expected.Count));
            foreach (var entry in record.Entries) Assert.That(entry.AmountMinor, Is.EqualTo(expected[entry.Source]), entry.Source);
            Assert.That(record.TotalMinor, Is.EqualTo(expected.Values.Sum())); Assert.That(record.NetMinor, Is.EqualTo(record.TotalMinor - record.TicketPriceMinor - record.ConsumableCostMinor));
        }
        static void AssertIndependent(RunState state)
        {
            // This oracle intentionally does NOT call production prize, face, settlement,
            // price, probability, ratio or invariant helpers to obtain expected values.
            Assert.That(state.RulesHash, Is.EqualTo("e959108cb2a4ef080862565de5b87814ccdfae14026204227e767d049bbdf668"));
            Assert.That(state.InitialCashMinor, Is.EqualTo(30000)); long balance = 30000;
            foreach (var line in state.Ledger)
            {
                balance += line.DeltaMinor; Assert.That(line.BalanceMinor, Is.EqualTo(balance)); Assert.That(balance, Is.GreaterThanOrEqualTo(0));
                if (line.Kind != "FIXTURE_PRIOR_PURCHASE")
                {
                    var receipt = state.Commands.Single(x => x.CommandId == line.CommandId);
                    Assert.That(line.DeltaMinor, Is.EqualTo(receipt.CashDeltaMinor)); Assert.That(line.Kind, Is.EqualTo(receipt.Kind));
                }
                else
                {
                    Assert.That(state.FixtureLabel.StartsWith("SYNTHETIC_", StringComparison.Ordinal), Is.True);
                    Assert.That(line.DeltaMinor, Is.LessThan(0));
                }
            }
            Assert.That(state.CashMinor, Is.EqualTo(balance)); Assert.That(state.Ledger.Select(x => x.CommandId).Distinct().Count(), Is.EqualTo(state.Ledger.Count));
            Assert.That(state.Commands.Count, Is.EqualTo(state.Revision));
            foreach (var receipt in state.Commands) Assert.That(state.Ledger.Count(x => x.CommandId == receipt.CommandId), Is.EqualTo(receipt.CashDeltaMinor == 0 ? 0 : 1));
            Assert.That(state.Tools.Count, Is.LessThanOrEqualTo(6)); Assert.That(state.Tools.Select(x => x.ItemId).Distinct().Count(), Is.EqualTo(state.Tools.Count));
            Assert.That(state.NextToolIds.Length, Is.EqualTo(3)); Assert.That(state.Tools.Count - state.NextToolIds.Count(x => x != ""), Is.LessThanOrEqualTo(3));
            Assert.That(state.NextToolIds.Where(x => x != "").Distinct().Count(), Is.EqualTo(state.NextToolIds.Count(x => x != "")));
            Assert.That(state.Drawers.Length, Is.EqualTo(2)); Assert.That(state.Stock.Count(x => x.IsConsumable), Is.EqualTo(1)); Assert.That(state.ConsumableBatch.Distinct().Count(), Is.EqualTo(4));
            foreach (var item in state.Stock) Assert.That(item.PriceMinor, Is.EqualTo(item.IsConsumable ? GoodsPrice(item.ItemId, item.Quality) : Price(item.ItemId)));
            var shop = new ReferenceStream(state.Seed, "shop-supply-v1"); var selected = new HashSet<string>();
            for (int slot = 0; slot < 3; slot++)
            {
                int rarity = slot < 2 ? 0 : shop.Next(1000000); string[] pool = rarity < 800000 ? ToolIds.Take(6).Where(x => !selected.Contains(x)).ToArray() : new[] { rarity < 995000 ? "alternating_stamp" : "last_tickets_stamp" };
                selected.Add(pool[shop.Next(pool.Length)]);
            }
            for (int remaining = 4; remaining >= 2; remaining--) shop.Next(remaining); shop.Next(1000000);
            Assert.That(state.ShopCounter, Is.EqualTo(shop.Counter), "Initial synthetic stock must not reroll the shop stream");
            var economic = new ReferenceStream(state.Seed, "economic-awards-v1"); var challenge = new ReferenceStream(state.Seed, "challenge-arrangements-v1");
            int clipTicks = 0, lampUses = 0, settlements = 0;
            for (int index = 0; index < state.Tickets.Count; index++)
            {
                var ticket = state.Tickets[index]; Assert.That(ticket.Id, Is.EqualTo(state.RunId + ":ticket-" + (index + 1)));
                Assert.That(ticket.PurchasedPosition, Is.EqualTo(index + 1)); Assert.That(ticket.PriceMinor, Is.EqualTo(1000));
                var purchaseLine = state.Ledger.Single(x => x.CommandId == ticket.PurchaseCommandId);
                Assert.That(purchaseLine.DeltaMinor, Is.EqualTo(-1000)); Assert.That(purchaseLine.BalanceMinor, Is.EqualTo(ticket.CashAfterPurchaseMinor));
                Assert.That(ticket.PreviousSettledTicketType, Is.EqualTo(index == 0 ? "" : state.Tickets[index - 1].TicketType));
                Assert.That(ticket.EconomicCounterBefore, Is.EqualTo(economic.Counter)); Assert.That(ticket.ChallengeCounterBefore, Is.EqualTo(challenge.Counter));
                if (ticket.TicketType == "number")
                {
                    var boost = ticket.ConsumableUses.SingleOrDefault(x => x.ItemId == "boost_coupon"); int draws = boost == null ? 1 : new[] { 2, 3, 5 }[Array.IndexOf(Qualities, boost.Quality)];
                    long award = 0; for (int i = 0; i < draws; i++) award = Math.Max(award, ReferencePrize(economic.Next(1000000)));
                    Assert.That(ticket.EconomicDrawCount, Is.EqualTo(draws)); Assert.That(ticket.RawPrizeMinor, Is.EqualTo(award)); AssertFace(state.Seed, ticket);
                    Assert.That(ticket.ChallengeSafe, Is.Empty); Assert.That(ticket.RevealedCells, Is.Empty);
                    Assert.That(ticket.Phase == TicketPhase.ACTIVE, Is.EqualTo(!ticket.Scratch.IsFullyRevealed));
                }
                else
                {
                    bool[] arrangement = { true, true, true, true, true, true, false, false };
                    for (int i = 7; i > 0; i--) { int chosen = challenge.Next(i + 1); bool held = arrangement[i]; arrangement[i] = arrangement[chosen]; arrangement[chosen] = held; }
                    Assert.That(ticket.ChallengeSafe, Is.EqualTo(arrangement)); Assert.That(ticket.Face, Is.Null);
                    int safe = Enumerable.Range(0, 8).Count(i => ticket.RevealedCells[i] && arrangement[i]); bool busted = Enumerable.Range(0, 8).Any(i => ticket.RevealedCells[i] && !arrangement[i]);
                    Assert.That(ticket.SafeCount, Is.EqualTo(safe)); Assert.That(ticket.Busted, Is.EqualTo(busted)); Assert.That(ticket.RawPrizeMinor, Is.EqualTo(busted || safe == 0 ? 0 : ChallengePrizes[safe - 1]));
                    for (int cell = 0; cell < 8; cell++) Assert.That(ticket.Scratch.CellCoverage(cell) == 1, Is.EqualTo(ticket.RevealedCells[cell]));
                    if (ticket.LampUsed) lampUses++;
                }
                Assert.That(ticket.EconomicCounterAfter, Is.EqualTo(economic.Counter)); Assert.That(ticket.ChallengeCounterAfter, Is.EqualTo(challenge.Counter));
                Assert.That(ticket.UsedConsumableTypes.Count, Is.LessThanOrEqualTo(2)); Assert.That(ticket.UsedConsumableTypes.Distinct().Count(), Is.EqualTo(ticket.UsedConsumableTypes.Count));
                Assert.That(ticket.UsedConsumableTypes, Is.EqualTo(ticket.ConsumableUses.Select(x => x.ItemId))); Assert.That(ticket.ConsumableCostMinor, Is.EqualTo(ticket.ConsumableUses.Sum(x => x.PurchasePriceMinor)));
                foreach (var use in ticket.ConsumableUses) Assert.That(use.PurchasePriceMinor, Is.EqualTo(GoodsPrice(use.ItemId, use.Quality)), "These fixtures contain no ad discounts");
                var settlement = state.Settlements.SingleOrDefault(x => x.TicketId == ticket.Id);
                Assert.That(ticket.Phase == TicketPhase.SETTLED, Is.EqualTo(settlement != null));
                if (settlement != null)
                {
                    AssertEntries(settlement, ExpectedEntries(ticket, clipTicks)); Assert.That(settlement.RawPrizeMinor, Is.EqualTo(ticket.RawPrizeMinor));
                    Assert.That(settlement.ConsumableCostMinor, Is.EqualTo(ticket.ConsumableCostMinor)); Assert.That(settlement.TicketPriceMinor, Is.EqualTo(1000));
                    if (ticket.RawPrizeMinor > 0 && ticket.ConfigurationSnapshot.Any(x => x.ItemId == "ticket_clip")) clipTicks = (clipTicks + 1) % 3;
                    settlements++;
                }
            }
            Assert.That(state.EconomicCounter, Is.EqualTo(economic.Counter)); Assert.That(state.ChallengeCounter, Is.EqualTo(challenge.Counter));
            Assert.That(state.ToolCounters.Single(x => x.ItemId == "ticket_clip").ClipTicks, Is.EqualTo(clipTicks)); Assert.That(state.ToolCounters.Single(x => x.ItemId == "inspection_lamp").UsedToday, Is.EqualTo(lampUses));
            Assert.That(state.TicketsPurchasedToday, Is.EqualTo(state.Tickets.Count)); Assert.That(state.TicketsPurchasedToday, Is.LessThanOrEqualTo(12));
            Assert.That(state.SettledTicketCount, Is.EqualTo(settlements)); Assert.That(state.LifetimeEffectiveTickets, Is.EqualTo(settlements));
        }
        static long ReferencePrize(int sample)
        {
            int[] cutoffs = { 400000, 600000, 820000, 950000, 997000, 999800, 999980, 1000000 };
            long[] prizes = { 0, 500, 1000, 2000, 5000, 20000, 100000, 1000000 };
            for (int i = 0; i < cutoffs.Length; i++) if (sample < cutoffs[i]) return prizes[i];
            throw new InvalidOperationException("Reference sample outside frozen distribution");
        }
        static void AssertFace(string seed, TicketState ticket)
        {
            var random = new ReferenceStream(seed, "ticket-display-v1\0" + ticket.Id + "\0"); int publicNumber = 1 + random.Next(49); int winning = ticket.RawPrizeMinor > 0 ? random.Next(6) : -1;
            Assert.That(ticket.Face.GeneratorVersion, Is.EqualTo("number-face-n1-sha256-v1")); Assert.That(ticket.Face.WinningNumber, Is.EqualTo(publicNumber)); Assert.That(ticket.Face.Cells.Length, Is.EqualTo(6));
            var pool = Enumerable.Range(1, 49).Where(x => x != publicNumber).ToList(); long[] distractors = { 500, 1000, 2000, 5000 };
            for (int cell = 0; cell < 6; cell++)
            {
                if (cell == winning) { Assert.That(ticket.Face.Cells[cell].Number, Is.EqualTo(publicNumber)); Assert.That(ticket.Face.Cells[cell].PrizeMinor, Is.EqualTo(ticket.RawPrizeMinor)); }
                else
                {
                    int position = random.Next(pool.Count); int number = pool[position]; pool.RemoveAt(position); long value = distractors[random.Next(4)];
                    Assert.That(ticket.Face.Cells[cell].Number, Is.EqualTo(number)); Assert.That(ticket.Face.Cells[cell].PrizeMinor, Is.EqualTo(value));
                }
            }
            Assert.That(ticket.Face.Cells.Select(x => x.Number).Distinct().Count(), Is.EqualTo(6));
            Assert.That(ticket.Face.Cells.Count(x => x.Number == publicNumber), Is.EqualTo(ticket.RawPrizeMinor > 0 ? 1 : 0));
        }
        // Independent SHA-256 stream implementation from the frozen byte contract.
        // It shares no production RNG, face constructor or award lookup implementation.
        sealed class ReferenceStream
        {
            readonly byte[] key;
            public ulong Counter { get; private set; }
            public ReferenceStream(string seed, string domain)
            { using (var sha = SHA256.Create()) key = sha.ComputeHash(Encoding.UTF8.GetBytes("lottery-sha256-stream-v1\0" + seed + "\0" + domain)); }
            public int Next(int bound)
            {
                ulong residue = 1; for (int byteIndex = 0; byteIndex < 32; byteIndex++) residue = (residue * 256) % (ulong)bound;
                while (true)
                {
                    byte[] input = new byte[48]; Array.Copy(key, input, 32); ulong cursor = Counter++;
                    for (int offset = 0; offset < 8; offset++) { input[47 - offset] = (byte)(cursor & 255); cursor >>= 8; }
                    byte[] hash; using (var sha = SHA256.Create()) hash = sha.ComputeHash(input);
                    bool upperMaximum = true; for (int n = 0; n < 28; n++) upperMaximum &= hash[n] == 255;
                    ulong last = 0; for (int n = 28; n < 32; n++) last = last * 256 + hash[n];
                    if (residue > 0 && upperMaximum && last >= 4294967296UL - residue) continue;
                    ulong remainder = 0; foreach (byte value in hash) remainder = (remainder * 256 + value) % (ulong)bound; return (int)remainder;
                }
            }
        }
    }
}

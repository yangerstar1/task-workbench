using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Lottery.G2.Core;
using Lottery.G2.Persistence;
using Lottery.G2.Ads;
using NUnit.Framework;
using UnityEngine;
namespace Lottery.G2.EditMode.Tests
{
    public sealed class CoreTests
    {
        string root;
        readonly List<FileStateStore> stores = new List<FileStateStore>();
        [SetUp] public void SetUp() { root = Path.Combine(Path.GetTempPath(), "lottery-g2-tests-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root); }
        [TearDown] public void TearDown() { foreach (var store in stores) store.Dispose(); stores.Clear(); if (Directory.Exists(root)) Directory.Delete(root, true); }
        FileStateStore Open(string name = "normal", RunState initial = null, IStoreFaultInjector faults = null)
        { var store = new FileStateStore(Path.Combine(root, name), initial ?? RunState.CreateNew("test-run", "g2-tests"), faults); stores.Add(store); return store; }
        static ScratchStroke[] FullBrush()
        {
            var strokes = new List<ScratchStroke>();
            for (int y = 0; y < 128; y += 7) strokes.Add(new ScratchStroke(0, y / 127.0, 1, y / 127.0, true, 7));
            strokes.Add(new ScratchStroke(0, 1, 1, 1, true, 7)); return strokes.ToArray();
        }
        static void Reveal(TicketService service, string id = "scratch")
        { var s = service.Snapshot; Assert.That(service.ApplyScratch(s.CurrentTicket.Id, id, s.Revision, FullBrush()).Status, Is.EqualTo(CommitStatus.COMMITTED)); }
        static void Buy(TicketService service, string id = "buy") { Assert.That(service.BuyNumberTicket(id, service.Snapshot.Revision).Status, Is.EqualTo(CommitStatus.COMMITTED)); }
        static void Claim(TicketService service, string id = "claim") { var s = service.Snapshot; Assert.That(service.Claim(s.CurrentTicket.Id, id, s.Revision).Status, Is.EqualTo(CommitStatus.COMMITTED)); }
        static RunState AdFixture(string seed = "ad-seed")
        { var state = RunState.CreateNew("ad-run", seed); state.FixtureLabel = "SYNTHETIC_AD_FIXTURE"; state.DayNumber = 2; state.SettledTicketCount = state.FixtureBaseSettlements = 12; return state; }
        static void Begin(AdPurchaseService ad) { Assert.That(ad.BeginAd("request", "begin", 0, 60).Status, Is.EqualTo(CommitStatus.COMMITTED)); }
        static void RewardReady(FileStateStore store, FakeRewardedAdService fake, AdPurchaseService ad)
        {
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.Reward);
            var e = fake.ReadEvents("request").Single(); Assert.That(ad.RecordEvent(e, "record-reward", store.Read().Revision).Committed, Is.True);
            Assert.That(ad.MarkCommitting("request", "mark-commit", store.Read().Revision).Committed, Is.True);
        }
        [Test] public void ExactWeightsAndAllSixteenBoundaries()
        {
            int[] starts = { 0, 400000, 600000, 820000, 950000, 997000, 999800, 999980 };
            int[] ends = { 399999, 599999, 819999, 949999, 996999, 999799, 999979, 999999 };
            long[] prizes = { 0, 500, 1000, 2000, 5000, 20000, 100000, 1000000 };
            long weighted = 0;
            for (int i = 0; i < prizes.Length; i++) { Assert.That(NumberTicketRules.PrizeForSample(starts[i]), Is.EqualTo(prizes[i])); Assert.That(NumberTicketRules.PrizeForSample(ends[i]), Is.EqualTo(prizes[i])); weighted += (ends[i] - starts[i] + 1L) * prizes[i]; }
            Assert.That(weighted, Is.EqualTo(909000000));
            Assert.Throws<ArgumentOutOfRangeException>(() => NumberTicketRules.PrizeForSample(-1)); Assert.Throws<ArgumentOutOfRangeException>(() => NumberTicketRules.PrizeForSample(1000000));
        }
        [Serializable] sealed class Vectors { public string rulesSha256; public Vector[] numberFaces; }
        [Serializable] sealed class Vector { public Input input; public Face face; }
        [Serializable] sealed class Input { public string ticket_id, display_master_seed, display_domain; public int ticket_price_minor; public long locked_raw_prize_minor; }
        [Serializable] sealed class Face { public int public_number; public Cell[] cells; public string generator_version; }
        [Serializable] sealed class Cell { public int number; public long amount_minor; }
        [Test] public void ExactG1SixteenFrozenFaceVectors()
        {
            string path = Path.GetFullPath(Path.Combine(Application.dataPath, "../../data/g1-number-face-vectors.json"));
            var vectors = JsonUtility.FromJson<Vectors>(File.ReadAllText(path)); Assert.That(vectors.rulesSha256, Is.EqualTo(NumberTicketRules.RulesSha256)); Assert.That(vectors.numberFaces.Length, Is.EqualTo(16));
            foreach (var v in vectors.numberFaces)
            {
                var face = NumberTicketRules.BuildFace(v.input.display_master_seed, v.input.ticket_id, v.input.locked_raw_prize_minor, v.input.display_domain, v.input.ticket_price_minor);
                Assert.That(face.WinningNumber, Is.EqualTo(v.face.public_number), v.input.ticket_id); Assert.That(face.GeneratorVersion, Is.EqualTo(v.face.generator_version));
                for (int i = 0; i < 6; i++) { Assert.That(face.Cells[i].Number, Is.EqualTo(v.face.cells[i].number), v.input.ticket_id + ":" + i); Assert.That(face.Cells[i].PrizeMinor, Is.EqualTo(v.face.cells[i].amount_minor)); }
            }
        }
        [Test] public void N1HasExactlyOnePositiveMatchAndZeroZeroPrizeMatches()
        {
            foreach (long prize in new long[] { 0, 500, 1000, 2000, 5000, 20000, 100000, 1000000 })
            {
                var face = NumberTicketRules.BuildFace("shape", "ticket", prize); NumberTicketRules.ValidateFace(face, prize);
                Assert.That(face.Cells.Select(c => c.Number).Distinct().Count(), Is.EqualTo(6));
                Assert.That(face.Cells.Count(c => c.Number == face.WinningNumber), Is.EqualTo(prize > 0 ? 1 : 0));
            }
        }
        [Test] public void DisplayConsumptionNeverChangesEconomicStream()
        {
            var a = new DeterministicStream("seed", NumberTicketRules.EconomicDomain); var b = new DeterministicStream("seed", NumberTicketRules.EconomicDomain);
            for (int i = 0; i < 30; i++) { NumberTicketRules.BuildFace("seed", "display-" + i, 500); Assert.That(a.Next(1000000), Is.EqualTo(b.Next(1000000))); }
        }
        [Test] public void BuyLocksFullFaceAndDebitsOnceAcrossReloadAndStaleRetry()
        {
            var store = Open(); var service = new TicketService(store); Buy(service); var original = service.Snapshot; string hash = StateCodec.ComputeHash(original);
            store.Dispose(); var reload = Open(); var again = new TicketService(reload);
            Assert.That(StateCodec.ComputeHash(again.Snapshot), Is.EqualTo(hash)); var result = again.BuyNumberTicket("buy", 0);
            Assert.That(result.Committed, Is.True); Assert.That(result.Receipt.Revision, Is.EqualTo(1)); Assert.That(result.State.CashMinor, Is.EqualTo(29000)); Assert.That(result.State.Tickets.Count, Is.EqualTo(1));
            Assert.That(again.BuyNumberTicket("different", result.State.Revision).Code, Is.EqualTo("TICKET_OCCUPIED"));
        }
        [Test] public void CommandIdCannotBeReusedForDifferentRequest()
        {
            var service = new TicketService(Open()); Buy(service);
            Assert.That(service.Claim(service.Snapshot.CurrentTicket.Id, "buy", 0).Code, Is.EqualTo("COMMAND_ID_REUSED"));
        }
        [Test] public void NewCommandHonorsExpectedRevision()
        { var service = new TicketService(Open()); Assert.That(service.BuyNumberTicket("buy", 1).Code, Is.EqualTo("STALE_REVISION")); Assert.That(service.Snapshot.CashMinor, Is.EqualTo(30000)); }
        [Test] public void UnrevealedPrizeDoesNotEnterWalletAndCannotBeClaimed()
        {
            var service = new TicketService(Open()); Buy(service); var state = service.Snapshot;
            Assert.That(state.CashMinor, Is.EqualTo(29000)); Assert.That(service.Claim(state.CurrentTicket.Id, "claim", state.Revision).Code, Is.EqualTo("NOT_FULLY_REVEALED"));
        }
        [Test] public void ClaimWritesUniqueSettlementAndSingleWalletCredit()
        {
            var service = new TicketService(Open()); Buy(service); Reveal(service); long raw = service.Snapshot.CurrentTicket.RawPrizeMinor; Claim(service);
            var result = service.Claim(service.Snapshot.CurrentTicket.Id, "claim", 0);
            Assert.That(result.Committed, Is.True); Assert.That(result.State.CashMinor, Is.EqualTo(29000 + raw)); Assert.That(result.State.SettledTicketCount, Is.EqualTo(1));
            Assert.That(result.State.Settlements.Single().NetMinor, Is.EqualTo(raw - 1000)); Assert.That(result.State.Settlements.Single().AdditionMinor, Is.Zero);
            Assert.That(service.Claim(result.State.CurrentTicket.Id, "another", result.State.Revision).Code, Is.EqualTo("ALREADY_SETTLED"));
        }
        [Test] public void ZeroPrizeStillSettlesExactlyOnce()
        {
            string seed = Enumerable.Range(0, 100).Select(i => "zero-" + i).First(s => NumberTicketRules.PrizeForSample(new DeterministicStream(s, NumberTicketRules.EconomicDomain).Next(1000000)) == 0);
            var service = new TicketService(Open(initial: RunState.CreateNew("test-run", seed))); Buy(service); Reveal(service); Claim(service);
            Assert.That(service.Snapshot.CashMinor, Is.EqualTo(29000)); Assert.That(service.Snapshot.Settlements.Single().TotalMinor, Is.Zero); Assert.That(service.Snapshot.SettledTicketCount, Is.EqualTo(1));
        }
        [Test] public void TwelveTicketProbeLimitDoesNotAdvanceDay()
        {
            var service = new TicketService(Open()); for (int i = 0; i < 12; i++) { Buy(service, "buy-" + i); Reveal(service, "scratch-" + i); Claim(service, "claim-" + i); }
            Assert.That(service.BuyNumberTicket("thirteenth", service.Snapshot.Revision).Code, Is.EqualTo("DAY_LIMIT")); Assert.That(service.Snapshot.DayNumber, Is.EqualTo(1)); Assert.That(service.Snapshot.TicketsPurchasedToday, Is.EqualTo(12));
        }
        [Test] public void SnapshotMutationCannotChangeCommittedState()
        { var service = new TicketService(Open()); var state = service.Snapshot; state.CashMinor = 0; Assert.That(service.Snapshot.CashMinor, Is.EqualTo(30000)); }
        [Test] public void DuplicateBrushCountsOnlyNewBitsAndInterpolatesContinuously()
        {
            var mask = new ScratchMask(); var stroke = new ScratchStroke(0.1, 0.25, 0.9, 0.25, true, 3);
            Assert.That(mask.Apply(new[] { stroke }), Is.True); byte[] bytes = mask.ToBytes(); Assert.That(mask.Apply(new[] { stroke }), Is.False); Assert.That(mask.ToBytes(), Is.EqualTo(bytes));
            for (int x = 26; x < 229; x++) Assert.That(mask.IsRevealed(x, 32), Is.True, "interpolated gap at " + x);
            Assert.That(mask.IsRevealed(128, 100), Is.False);
        }
        [Test] public void BrushBoundsAndBatchValidationAreAtomic()
        {
            var mask = new ScratchMask(); Assert.That(mask.Apply(new[] { new ScratchStroke(0, 0, 0, 0, false, 7) }), Is.True); Assert.That(mask.IsRevealed(0, 0), Is.True);
            byte[] before = mask.ToBytes(); Assert.Throws<ArgumentException>(() => mask.Apply(new[] { new ScratchStroke(0, 0, .7, .7, false, 7), new ScratchStroke(0, 0, 1.1, .5, false, 7) })); Assert.That(mask.ToBytes(), Is.EqualTo(before));
        }
        [Test] public void CellNinetyPercentCompletionUsesActualBitsOnly()
        {
            var mask = new ScratchMask(); var region = ScratchMask.GetCellRegion(0); var strokes = new List<ScratchStroke>();
            for (int y = 0; y < 57; y += 5) strokes.Add(new ScratchStroke(0, y / 127.0, (region.Width - 1) / 255.0, y / 127.0, true, 3));
            mask.Apply(strokes.ToArray()); Assert.That(mask.CellCoverage(0), Is.EqualTo(1)); Assert.That(mask.RevealedCellCount, Is.EqualTo(1)); Assert.That(mask.IsFullyRevealed, Is.False);
        }
        [Test] public void HalfScratchRestoresExactCommittedBitset()
        {
            var store = Open(); var service = new TicketService(store); Buy(service); var s = service.Snapshot;
            service.ApplyScratch(s.CurrentTicket.Id, "half", s.Revision, new[] { new ScratchStroke(.05, .2, .45, .2, true, 7) });
            byte[] mask = service.Snapshot.CurrentTicket.Scratch.ToBytes(); string face = StateCodec.ComputeHash(service.Snapshot); store.Dispose(); var reload = new TicketService(Open());
            Assert.That(reload.Snapshot.CurrentTicket.Scratch.ToBytes(), Is.EqualTo(mask)); Assert.That(StateCodec.ComputeHash(reload.Snapshot), Is.EqualTo(face)); Assert.That(reload.Snapshot.CurrentTicket.Phase, Is.EqualTo(TicketPhase.ACTIVE));
        }
        sealed class Faults : IStoreFaultInjector
        {
            public StoreFaultPoint? Point; public bool ReadBlocked;
            public void OnPoint(StoreFaultPoint point)
            { if (point == StoreFaultPoint.BeforeRecoveryRead && ReadBlocked) throw new IOException("SYNTHETIC read unavailable"); if (Point == point) { Point = null; throw new IOException("SYNTHETIC fault at " + point); } }
        }
        void CheckFaultWindows(string operation)
        {
            foreach (var point in new[] { StoreFaultPoint.BeforeWrite, StoreFaultPoint.TempHalfWritten, StoreFaultPoint.TempFlushed, StoreFaultPoint.BeforePublish, StoreFaultPoint.AfterPublish, StoreFaultPoint.BeforeResponse })
            {
                var faults = new Faults(); var store = Open(operation + point, operation == "ad" ? AdFixture() : null, faults); var service = new TicketService(store);
                FakeRewardedAdService fake = null; AdPurchaseService ad = null;
                if (operation == "scratch" || operation == "claim") Buy(service);
                if (operation == "claim") Reveal(service);
                if (operation == "ad") { fake = new FakeRewardedAdService(store); ad = new AdPurchaseService(store, fake); Begin(ad); RewardReady(store, fake, ad); }
                var before = service.Snapshot; string oldHash = StateCodec.ComputeHash(before); faults.Point = point;
                CommandResult result;
                if (operation == "buy") result = service.BuyNumberTicket("fault-command", before.Revision);
                else if (operation == "scratch") result = service.ApplyScratch(before.CurrentTicket.Id, "fault-command", before.Revision, new[] { new ScratchStroke(.1, .1, .5, .1, true, 7) });
                else if (operation == "claim") result = service.Claim(before.CurrentTicket.Id, "fault-command", before.Revision);
                else result = ad.CommitAd("request", "fault-command", before.Revision);
                bool committed = point == StoreFaultPoint.AfterPublish || point == StoreFaultPoint.BeforeResponse;
                Assert.That(result.Status, Is.EqualTo(committed ? CommitStatus.COMMITTED : CommitStatus.PROVEN_NOT_COMMITTED), operation + point);
                string expected = StateCodec.ComputeHash(result.State); if (!committed) Assert.That(expected, Is.EqualTo(oldHash));
                store.Dispose(); var reloaded = Open(operation + point, operation == "ad" ? AdFixture() : null);
                Assert.That(StateCodec.ComputeHash(reloaded.Read()), Is.EqualTo(expected), "reload " + operation + point);
                Assert.That(reloaded.Recover("fault-command").Status, Is.EqualTo(result.Status)); Assert.That(reloaded.Read().CashMinor, Is.GreaterThanOrEqualTo(0));
            }
        }
        [Test] public void BuySixFileFaultWindowsRecoverAuthoritativeLedger() { CheckFaultWindows("buy"); }
        [Test] public void ScratchSixFileFaultWindowsRecoverAuthoritativeLedger() { CheckFaultWindows("scratch"); }
        [Test] public void ClaimSixFileFaultWindowsRecoverAuthoritativeLedger() { CheckFaultWindows("claim"); }
        [Test] public void AdCommitSixFileFaultWindowsRecoverAuthoritativeLedger() { CheckFaultWindows("ad"); }
        [Test] public void UnknownCommitBlocksNewCommandUntilSameIdRecovery()
        {
            var faults = new Faults { Point = StoreFaultPoint.AfterPublish, ReadBlocked = true }; var store = Open(faults: faults); var service = new TicketService(store);
            var unknown = service.BuyNumberTicket("buy", 0); Assert.That(unknown.Status, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN)); Assert.That(unknown.Code, Is.EqualTo("COMMIT_UNKNOWN")); Assert.That(service.CanMutate, Is.False);
            Assert.That(service.BuyNumberTicket("second", 0).Status, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN)); Assert.That(service.Snapshot.CurrentTicket, Is.Null);
            faults.ReadBlocked = false; var recovered = service.Recover("buy"); Assert.That(recovered.Committed, Is.True); Assert.That(recovered.State.CashMinor, Is.EqualTo(29000)); Assert.That(service.CanMutate, Is.True);
            Assert.That(service.BuyNumberTicket("buy", 0).Committed, Is.True); Assert.That(service.Snapshot.Tickets.Count, Is.EqualTo(1));
        }
        [Test] public void UnknownUnpublishedCommitCanOnlyRetryAfterProof()
        {
            var faults = new Faults { Point = StoreFaultPoint.BeforePublish, ReadBlocked = true }; var store = Open(faults: faults); var service = new TicketService(store);
            Assert.That(service.BuyNumberTicket("buy", 0).Status, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN)); faults.ReadBlocked = false;
            Assert.That(service.Recover("buy").Code, Is.EqualTo("SAVE_NOT_COMMITTED")); Assert.That(service.BuyNumberTicket("buy", 0).Committed, Is.True);
        }
        [Test] public void CorruptConfirmedStateNeverFallsBackToOlderBackup()
        {
            var store = Open(); var service = new TicketService(store); Buy(service); Reveal(service); store.Dispose();
            string path = Path.Combine(root, "normal", "state.bin"); File.WriteAllBytes(path, new byte[] { 1, 2, 3 });
            FileStateStore reload = null; Assert.DoesNotThrow(() => reload = Open()); Assert.That(reload.CanMutate, Is.False); Assert.That(reload.Read().RecoveryRequired, Is.True);
            Assert.That(reload.Recover("buy").Code, Is.EqualTo("RECOVERY_REQUIRED")); Assert.That(new TicketService(reload).BuyNumberTicket("must-stay-blocked", reload.Read().Revision).Code, Is.EqualTo("RECOVERY_REQUIRED"));
            Assert.That(File.ReadAllBytes(path), Is.EqualTo(new byte[] { 1, 2, 3 })); Assert.That(File.Exists(Path.Combine(root, "normal", "previous.bin")), Is.True);
        }
        [Test] public void MalformedLengthPrefixesBlockStateCommitAndIntentWithoutChangingFiles()
        {
            byte[][] malformedInputs = { new byte[] { 0x80, 0x80, 0x80, 0x80, 0x80 }, new byte[] { 0xff, 0xff, 0xff, 0xff, 0x0f }, new byte[] { 0x80 }, Array.Empty<byte>() };
            for (int i = 0; i < malformedInputs.Length; i++)
            {
                byte[] malformed = malformedInputs[i]; Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(malformed));
                foreach (string filename in new[] { "state.bin", "commit.record", "intent.record" })
                {
                    string name = "malformed-" + i + "-" + filename; var original = Open(name); original.Dispose();
                    string path = Path.Combine(root, name, filename); File.WriteAllBytes(path, malformed);
                    FileStateStore reload = null; Assert.DoesNotThrow(() => reload = Open(name), filename); Assert.That(reload.CanMutate, Is.False, filename); Assert.That(reload.Read().RecoveryRequired, Is.True, filename);
                    var result = reload.Recover("unresolved"); Assert.That(result.Code, Is.EqualTo("RECOVERY_REQUIRED"), filename); Assert.That(result.Status, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN), filename);
                    Assert.That(new TicketService(reload).BuyNumberTicket("must-stay-blocked", reload.Read().Revision).Code, Is.EqualTo("RECOVERY_REQUIRED"), filename);
                    Assert.That(File.ReadAllBytes(path), Is.EqualTo(malformed), filename);
                }
            }
        }
        [Test] public void UnknownSchemaIsRejectedAndOriginalBytesPreserved()
        {
            var original = Open(); var state = original.Read(); original.Dispose(); state.SchemaVersion = 99; byte[] bytes = StateCodec.SerializeCanonical(state);
            Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(bytes));
            string path = Path.Combine(root, "normal", "state.bin");
            using (var stream = new MemoryStream()) using (var writer = new BinaryWriter(stream))
            { writer.Write("LOTTERY-G2-CHECKSUM-v1"); writer.Write(bytes.Length); writer.Write(StateCodec.HashBytes(bytes)); writer.Write(bytes); writer.Flush(); File.WriteAllBytes(path, stream.ToArray()); }
            byte[] unknownVersionFile = File.ReadAllBytes(path); FileStateStore reload = null; Assert.DoesNotThrow(() => reload = Open());
            Assert.That(reload.CanMutate, Is.False); Assert.That(reload.Read().RecoveryRequired, Is.True); Assert.That(reload.Recover("unresolved").Code, Is.EqualTo("RECOVERY_REQUIRED"));
            Assert.That(new TicketService(reload).BuyNumberTicket("must-stay-blocked", reload.Read().Revision).Code, Is.EqualTo("RECOVERY_REQUIRED")); Assert.That(File.ReadAllBytes(path), Is.EqualTo(unknownVersionFile));
        }
        [Test] public void ExclusiveWriterRejectsSecondStoreWithoutDeletingSave()
        { var store = Open(); var second = Open(); Assert.That(store.CanMutate, Is.True); Assert.That(second.CanMutate, Is.False); Assert.That(second.Read().RecoveryRequired, Is.True); }
        [Test] public void NormalFirstDayUsesOrdinaryPurchaseWithoutAd()
        {
            var store = Open(); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake);
            Assert.That(ad.GetAvailability(1000).Reason, Is.EqualTo("AD_TUTORIAL_DAY")); Assert.That(ad.GetAvailability(1000).CanBuyNormally, Is.True);
            Assert.That(ad.BuyNormally("ordinary", 0).Committed, Is.True); Assert.That(store.Read().CashMinor, Is.EqualTo(29200)); Assert.That(store.Read().Drawers.Count(x => x != null), Is.EqualTo(1));
            Assert.That(ad.BuyNormally("ordinary", 0).Committed, Is.True); Assert.That(store.Read().CashMinor, Is.EqualTo(29200));
        }
        [Test] public void SyntheticAdQualificationChecksSecondsCountDayAndCooldown()
        {
            var state = AdFixture(); var store = Open("eligible", state); var ad = new AdPurchaseService(store, new FakeRewardedAdService(store));
            Assert.That(ad.GetAvailability(59).Reason, Is.EqualTo("AD_FIRST_LAUNCH_DELAY")); Assert.That(ad.GetAvailability(60).CanWatchAd, Is.True);
            state = AdFixture(); state.SettledTicketCount = state.FixtureBaseSettlements = 11; var low = Open("low", state); Assert.That(new AdPurchaseService(low, new FakeRewardedAdService(low)).GetAvailability(60).Reason, Is.EqualTo("AD_MINIMUM_SETTLEMENTS"));
            state = AdFixture(); state.SettledCountAtLastAdSuccess = 1; var cooldown = Open("cooldown", state); Assert.That(new AdPurchaseService(cooldown, new FakeRewardedAdService(cooldown)).GetAvailability(60).Reason, Is.EqualTo("AD_COOLDOWN"));
        }
        [Test] public void CloseThenLateRewardKeepsReservationAndCommitsOnce()
        {
            var store = Open(initial: AdFixture()); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake); Begin(ad);
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.Closed); ad.PollAd("request", "poll", store.Read().Revision);
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.CLOSED_AWAITING_REWARD)); Assert.That(store.Read().CashMinor, Is.EqualTo(30000)); Assert.That(store.Read().StockAvailable, Is.True);
            Assert.That(ad.BuyNormally("steal", store.Read().Revision).Code, Is.EqualTo("RESOURCE_RESERVED"));
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.Reward); Assert.That(ad.PollAd("request", "poll-2", store.Read().Revision).Committed, Is.True);
            ad.PollAd("request", "poll-3", store.Read().Revision); Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTED)); Assert.That(store.Read().CashMinor, Is.EqualTo(29600)); Assert.That(store.Read().AdSuccessesToday, Is.EqualTo(1));
        }
        [Test] public void RewardThenCloseAndDuplicateRewardCannotDoubleSpend()
        {
            var store = Open(initial: AdFixture()); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake); Begin(ad);
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.Reward); ad.PollAd("request", "poll", store.Read().Revision);
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.Closed); fake.QueueEvent("request", store.Read().RunId, AdEventKind.Reward, "duplicate-reward"); ad.PollAd("request", "again", store.Read().Revision);
            Assert.That(store.Read().CashMinor, Is.EqualTo(29600)); Assert.That(store.Read().Commands.Count(c => c.Kind == "AD_COMMIT"), Is.EqualTo(1)); Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTED));
        }
        [Test] public void WrongRequestAndWrongRunCallbacksNeverReward()
        {
            var store = Open(initial: AdFixture()); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake); Begin(ad);
            fake.QueueEvent("wrong-request", store.Read().RunId, AdEventKind.Reward); fake.QueueEvent("request", "wrong-run", AdEventKind.Reward); ad.PollAd("request", "poll", store.Read().Revision);
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.SHOWING)); Assert.That(store.Read().CashMinor, Is.EqualTo(30000));
        }
        [Test] public void DefinitiveNoRewardThenRewardIsRecoveryConflict()
        {
            var store = Open(initial: AdFixture()); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake); Begin(ad);
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.NoRewardTerminal); ad.PollAd("request", "poll", store.Read().Revision); Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.ABORTED_NO_REWARD));
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.Reward); ad.PollAd("request", "late", store.Read().Revision);
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.RECOVERY_CONFLICT)); Assert.That(store.Read().CashMinor, Is.EqualTo(30000)); Assert.That(store.Read().StockAvailable, Is.True);
        }
        [Test] public void FakeReceiptSourceAndWaitingReservationSurviveStoreRebuild()
        {
            var store = Open(initial: AdFixture()); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake); Begin(ad);
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.Closed); ad.PollAd("request", "poll", store.Read().Revision);
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.Reward); store.Dispose(); var reload = Open(initial: AdFixture()); var restored = new AdPurchaseService(reload, new FakeRewardedAdService(reload));
            Assert.That(reload.Read().Ad.Phase, Is.EqualTo(AdPhase.CLOSED_AWAITING_REWARD)); Assert.That(restored.PollAd("request", "restore", reload.Read().Revision).Committed, Is.True); Assert.That(reload.Read().CashMinor, Is.EqualTo(29600));
        }
        [Test] public void AdCreatedAndReservedResumeOriginalRequestAfterStoreRebuild()
        {
            foreach (bool reserve in new[] { false, true })
            {
                string name = "resume-" + reserve; var store = Open(name, AdFixture()); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake);
                Assert.That(ad.CreateAd("request", "original-create", 0, 60).Committed, Is.True);
                if (reserve) Assert.That(ad.ReserveAd("request", "original-reserve", store.Read().Revision).Committed, Is.True);
                store.Dispose(); var reload = Open(name, AdFixture()); var resumed = new AdPurchaseService(reload, new FakeRewardedAdService(reload));
                Assert.That(resumed.PollAd("request", "poll", reload.Read().Revision).Committed, Is.True); Assert.That(reload.Read().Ad.Phase, Is.EqualTo(AdPhase.SHOWING)); Assert.That(reload.Read().FakeShownRequests.Count, Is.EqualTo(1));
                resumed.PollAd("request", "again", reload.Read().Revision); Assert.That(reload.Read().FakeShownRequests.Count, Is.EqualTo(1)); Assert.That(reload.Read().CashMinor, Is.EqualTo(30000));
            }
        }
        [Test] public void RewardConfirmationAndCommitIntentSurviveStoreRebuild()
        {
            var store = Open(initial: AdFixture()); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake); Begin(ad); RewardReady(store, fake, ad); store.Dispose();
            var reload = Open(initial: AdFixture()); Assert.That(reload.Read().Ad.Phase, Is.EqualTo(AdPhase.COMMITTING)); var restored = new AdPurchaseService(reload, new FakeRewardedAdService(reload));
            Assert.That(restored.CommitAd("request", "final", reload.Read().Revision).Committed, Is.True); Assert.That(reload.Read().CashMinor, Is.EqualTo(29600));
        }
        [Test] public void ValidRewardFromReservedPhaseIsDurablyConfirmed()
        {
            var store = Open(initial: AdFixture()); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake);
            Assert.That(ad.CreateAd("request", "create", 0, 60).Committed, Is.True); Assert.That(ad.ReserveAd("request", "reserve", store.Read().Revision).Committed, Is.True);
            fake.QueueEvent("request", store.Read().RunId, AdEventKind.Reward); var receipt = fake.ReadEvents("request").Single();
            Assert.That(ad.RecordEvent(receipt, "record", store.Read().Revision).Committed, Is.True); Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.REWARD_CONFIRMED)); Assert.That(store.Read().CashMinor, Is.EqualTo(30000));
        }
        [Test] public void InsufficientCashAndReservedCashNeverGoNegative()
        {
            var initial = AdFixture(); initial.InitialCashMinor = initial.CashMinor = 1200;
            var store = Open(initial: initial); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake); Begin(ad);
            var tickets = new TicketService(store); Assert.That(tickets.BuyNumberTicket("spend-reserved", store.Read().Revision).Code, Is.EqualTo("INSUFFICIENT_CASH")); Assert.That(store.Read().CashMinor, Is.EqualTo(1200));
            var empty = AdFixture(); empty.InitialCashMinor = empty.CashMinor = 999; var low = new TicketService(Open("low-cash", empty));
            Assert.That(low.BuyNumberTicket("buy", 0).Code, Is.EqualTo("INSUFFICIENT_CASH")); Assert.That(low.Snapshot.CurrentTicket, Is.Null);
        }
        [Test] public void ChangedOriginalStockBecomesConflictWithoutReplacement()
        {
            var store = Open(initial: AdFixture()); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake);
            Assert.That(ad.CreateAd("request", "create", 0, 60).Committed, Is.True); Assert.That(ad.BuyNormally("normal", store.Read().Revision).Committed, Is.True);
            Assert.That(ad.ReserveAd("request", "reserve", store.Read().Revision).Committed, Is.True);
            Assert.That(store.Read().Ad.Phase, Is.EqualTo(AdPhase.RECOVERY_CONFLICT)); Assert.That(store.Read().StockAvailable, Is.False); Assert.That(store.Read().Drawers.Count(x => x != null), Is.EqualTo(1)); Assert.That(store.Read().CashMinor, Is.EqualTo(29200));
        }
        [Test] public void AdUnknownCommitRetainsReservationUntilAuthoritativeRecovery()
        {
            var faults = new Faults(); var store = Open(initial: AdFixture(), faults: faults); var fake = new FakeRewardedAdService(store); var ad = new AdPurchaseService(store, fake); Begin(ad); RewardReady(store, fake, ad);
            faults.Point = StoreFaultPoint.AfterPublish; faults.ReadBlocked = true; var result = ad.CommitAd("request", "final", store.Read().Revision);
            Assert.That(result.Status, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN)); Assert.That(result.State.Ad.Phase, Is.EqualTo(AdPhase.COMMITTING)); Assert.That(store.CanMutate, Is.False);
            faults.ReadBlocked = false; Assert.That(store.Recover("final").Committed, Is.True); Assert.That(store.Read().CashMinor, Is.EqualTo(29600));
        }
    }
}

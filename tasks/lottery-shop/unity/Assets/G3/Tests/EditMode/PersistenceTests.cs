using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Lottery.G3.Core;
using Lottery.G3.Persistence;
using NUnit.Framework;
using ScratchStroke = Lottery.G2.Core.ScratchStroke;

namespace Lottery.G3.EditMode.Tests
{
    public sealed class PersistenceTests
    {
        string root;
        readonly List<FileStateStore> stores = new List<FileStateStore>();
        [SetUp] public void SetUp() { root = Path.Combine(Path.GetTempPath(), "lottery-g3-store-tests-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root); }
        [TearDown] public void TearDown() { foreach (var store in stores) store.Dispose(); stores.Clear(); if (Directory.Exists(root)) Directory.Delete(root, true); }
        FileStateStore Open(string name = "normal", IStoreFaultInjector faults = null)
        { var store = new FileStateStore(Path.Combine(root, name), RunFactory.Create("test-run", "g3-store-test-seed"), faults); stores.Add(store); return store; }
        string PathFor(string filename, string name = "normal") => Path.Combine(root, name, filename);
        static void Committed(CommandResult result) { Assert.That(result.CommitStatus, Is.EqualTo(CommitStatus.COMMITTED), result.Code); }
        sealed class Faults : IStoreFaultInjector
        {
            public StoreFaultPoint? Point; public bool ReadBlocked;
            public void OnPoint(StoreFaultPoint point)
            {
                if (point == StoreFaultPoint.BeforeRecoveryRead && ReadBlocked) throw new IOException("SYNTHETIC recovery read unavailable");
                if (Point == point) { Point = null; throw new IOException("SYNTHETIC fault at " + point); }
            }
        }
        static readonly StoreFaultPoint[] Windows = { StoreFaultPoint.BeforeWrite, StoreFaultPoint.TempHalfWritten, StoreFaultPoint.TempFlushed, StoreFaultPoint.BeforePublish, StoreFaultPoint.AfterPublish, StoreFaultPoint.BeforeResponse };
        public static IEnumerable<TestCaseData> AtomicWindows
        {
            get
            {
                foreach (string operation in new[] { "buy-number", "buy-challenge", "scratch", "claim", "select", "reveal-challenge" })
                    foreach (var point in Windows)
                        foreach (bool coldRecovery in new[] { false, true })
                            yield return new TestCaseData(operation, point, coldRecovery).SetName("Atomic_" + operation.Replace("-", "_") + "_" + point + (coldRecovery ? "_cold" : "_live"));
            }
        }
        static void Prepare(DayGameService service, string operation)
        {
            if (operation == "scratch" || operation == "claim") Committed(service.BuyNumberTicket("prepare-buy", service.Snapshot.Revision));
            if (operation == "claim") Committed(service.QuickReveal(service.Snapshot.CurrentTicket.Id, "prepare-reveal", service.Snapshot.Revision));
            if (operation == "select" || operation == "reveal-challenge") Committed(service.BuyChallengeTicket("prepare-buy", service.Snapshot.Revision));
            if (operation == "reveal-challenge") Committed(service.SelectChallengeCell(service.Snapshot.CurrentTicket.Id, 0, "prepare-select", service.Snapshot.Revision));
        }
        static CommandResult Perform(DayGameService service, string operation, long revision)
        {
            const string id = "fault-command";
            switch (operation)
            {
                case "buy-number": return service.BuyNumberTicket(id, revision);
                case "buy-challenge": return service.BuyChallengeTicket(id, revision);
                case "scratch": return service.ApplyScratch(service.Snapshot.CurrentTicket.Id, new[] { new ScratchStroke(.1, .1, .2, .1, true, 7) }, id, revision);
                case "claim": return service.Claim(service.Snapshot.CurrentTicket.Id, id, revision);
                case "select": return service.SelectChallengeCell(service.Snapshot.CurrentTicket.Id, 0, id, revision);
                case "reveal-challenge": return service.QuickReveal(service.Snapshot.CurrentTicket.Id, id, revision);
                default: throw new ArgumentException(operation);
            }
        }
        [TestCaseSource(nameof(AtomicWindows))]
        public void AllAtomicWindowsKeepExactlyOldOrExactlyNewState(string operation, StoreFaultPoint point, bool coldRecovery)
        {
            var faults = new Faults(); var store = Open(faults: faults); var service = new DayGameService(store); Prepare(service, operation);
            var before = service.Snapshot; string beforeHash = StateCodec.ComputeHash(before);
            faults.Point = point; faults.ReadBlocked = coldRecovery; var result = Perform(service, operation, before.Revision);
            bool published = point == StoreFaultPoint.AfterPublish || point == StoreFaultPoint.BeforeResponse;
            var expectedStatus = published ? CommitStatus.COMMITTED : CommitStatus.PROVEN_NOT_COMMITTED;
            if (coldRecovery)
            {
                Assert.That(result.CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN)); Assert.That(store.CanMutate, Is.False);
                Assert.That(StateCodec.ComputeHash(result.State), Is.EqualTo(beforeHash), "Unknown may expose only last-confirmed state");
                Assert.That(result.Receipt, Is.Null); Assert.That(result.State.PendingCommandId, Is.EqualTo("fault-command"));
                store.Dispose(); store = Open(); service = new DayGameService(store); result = store.Recover("fault-command");
            }
            Assert.That(result.CommitStatus, Is.EqualTo(expectedStatus)); Assert.That(store.CanMutate, Is.True);
            if (!published) Assert.That(StateCodec.ComputeHash(result.State), Is.EqualTo(beforeHash));
            else
            {
                Assert.That(result.State.Revision, Is.EqualTo(before.Revision + 1));
                Assert.That(result.State.Commands.Count(c => c.CommandId == "fault-command"), Is.EqualTo(1));
            }
            string expectedHash = StateCodec.ComputeHash(result.State); store.Dispose(); store = Open();
            Assert.That(StateCodec.ComputeHash(store.Read()), Is.EqualTo(expectedHash));
            Assert.That(store.Recover("fault-command").CommitStatus, Is.EqualTo(expectedStatus));
            var retry = Perform(new DayGameService(store), operation, before.Revision); Committed(retry);
            Assert.That(retry.State.Commands.Count(c => c.CommandId == "fault-command"), Is.EqualTo(1));
            if (published) Assert.That(StateCodec.ComputeHash(retry.State), Is.EqualTo(expectedHash));
        }
        [TestCase(StoreFaultPoint.BeforePublish, TestName = "UnknownBeforePublishRequiresPendingRecovery")] [TestCase(StoreFaultPoint.AfterPublish, TestName = "UnknownAfterPublishRequiresPendingRecovery")]
        public void UnknownRequiresRecoveryOfPendingIdBeforeNewMutation(StoreFaultPoint point)
        {
            var faults = new Faults { Point = point, ReadBlocked = true }; var store = Open(faults: faults); var service = new DayGameService(store);
            string before = store.ConfirmedHash; var result = service.BuyChallengeTicket("pending", 0);
            Assert.That(result.CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN)); Assert.That(result.State.CurrentTicket, Is.Null); Assert.That(store.ConfirmedHash, Is.EqualTo(before));
            Assert.That(service.BuyNumberTicket("other", 0).CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN));
            faults.ReadBlocked = false;
            Assert.That(store.Recover("wrong-id").CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN)); Assert.That(store.CanMutate, Is.False);
            Assert.That(store.Recover("pending").CommitStatus, Is.EqualTo(point == StoreFaultPoint.AfterPublish ? CommitStatus.COMMITTED : CommitStatus.PROVEN_NOT_COMMITTED));
            Assert.That(store.CanMutate, Is.True);
        }
        [Test] public void StaleReplayReturnsOriginalReceiptAndNeverRunsMutationAgain()
        {
            var store = Open(); var service = new DayGameService(store); Committed(service.BuyNumberTicket("buy", 0));
            var before = store.Read(); string digest = before.Commands.Single().RequestDigest; bool ran = false;
            var replay = store.Execute("buy", digest, -123, state => { ran = true; throw new InvalidOperationException("Must not run replay"); });
            Committed(replay); Assert.That(ran, Is.False); Assert.That(replay.Receipt.Revision, Is.EqualTo(1)); Assert.That(StateCodec.ComputeHash(replay.State), Is.EqualTo(store.ConfirmedHash));
            Assert.That(service.BuyChallengeTicket("buy", 0).Code, Is.EqualTo("COMMAND_ID_REUSED"));
            Assert.That(service.BuyChallengeTicket("stale", 0).Code, Is.EqualTo("STALE_REVISION"));
            store.Dispose(); var reloaded = new DayGameService(Open()); Committed(reloaded.BuyNumberTicket("buy", 0)); Assert.That(reloaded.Snapshot.Tickets.Count, Is.EqualTo(1));
        }
        [Test] public void ResultsAndReceiptsAreDetachedFromConfirmedJournal()
        {
            var store = Open(); var service = new DayGameService(store); var result = service.BuyNumberTicket("buy", 0); Committed(result); string hash = store.ConfirmedHash;
            result.State.CashMinor = 0; result.State.CurrentTicket.Face.Cells[0] = new Lottery.G2.Core.NumberCell(99, 999);
            result.Receipt.Kind = "changed"; result.State.Stock.Clear(); result.State.NextToolIds[0] = "changed";
            Assert.That(StateCodec.ComputeHash(store.Read()), Is.EqualTo(hash)); Committed(service.BuyNumberTicket("buy", 0));
        }
        [Test] public void PrepublicationCapacityFailureLeavesStoreUsable()
        {
            var store = Open(); var before = store.Read(); string hash = store.ConfirmedHash;
            string directory = Path.GetDirectoryName(PathFor("state.bin"));
            var files = Directory.GetFiles(directory).Where(p => Path.GetFileName(p) != "writer.lock").ToDictionary(Path.GetFileName, File.ReadAllBytes);
            bool applied = false;
            var result = store.Execute("oversize", new string('a', 64), before.Revision, state =>
            { applied = true; return new CommandReceipt { Kind = new string('K', 4097) }; });
            Assert.That(applied, Is.True); Assert.That(result.CommitStatus, Is.EqualTo(CommitStatus.PROVEN_NOT_COMMITTED));
            Assert.That(result.Code, Is.EqualTo("SAVE_CAPACITY_REACHED")); Assert.That(result.Receipt, Is.Null);
            Assert.That(result.State.Revision, Is.EqualTo(before.Revision)); Assert.That(StateCodec.ComputeHash(result.State), Is.EqualTo(hash));
            Assert.That(result.State.PendingCommandId, Is.Empty); Assert.That(result.State.RecoveryRequired, Is.False);
            Assert.That(store.ConfirmedHash, Is.EqualTo(hash)); Assert.That(store.CanMutate, Is.True);
            string[] afterFiles = Directory.GetFiles(directory).Where(p => Path.GetFileName(p) != "writer.lock").Select(Path.GetFileName).ToArray();
            Assert.That(afterFiles, Is.EquivalentTo(files.Keys));
            foreach (var file in files) Assert.That(File.ReadAllBytes(Path.Combine(directory, file.Key)), Is.EqualTo(file.Value), file.Key);
            Committed(new DayGameService(store).BuyNumberTicket("real-buy", before.Revision));
            Assert.That(store.Read().Commands.Any(c => c.CommandId == "oversize"), Is.False);
            Assert.That(store.Read().Revision, Is.EqualTo(before.Revision + 1));
        }
        [Test] public void InvalidCommandIdentifiersAndNonHexDigestAreRejectedBeforeApply()
        {
            var store = Open(); string hash = store.ConfirmedHash; bool ran = false;
            foreach (string id in new[] { "", "\n", "contains\nline", new string('a', 257) })
                Assert.That(store.Execute(id, new string('a', 64), 0, s => { ran = true; return null; }).Code, Is.EqualTo("INVALID_REQUEST"));
            Assert.That(store.Execute("valid", new string('z', 64), 0, s => { ran = true; return null; }).Code, Is.EqualTo("INVALID_REQUEST"));
            Assert.That(ran, Is.False); Assert.That(store.ConfirmedHash, Is.EqualTo(hash));
        }
        [Test] public void ExclusiveWriterPreservesSaveAndReleaseAllowsReopen()
        {
            var first = Open(); byte[] bytes = File.ReadAllBytes(PathFor("state.bin")); var second = Open();
            Assert.That(first.CanMutate, Is.True); Assert.That(second.CanMutate, Is.False); Assert.That(second.Read().RecoveryRequired, Is.True);
            Assert.That(second.Recover("anything").CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN)); Assert.That(File.ReadAllBytes(PathFor("state.bin")), Is.EqualTo(bytes));
            first.Dispose(); var third = Open(); Assert.That(third.CanMutate, Is.True);
        }
        static byte[] Envelope(byte[] payload, string magic = "LOTTERY-G3-CHECKSUM-v1")
        {
            using (var stream = new MemoryStream()) using (var w = new BinaryWriter(stream))
            { w.Write(magic); w.Write(payload.Length); w.Write(StateCodec.HashBytes(payload)); w.Write(payload); w.Flush(); return stream.ToArray(); }
        }
        void AssertBlockedPreserved(string filename, byte[] bytes, string name = "normal")
        {
            string path = PathFor(filename, name); File.WriteAllBytes(path, bytes); FileStateStore reload = null;
            Assert.DoesNotThrow(() => reload = Open(name)); Assert.That(reload.CanMutate, Is.False); Assert.That(reload.Read().RecoveryRequired, Is.True);
            Assert.That(reload.Recover("unresolved").CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN));
            Assert.That(new DayGameService(reload).BuyNumberTicket("blocked", 0).Code, Is.EqualTo("RECOVERY_REQUIRED"));
            Assert.That(File.ReadAllBytes(path), Is.EqualTo(bytes)); reload.Dispose();
        }
        [Test] public void CorruptionOfAnyAuthoritativeFileFailsClosedAndPreservesBytes()
        {
            byte[][] malformed = { new byte[] { 1, 2, 3 }, new byte[] { 0x80, 0x80, 0x80, 0x80, 0x80 }, new byte[] { 0xff, 0xff, 0xff, 0xff, 0x0f }, new byte[0] };
            int sequence = 0;
            foreach (string filename in new[] { "state.bin", "commit.record", "intent.record" })
                foreach (var bytes in malformed)
                { string name = "corrupt-" + sequence++; Open(name).Dispose(); AssertBlockedPreserved(filename, bytes, name); }
        }
        [Test] public void CorruptNewestStateNeverRestoresValidOlderBackup()
        {
            var store = Open(); var service = new DayGameService(store); Committed(service.BuyNumberTicket("buy", 0));
            Committed(service.QuickReveal(service.Snapshot.CurrentTicket.Id, "reveal", 1)); store.Dispose();
            Assert.That(File.Exists(PathFor("previous.bin")), Is.True); byte[] older = File.ReadAllBytes(PathFor("previous.bin"));
            AssertBlockedPreserved("state.bin", new byte[] { 1, 2, 3 }); Assert.That(File.ReadAllBytes(PathFor("previous.bin")), Is.EqualTo(older));
        }
        [TestCase("state.bin", TestName = "MissingStateNeverCreatesFreshRun")] [TestCase("commit.record", TestName = "MissingMarkerNeverCreatesFreshRun")]
        public void MissingAuthoritativeFileNeverCreatesFreshRun(string filename)
        {
            var store = Open(); Committed(new DayGameService(store).BuyNumberTicket("buy", 0)); store.Dispose(); File.Delete(PathFor(filename));
            var reload = Open(); Assert.That(reload.CanMutate, Is.False); Assert.That(reload.Read().RecoveryRequired, Is.True); Assert.That(File.Exists(PathFor(filename)), Is.False);
        }
        [Test] public void UnknownSchemaAndEnvelopeVersionArePreserved()
        {
            var store = Open("schema"); var state = store.Read(); store.Dispose(); state.SchemaVersion = 99;
            byte[] unknown = StateCodec.SerializeCanonical(state); Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(unknown));
            AssertBlockedPreserved("state.bin", Envelope(unknown), "schema");
            var version = Open("version"); byte[] valid = StateCodec.SerializeCanonical(version.Read()); version.Dispose(); AssertBlockedPreserved("state.bin", Envelope(valid, "LOTTERY-G3-CHECKSUM-v99"), "version");
        }
        [Test] public void G2EnvelopeOrPayloadCannotBeOpenedAsG3()
        {
            var store = Open(); byte[] valid = StateCodec.SerializeCanonical(store.Read()); store.Dispose();
            AssertBlockedPreserved("state.bin", Envelope(valid, "LOTTERY-G2-CHECKSUM-v1"));
            byte[] g2Payload = Lottery.G2.Core.StateCodec.SerializeCanonical(Lottery.G2.Core.RunState.CreateNew("g2-run", "g2-seed"));
            Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(g2Payload));
        }
        [Test] public void TrailingBytesInEnvelopeOrCanonicalPayloadAreRejected()
        {
            var store = Open(); byte[] payload = StateCodec.SerializeCanonical(store.Read()); store.Dispose();
            byte[] appendedPayload = payload.Concat(new byte[] { 0 }).ToArray(); Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(appendedPayload));
            AssertBlockedPreserved("state.bin", Envelope(appendedPayload));
            Open("envelope").Dispose(); AssertBlockedPreserved("state.bin", Envelope(payload).Concat(new byte[] { 0 }).ToArray(), "envelope");
        }
        [Test] public void ChecksumMismatchIsRejectedWithoutRewrite()
        {
            var store = Open(); store.Dispose(); byte[] bytes = File.ReadAllBytes(PathFor("state.bin")); bytes[bytes.Length - 1] ^= 0x01;
            AssertBlockedPreserved("state.bin", bytes);
        }
        [Test] public void RollbackOfStateBehindHighWaterMarkIsRejected()
        {
            var store = Open(); var service = new DayGameService(store); Committed(service.BuyNumberTicket("buy", 0)); store.Dispose();
            byte[] oldState = File.ReadAllBytes(PathFor("previous.bin")); AssertBlockedPreserved("state.bin", oldState);
        }
        [Test] public void InMemoryHighWaterMarkRejectsRollbackOfBothStateAndMarker()
        {
            var store = Open(); byte[] oldState = File.ReadAllBytes(PathFor("state.bin")), oldMarker = File.ReadAllBytes(PathFor("commit.record"));
            Committed(new DayGameService(store).BuyNumberTicket("buy", 0)); string confirmed = store.ConfirmedHash;
            File.WriteAllBytes(PathFor("state.bin"), oldState); File.WriteAllBytes(PathFor("commit.record"), oldMarker);
            Assert.That(store.Recover("buy").CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN)); Assert.That(store.CanMutate, Is.False); Assert.That(store.ConfirmedHash, Is.EqualTo(confirmed));
        }
        [Test] public void ConflictingButChecksummedIntentIsNotTreatedAsUncommitted()
        {
            var store = Open(); string hash = store.ConfirmedHash; store.Dispose();
            byte[] conflict = Encoding.UTF8.GetBytes("pending\n" + new string('a', 64) + "\n0\n" + new string('b', 64) + "\n1\n" + hash);
            AssertBlockedPreserved("intent.record", Envelope(conflict));
        }
        void AssertChecksummedStateFailsInvariants(RunState state)
        {
            byte[] payload = StateCodec.SerializeCanonical(state);
            byte[] envelope = Envelope(payload);
            byte[] marker = Envelope(Encoding.UTF8.GetBytes(state.Revision.ToString(CultureInfo.InvariantCulture) + "\n" + StateCodec.HashBytes(payload)));
            File.WriteAllBytes(PathFor("state.bin"), envelope); File.WriteAllBytes(PathFor("commit.record"), marker);
            // Both transport checksums and the marker agree. Only domain/journal validation can reject this save.
            var reload = Open(); Assert.That(reload.CanMutate, Is.False); Assert.That(reload.Read().RecoveryRequired, Is.True);
            Assert.That(reload.Recover("unresolved").CommitStatus, Is.EqualTo(CommitStatus.COMMIT_UNKNOWN));
            Assert.That(File.ReadAllBytes(PathFor("state.bin")), Is.EqualTo(envelope)); Assert.That(File.ReadAllBytes(PathFor("commit.record")), Is.EqualTo(marker));
        }
        [Test] public void ChecksummedUnjournaledCashCreditFailsClosed()
        {
            var store = Open(); var state = store.Read(); store.Dispose();
            state.CashMinor++;
            state.Ledger.Add(new LedgerEntry { CommandId = "forged", Kind = "BORROW", ReferenceId = "mother", DeltaMinor = 1, BalanceMinor = state.CashMinor });
            AssertChecksummedStateFailsInvariants(state);
        }
        [Test] public void ChecksummedOrphanPurchaseReceiptFailsClosed()
        {
            var store = Open(); Committed(new DayGameService(store).BuyNumberTicket("buy", 0)); var state = store.Read(); store.Dispose();
            state.Commands.Single().CommandId = "orphan-receipt"; state.Ledger.Single().CommandId = "orphan-receipt";
            AssertChecksummedStateFailsInvariants(state);
        }
        [Test] public void ChecksummedChangedStartingCashFailsClosed()
        {
            var store = Open(); var state = store.Read(); store.Dispose(); state.InitialCashMinor++; state.CashMinor++;
            AssertChecksummedStateFailsInvariants(state);
        }
        [Test] public void MalformedTextAndNoncanonicalLengthFailBeforeAllocation()
        {
            foreach (byte[] bytes in new[] { new byte[0], new byte[] { 0x80 }, new byte[] { 0x80, 0x80, 0x80, 0x80, 0x80 }, new byte[] { 0xff, 0xff, 0xff, 0xff, 0x0f } })
                Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(bytes));
            byte[] valid = StateCodec.SerializeCanonical(RunFactory.Create("run", "seed"));
            byte[] redundantPrefix = new byte[valid.Length + 1]; redundantPrefix[0] = (byte)(valid[0] | 0x80); redundantPrefix[1] = 0; Array.Copy(valid, 1, redundantPrefix, 2, valid.Length - 1);
            Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(redundantPrefix)); valid[1] = 0xff; Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(valid));
        }
        [Test] public void UnknownEnumerationAndNoncanonicalBooleanAreRejected()
        {
            var state = RunFactory.Create("run", "seed"); state.Phase = (DayPhase)99;
            Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(StateCodec.SerializeCanonical(state)));
            state.Phase = DayPhase.DAY_OPEN; byte[] bytes = StateCodec.SerializeCanonical(state);
            // Empty ad/event/provider/diagnostic tail: presence flag + 3 int32 + int64 + 3 collection counts.
            Assert.That(bytes[bytes.Length - 33], Is.EqualTo(0)); bytes[bytes.Length - 33] = 2;
            Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(bytes));
        }
        [Test] public void UnknownMaskVersionAndTruncatedMaskAreRejected()
        {
            var service = new DayGameService(Open()); Committed(service.BuyNumberTicket("buy", 0));
            byte[] bytes = StateCodec.SerializeCanonical(service.Snapshot), token = Encoding.UTF8.GetBytes(StateCodec.MaskVersion);
            int offset = -1;
            for (int i = 0; i <= bytes.Length - token.Length; i++)
            { bool same = true; for (int j = 0; j < token.Length; j++) if (bytes[i + j] != token[j]) { same = false; break; } if (same) { offset = i; break; } }
            Assert.That(offset, Is.GreaterThanOrEqualTo(0)); byte[] wrongVersion = (byte[])bytes.Clone(); wrongVersion[offset] = (byte)'x';
            Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(wrongVersion));
            byte[] truncated = bytes.Take(offset + token.Length + 8 + 2000).ToArray();
            Assert.Throws<InvalidDataException>(() => StateCodec.DeserializeCanonical(truncated));
        }
        [Test] public void CanonicalHashIsCultureInvariantAndTransientFlagsAreExcluded()
        {
            var state = RunFactory.Create("run", "seed"); byte[] expected = StateCodec.SerializeCanonical(state); var original = CultureInfo.CurrentCulture;
            try { CultureInfo.CurrentCulture = new CultureInfo("ar-SA"); Assert.That(StateCodec.SerializeCanonical(state), Is.EqualTo(expected)); }
            finally { CultureInfo.CurrentCulture = original; }
            state.RecoveryRequired = true; state.PendingCommandId = "transient"; Assert.That(StateCodec.SerializeCanonical(state), Is.EqualTo(expected));
            var copy = StateCodec.DeserializeCanonical(expected); Assert.That(copy.RecoveryRequired, Is.False); Assert.That(copy.PendingCommandId, Is.Empty);
        }
        [Test] public void DiagnosticAndCompleteNestedStateRoundTripWithoutAliasing()
        {
            // Deliberately non-admissible values exercise field fidelity only. No store or StateInvariants admits this object.
            var s = RunFactory.CreateDiagnostic("codec-run"); s.Revision = 9; s.InitialCashMinor = 32000; s.CashMinor = 23456; s.DayNumber = 2; s.Phase = DayPhase.NIGHT_BILL;
            s.PrincipalMinor = 290000; s.PrincipalAtOpenMinor = 299000; s.PrincipalRepaidMinor = 9000; s.InterestDueMinor = 1450; s.InterestPaidMinor = 450;
            s.TicketsPurchasedToday = 1; s.SettledTicketCount = 3; s.LifetimeEffectiveTickets = 9; s.LifetimeEffectiveAtOpen = 6;
            s.EconomicCounter = 11; s.ChallengeCounter = 12; s.ShopCounter = 13;
            var t = new TicketState { Id = "ticket", PurchaseCommandId = "buy", TicketType = "challenge", Phase = TicketPhase.REVEALED_UNCLAIMED, PriceMinor = 1000, RawPrizeMinor = 2000,
                CashAfterPurchaseMinor = 31000, PurchasedPosition = 1, EconomicDrawCount = 5, PreviousSettledTicketType = "number", ConfigurationSnapshot = new[] { new ToolSnapshot { ItemId = "lamp", Level = 2 } },
                Scratch = new TicketMask(8), ChallengeSafe = new[] { true, false, true, true, false, true, true, true }, RevealedCells = new[] { true, false, false, false, false, false, false, false }, PeekedCells = new[] { false, true, false, false, false, false, false, false },
                SelectedCell = 3, SelectionId = "selection", SafeCount = 1, Busted = false, LampUsed = true, InformationSource = "lamp", CopyMinor = 44, ProtectionMinor = 55, ConsumableCostMinor = 66,
                EconomicCounterBefore = 7, EconomicCounterAfter = 8, ChallengeCounterBefore = 9, ChallengeCounterAfter = 10 };
            t.ConsumableUses.Add(new ConsumableUse { ItemId = "film", Quality = "rare", StockId = "consumed", PurchasePriceMinor = 66, LockedAmountMinor = 777, TargetCells = new[] { 1, 3 } });
            t.UsedConsumableTypes.Add("film"); s.Tickets.Add(t); s.Tools.Add(new OwnedTool { ItemId = "lamp", Level = 2, InitialPaymentMinor = 2200 }); s.NextToolIds[0] = "lamp";
            s.Drawers[0] = new DrawerItem { StockId = "drawer", ItemId = "film", Quality = "rare", PurchasePriceMinor = 600 }; s.ToolCounters.Add(new ToolCounter { ItemId = "lamp", UsedToday = 1, ClipTicks = 7 });
            s.Loans.Add(new LoanRecord { LoanId = "loan", ContactId = "friend", BorrowedMinor = 3000, RemainingMinor = 2000, BorrowedDay = 1, DueNight = 2 });
            s.Contacts.Add(new ContactState { ContactId = "codec-friend", BorrowedLifetimeMinor = 3500 });
            s.Settlements.Add(new SettlementRecord { TicketId = "prior", RawPrizeMinor = 1000, TotalMinor = 1100, TicketPriceMinor = 1000, ConsumableCostMinor = 50, NetMinor = 50, Entries = new List<PayoutEntry> { new PayoutEntry { Source = "tool", AmountMinor = 100 } } });
            s.Commands.Add(new CommandReceipt { CommandId = "command", RequestDigest = new string('a', 64), Kind = "CLAIM", TicketId = "prior", Code = "SUCCESS", Revision = 9, CashDeltaMinor = 1100 });
            s.ClaimBuyIntents.Add(new ClaimBuyIntent { IntentId = "next-intent", TicketId = "prior", NextTicketType = "challenge", ClaimCommandId = "next-claim", BuyCommandId = "next-buy", BoostDrawerSlot = -1, Cancelled = true });
            s.Ledger.Add(new LedgerEntry { CommandId = "command", Kind = "CLAIM", ReferenceId = "prior", DeltaMinor = 1100, BalanceMinor = 23456 });
            s.PhoneEvents.Add(new PhoneEvent { EventId = "phone", ContactId = "friend", Kind = "BORROW", LoanId = "loan", AmountMinor = 3000, Day = 1, DueNight = 2 });
            s.ConsumableBatch = new[] { "film", "seal", "copy", "boost" };
            s.Ad = new AdTransaction { RequestId = "request", RunId = "codec-run", StockId = "ad-stock", ItemId = "film", Quality = "precious", Version = "g3-fake-ad-v1", Conflict = "test-conflict", CreateCommandId = "create", ReserveCommandId = "reserve", ShowingCommandId = "show", CommittingCommandId = "committing", CommitCommandId = "commit", Phase = AdPhase.RECOVERY_CONFLICT, ReservedPriceMinor = 150, ReservedDrawerSlot = 1, DayNumber = 2, RewardRecorded = true };
            s.AdSuccessesToday = 1; s.SettledCountAtLastAdSuccess = 2; s.FixtureBaseSettlements = 12; s.FirstLaunchElapsedSeconds = 123;
            s.AdEvents.Add(new AdEventRecord { EventId = "event", RequestId = "request", RunId = "codec-run", Kind = "reward" }); s.FakeShownRequests.Add("request");
            byte[] bytes = StateCodec.SerializeCanonical(s); var copy = StateCodec.DeserializeCanonical(bytes);
            Assert.That(StateCodec.SerializeCanonical(copy), Is.EqualTo(bytes)); Assert.That(copy.Ad.Conflict, Is.EqualTo("test-conflict")); Assert.That(copy.ClaimBuyIntents.Single().NextTicketType, Is.EqualTo("challenge")); Assert.That(copy.Loans[0].RemainingMinor, Is.EqualTo(2000));
            Assert.That(copy.Tickets[0].InformationSource, Is.EqualTo("lamp")); Assert.That(copy.Tickets[0].EconomicDrawCount, Is.EqualTo(5)); Assert.That(copy.Tickets[0].ConsumableUses.Single().TargetCells, Is.EqualTo(new[] { 1, 3 })); Assert.That(copy.ClaimBuyIntents.Single().Cancelled, Is.True); Assert.That(copy.Tickets[0].Scratch.CellCount, Is.EqualTo(8)); Assert.That(copy.Tickets[0].Face, Is.Null);
            Assert.That(copy.DiagnosticChallengeArrangements.Count, Is.EqualTo(s.DiagnosticChallengeArrangements.Count));
            copy.Tickets[0].ConsumableUses[0].TargetCells[0] = 7; copy.Tickets[0].ChallengeSafe[0] = false; copy.Tickets[0].ConfigurationSnapshot[0].Level = 99; copy.Drawers[0].PurchasePriceMinor = 0; copy.Ad.RewardRecorded = false;
            Assert.That(StateCodec.SerializeCanonical(s), Is.EqualTo(bytes));
        }
    }
}

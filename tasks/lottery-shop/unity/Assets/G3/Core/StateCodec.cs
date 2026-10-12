using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using NumberFace = Lottery.G2.Core.NumberFace;
using NumberCell = Lottery.G2.Core.NumberCell;

namespace Lottery.G3.Core
{
    // Ordered, little-endian G3 wire format. Collection order is meaningful; no reflection or Unity serializer.
    // Checksums detect accidental corruption, not tampering. G2 payloads are never migrated implicitly.
    public static class StateCodec
    {
        public const string StateMagic = "LOTTERY-G3-STATE";
        public const string MaskVersion = TicketMask.Version;
        public const int MaximumPayloadBytes = 16 * 1024 * 1024;
        const int MaximumTextCharacters = 4096;
        static readonly Encoding Utf8 = new UTF8Encoding(false, true);
        static void Text(BinaryWriter w, string value)
        {
            value = value ?? "";
            if (value.Length > MaximumTextCharacters) throw new InvalidDataException("Oversized text field");
            w.Write(value);
        }
        static string Text(BinaryReader r)
        {
            // BinaryWriter's canonical unsigned 7-bit byte length, bounded before allocation.
            uint length = 0; int shift = 0; byte part;
            do
            {
                if (shift == 35) throw new InvalidDataException("Malformed text length");
                part = r.ReadByte();
                if (shift == 28 && (part & 0xf8) != 0) throw new InvalidDataException("Malformed text length");
                length |= (uint)(part & 0x7f) << shift; shift += 7;
            } while ((part & 0x80) != 0);
            if ((shift > 7 && part == 0) || length > MaximumTextCharacters * 4) throw new InvalidDataException("Invalid text length");
            byte[] bytes = r.ReadBytes((int)length);
            if (bytes.Length != length) throw new EndOfStreamException();
            string value = Utf8.GetString(bytes);
            if (value.Length > MaximumTextCharacters) throw new InvalidDataException("Oversized text field");
            return value;
        }
        static int Count(BinaryReader r, int maximum = 100000)
        { int value = r.ReadInt32(); if (value < 0 || value > maximum) throw new InvalidDataException("Invalid collection size"); return value; }
        static void Size(BinaryWriter w, int count, int maximum = 100000)
        { if (count < 0 || count > maximum) throw new InvalidDataException("Invalid collection size"); w.Write(count); }
        static bool Flag(BinaryReader r)
        { byte value = r.ReadByte(); if (value > 1) throw new InvalidDataException("Noncanonical boolean"); return value == 1; }
        static bool[] Flags(BinaryReader r)
        { var values = new bool[Count(r, 8)]; for (int i = 0; i < values.Length; i++) values[i] = Flag(r); return values; }
        static void Flags(BinaryWriter w, bool[] values)
        { if (values == null) throw new InvalidDataException("Missing boolean array"); Size(w, values.Length, 8); foreach (bool value in values) w.Write(value); }
        static int Choice(BinaryReader r, int maximum)
        { int value = r.ReadInt32(); if (value < 0 || value > maximum) throw new InvalidDataException("Unknown state enumeration"); return value; }
        static void Receipt(BinaryWriter w, CommandReceipt c)
        { Text(w, c.CommandId); Text(w, c.RequestDigest); Text(w, c.Kind); Text(w, c.TicketId); Text(w, c.Code); w.Write(c.Revision); w.Write(c.CashDeltaMinor); }
        static CommandReceipt Receipt(BinaryReader r)
        { return new CommandReceipt { CommandId = Text(r), RequestDigest = Text(r), Kind = Text(r), TicketId = Text(r), Code = Text(r), Revision = r.ReadInt64(), CashDeltaMinor = r.ReadInt64() }; }

        public static byte[] SerializeCanonical(RunState s)
        {
            if (s == null) throw new ArgumentNullException(nameof(s));
            using (var stream = new MemoryStream()) using (var w = new BinaryWriter(stream, Utf8, true))
            {
                Text(w, StateMagic); w.Write(s.SchemaVersion); Text(w, s.RulesHash); Text(w, s.RunId); Text(w, s.Seed); Text(w, s.FixtureLabel);
                w.Write(s.Revision); w.Write(s.InitialCashMinor); w.Write(s.CashMinor); w.Write(s.DayNumber); w.Write((int)s.Phase);
                w.Write(s.PrincipalMinor); w.Write(s.PrincipalAtOpenMinor); w.Write(s.PrincipalRepaidMinor); w.Write(s.InterestDueMinor); w.Write(s.InterestPaidMinor);
                w.Write(s.TicketsPurchasedToday); w.Write(s.SettledTicketCount); w.Write(s.LifetimeEffectiveTickets); w.Write(s.LifetimeEffectiveAtOpen);
                w.Write(s.EconomicCounter); w.Write(s.ChallengeCounter); w.Write(s.ShopCounter);
                Size(w, s.Tickets.Count, 12);
                foreach (var t in s.Tickets)
                {
                    Text(w, t.Id); Text(w, t.PurchaseCommandId); Text(w, t.TicketType); w.Write((int)t.Phase);
                    w.Write(t.PriceMinor); w.Write(t.RawPrizeMinor); w.Write(t.CashAfterPurchaseMinor); w.Write(t.PurchasedPosition); w.Write(t.EconomicDrawCount); Text(w, t.PreviousSettledTicketType);
                    Size(w, t.ConfigurationSnapshot.Length, 3); foreach (var x in t.ConfigurationSnapshot) { Text(w, x.ItemId); w.Write(x.Level); }
                    w.Write(t.Face != null);
                    if (t.Face != null)
                    {
                        Text(w, t.Face.GeneratorVersion); w.Write(t.Face.WinningNumber); Size(w, t.Face.Cells.Length, 6);
                        foreach (var cell in t.Face.Cells) { w.Write(cell.Number); w.Write(cell.PrizeMinor); }
                    }
                    if (t.Scratch == null) throw new InvalidDataException("Missing ticket mask");
                    Text(w, MaskVersion); w.Write(t.Scratch.CellCount); byte[] mask = t.Scratch.ToBytes(); Size(w, mask.Length, 4096); w.Write(mask);
                    Flags(w, t.ChallengeSafe); Flags(w, t.RevealedCells); Flags(w, t.PeekedCells);
                    w.Write(t.SelectedCell); Text(w, t.SelectionId); w.Write(t.SafeCount); w.Write(t.Busted); w.Write(t.LampUsed); Text(w, t.InformationSource);
                    w.Write(t.CopyMinor); w.Write(t.ProtectionMinor); w.Write(t.ConsumableCostMinor);
                    Size(w, t.UsedConsumableTypes.Count, 4); foreach (string type in t.UsedConsumableTypes) Text(w, type);
                    Size(w, t.ConsumableUses.Count, 4);
                    foreach (var use in t.ConsumableUses)
                    { Text(w, use.ItemId); Text(w, use.Quality); Text(w, use.StockId); w.Write(use.PurchasePriceMinor); w.Write(use.LockedAmountMinor); Size(w, use.TargetCells.Length, 8); foreach (int cell in use.TargetCells) w.Write(cell); }
                    w.Write(t.EconomicCounterBefore); w.Write(t.EconomicCounterAfter); w.Write(t.ChallengeCounterBefore); w.Write(t.ChallengeCounterAfter);
                }
                Size(w, s.Stock.Count, 1000);
                foreach (var x in s.Stock) { Text(w, x.StockId); Text(w, x.ItemId); Text(w, x.Quality); w.Write(x.IsConsumable); w.Write(x.PriceMinor); w.Write(x.Quantity); }
                Size(w, s.Tools.Count, 6);
                foreach (var x in s.Tools) { Text(w, x.ItemId); w.Write(x.Level); w.Write(x.InitialPaymentMinor); }
                Size(w, s.NextToolIds.Length, 3); foreach (string id in s.NextToolIds) Text(w, id);
                Size(w, s.Drawers.Length, 2);
                foreach (var x in s.Drawers)
                { w.Write(x != null); if (x != null) { Text(w, x.StockId); Text(w, x.ItemId); Text(w, x.Quality); w.Write(x.PurchasePriceMinor); } }
                Size(w, s.ToolCounters.Count, 1000); foreach (var x in s.ToolCounters) { Text(w, x.ItemId); w.Write(x.UsedToday); w.Write(x.ClipTicks); }
                Size(w, s.Loans.Count); foreach (var x in s.Loans) { Text(w, x.LoanId); Text(w, x.ContactId); w.Write(x.BorrowedMinor); w.Write(x.RemainingMinor); w.Write(x.BorrowedDay); w.Write(x.DueNight); }
                Size(w, s.Contacts.Count, 1000); foreach (var x in s.Contacts) { Text(w, x.ContactId); w.Write(x.BorrowedLifetimeMinor); }
                Size(w, s.Settlements.Count, 12);
                foreach (var x in s.Settlements)
                {
                    Text(w, x.TicketId); w.Write(x.RawPrizeMinor); Size(w, x.Entries.Count, 32);
                    foreach (var entry in x.Entries) { Text(w, entry.Source); w.Write(entry.AmountMinor); }
                    w.Write(x.TotalMinor); w.Write(x.TicketPriceMinor); w.Write(x.ConsumableCostMinor); w.Write(x.NetMinor);
                }
                Size(w, s.Commands.Count); foreach (var x in s.Commands) Receipt(w, x);
                Size(w, s.ClaimBuyIntents.Count); foreach (var x in s.ClaimBuyIntents) { Text(w, x.IntentId); Text(w, x.TicketId); Text(w, x.NextTicketType); Text(w, x.ClaimCommandId); Text(w, x.BuyCommandId); w.Write(x.BoostDrawerSlot); w.Write(x.Cancelled); }
                Size(w, s.Ledger.Count); foreach (var x in s.Ledger) { Text(w, x.CommandId); Text(w, x.Kind); Text(w, x.ReferenceId); w.Write(x.DeltaMinor); w.Write(x.BalanceMinor); }
                Size(w, s.PhoneEvents.Count); foreach (var x in s.PhoneEvents) { Text(w, x.EventId); Text(w, x.ContactId); Text(w, x.Kind); Text(w, x.LoanId); w.Write(x.AmountMinor); w.Write(x.Day); w.Write(x.DueNight); }
                Size(w, s.ConsumableBatch.Length, 4); foreach (string id in s.ConsumableBatch) Text(w, id);
                w.Write(s.Ad != null);
                if (s.Ad != null)
                {
                    var a = s.Ad; Text(w, a.RequestId); Text(w, a.RunId); Text(w, a.StockId); Text(w, a.ItemId); Text(w, a.Quality); Text(w, a.Version); Text(w, a.Conflict);
                    Text(w, a.CreateCommandId); Text(w, a.ReserveCommandId); Text(w, a.ShowingCommandId); Text(w, a.CommittingCommandId); Text(w, a.CommitCommandId);
                    w.Write((int)a.Phase); w.Write(a.ReservedPriceMinor); w.Write(a.ReservedDrawerSlot); w.Write(a.DayNumber); w.Write(a.RewardRecorded);
                }
                w.Write(s.AdSuccessesToday); w.Write(s.SettledCountAtLastAdSuccess); w.Write(s.FixtureBaseSettlements); w.Write(s.FirstLaunchElapsedSeconds);
                Size(w, s.AdEvents.Count); foreach (var x in s.AdEvents) { Text(w, x.EventId); Text(w, x.RequestId); Text(w, x.RunId); Text(w, x.Kind); }
                Size(w, s.FakeShownRequests.Count); foreach (string id in s.FakeShownRequests) Text(w, id);
                Size(w, s.DiagnosticChallengeArrangements.Count, 12); foreach (bool[] x in s.DiagnosticChallengeArrangements) Flags(w, x);
                w.Flush(); if (stream.Length > MaximumPayloadBytes) throw new InvalidDataException("Oversized state"); return stream.ToArray();
            }
        }
        public static RunState DeserializeCanonical(byte[] bytes)
        {
            try { return DeserializePayload(bytes); }
            catch (Exception e) when (!(e is InvalidDataException) && (e is FormatException || e is IOException || e is ArgumentException || e is OverflowException))
            { throw new InvalidDataException("Malformed G3 state encoding; preserve original bytes", e); }
        }
        static RunState DeserializePayload(byte[] bytes)
        {
            if (bytes == null || bytes.Length > MaximumPayloadBytes) throw new InvalidDataException("Invalid state size");
            using (var stream = new MemoryStream(bytes, false)) using (var r = new BinaryReader(stream, Utf8, true))
            {
                if (Text(r) != StateMagic) throw new InvalidDataException("Wrong state magic; G2 is not a G3 save");
                int schema = r.ReadInt32(); if (schema != RunState.CurrentSchema) throw new InvalidDataException("Unknown G3 schema; preserve original files");
                var s = new RunState { SchemaVersion = schema, RulesHash = Text(r), RunId = Text(r), Seed = Text(r), FixtureLabel = Text(r),
                    Revision = r.ReadInt64(), InitialCashMinor = r.ReadInt64(), CashMinor = r.ReadInt64(), DayNumber = r.ReadInt32(), Phase = (DayPhase)Choice(r, 4),
                    PrincipalMinor = r.ReadInt64(), PrincipalAtOpenMinor = r.ReadInt64(), PrincipalRepaidMinor = r.ReadInt64(), InterestDueMinor = r.ReadInt64(), InterestPaidMinor = r.ReadInt64(),
                    TicketsPurchasedToday = r.ReadInt32(), SettledTicketCount = r.ReadInt32(), LifetimeEffectiveTickets = r.ReadInt32(), LifetimeEffectiveAtOpen = r.ReadInt32(),
                    EconomicCounter = r.ReadUInt64(), ChallengeCounter = r.ReadUInt64(), ShopCounter = r.ReadUInt64() };
                int count = Count(r, 12);
                for (int i = 0; i < count; i++)
                {
                    var t = new TicketState { Id = Text(r), PurchaseCommandId = Text(r), TicketType = Text(r), Phase = (TicketPhase)Choice(r, 2),
                        PriceMinor = r.ReadInt64(), RawPrizeMinor = r.ReadInt64(), CashAfterPurchaseMinor = r.ReadInt64(), PurchasedPosition = r.ReadInt32(), EconomicDrawCount = r.ReadInt32(), PreviousSettledTicketType = Text(r) };
                    t.ConfigurationSnapshot = new ToolSnapshot[Count(r, 3)];
                    for (int j = 0; j < t.ConfigurationSnapshot.Length; j++) t.ConfigurationSnapshot[j] = new ToolSnapshot { ItemId = Text(r), Level = r.ReadInt32() };
                    if (Flag(r))
                    {
                        t.Face = new NumberFace { GeneratorVersion = Text(r), WinningNumber = r.ReadInt32(), Cells = new NumberCell[Count(r, 6)] };
                        if (t.Face.Cells.Length != 6) throw new InvalidDataException("Number face must contain six cells");
                        for (int j = 0; j < t.Face.Cells.Length; j++) t.Face.Cells[j] = new NumberCell(r.ReadInt32(), r.ReadInt64());
                    }
                    if (Text(r) != MaskVersion) throw new InvalidDataException("Unknown G3 mask version");
                    int cellCount = r.ReadInt32(); if (cellCount != 6 && cellCount != 8) throw new InvalidDataException("Invalid mask grid");
                    int maskSize = Count(r, 4096); if (maskSize != 4096) throw new InvalidDataException("Invalid mask byte length");
                    byte[] mask = r.ReadBytes(maskSize); if (mask.Length != maskSize) throw new EndOfStreamException(); t.Scratch = new TicketMask(cellCount, mask);
                    t.ChallengeSafe = Flags(r); t.RevealedCells = Flags(r); t.PeekedCells = Flags(r);
                    t.SelectedCell = r.ReadInt32(); t.SelectionId = Text(r); t.SafeCount = r.ReadInt32(); t.Busted = Flag(r); t.LampUsed = Flag(r); t.InformationSource = Text(r);
                    t.CopyMinor = r.ReadInt64(); t.ProtectionMinor = r.ReadInt64(); t.ConsumableCostMinor = r.ReadInt64();
                    int used = Count(r, 4); for (int j = 0; j < used; j++) t.UsedConsumableTypes.Add(Text(r));
                    int uses = Count(r, 4);
                    for (int j = 0; j < uses; j++)
                    { var use = new ConsumableUse { ItemId = Text(r), Quality = Text(r), StockId = Text(r), PurchasePriceMinor = r.ReadInt64(), LockedAmountMinor = r.ReadInt64(), TargetCells = new int[Count(r, 8)] }; for (int k = 0; k < use.TargetCells.Length; k++) use.TargetCells[k] = r.ReadInt32(); t.ConsumableUses.Add(use); }
                    t.EconomicCounterBefore = r.ReadUInt64(); t.EconomicCounterAfter = r.ReadUInt64(); t.ChallengeCounterBefore = r.ReadUInt64(); t.ChallengeCounterAfter = r.ReadUInt64(); s.Tickets.Add(t);
                }
                count = Count(r, 1000); for (int i = 0; i < count; i++) s.Stock.Add(new StockItem { StockId = Text(r), ItemId = Text(r), Quality = Text(r), IsConsumable = Flag(r), PriceMinor = r.ReadInt64(), Quantity = r.ReadInt32() });
                count = Count(r, 6); for (int i = 0; i < count; i++) s.Tools.Add(new OwnedTool { ItemId = Text(r), Level = r.ReadInt32(), InitialPaymentMinor = r.ReadInt64() });
                if (Count(r, 3) != 3) throw new InvalidDataException("Invalid table slots"); s.NextToolIds = new string[3]; for (int i = 0; i < 3; i++) s.NextToolIds[i] = Text(r);
                if (Count(r, 2) != 2) throw new InvalidDataException("Invalid drawer slots"); s.Drawers = new DrawerItem[2];
                for (int i = 0; i < 2; i++) if (Flag(r)) s.Drawers[i] = new DrawerItem { StockId = Text(r), ItemId = Text(r), Quality = Text(r), PurchasePriceMinor = r.ReadInt64() };
                count = Count(r, 1000); for (int i = 0; i < count; i++) s.ToolCounters.Add(new ToolCounter { ItemId = Text(r), UsedToday = r.ReadInt32(), ClipTicks = r.ReadInt32() });
                count = Count(r); for (int i = 0; i < count; i++) s.Loans.Add(new LoanRecord { LoanId = Text(r), ContactId = Text(r), BorrowedMinor = r.ReadInt64(), RemainingMinor = r.ReadInt64(), BorrowedDay = r.ReadInt32(), DueNight = r.ReadInt32() });
                count = Count(r, 1000); for (int i = 0; i < count; i++) s.Contacts.Add(new ContactState { ContactId = Text(r), BorrowedLifetimeMinor = r.ReadInt64() });
                count = Count(r, 12);
                for (int i = 0; i < count; i++)
                {
                    var x = new SettlementRecord { TicketId = Text(r), RawPrizeMinor = r.ReadInt64() }; int entries = Count(r, 32);
                    for (int j = 0; j < entries; j++) x.Entries.Add(new PayoutEntry { Source = Text(r), AmountMinor = r.ReadInt64() });
                    x.TotalMinor = r.ReadInt64(); x.TicketPriceMinor = r.ReadInt64(); x.ConsumableCostMinor = r.ReadInt64(); x.NetMinor = r.ReadInt64(); s.Settlements.Add(x);
                }
                count = Count(r); for (int i = 0; i < count; i++) s.Commands.Add(Receipt(r));
                count = Count(r); for (int i = 0; i < count; i++) s.ClaimBuyIntents.Add(new ClaimBuyIntent { IntentId = Text(r), TicketId = Text(r), NextTicketType = Text(r), ClaimCommandId = Text(r), BuyCommandId = Text(r), BoostDrawerSlot = r.ReadInt32(), Cancelled = Flag(r) });
                count = Count(r); for (int i = 0; i < count; i++) s.Ledger.Add(new LedgerEntry { CommandId = Text(r), Kind = Text(r), ReferenceId = Text(r), DeltaMinor = r.ReadInt64(), BalanceMinor = r.ReadInt64() });
                count = Count(r); for (int i = 0; i < count; i++) s.PhoneEvents.Add(new PhoneEvent { EventId = Text(r), ContactId = Text(r), Kind = Text(r), LoanId = Text(r), AmountMinor = r.ReadInt64(), Day = r.ReadInt32(), DueNight = r.ReadInt32() });
                if (Count(r, 4) != 4) throw new InvalidDataException("Invalid consumable batch"); s.ConsumableBatch = new string[4]; for (int i = 0; i < 4; i++) s.ConsumableBatch[i] = Text(r);
                if (Flag(r)) s.Ad = new AdTransaction { RequestId = Text(r), RunId = Text(r), StockId = Text(r), ItemId = Text(r), Quality = Text(r), Version = Text(r), Conflict = Text(r),
                    CreateCommandId = Text(r), ReserveCommandId = Text(r), ShowingCommandId = Text(r), CommittingCommandId = Text(r), CommitCommandId = Text(r),
                    Phase = (AdPhase)Choice(r, 8), ReservedPriceMinor = r.ReadInt64(), ReservedDrawerSlot = r.ReadInt32(), DayNumber = r.ReadInt32(), RewardRecorded = Flag(r) };
                s.AdSuccessesToday = r.ReadInt32(); s.SettledCountAtLastAdSuccess = r.ReadInt32(); s.FixtureBaseSettlements = r.ReadInt32(); s.FirstLaunchElapsedSeconds = r.ReadInt64();
                count = Count(r); for (int i = 0; i < count; i++) s.AdEvents.Add(new AdEventRecord { EventId = Text(r), RequestId = Text(r), RunId = Text(r), Kind = Text(r) });
                count = Count(r); for (int i = 0; i < count; i++) s.FakeShownRequests.Add(Text(r));
                count = Count(r, 12); for (int i = 0; i < count; i++) s.DiagnosticChallengeArrangements.Add(Flags(r));
                if (stream.Position != stream.Length) throw new InvalidDataException("Trailing G3 state data");
                return s;
            }
        }
        public static string ComputeHash(RunState state) => HashBytes(SerializeCanonical(state));
        public static string HashBytes(byte[] bytes)
        {
            if (bytes == null) throw new ArgumentNullException(nameof(bytes));
            using (var sha = SHA256.Create()) { var hash = sha.ComputeHash(bytes); var result = new StringBuilder(64); foreach (byte b in hash) result.Append(b.ToString("x2")); return result.ToString(); }
        }
    }
}

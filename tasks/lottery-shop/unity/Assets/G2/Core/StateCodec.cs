using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
namespace Lottery.G2.Core
{
    // Canonical little-endian BinaryWriter encoding, version 1. Not a security/anti-cheat mechanism.
    public static class StateCodec
    {
        static void String(BinaryWriter w, string value) => w.Write(value ?? "");
        static string String(BinaryReader r) { string s = r.ReadString(); if (s.Length > 4096) throw new InvalidDataException("Oversized text field"); return s; }
        static int Count(BinaryReader r, int max = 100000) { int value = r.ReadInt32(); if (value < 0 || value > max) throw new InvalidDataException("Invalid collection size"); return value; }
        public static byte[] SerializeCanonical(RunState s)
        {
            using (var stream = new MemoryStream()) using (var w = new BinaryWriter(stream, Encoding.UTF8, true))
            {
                w.Write("LOTTERY-G2-STATE"); w.Write(s.SchemaVersion); String(w, s.RulesHash); String(w, s.RunId); String(w, s.Seed); String(w, s.FixtureLabel);
                w.Write(s.Revision); w.Write(s.InitialCashMinor); w.Write(s.CashMinor); w.Write(s.DayNumber); w.Write(s.TicketsPurchasedToday); w.Write(s.SettledTicketCount); w.Write(s.FixtureBaseSettlements);
                w.Write(s.AdSuccessesToday); w.Write(s.SettledCountAtLastAdSuccess); w.Write(s.EconomicCounter); w.Write(s.StockAvailable);
                w.Write(s.Tickets.Count);
                foreach (var t in s.Tickets)
                {
                    String(w, t.Id); String(w, t.TicketType); String(w, t.PreviousSettledTicketType); String(w, t.EconomicAlgorithm); w.Write((int)t.Phase);
                    w.Write(t.RawPrizeMinor); w.Write(t.PriceMinor); w.Write(t.CashAfterPurchaseMinor); w.Write(t.PurchasedPosition); w.Write(t.EconomicCounterBefore); w.Write(t.EconomicCounterAfter); w.Write(t.SettledCountSnapshot);
                    w.Write(t.ConfigurationSnapshot.Length); foreach (string x in t.ConfigurationSnapshot) String(w, x);
                    String(w, t.Face.GeneratorVersion); w.Write(t.Face.WinningNumber); w.Write(t.Face.Cells.Length);
                    foreach (var cell in t.Face.Cells) { w.Write(cell.Number); w.Write(cell.PrizeMinor); }
                    String(w, ScratchMask.Version); byte[] mask = t.Scratch.ToBytes(); w.Write(mask.Length); w.Write(mask);
                }
                w.Write(s.Settlements.Count);
                foreach (var x in s.Settlements) { String(w, x.TicketId); w.Write(x.RawPrizeMinor); w.Write(x.AdditionMinor); w.Write(x.TotalMinor); w.Write(x.TicketPriceMinor); w.Write(x.NetMinor); }
                w.Write(s.Commands.Count);
                foreach (var x in s.Commands) { String(w, x.CommandId); String(w, x.RequestDigest); String(w, x.Kind); String(w, x.TicketId); String(w, x.Code); w.Write(x.Revision); w.Write(x.CashDeltaMinor); }
                w.Write(s.Drawers.Length);
                foreach (var item in s.Drawers) { w.Write(item != null); if (item != null) { String(w, item.StockId); String(w, item.ItemId); String(w, item.Quality); } }
                w.Write(s.Ad != null);
                if (s.Ad != null)
                {
                    var a = s.Ad; String(w, a.RequestId); String(w, a.RunId); String(w, a.StockId); String(w, a.ItemId); String(w, a.Quality); String(w, a.Version); w.Write((int)a.Phase);
                    w.Write(a.ReservedPriceMinor); w.Write(a.ReservedDrawerSlot); w.Write(a.DayNumber); w.Write(a.RewardRecorded); String(w, a.Conflict); String(w, a.CreateCommandId); String(w, a.ReserveCommandId); String(w, a.ShowingCommandId); String(w, a.CommittingCommandId); String(w, a.CommitCommandId);
                }
                w.Write(s.FakeEvents.Count);
                foreach (var e in s.FakeEvents) { String(w, e.EventId); String(w, e.RequestId); String(w, e.RunId); w.Write((int)e.Kind); }
                w.Write(s.FakeShownRequests.Count); foreach (string request in s.FakeShownRequests) String(w, request);
                w.Flush(); return stream.ToArray();
            }
        }
        public static RunState DeserializeCanonical(byte[] bytes)
        {
            if (bytes == null || bytes.Length > 16 * 1024 * 1024) throw new InvalidDataException("Invalid state size");
            using (var stream = new MemoryStream(bytes, false)) using (var r = new BinaryReader(stream, Encoding.UTF8, true))
            {
                if (String(r) != "LOTTERY-G2-STATE") throw new InvalidDataException("Wrong state magic");
                int schema = r.ReadInt32(); if (schema != RunState.CurrentSchema) throw new InvalidDataException("Unknown schema; preserve original files");
                var s = new RunState { SchemaVersion = schema, RulesHash = String(r), RunId = String(r), Seed = String(r), FixtureLabel = String(r), Revision = r.ReadInt64(), InitialCashMinor = r.ReadInt64(), CashMinor = r.ReadInt64(), DayNumber = r.ReadInt32(), TicketsPurchasedToday = r.ReadInt32(), SettledTicketCount = r.ReadInt32(), FixtureBaseSettlements = r.ReadInt32(), AdSuccessesToday = r.ReadInt32(), SettledCountAtLastAdSuccess = r.ReadInt32(), EconomicCounter = r.ReadUInt64(), StockAvailable = r.ReadBoolean() };
                int count = Count(r, 12);
                for (int i = 0; i < count; i++)
                {
                    var t = new TicketState { Id = String(r), TicketType = String(r), PreviousSettledTicketType = String(r), EconomicAlgorithm = String(r), Phase = (TicketPhase)r.ReadInt32(), RawPrizeMinor = r.ReadInt64(), PriceMinor = r.ReadInt64(), CashAfterPurchaseMinor = r.ReadInt64(), PurchasedPosition = r.ReadInt32(), EconomicCounterBefore = r.ReadUInt64(), EconomicCounterAfter = r.ReadUInt64(), SettledCountSnapshot = r.ReadInt32() };
                    t.ConfigurationSnapshot = new string[Count(r, 3)]; for (int j = 0; j < t.ConfigurationSnapshot.Length; j++) t.ConfigurationSnapshot[j] = String(r);
                    t.Face = new NumberFace { GeneratorVersion = String(r), WinningNumber = r.ReadInt32(), Cells = new NumberCell[Count(r, 6)] };
                    for (int j = 0; j < t.Face.Cells.Length; j++) t.Face.Cells[j] = new NumberCell(r.ReadInt32(), r.ReadInt64());
                    if (String(r) != ScratchMask.Version) throw new InvalidDataException("Unknown mask version");
                    int maskSize = Count(r, ScratchMask.GridWidth * ScratchMask.GridHeight / 8); byte[] mask = r.ReadBytes(maskSize);
                    if (mask.Length != maskSize) throw new EndOfStreamException(); t.Scratch = new ScratchMask(mask); s.Tickets.Add(t);
                }
                count = Count(r, 12);
                for (int i = 0; i < count; i++) s.Settlements.Add(new SettlementRecord { TicketId = String(r), RawPrizeMinor = r.ReadInt64(), AdditionMinor = r.ReadInt64(), TotalMinor = r.ReadInt64(), TicketPriceMinor = r.ReadInt64(), NetMinor = r.ReadInt64() });
                count = Count(r);
                for (int i = 0; i < count; i++) s.Commands.Add(new CommandReceipt { CommandId = String(r), RequestDigest = String(r), Kind = String(r), TicketId = String(r), Code = String(r), Revision = r.ReadInt64(), CashDeltaMinor = r.ReadInt64() });
                s.Drawers = new DrawerItem[Count(r, 2)];
                for (int i = 0; i < s.Drawers.Length; i++) if (r.ReadBoolean()) s.Drawers[i] = new DrawerItem { StockId = String(r), ItemId = String(r), Quality = String(r) };
                if (r.ReadBoolean()) s.Ad = new AdTransaction { RequestId = String(r), RunId = String(r), StockId = String(r), ItemId = String(r), Quality = String(r), Version = String(r), Phase = (AdPhase)r.ReadInt32(), ReservedPriceMinor = r.ReadInt64(), ReservedDrawerSlot = r.ReadInt32(), DayNumber = r.ReadInt32(), RewardRecorded = r.ReadBoolean(), Conflict = String(r), CreateCommandId = String(r), ReserveCommandId = String(r), ShowingCommandId = String(r), CommittingCommandId = String(r), CommitCommandId = String(r) };
                count = Count(r);
                for (int i = 0; i < count; i++) s.FakeEvents.Add(new Ads.FakeAdEvent { EventId = String(r), RequestId = String(r), RunId = String(r), Kind = (Ads.AdEventKind)r.ReadInt32() });
                count = Count(r, 1000); for (int i = 0; i < count; i++) s.FakeShownRequests.Add(String(r));
                if (stream.Position != stream.Length) throw new InvalidDataException("Trailing state data");
                return s;
            }
        }
        public static string ComputeHash(RunState state) => HashBytes(SerializeCanonical(state));
        public static string HashBytes(byte[] bytes)
        { using (var sha = SHA256.Create()) { var hash = sha.ComputeHash(bytes); var text = new StringBuilder(64); foreach (byte b in hash) text.Append(b.ToString("x2")); return text.ToString(); } }
    }
}

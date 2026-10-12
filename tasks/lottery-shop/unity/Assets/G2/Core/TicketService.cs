using System;
using System.IO;
using System.Linq;
namespace Lottery.G2.Core
{
    public sealed class TicketService : IDisposable
    {
        readonly IStateStore store;
        public TicketService(IStateStore store) { this.store = store ?? throw new ArgumentNullException(nameof(store)); }
        public RunState Snapshot => store.Read();
        public bool CanMutate => store.CanMutate;
        public void Dispose() { (store as IDisposable)?.Dispose(); }
        public CommandResult Recover(string commandId) => store.Recover(commandId);
        public CommandResult BuyNumberTicket(string commandId, long expectedRevision)
        {
            string digest = CommandDigest.Create(Snapshot.RunId, "BUY_TICKET");
            return store.Execute(commandId, digest, expectedRevision, s =>
            {
                if (s.CurrentTicket != null && s.CurrentTicket.Phase != TicketPhase.SETTLED) throw new RuleViolation("TICKET_OCCUPIED");
                if (s.TicketsPurchasedToday >= NumberTicketRules.DailyTicketLimit) throw new RuleViolation("DAY_LIMIT");
                if (s.Ad != null && s.Ad.Phase == AdPhase.RECOVERY_CONFLICT) throw new RuleViolation("RECOVERY_REQUIRED");
                long reserved = Ads.AdPurchaseService.HasReservation(s.Ad) ? s.Ad.ReservedPriceMinor : 0;
                if (s.CashMinor - reserved < NumberTicketRules.PriceMinor) throw new RuleViolation("INSUFFICIENT_CASH");
                string id = s.RunId + ":ticket-" + (s.TicketsPurchasedToday + 1);
                var random = new DeterministicStream(s.Seed, NumberTicketRules.EconomicDomain, s.EconomicCounter);
                long raw = NumberTicketRules.PrizeForSample(random.Next(NumberTicketRules.ProbabilityDenominator));
                s.CashMinor -= NumberTicketRules.PriceMinor;
                var ticket = new TicketState { Id = id, Phase = TicketPhase.ACTIVE, PriceMinor = NumberTicketRules.PriceMinor, RawPrizeMinor = raw,
                    Face = NumberTicketRules.BuildFace(s.Seed, id, raw), PurchasedPosition = ++s.TicketsPurchasedToday,
                    PreviousSettledTicketType = s.CurrentTicket == null ? "" : s.CurrentTicket.TicketType, CashAfterPurchaseMinor = s.CashMinor,
                    EconomicCounterBefore = s.EconomicCounter, EconomicCounterAfter = random.Counter, SettledCountSnapshot = s.SettledTicketCount };
                s.EconomicCounter = random.Counter; s.Tickets.Add(ticket);
                return new CommandReceipt { Kind = "BUY_TICKET", TicketId = id, CashDeltaMinor = -NumberTicketRules.PriceMinor };
            });
        }
        public CommandResult ApplyScratch(string ticketId, string commandId, long expectedRevision, ScratchStroke[] strokes)
        {
            string digest = CommandDigest.Create(Snapshot.RunId, "SCRATCH", writer =>
            { writer.Write(ticketId ?? ""); writer.Write(strokes == null ? -1 : strokes.Length); if (strokes != null) foreach (var x in strokes) { writer.Write(x.FromU); writer.Write(x.FromV); writer.Write(x.ToU); writer.Write(x.ToV); writer.Write(x.HasFrom); writer.Write(x.RadiusPixels); } });
            return store.Execute(commandId, digest, expectedRevision, s =>
            {
                var t = RequireTicket(s, ticketId);
                if (t.Phase == TicketPhase.SETTLED) throw new RuleViolation("ALREADY_SETTLED");
                bool changed;
                try { changed = t.Scratch.Apply(strokes); } catch (ArgumentException) { throw new RuleViolation("INVALID_REQUEST"); }
                if (!changed) throw new RuleViolation("NO_CHANGE");
                if (t.Scratch.IsFullyRevealed) t.Phase = TicketPhase.REVEALED_UNCLAIMED;
                return new CommandReceipt { Kind = "SCRATCH", TicketId = t.Id };
            });
        }
        public CommandResult Claim(string ticketId, string commandId, long expectedRevision)
        {
            return store.Execute(commandId, CommandDigest.Create(Snapshot.RunId, "CLAIM", w => w.Write(ticketId ?? "")), expectedRevision, s =>
            {
                var t = RequireTicket(s, ticketId);
                if (t.Phase == TicketPhase.SETTLED || s.Settlements.Any(x => x.TicketId == ticketId)) throw new RuleViolation("ALREADY_SETTLED");
                if (t.Phase != TicketPhase.REVEALED_UNCLAIMED || !t.Scratch.IsFullyRevealed) throw new RuleViolation("NOT_FULLY_REVEALED");
                s.CashMinor = checked(s.CashMinor + t.RawPrizeMinor); t.Phase = TicketPhase.SETTLED; s.SettledTicketCount++;
                s.Settlements.Add(new SettlementRecord { TicketId = t.Id, RawPrizeMinor = t.RawPrizeMinor, TotalMinor = t.RawPrizeMinor, TicketPriceMinor = t.PriceMinor, NetMinor = t.RawPrizeMinor - t.PriceMinor });
                return new CommandReceipt { Kind = "CLAIM", TicketId = t.Id, CashDeltaMinor = t.RawPrizeMinor };
            });
        }
        static TicketState RequireTicket(RunState s, string id)
        { if (s.CurrentTicket == null || s.CurrentTicket.Id != id) throw new RuleViolation("TICKET_NOT_FOUND"); return s.CurrentTicket; }
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

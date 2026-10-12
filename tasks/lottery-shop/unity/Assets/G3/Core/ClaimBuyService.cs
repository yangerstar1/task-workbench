using System.Linq;
namespace Lottery.G3.Core
{
    public sealed partial class DayGameService
    {
        public CommandResult ClaimThenBuy(string ticketId,string nextTicketType,int boostDrawerSlot,string parentIntentId,long expectedRevision)
        {
            string claimId=parentIntentId+":claim",buyId=parentIntentId+":buy";
            var claim=Execute("CLAIM_THEN_BUY",claimId,expectedRevision,w=>{w.Write(parentIntentId??"");w.Write(ticketId??"");w.Write(nextTicketType??"");w.Write(boostDrawerSlot);},s=>
            {
                if(string.IsNullOrWhiteSpace(parentIntentId)||parentIntentId.Length>220)throw new RuleViolation("INVALID_REQUEST");
                if(nextTicketType!="number"&&nextTicketType!="challenge")throw new RuleViolation("INVALID_TICKET_TYPE");if(boostDrawerSlot< -1||boostDrawerSlot>1)throw new RuleViolation("INVALID_DRAWER_SLOT");
                var t=RequireActive(s,ticketId);if(!SettlementRules.CanClaim(t))throw new RuleViolation("NOT_READY_TO_CLAIM");
                var settlement=SettlementRules.Calculate(s,t,true);s.CashMinor=checked(s.CashMinor+settlement.TotalMinor);s.Settlements.Add(settlement);t.Phase=TicketPhase.SETTLED;s.SettledTicketCount++;s.LifetimeEffectiveTickets++;
                if(s.TicketsPurchasedToday==12)s.Phase=DayPhase.CLOSING_PREP;
                s.ClaimBuyIntents.Add(new ClaimBuyIntent{IntentId=parentIntentId,TicketId=ticketId,NextTicketType=nextTicketType,BoostDrawerSlot=boostDrawerSlot,ClaimCommandId=claimId,BuyCommandId=buyId});return t.Id;
            });
            if(!claim.Success)return claim;return ResumeClaimThenBuy(parentIntentId);
        }
        public CommandResult ResumeClaimThenBuy(string parentIntentId)
        {
            var s=Snapshot;var intent=s.ClaimBuyIntents.SingleOrDefault(x=>x.IntentId==parentIntentId);
            if(intent==null)return new CommandResult{CommitStatus=CommitStatus.PROVEN_NOT_COMMITTED,Code="INTENT_NOT_FOUND",State=s};
            if(intent.Cancelled)return new CommandResult{CommitStatus=CommitStatus.PROVEN_NOT_COMMITTED,Code="INTENT_CANCELLED",State=s};
            return BuyTicket(intent.NextTicketType,intent.BoostDrawerSlot,intent.BuyCommandId,s.Revision);
        }
        public CommandResult CancelNextPurchase(string parentIntentId,string commandId,long expectedRevision)
        {
            return Execute("CANCEL_NEXT_PURCHASE",commandId,expectedRevision,w=>w.Write(parentIntentId??""),s=>
            {var intent=s.ClaimBuyIntents.SingleOrDefault(x=>x.IntentId==parentIntentId);if(intent==null)throw new RuleViolation("INTENT_NOT_FOUND");if(s.Commands.Any(c=>c.CommandId==intent.BuyCommandId))throw new RuleViolation("NEXT_ALREADY_PURCHASED");if(intent.Cancelled)throw new RuleViolation("INTENT_CANCELLED");intent.Cancelled=true;return intent.TicketId;});
        }
    }
}

using System;
using System.Linq;
namespace Lottery.G3.Core
{
    public static class SettlementRules
    {
        public static bool CanClaim(TicketState t)
        {return t!=null&&t.Phase!=TicketPhase.SETTLED&&(t.TicketType=="number"?t.Phase==TicketPhase.REVEALED_UNCLAIMED&&t.Scratch.IsFullyRevealed:t.SelectedCell<0&&(t.Busted||t.SafeCount>0)&&t.RevealedCells.Any(x=>x));}
        public static SettlementRecord Calculate(RunState state,TicketState t,bool updateCounters)
        {
            if(!CanClaim(t))throw new RuleViolation("NOT_READY_TO_CLAIM");
            var result=new SettlementRecord{TicketId=t.Id,RawPrizeMinor=t.RawPrizeMinor,TicketPriceMinor=t.PriceMinor,ConsumableCostMinor=t.ConsumableCostMinor};
            Add(result,"raw_prize",t.RawPrizeMinor);
            foreach(var snapshot in t.ConfigurationSnapshot)
            {
                int l=snapshot.Level-1;long amount=0;
                switch(snapshot.ItemId)
                {
                    case "small_prize_box":if(t.TicketType=="number"&&t.RawPrizeMinor>0&&t.RawPrizeMinor<=t.PriceMinor*2)amount=new long[]{300,700,1500}[l];break;
                    case "ticket_clip":
                        if(t.RawPrizeMinor>0){var counter=state.ToolCounters.Single(x=>x.ItemId==snapshot.ItemId);int ticks=counter.ClipTicks+1;if(ticks==3)amount=new long[]{750,1500,3000}[l];if(updateCounters)counter.ClipTicks=ticks%3;}break;
                    case "large_prize_stamp":if(t.TicketType=="number"&&t.RawPrizeMinor>=t.PriceMinor*5)amount=Math.Min(DayRules.Ratio(t.RawPrizeMinor,new long[]{1,1,2}[l],new long[]{2,1,1}[l]),new long[]{3000,6000,12000}[l]);break;
                    case "loss_mat":if(t.RawPrizeMinor==0)amount=Math.Min(DayRules.Ratio(t.PriceMinor,new long[]{20,35,50}[l],100),new long[]{200,350,500}[l]);break;
                    case "inspection_lamp":break;
                    case "cashout_stamp":if(t.TicketType=="challenge"&&!t.Busted&&(t.SafeCount==2||t.SafeCount==3))amount=new long[]{400,800,1500}[l];break;
                    case "alternating_stamp":if(t.RawPrizeMinor>0&&t.PreviousSettledTicketType!=""&&t.PreviousSettledTicketType!=t.TicketType)amount=Math.Min(DayRules.Ratio(t.RawPrizeMinor,3,4),6000);break;
                    case "last_tickets_stamp":if(t.RawPrizeMinor>0&&t.PurchasedPosition>=10&&t.PurchasedPosition<=12)amount=Math.Min(checked(t.RawPrizeMinor*2),30000);break;
                    default:throw new RuleViolation("G3_UNAVAILABLE_TOOL");
                }
                if(amount>0)Add(result,snapshot.ItemId,amount);
            }
            // G3 has no unlocked copy-base: no recursive or hidden source enters this list.
            if(t.CopyMinor>0)Add(result,"copy_paper",t.CopyMinor);
            if(t.Busted&&t.ProtectionMinor>0)Add(result,"seal_sticker",t.ProtectionMinor);
            result.NetMinor=checked(result.TotalMinor-result.TicketPriceMinor-result.ConsumableCostMinor);return result;
        }
        static void Add(SettlementRecord result,string source,long amount)
        {result.Entries.Add(new PayoutEntry{Source=source,AmountMinor=amount});result.TotalMinor=checked(result.TotalMinor+amount);}
    }
}

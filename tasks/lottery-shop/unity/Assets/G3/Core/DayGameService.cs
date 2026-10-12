using System;
using System.IO;
using System.Linq;
using Lottery.G2.Core;
namespace Lottery.G3.Core
{
    public sealed partial class DayGameService : IDisposable
    {
        readonly IStateStore store;
        public DayGameService(IStateStore store){this.store=store??throw new ArgumentNullException(nameof(store));}
        public RunState Snapshot=>store.Read(); public bool CanMutate=>store.CanMutate;
        public void Dispose(){(store as IDisposable)?.Dispose();} public CommandResult Recover(string commandId)=>store.Recover(commandId);
        CommandResult Execute(string kind,string id,long revision,Action<BinaryWriter> fields,Func<RunState,string> apply)
        {
            return store.Execute(id,CommandDigest.Create(Snapshot.RunId,kind,fields),revision,s=>
            {long before=s.CashMinor;string reference=apply(s)??"";long delta=checked(s.CashMinor-before);
                if(delta!=0)s.Ledger.Add(new LedgerEntry{CommandId=id,Kind=kind,ReferenceId=reference,DeltaMinor=delta,BalanceMinor=s.CashMinor});
                return new CommandReceipt{Kind=kind,TicketId=reference,CashDeltaMinor=delta};});
        }
        internal static void RequireLive(RunState s)
        {if(s.Phase==DayPhase.DAY_COMPLETE||s.Phase==DayPhase.RUN_FAILED)throw new RuleViolation("G3_DAY_BOUNDARY");}
        internal static void RequireStable(RunState s)
        {RequireLive(s);if(s.HasUnsettledTicket&&s.CurrentTicket.SelectedCell>=0)throw new RuleViolation("REVEAL_PENDING");}
        internal static void RequireShopping(RunState s)
        {RequireStable(s);if(s.Phase!=DayPhase.DAY_OPEN&&s.Phase!=DayPhase.CLOSING_PREP)throw new RuleViolation("SHOP_CLOSED");}
        internal static TicketState RequireTicket(RunState s,string id)
        {RequireLive(s);if(s.CurrentTicket==null||s.CurrentTicket.Id!=id)throw new RuleViolation("TICKET_NOT_FOUND");return s.CurrentTicket;}
        static TicketState RequireActive(RunState s,string id)
        {var t=RequireTicket(s,id);if(t.Phase==TicketPhase.SETTLED)throw new RuleViolation("ALREADY_SETTLED");return t;}
        internal static void RequireCash(RunState s,long amount){if(amount<0||s.AvailableCashMinor<amount)throw new RuleViolation("INSUFFICIENT_CASH");}
        public CommandResult BuyNumberTicket(string commandId,long expectedRevision)=>BuyTicket("number",-1,commandId,expectedRevision);
        public CommandResult BuyChallengeTicket(string commandId,long expectedRevision)=>BuyTicket("challenge",-1,commandId,expectedRevision);
        public CommandResult BuyTicket(string ticketType,int boostDrawerSlot,string commandId,long expectedRevision)
        {
            return Execute("BUY_TICKET",commandId,expectedRevision,w=>{w.Write(ticketType??"");w.Write(boostDrawerSlot);},s=>
            {
                RequireLive(s);if(ticketType!="number"&&ticketType!="challenge")throw new RuleViolation("INVALID_TICKET_TYPE");
                if(s.HasUnsettledTicket)throw new RuleViolation("TICKET_OCCUPIED");
                var pending=s.ClaimBuyIntents.LastOrDefault(x=>!x.Cancelled&&!s.Commands.Any(c=>c.CommandId==x.BuyCommandId));if(pending!=null&&pending.BuyCommandId!=commandId)throw new RuleViolation("NEXT_PURCHASE_INTENT_PENDING");
                if(s.TicketsPurchasedToday>=12)throw new RuleViolation("DAY_LIMIT");if(s.Phase!=DayPhase.DAY_OPEN)throw new RuleViolation("DAY_CLOSED");
                RequireCash(s,DayRules.TicketPriceMinor);int draws=1;DrawerItem boost=null;
                if(boostDrawerSlot!=-1)
                {if(ticketType!="number")throw new RuleViolation("BOOST_NUMBER_ONLY");boost=RequireDrawer(s,boostDrawerSlot);if(boost.ItemId!="boost_coupon")throw new RuleViolation("WRONG_CONSUMABLE");draws=new[]{2,3,5}[DayRules.QualityIndex(boost.Quality)];}
                string ticketId=s.RunId+":ticket-"+(s.TicketsPurchasedToday+1);
                var t=new TicketState{Id=ticketId,PurchaseCommandId=commandId,TicketType=ticketType,Phase=TicketPhase.ACTIVE,PriceMinor=DayRules.TicketPriceMinor,
                    PurchasedPosition=s.TicketsPurchasedToday+1,CashAfterPurchaseMinor=s.CashMinor-DayRules.TicketPriceMinor,PreviousSettledTicketType=s.CurrentTicket==null?"":s.CurrentTicket.TicketType,
                    ConfigurationSnapshot=s.NextToolIds.Where(x=>x!="").Select(x=>{var owned=s.Tools.Single(z=>z.ItemId==x);return new ToolSnapshot{ItemId=x,Level=owned.Level};}).ToArray(),
                    Scratch=new TicketMask(ticketType=="number"?6:8),EconomicCounterBefore=s.EconomicCounter,EconomicCounterAfter=s.EconomicCounter,ChallengeCounterBefore=s.ChallengeCounter,ChallengeCounterAfter=s.ChallengeCounter};
                if(ticketType=="number")
                {
                    var random=new DeterministicStream(s.Seed,NumberTicketRules.EconomicDomain,s.EconomicCounter);long raw=0;
                    for(int i=0;i<draws;i++)raw=Math.Max(raw,NumberTicketRules.PrizeForSample(random.Next(1000000)));
                    t.RawPrizeMinor=raw;t.EconomicDrawCount=draws;t.Face=NumberTicketRules.BuildFace(s.Seed,ticketId,raw);t.EconomicCounterAfter=random.Counter;s.EconomicCounter=random.Counter;
                    if(boost!=null){t.UsedConsumableTypes.Add(boost.ItemId);t.ConsumableUses.Add(new ConsumableUse{ItemId=boost.ItemId,Quality=boost.Quality,StockId=boost.StockId,PurchasePriceMinor=boost.PurchasePriceMinor});t.ConsumableCostMinor=boost.PurchasePriceMinor;s.Drawers[boostDrawerSlot]=null;}
                }
                else
                {
                    var random=new DeterministicStream(s.Seed,"challenge-arrangements-v1",s.ChallengeCounter);var safe=new[]{true,true,true,true,true,true,false,false};
                    for(int i=7;i>0;i--){int j=random.Next(i+1);bool tmp=safe[i];safe[i]=safe[j];safe[j]=tmp;}
                    int challengeIndex=s.Tickets.Count(x=>x.TicketType=="challenge");
                    if(s.FixtureLabel==RunFactory.DiagnosticLabel&&challengeIndex<s.DiagnosticChallengeArrangements.Count)safe=(bool[])s.DiagnosticChallengeArrangements[challengeIndex].Clone();
                    t.ChallengeSafe=safe;t.RevealedCells=new bool[8];t.PeekedCells=new bool[8];t.ChallengeCounterAfter=random.Counter;s.ChallengeCounter=random.Counter;
                }
                s.CashMinor-=DayRules.TicketPriceMinor;s.TicketsPurchasedToday++;s.Tickets.Add(t);return ticketId;
            });
        }
        public CommandResult SelectChallengeCell(string ticketId,int cell,string commandId,long expectedRevision)
        {
            return Execute("SELECT_CHALLENGE_CELL",commandId,expectedRevision,w=>{w.Write(ticketId??"");w.Write(cell);},s=>
            {var t=RequireActive(s,ticketId);RequireChallengeStable(t);if(cell<0||cell>=8||t.RevealedCells[cell])throw new RuleViolation("INVALID_CELL");t.SelectedCell=cell;t.SelectionId=commandId;return t.Id;});
        }
        static void RequireChallengeStable(TicketState t)
        {if(t.TicketType!="challenge")throw new RuleViolation("CHALLENGE_ONLY");if(t.SelectedCell>=0)throw new RuleViolation("REVEAL_PENDING");if(t.Busted||t.SafeCount>=6||t.Phase!=TicketPhase.ACTIVE)throw new RuleViolation("CHALLENGE_FINISHED");}
        public CommandResult ApplyCellScratch(string ticketId,CellStroke[] strokes,string commandId,long expectedRevision)
        {
            return Execute("CELL_SCRATCH",commandId,expectedRevision,w=>
            {w.Write(ticketId??"");w.Write(strokes==null?-1:strokes.Length);if(strokes!=null)foreach(var x in strokes){w.Write(x.CellIndex);w.Write(x.FromU);w.Write(x.FromV);w.Write(x.ToU);w.Write(x.ToV);w.Write(x.HasFrom);w.Write(x.RadiusU);w.Write(x.RadiusV);}},s=>
            {var t=RequireActive(s,ticketId);if(t.Phase!=TicketPhase.ACTIVE)throw new RuleViolation("ALREADY_REVEALED");if(t.TicketType=="challenge"&&t.SelectedCell<0)throw new RuleViolation("SELECT_CELL_FIRST");
                bool changed;try{changed=t.Scratch.Apply(strokes,t.TicketType=="challenge"?t.SelectedCell:-1);}catch(ArgumentException){throw new RuleViolation("INVALID_STROKE");}
                if(!changed)throw new RuleViolation("NO_CHANGE");CompleteReveal(t);return t.Id;});
        }
        // Legacy diagnostic adapter. Crossing logical cell boundaries rejects instead of bridging gutters.
        public CommandResult ApplyScratch(string ticketId,ScratchStroke[] strokes,string commandId,long expectedRevision)
        {
            var state=Snapshot;var t=state.CurrentTicket;CellStroke[] local=null;
            if(t!=null&&strokes!=null)
            {
                local=new CellStroke[strokes.Length];int cols=t.Scratch.CellCount/2;
                for(int i=0;i<strokes.Length;i++)
                {
                    var x=strokes[i];int col=(int)Math.Floor(x.ToU*cols),row=(int)Math.Floor(x.ToV*2);if(col==cols&&x.ToU==1)col--;if(row==2&&x.ToV==1)row--;
                    int cell=row*cols+col;double fu=x.HasFrom?x.FromU*cols-col:x.ToU*cols-col,fv=x.HasFrom?x.FromV*2-row:x.ToV*2-row;
                    local[i]=new CellStroke(cell,fu,fv,x.ToU*cols-col,x.ToV*2-row,x.HasFrom,x.RadiusPixels/(256.0/cols),x.RadiusPixels/64.0);
                }
            }
            return ApplyCellScratch(ticketId,local,commandId,expectedRevision);
        }
        public CommandResult QuickReveal(string ticketId,string commandId,long expectedRevision)
        {
            return Execute("QUICK_REVEAL",commandId,expectedRevision,w=>w.Write(ticketId??""),s=>
            {var t=RequireActive(s,ticketId);if(t.Phase!=TicketPhase.ACTIVE)throw new RuleViolation("ALREADY_REVEALED");if(t.TicketType=="number")t.Scratch.RevealAll();else{if(t.SelectedCell<0)throw new RuleViolation("SELECT_CELL_FIRST");t.Scratch.RevealCell(t.SelectedCell);}CompleteReveal(t);return t.Id;});
        }
        static void CompleteReveal(TicketState t)
        {
            if(t.TicketType=="number"){if(t.Scratch.IsFullyRevealed)t.Phase=TicketPhase.REVEALED_UNCLAIMED;return;}
            int cell=t.SelectedCell;if(cell<0||t.Scratch.CellCoverage(cell)!=1)return;
            if(t.RevealedCells[cell])throw new RuleViolation("CELL_ALREADY_REVEALED");t.RevealedCells[cell]=true;t.SelectedCell=-1;
            if(t.ChallengeSafe[cell]){t.SafeCount++;t.RawPrizeMinor=DayRules.ChallengePrizes[t.SafeCount-1];if(t.SafeCount==6)t.Phase=TicketPhase.REVEALED_UNCLAIMED;}
            else{t.Busted=true;t.RawPrizeMinor=0;t.Phase=TicketPhase.REVEALED_UNCLAIMED;}
        }
        public SettlementRecord PreviewSettlement()
        {var s=Snapshot;var t=s.CurrentTicket;if(t==null||!SettlementRules.CanClaim(t))return null;return SettlementRules.Calculate(s,t,false);}
        public CommandResult Claim(string ticketId,string commandId,long expectedRevision)
        {
            return Execute("CLAIM",commandId,expectedRevision,w=>w.Write(ticketId??""),s=>
            {var t=RequireActive(s,ticketId);if(!SettlementRules.CanClaim(t))throw new RuleViolation(t.SelectedCell>=0?"REVEAL_PENDING":"NOT_READY_TO_CLAIM");
                if(s.Settlements.Any(x=>x.TicketId==ticketId))throw new RuleViolation("ALREADY_SETTLED");var settlement=SettlementRules.Calculate(s,t,true);
                s.CashMinor=checked(s.CashMinor+settlement.TotalMinor);s.Settlements.Add(settlement);t.Phase=TicketPhase.SETTLED;s.SettledTicketCount++;s.LifetimeEffectiveTickets++;
                if(s.TicketsPurchasedToday==12)s.Phase=DayPhase.CLOSING_PREP;return t.Id;});
        }
    }
}

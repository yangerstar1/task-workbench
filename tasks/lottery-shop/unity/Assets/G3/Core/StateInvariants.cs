using System;
using System.Linq;
using Lottery.G2.Core;
namespace Lottery.G3.Core
{
    public static class StateInvariants
    {
        static void Need(bool value,string reason){if(!value)throw new InvalidOperationException("G3 invariant: "+reason);}
        static bool Id(string value)=>!string.IsNullOrWhiteSpace(value)&&value.Length<=512&&!value.Any(char.IsControl);
        public static void Validate(RunState s)
        {
            try { ValidateCore(s); } catch(RuleViolation e) { throw new InvalidOperationException("G3 invalid rule identity: "+e.Code,e); }
        }
        static void ValidatePaidConsumable(RunState s,string stockId,string itemId,string quality,long payment)
        {
            bool prior=s.Ledger.Any(l=>l.Kind=="FIXTURE_PRIOR_PURCHASE"&&l.ReferenceId==itemId&&-l.DeltaMinor==payment);
            bool bought=s.Stock.Any(x=>x.IsConsumable&&x.StockId==stockId&&x.ItemId==itemId&&x.Quality==quality&&x.Quantity==0&&(x.PriceMinor==payment||(s.Ad!=null&&s.Ad.StockId==stockId&&s.Ad.RewardRecorded&&s.Ad.ReservedPriceMinor==payment)));
            Need(prior||bought,"consumable has actual paid acquisition");
        }
        static void ValidateCore(RunState s)
        {
            Need(s!=null,"missing root");Need(s.SchemaVersion==RunState.CurrentSchema&&s.RulesHash==NumberTicketRules.RulesSha256,"schema/rules binding");
            Need(Id(s.RunId)&&Id(s.Seed)&&s.DayNumber==1&&Enum.IsDefined(typeof(DayPhase),s.Phase),"identity/day/phase");
            Need(s.UsedRunIds!=null&&s.UsedRunIds.Count>=1&&s.UsedRunIds.All(Id)&&s.UsedRunIds.Distinct().Count()==s.UsedRunIds.Count&&s.UsedRunIds[s.UsedRunIds.Count-1]==s.RunId,"all run identities retained uniquely");
            Need(s.UsedRunIds.Skip(1).SequenceEqual(s.Commands.Where(c=>c.Kind=="RESTART_DAY").Select(c=>c.TicketId)),"used run identities match restart journal");
            Need(s.FixtureLabel==""||s.FixtureLabel==RunFactory.DiagnosticLabel||s.FixtureLabel=="SYNTHETIC_INVENTORY_BOUNDARY_FIXTURE"||s.FixtureLabel=="SYNTHETIC_AD_FIXTURE"||s.FixtureLabel=="SYNTHETIC_CONSUMABLE_BOUNDARY_FIXTURE","unknown fixture");
            Need(s.FixtureLabel==""||FixtureAccess.Enabled,"fixture disabled outside development/test");
            Need(s.CashMinor>=0&&s.InitialCashMinor==30000&&s.Revision>=0,"wallet/revision");
            Need(s.PrincipalMinor>0&&s.PrincipalMinor<=300000&&s.PrincipalRepaidMinor>=0&&checked(s.PrincipalMinor+s.PrincipalRepaidMinor)==300000,"principal conservation/G4 boundary");
            Need(s.PrincipalAtOpenMinor==300000&&s.InterestDueMinor==DayRules.Interest(s.PrincipalAtOpenMinor)&&s.InterestPaidMinor>=0&&s.InterestPaidMinor<=s.InterestDueMinor,"locked interest");
            Need(s.TicketsPurchasedToday==s.Tickets.Count&&s.Tickets.Count<=12&&s.Tickets.Count>=0,"day ticket cap");
            Need(s.FixtureBaseSettlements==0||(s.FixtureLabel=="SYNTHETIC_AD_FIXTURE"&&s.FixtureBaseSettlements>=0&&s.FixtureBaseSettlements<=12),"synthetic base settlements");
            Need(s.SettledTicketCount==s.Settlements.Count+s.FixtureBaseSettlements&&s.LifetimeEffectiveAtOpen>=0&&s.LifetimeEffectiveTickets==s.LifetimeEffectiveAtOpen+s.Settlements.Count,"unique effective ticket count");
            Need(s.NextToolIds!=null&&s.NextToolIds.Length==3&&s.Drawers!=null&&s.Drawers.Length==2,"slot shapes");
            Need(s.Tools.Count<=6&&s.Tools.Select(x=>x.ItemId).Distinct().Count()==s.Tools.Count,"tool capacity/identity");
            var equipped=s.NextToolIds.Where(x=>x!="").ToArray();Need(equipped.Distinct().Count()==equipped.Length&&equipped.All(x=>s.Tools.Any(t=>t.ItemId==x))&&s.Tools.Count-equipped.Length<=3,"table/reserve partition");
            foreach(var t in s.Tools){var rule=DayRules.Tool(t.ItemId);Need(t.Level>=1&&t.Level<=rule.LevelCap&&t.InitialPaymentMinor>0&&t.InitialPaymentMinor<=rule.PriceMinor,"owned tool");}
            Need(s.ToolCounters.Count==8&&s.ToolCounters.Select(x=>x.ItemId).Distinct().Count()==8,"persistent counter keys");
            foreach(var c in s.ToolCounters){DayRules.Tool(c.ItemId);Need(c.UsedToday>=0&&c.UsedToday<=3&&c.ClipTicks>=0&&c.ClipTicks<3,"counter range");if(c.ItemId!="inspection_lamp")Need(c.UsedToday==0,"unused daily counters");if(c.ItemId!="ticket_clip")Need(c.ClipTicks==0,"unused clip counters");}
            Need(s.Stock.Count(x=>x.IsConsumable)==1&&s.Stock.Count(x=>!x.IsConsumable)<=3&&s.Stock.Select(x=>x.StockId).Distinct().Count()==s.Stock.Count&&s.Stock.Select(x=>x.ItemId).Distinct().Count()==s.Stock.Count,"daily fixed stock");
            Need(s.ConsumableBatch.Length==4&&s.ConsumableBatch.Distinct().Count()==4&&s.ConsumableBatch.All(x=>DayRules.ConsumableIds.Contains(x)),"four-type batch");
            foreach(var stock in s.Stock)
            {
                Need(stock.StockId==s.RunId+":day1:"+stock.ItemId&&(stock.Quantity==0||stock.Quantity==1),"stock identity/count");
                if(stock.IsConsumable)Need(stock.ItemId==s.ConsumableBatch[0]&&stock.PriceMinor==DayRules.ConsumablePrice(stock.ItemId,stock.Quality),"consumable stock rule");
                else {var r=DayRules.Tool(stock.ItemId);Need(stock.PriceMinor==r.PriceMinor&&stock.Quality==r.Rarity,"tool stock rule");}
            }
            foreach(var item in s.Drawers.Where(x=>x!=null))
            {long price=DayRules.ConsumablePrice(item.ItemId,item.Quality);Need(Id(item.StockId)&&item.PurchasePriceMinor>0&&item.PurchasePriceMinor<=price,"drawer paid basis");}
            Need(s.Contacts.Count==2&&s.Contacts.Select(x=>x.ContactId).Distinct().Count()==2,"contact identities");
            foreach(var contact in s.Contacts)
            {long limit=DayRules.ContactLimit(contact.ContactId);Need(contact.BorrowedLifetimeMinor>=0&&contact.BorrowedLifetimeMinor<=limit&&s.Loans.Where(x=>x.ContactId==contact.ContactId).Sum(x=>x.BorrowedMinor)==contact.BorrowedLifetimeMinor,"nonrestoring cumulative loan limit");}
            Need(s.Loans.Select(x=>x.LoanId).Distinct().Count()==s.Loans.Count,"unique loans");
            foreach(var loan in s.Loans)Need(Id(loan.LoanId)&&loan.BorrowedDay==1&&loan.DueNight==loan.BorrowedDay+DayRules.ContactDueOffset(loan.ContactId)&&loan.BorrowedMinor>0&&loan.RemainingMinor>=0&&loan.RemainingMinor<=loan.BorrowedMinor,"loan amounts/deadline");
            long balance=s.InitialCashMinor;foreach(var line in s.Ledger){Need(Id(line.CommandId)&&line.DeltaMinor!=0,"nonzero identified ledger");balance=checked(balance+line.DeltaMinor);Need(balance>=0&&line.BalanceMinor==balance,"ledger conservation");}Need(balance==s.CashMinor,"wallet equals ledger");
            Need(s.Commands.Count==s.Revision&&s.Commands.Select(x=>x.CommandId).Distinct().Count()==s.Commands.Count,"unique command journal");
            for(int i=0;i<s.Commands.Count;i++){var c=s.Commands[i];Need(Id(c.CommandId)&&c.RequestDigest.Length==64&&c.RequestDigest.All(x=>(x>='0'&&x<='9')||(x>='a'&&x<='f'))&&c.Revision==i+1&&c.Code=="SUCCESS","receipt binding");}
            Need(s.Ledger.Select(x=>x.CommandId).Distinct().Count()==s.Ledger.Count,"unique cash command rows");
            foreach(var line in s.Ledger)
            {
                if(line.Kind=="FIXTURE_PRIOR_PURCHASE")
                {
                    Need((s.FixtureLabel=="SYNTHETIC_INVENTORY_BOUNDARY_FIXTURE"||s.FixtureLabel=="SYNTHETIC_CONSUMABLE_BOUNDARY_FIXTURE")&&line.CommandId.StartsWith("fixture-purchase:",StringComparison.Ordinal)&&line.DeltaMinor<0,"narrow paid fixture purchase");
                    long paid=checked(-line.DeltaMinor);var tool=DayRules.Tools.FirstOrDefault(x=>x.Id==line.ReferenceId);
                    Need(tool!=null?paid==tool.PriceMinor:DayRules.ConsumableIds.Contains(line.ReferenceId)&&DayRules.Qualities.Any(q=>paid==DayRules.ConsumablePrice(line.ReferenceId,q)),"fixture frozen paid basis");
                }
                else
                {
                    var receipt=s.Commands.SingleOrDefault(x=>x.CommandId==line.CommandId);
                    Need(receipt!=null&&receipt.CashDeltaMinor==line.DeltaMinor&&(receipt.Kind==line.Kind||(receipt.Kind=="AD_COMMIT"&&line.Kind=="AD_PURCHASE")),"cash line bound to exact command");
                }
            }
            foreach(var loan in s.Loans)
            {
                var receipt=s.Commands.SingleOrDefault(c=>c.Kind=="BORROW"&&c.TicketId==loan.LoanId);
                Need(receipt!=null&&receipt.CashDeltaMinor==loan.BorrowedMinor,"loan cash receipt");
                Need(s.PhoneEvents.Count(e=>e.Kind=="BORROWED"&&e.LoanId==loan.LoanId&&e.ContactId==loan.ContactId&&e.AmountMinor==loan.BorrowedMinor&&e.DueNight==loan.DueNight)==1,"one factual loan message");
                Need(s.PhoneEvents.Where(e=>e.Kind=="REPAID"&&e.LoanId==loan.LoanId).Sum(e=>e.AmountMinor)==loan.BorrowedMinor-loan.RemainingMinor,"repayment event conservation");
            }
            Need(s.PhoneEvents.Select(x=>x.EventId).Distinct().Count()==s.PhoneEvents.Count,"unique phone events");
            var phoneRequests=s.PhoneEvents.Where(x=>x.Kind=="BORROW_REQUESTED").ToArray();
            var phoneCancellations=s.PhoneEvents.Where(x=>x.Kind=="BORROW_CANCELLED").ToArray();
            Need(phoneCancellations.Select(x=>x.LoanId).Distinct().Count()==phoneCancellations.Length,"unique phone cancellations");
            foreach(var cancellation in phoneCancellations)
            {
                Need(Id(cancellation.EventId)&&cancellation.DueNight==0&&cancellation.Day>0,"identified phone cancellation");
                Need(phoneRequests.Count(x=>x.LoanId==cancellation.LoanId&&x.ContactId==cancellation.ContactId&&x.AmountMinor==cancellation.AmountMinor)==1,"cancellation matches proposal");
                Need(!s.PhoneEvents.Any(x=>x.Kind=="BORROWED"&&x.LoanId==cancellation.LoanId),"cancelled packet never borrowed");
            }

            Need(phoneRequests.Select(x=>x.LoanId).Distinct().Count()==phoneRequests.Length,"unique phone proposal claim identities");
            foreach(var request in phoneRequests)
            {
                Need(Id(request.EventId)&&Id(request.LoanId)&&request.LoanId.StartsWith(s.RunId+":loan:",StringComparison.Ordinal),"identified phone proposal");
                Need(s.Contacts.Any(x=>x.ContactId==request.ContactId)&&request.AmountMinor>0&&request.Day>0&&request.DueNight==0,"non-economic phone proposal");
                foreach(var claim in s.PhoneEvents.Where(x=>x.Kind=="BORROWED"&&x.LoanId==request.LoanId))
                    Need(claim.ContactId==request.ContactId&&claim.AmountMinor==request.AmountMinor,"phone proposal claim matches");
            }

            foreach(var stock in s.Stock)
            {
                int purchases=s.Commands.Count(c=>(c.Kind=="BUY_STOCK"&&c.TicketId==stock.StockId)||(c.Kind=="AD_COMMIT"&&c.CashDeltaMinor!=0&&s.Ad!=null&&s.Ad.StockId==stock.StockId));
                Need(purchases<=1&&stock.Quantity==1-purchases,"daily stock consumed exactly once");
            }
            foreach(var tool in s.Tools)
            {
                bool prior=s.Ledger.Any(l=>l.Kind=="FIXTURE_PRIOR_PURCHASE"&&l.ReferenceId==tool.ItemId&&-l.DeltaMinor==tool.InitialPaymentMinor);
                bool bought=s.Stock.Any(x=>!x.IsConsumable&&x.ItemId==tool.ItemId&&x.Quantity==0&&x.PriceMinor==tool.InitialPaymentMinor);
                Need(prior||bought,"owned tool has actual paid acquisition");
                int upgrades=s.Commands.Count(c=>c.Kind=="UPGRADE_TOOL"&&c.TicketId==tool.ItemId&&c.Revision>(s.Commands.LastOrDefault(r=>r.Kind=="RESTART_DAY")?.Revision??0));
                Need(tool.Level<=1+upgrades,"tool upgrade paid before level");
            }
            var consumedIds=s.Tickets.SelectMany(t=>t.ConsumableUses).Select(x=>x.StockId).Concat(s.Drawers.Where(x=>x!=null).Select(x=>x.StockId)).ToArray();Need(consumedIds.Distinct().Count()==consumedIds.Length,"one acquired consumable instance cannot be used twice");
            foreach(var item in s.Drawers.Where(x=>x!=null))ValidatePaidConsumable(s,item.StockId,item.ItemId,item.Quality,item.PurchasePriceMinor);
            foreach(var ticket in s.Tickets)foreach(var use in ticket.ConsumableUses)ValidatePaidConsumable(s,use.StockId,use.ItemId,use.Quality,use.PurchasePriceMinor);
            // Historical receipts survive a deliberate fresh-run restart; only the current run's lines are present.
            int runStart=s.Commands.FindLastIndex(x=>x.Kind=="RESTART_DAY");
            Need(s.PrincipalRepaidMinor==-s.Commands.Skip(runStart+1).Where(c=>c.Kind=="REPAY_PRINCIPAL").Sum(c=>c.CashDeltaMinor),"principal payments bound to cash journal");
            Need(s.InterestPaidMinor==-s.Commands.Skip(runStart+1).Where(c=>c.Kind=="PAY_NIGHT_BILL").Sum(c=>c.CashDeltaMinor),"interest payment bound to night receipt");
            foreach(var receipt in s.Commands.Skip(runStart+1).Where(x=>x.CashDeltaMinor!=0))Need(s.Ledger.Count(x=>x.CommandId==receipt.CommandId)==1,"economic receipt has one cash line");
            Need(s.Tickets.Select(x=>x.Id).Distinct().Count()==s.Tickets.Count&&s.Settlements.Select(x=>x.TicketId).Distinct().Count()==s.Settlements.Count,"unique ticket settlements");
            ulong economic=0,challenge=0;int challengeIndex=0,clipTicks=0,lampUses=0;
            for(int i=0;i<s.Tickets.Count;i++)
            {
                var t=s.Tickets[i];Need(t.Id==s.RunId+":ticket-"+(i+1)&&t.PurchasedPosition==i+1&&Id(t.PurchaseCommandId)&&t.PriceMinor==1000&&t.CashAfterPurchaseMinor>=0,"ticket purchase snapshot");
                var purchase=s.Commands.SingleOrDefault(c=>c.CommandId==t.PurchaseCommandId);Need(purchase!=null&&purchase.Kind=="BUY_TICKET"&&purchase.TicketId==t.Id&&purchase.CashDeltaMinor==-t.PriceMinor,"ticket purchase receipt binding");
                Need(t.TicketType=="number"||t.TicketType=="challenge","ticket type");Need(Enum.IsDefined(typeof(TicketPhase),t.Phase),"ticket phase");
                Need(i==s.Tickets.Count-1||t.Phase==TicketPhase.SETTLED,"one unsettled current ticket");Need(t.PreviousSettledTicketType==(i==0?"":s.Tickets[i-1].TicketType),"previous settled snapshot");
                Need(t.ConfigurationSnapshot.Length<=3&&t.ConfigurationSnapshot.Select(x=>x.ItemId).Distinct().Count()==t.ConfigurationSnapshot.Length&&t.ConfigurationSnapshot.All(x=>x.TableSlot>=0&&x.TableSlot<3)&&t.ConfigurationSnapshot.Select(x=>x.TableSlot).Distinct().Count()==t.ConfigurationSnapshot.Length,"three unique physical snapshot slots");
                foreach(var snap in t.ConfigurationSnapshot){var rule=DayRules.Tool(snap.ItemId);Need(snap.Level>=1&&snap.Level<=rule.LevelCap,"snapshot level");if(t.Phase!=TicketPhase.SETTLED)Need(s.Tools.Any(x=>x.ItemId==snap.ItemId),"current snapshot sale lock");}
                Need(t.UsedConsumableTypes.Count<=2&&t.UsedConsumableTypes.Distinct().Count()==t.UsedConsumableTypes.Count&&t.ConsumableUses.Count==t.UsedConsumableTypes.Count&&t.ConsumableUses.Select(x=>x.ItemId).SequenceEqual(t.UsedConsumableTypes),"consumable type limits");
                Need(t.ConsumableCostMinor==t.ConsumableUses.Sum(x=>x.PurchasePriceMinor),"consumed paid cost");
                foreach(var use in t.ConsumableUses){long full=DayRules.ConsumablePrice(use.ItemId,use.Quality);Need(Id(use.StockId)&&use.PurchasePriceMinor>0&&use.PurchasePriceMinor<=full,"consumed item receipt");}
                Need(t.EconomicCounterBefore==economic&&t.ChallengeCounterBefore==challenge,"independent random domains");
                if(t.TicketType=="number")
                {
                    Need(t.Scratch.CellCount==6&&t.ChallengeSafe.Length==0&&t.RevealedCells.Length==0&&t.PeekedCells.Length==0&&t.SelectedCell==-1&&!t.Busted&&t.SafeCount==0&&!t.LampUsed&&t.InformationSource==""&&t.ProtectionMinor==0,"number shape");
                    var boost=t.ConsumableUses.SingleOrDefault(x=>x.ItemId=="boost_coupon");int draws=boost==null?1:new[]{2,3,5}[DayRules.QualityIndex(boost.Quality)];Need(t.EconomicDrawCount==draws,"boost draw count");
                    var rng=new DeterministicStream(s.Seed,NumberTicketRules.EconomicDomain,economic);long raw=0;for(int draw=0;draw<draws;draw++)raw=Math.Max(raw,NumberTicketRules.PrizeForSample(rng.Next(1000000)));
                    economic=rng.Counter;Need(raw==t.RawPrizeMinor&&t.EconomicCounterAfter==economic&&t.ChallengeCounterAfter==challenge,"locked number draw");
                    NumberTicketRules.ValidateFace(t.Face,t.RawPrizeMinor);var face=NumberTicketRules.BuildFace(s.Seed,t.Id,t.RawPrizeMinor);Need(face.WinningNumber==t.Face.WinningNumber&&face.Cells.Zip(t.Face.Cells,(a,b)=>a.Number==b.Number&&a.PrizeMinor==b.PrizeMinor).All(x=>x),"exact N1 face");
                    Need(t.Phase==TicketPhase.ACTIVE?!t.Scratch.IsFullyRevealed:t.Scratch.IsFullyRevealed,"number reveal phase");
                    var copy=t.ConsumableUses.SingleOrDefault(x=>x.ItemId=="copy_paper");if(copy==null)Need(t.CopyMinor==0,"no free copy");else{int q=DayRules.QualityIndex(copy.Quality);Need(t.RawPrizeMinor>0&&t.Scratch.IsFullyRevealed&&t.CopyMinor==Math.Min(DayRules.Ratio(t.RawPrizeMinor,new long[]{1,3,2}[q],new long[]{1,2,1}[q]),new long[]{10000,15000,20000}[q])&&copy.LockedAmountMinor==t.CopyMinor,"raw-only copy");}
                    Need(t.UsedConsumableTypes.All(x=>x=="boost_coupon"||x=="copy_paper"),"number consumable scope");
                }
                else
                {
                    Need(t.SafeCount>=0&&t.SafeCount<=6,"safe-count range");
                    Need(t.Scratch.CellCount==8&&t.Face==null&&t.ChallengeSafe.Length==8&&t.ChallengeSafe.Count(x=>x)==6&&t.RevealedCells.Length==8&&t.PeekedCells.Length==8&&t.SelectedCell>=-1&&t.SelectedCell<8&&t.CopyMinor==0,"challenge shape");
                    var rng=new DeterministicStream(s.Seed,"challenge-arrangements-v1",challenge);var expected=new[]{true,true,true,true,true,true,false,false};for(int j=7;j>0;j--){int k=rng.Next(j+1);bool tmp=expected[j];expected[j]=expected[k];expected[k]=tmp;}challenge=rng.Counter;
                    if(s.FixtureLabel==RunFactory.DiagnosticLabel&&challengeIndex<s.DiagnosticChallengeArrangements.Count)expected=s.DiagnosticChallengeArrangements[challengeIndex];challengeIndex++;
                    Need(t.ChallengeSafe.SequenceEqual(expected)&&t.ChallengeCounterAfter==challenge&&t.EconomicCounterAfter==economic,"locked challenge arrangement");
                    Need(t.SafeCount==Enumerable.Range(0,8).Count(c=>t.RevealedCells[c]&&t.ChallengeSafe[c])&&t.Busted==Enumerable.Range(0,8).Any(c=>t.RevealedCells[c]&&!t.ChallengeSafe[c]),"challenge reveal count");
                    Need(t.RawPrizeMinor==(t.Busted||t.SafeCount==0?0:DayRules.ChallengePrizes[t.SafeCount-1]),"challenge original prize");
                    for(int c=0;c<8;c++){Need(t.RevealedCells[c]==(t.Scratch.CellCoverage(c)==1),"confirmed mask matches cell outcome");if(!t.RevealedCells[c]&&c!=t.SelectedCell)Need(t.Scratch.CellCoverage(c)==0,"unselected cell untouched");}
                    if(t.SelectedCell>=0)Need(t.Phase==TicketPhase.ACTIVE&&!t.RevealedCells[t.SelectedCell]&&Id(t.SelectionId)&&!t.Busted&&t.SafeCount<6,"selection lock");
                    if(t.Phase==TicketPhase.REVEALED_UNCLAIMED)Need(t.Busted||t.SafeCount==6,"challenge terminal reveal");if(t.Phase==TicketPhase.SETTLED)Need(t.SelectedCell==-1&&t.RevealedCells.Any(x=>x),"minimum actual revealed cell");
                    Need(t.InformationSource==""||t.InformationSource=="inspection_lamp"||t.InformationSource=="reveal_film","information source");Need(t.LampUsed==(t.InformationSource=="inspection_lamp"),"lamp source exclusivity");if(t.LampUsed){lampUses++;Need(t.ConfigurationSnapshot.Any(x=>x.ItemId=="inspection_lamp"&&lampUses<=x.Level),"lamp snapshot daily capacity");}
                    Need(t.UsedConsumableTypes.All(x=>x=="reveal_film"||x=="seal_sticker")&&(!t.UsedConsumableTypes.Contains("reveal_film")||t.InformationSource=="reveal_film"),"challenge consumable scope");
                    var seal=t.ConsumableUses.SingleOrDefault(x=>x.ItemId=="seal_sticker");Need(seal==null?t.ProtectionMinor==0:t.ProtectionMinor==seal.LockedAmountMinor&&t.ProtectionMinor>0&&t.ProtectionMinor<=new long[]{3000,6000,12000}[DayRules.QualityIndex(seal.Quality)],"locked protection");
                }
                var settlement=s.Settlements.SingleOrDefault(x=>x.TicketId==t.Id);Need((t.Phase==TicketPhase.SETTLED)==(settlement!=null),"one settlement record");
                if(settlement!=null)
                {
                    Need(settlement.RawPrizeMinor==t.RawPrizeMinor&&settlement.TicketPriceMinor==t.PriceMinor&&settlement.ConsumableCostMinor==t.ConsumableCostMinor&&settlement.Entries.Select(x=>x.Source).Distinct().Count()==settlement.Entries.Count&&settlement.Entries.All(x=>x.AmountMinor>=0)&&settlement.Entries.Sum(x=>x.AmountMinor)==settlement.TotalMinor&&settlement.NetMinor==settlement.TotalMinor-t.PriceMinor-t.ConsumableCostMinor,"settlement conservation");
                    var checkState=new RunState();checkState.ToolCounters.Add(new ToolCounter{ItemId="ticket_clip",ClipTicks=clipTicks});
                    var checkTicket=new TicketState{Id=t.Id,TicketType=t.TicketType,Phase=TicketPhase.REVEALED_UNCLAIMED,RawPrizeMinor=t.RawPrizeMinor,PriceMinor=t.PriceMinor,ConsumableCostMinor=t.ConsumableCostMinor,CopyMinor=t.CopyMinor,ProtectionMinor=t.ProtectionMinor,ConfigurationSnapshot=t.ConfigurationSnapshot,PreviousSettledTicketType=t.PreviousSettledTicketType,PurchasedPosition=t.PurchasedPosition,Scratch=t.Scratch,SelectedCell=-1,SafeCount=t.SafeCount,Busted=t.Busted,RevealedCells=t.RevealedCells};
                    var expectedPayout=SettlementRules.Calculate(checkState,checkTicket,false);
                    Need(settlement.TotalMinor==expectedPayout.TotalMinor&&settlement.Entries.Count==expectedPayout.Entries.Count&&settlement.Entries.Zip(expectedPayout.Entries,(a,b)=>a.Source==b.Source&&a.AmountMinor==b.AmountMinor).All(x=>x),"exact settlement sources and amounts");
                    if(t.RawPrizeMinor>0&&t.ConfigurationSnapshot.Any(x=>x.ItemId=="ticket_clip"))clipTicks=(clipTicks+1)%3;
                }
            }
            Need(s.EconomicCounter==economic&&s.ChallengeCounter==challenge,"root random cursors");
            Need(s.ToolCounters.Single(x=>x.ItemId=="ticket_clip").ClipTicks==clipTicks&&s.ToolCounters.Single(x=>x.ItemId=="inspection_lamp").UsedToday==lampUses,"counters survive configuration and sale");
            if(s.FixtureLabel!=RunFactory.DiagnosticLabel)Need(s.DiagnosticChallengeArrangements.Count==0,"no normal outcome overrides");else Need(s.DiagnosticChallengeArrangements.Count==2&&s.DiagnosticChallengeArrangements.All(a=>a.Length==8&&a.Count(x=>x)==6),"diagnostic arrangement shape");
            Need(s.ClaimBuyIntents.Select(x=>x.IntentId).Distinct().Count()==s.ClaimBuyIntents.Count,"unique parent intent");
            foreach(var intent in s.ClaimBuyIntents)Need(Id(intent.IntentId)&&intent.ClaimCommandId==intent.IntentId+":claim"&&intent.BuyCommandId==intent.IntentId+":buy"&&s.Settlements.Any(x=>x.TicketId==intent.TicketId)&&(intent.NextTicketType=="number"||intent.NextTicketType=="challenge")&&intent.BoostDrawerSlot>=-1&&intent.BoostDrawerSlot<2,"durable claim/next binding");
            if(s.Phase!=DayPhase.DAY_OPEN)Need(!s.HasUnsettledTicket,"closed day active ticket");if(s.Phase==DayPhase.DAY_OPEN&&s.Tickets.Count==12)Need(s.HasUnsettledTicket,"full day closes only after settlement");
            if(s.Phase==DayPhase.DAY_COMPLETE)Need(s.InterestPaidMinor==s.InterestDueMinor,"completed bill paid");
            Need(s.AdEvents.Select(x=>x.EventId).Distinct().Count()==s.AdEvents.Count&&s.AdEvents.All(x=>Id(x.EventId)&&Id(x.RequestId)&&Id(x.RunId)&&new[]{"Reward","Closed","NoFill","NotShown","NoRewardTerminal"}.Contains(x.Kind)),"verified provider event identities");
            Need(s.FakeShownRequests.Distinct().Count()==s.FakeShownRequests.Count&&s.FakeShownRequests.All(Id),"unique provider shows");
            Need(s.AdSuccessesToday>=0&&s.AdSuccessesToday<=1,"ad daily limit");
            if(s.Ad!=null)
            {
                var a=s.Ad;Need(s.FixtureLabel=="SYNTHETIC_AD_FIXTURE"&&Id(a.RequestId)&&a.RunId==s.RunId&&a.DayNumber==s.DayNumber&&a.Version=="g3-fake-ad-v1"&&Enum.IsDefined(typeof(AdPhase),a.Phase),"synthetic ad binding");
                var stock=s.Stock.SingleOrDefault(x=>x.StockId==a.StockId);Need(stock!=null&&stock.IsConsumable&&stock.ItemId==a.ItemId&&stock.Quality==a.Quality&&a.ReservedPriceMinor==DayRules.Ratio(stock.PriceMinor,1,2)&&a.ReservedDrawerSlot>=0&&a.ReservedDrawerSlot<2,"original ad offer");
                if(AdReservations.HasReservation(a)&&a.Phase!=AdPhase.RECOVERY_CONFLICT)Need(stock.Quantity==1&&s.Drawers[a.ReservedDrawerSlot]==null&&s.AvailableCashMinor>=0,"reservation intact");
                if(a.Phase==AdPhase.COMMITTED)Need(a.RewardRecorded&&stock.Quantity==0&&s.AdSuccessesToday==1,"single ad purchase");
                if(a.Phase==AdPhase.REWARD_CONFIRMED||a.Phase==AdPhase.COMMITTING)Need(a.RewardRecorded,"verified reward before commit");
            }
            else Need(s.AdSuccessesToday==0,"no unrecorded ad success");
        }
    }
}

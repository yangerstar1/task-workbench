using System;
using System.Linq;
namespace Lottery.G3.Core
{
    public static class LoanRules
    {
        public static bool IsFrozen(RunState s,string contactId,int day)=>s.Loans.Any(x=>x.ContactId==contactId&&x.RemainingMinor>0&&day>x.DueNight);
        public static long RemainingLimit(RunState s,string contactId)=>DayRules.ContactLimit(contactId)-s.Contacts.Single(x=>x.ContactId==contactId).BorrowedLifetimeMinor;
    }
    public sealed partial class DayGameService
    {
        public CommandResult Borrow(string contactId,long amountMinor,string commandId,long expectedRevision)
        {
            return Execute("BORROW",commandId,expectedRevision,w=>{w.Write(contactId??"");w.Write(amountMinor);},s=>
            {
                RequireStable(s);DayRules.ContactLimit(contactId);if(amountMinor<=0)throw new RuleViolation("INVALID_AMOUNT");
                if(LoanRules.IsFrozen(s,contactId,s.DayNumber))throw new RuleViolation("CONTACT_OVERDUE_FROZEN");
                var contact=s.Contacts.Single(x=>x.ContactId==contactId);if(amountMinor>DayRules.ContactLimit(contactId)-contact.BorrowedLifetimeMinor)throw new RuleViolation("LOAN_LIMIT");
                string loanId=s.RunId+":loan:"+commandId;int due=s.DayNumber+DayRules.ContactDueOffset(contactId);
                s.CashMinor=checked(s.CashMinor+amountMinor);contact.BorrowedLifetimeMinor=checked(contact.BorrowedLifetimeMinor+amountMinor);
                s.Loans.Add(new LoanRecord{LoanId=loanId,ContactId=contactId,BorrowedMinor=amountMinor,RemainingMinor=amountMinor,BorrowedDay=s.DayNumber,DueNight=due});
                s.PhoneEvents.Add(new PhoneEvent{EventId=commandId+":borrow",ContactId=contactId,Kind="BORROWED",LoanId=loanId,AmountMinor=amountMinor,Day=s.DayNumber,DueNight=due});return loanId;
            });
        }
        public CommandResult RepayLoan(string contactId,long amountMinor,string commandId,long expectedRevision)
        {
            return Execute("REPAY_LOAN",commandId,expectedRevision,w=>{w.Write(contactId??"");w.Write(amountMinor);},s=>
            {
                RequireStable(s);DayRules.ContactLimit(contactId);if(amountMinor<=0)throw new RuleViolation("INVALID_AMOUNT");
                var loans=s.Loans.Where(x=>x.ContactId==contactId&&x.RemainingMinor>0).OrderBy(x=>x.DueNight).ThenBy(x=>x.BorrowedDay).ThenBy(x=>x.LoanId,StringComparer.Ordinal).ToArray();
                if(amountMinor>loans.Sum(x=>x.RemainingMinor))throw new RuleViolation("REPAY_EXCEEDS_DEBT");RequireCash(s,amountMinor);long remaining=amountMinor;
                foreach(var loan in loans){long pay=Math.Min(remaining,loan.RemainingMinor);loan.RemainingMinor-=pay;remaining-=pay;if(pay>0)s.PhoneEvents.Add(new PhoneEvent{EventId=commandId+":"+loan.LoanId,ContactId=contactId,Kind="REPAID",LoanId=loan.LoanId,AmountMinor=pay,Day=s.DayNumber,DueNight=loan.DueNight});if(remaining==0)break;}
                s.CashMinor-=amountMinor;return contactId;
            });
        }
        public CommandResult RepayPrincipal(long amountMinor,string commandId,long expectedRevision)
        {
            return Execute("REPAY_PRINCIPAL",commandId,expectedRevision,w=>w.Write(amountMinor),s=>
            {RequireStable(s);if(amountMinor<=0)throw new RuleViolation("INVALID_AMOUNT");if(amountMinor>=s.PrincipalMinor)throw new RuleViolation("G3_FULL_CLEAR_BOUNDARY");RequireCash(s,amountMinor);s.CashMinor-=amountMinor;s.PrincipalMinor-=amountMinor;s.PrincipalRepaidMinor=checked(s.PrincipalRepaidMinor+amountMinor);return s.RunId;});
        }
        public NightBill PreviewNightBill()=>BuildNightBill(Snapshot);
        public static NightBill BuildNightBill(RunState s)
        {
            long principal=DayRules.PrincipalDue(s.DayNumber,s.PrincipalRepaidMinor),interest=s.InterestDueMinor-s.InterestPaidMinor,total=checked(principal+interest);
            return new NightBill{PrincipalDueMinor=principal,InterestUnpaidMinor=interest,TotalDueMinor=total,AvailableCashMinor=s.AvailableCashMinor,ShortfallMinor=Math.Max(0,total-s.AvailableCashMinor),NextDayInterestMinor=DayRules.Interest(s.PrincipalMinor-principal),RemainingOpportunities=Math.Max(0,12-s.TicketsPurchasedToday)};
        }
        public CommandResult BeginClosing(string commandId,long expectedRevision)
        {
            return Execute("BEGIN_CLOSING",commandId,expectedRevision,null,s=>
            {RequireLive(s);if(s.HasUnsettledTicket)throw new RuleViolation("UNSETTLED_TICKET");if(s.Phase!=DayPhase.DAY_OPEN)throw new RuleViolation("NOT_DAY_OPEN");s.Phase=DayPhase.CLOSING_PREP;return s.RunId;});
        }
        public CommandResult EnterNightBill(string commandId,long expectedRevision)
        {
            return Execute("ENTER_NIGHT_BILL",commandId,expectedRevision,null,s=>
            {RequireLive(s);if(s.HasUnsettledTicket)throw new RuleViolation("UNSETTLED_TICKET");if(s.Phase!=DayPhase.CLOSING_PREP)throw new RuleViolation("NOT_CLOSING_PREP");s.Phase=DayPhase.NIGHT_BILL;return s.RunId;});
        }
        public CommandResult PayNightBill(bool confirmFailure,string commandId,long expectedRevision)
        {
            return Execute("PAY_NIGHT_BILL",commandId,expectedRevision,w=>w.Write(confirmFailure),s=>
            {
                RequireLive(s);if(s.Phase!=DayPhase.NIGHT_BILL)throw new RuleViolation("NOT_NIGHT_BILL");if(s.HasUnsettledTicket)throw new RuleViolation("UNSETTLED_TICKET");
                if(AdReservations.HasPending(s.Ad))throw new RuleViolation("AD_RESOLUTION_REQUIRED");var bill=BuildNightBill(s);
                if(bill.ShortfallMinor>0){if(!confirmFailure)throw new RuleViolation("INSUFFICIENT_CASH");s.Phase=DayPhase.RUN_FAILED;return s.RunId;}
                s.CashMinor-=bill.TotalDueMinor;s.PrincipalMinor-=bill.PrincipalDueMinor;s.PrincipalRepaidMinor+=bill.PrincipalDueMinor;s.InterestPaidMinor=s.InterestDueMinor;s.Phase=DayPhase.DAY_COMPLETE;return s.RunId;
            });
        }
        public CommandResult RestartDay(string newRunId,string seed,string commandId,long expectedRevision)
        {
            return store.Execute(commandId,CommandDigest.Create("G3_RESTART_INTENT","RESTART_DAY",w=>{w.Write(newRunId??"");w.Write(seed??"");}),expectedRevision,s=>
            {
                if(s.Phase!=DayPhase.DAY_COMPLETE&&s.Phase!=DayPhase.RUN_FAILED)throw new RuleViolation("DAY_NOT_FINISHED");if(AdReservations.HasPending(s.Ad))throw new RuleViolation("AD_RESOLUTION_REQUIRED");
                if(s.UsedRunIds.Contains(newRunId))throw new RuleViolation("RUN_ID_REUSED");RunState fresh;
                try{fresh=RunFactory.Create(newRunId,seed);}catch(ArgumentException){throw new RuleViolation("INVALID_REQUEST");}
                int lifetime=s.LifetimeEffectiveTickets;
                s.UsedRunIds.Add(newRunId);s.RunId=fresh.RunId;s.Seed=fresh.Seed;s.FixtureLabel="";s.InitialCashMinor=fresh.InitialCashMinor;s.CashMinor=fresh.CashMinor;s.PrincipalMinor=fresh.PrincipalMinor;s.PrincipalAtOpenMinor=fresh.PrincipalAtOpenMinor;s.PrincipalRepaidMinor=0;s.InterestDueMinor=fresh.InterestDueMinor;s.InterestPaidMinor=0;
                s.DayNumber=1;s.Phase=DayPhase.DAY_OPEN;s.TicketsPurchasedToday=0;s.SettledTicketCount=0;s.LifetimeEffectiveTickets=lifetime;s.LifetimeEffectiveAtOpen=lifetime;s.EconomicCounter=0;s.ChallengeCounter=0;s.ShopCounter=fresh.ShopCounter;
                s.Tickets=fresh.Tickets;s.Stock=fresh.Stock;s.Tools=fresh.Tools;s.NextToolIds=fresh.NextToolIds;s.Drawers=fresh.Drawers;s.ToolCounters=fresh.ToolCounters;s.Loans=fresh.Loans;s.Contacts=fresh.Contacts;s.Settlements=fresh.Settlements;s.Ledger=fresh.Ledger;s.PhoneEvents=fresh.PhoneEvents;s.ConsumableBatch=fresh.ConsumableBatch;s.Ad=null;s.AdSuccessesToday=0;s.SettledCountAtLastAdSuccess=0;s.FixtureBaseSettlements=0;s.AdEvents=fresh.AdEvents;s.FakeShownRequests=fresh.FakeShownRequests;s.DiagnosticChallengeArrangements=fresh.DiagnosticChallengeArrangements;s.ClaimBuyIntents=fresh.ClaimBuyIntents;s.FirstLaunchElapsedSeconds=0;
                return new CommandReceipt{Kind="RESTART_DAY",TicketId=newRunId,CashDeltaMinor=0};
            });
        }
    }
}

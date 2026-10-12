using System;
using System.IO;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Persistence;
using NUnit.Framework;
namespace Lottery.G3.EditMode.Tests
{
    public sealed class DayScenarioTests
    {
        string path; FileStateStore store; DayGameService game; int sequence;
        [SetUp]public void Start(){path=Path.Combine(Path.GetTempPath(),"g3-day-scenario-"+Guid.NewGuid().ToString("N"));Open();}
        [TearDown]public void End(){store?.Dispose();if(Directory.Exists(path))Directory.Delete(path,true);}
        void Open(){store=new FileStateStore(path,RunFactory.CreateDiagnostic("g3-day-qafixture-001"));game=new DayGameService(store);}
        string Cmd()=>"scenario-"+(++sequence);long Rev=>game.Snapshot.Revision;string Ticket=>game.Snapshot.CurrentTicket.Id;
        void Ok(CommandResult result,long cash){Assert.That(result.Success,Is.True,result.Code);Assert.That(result.State.CashMinor,Is.EqualTo(cash));StateInvariants.Validate(result.State);}
        void Buy(string kind,long cash){Ok(game.BuyTicket(kind,-1,Cmd(),Rev),cash);}
        void Reveal(long cash){Ok(game.QuickReveal(Ticket,Cmd(),Rev),cash);}
        void Stock(string item,long cash){Ok(game.BuyStock("g3-day-qafixture-001:day1:"+item,"",Cmd(),Rev),cash);}
        void Reload(){string hash=store.ConfirmedHash;store.Dispose();Open();Assert.That(store.ConfirmedHash,Is.EqualTo(hash));}
        [Test]public void ReviewedDiagnosticTwelveTicketsProduceExactOneDayLedger()
        {
            Buy("number",29000);string t1=Ticket;
            Ok(game.ApplyCellScratch(t1,new[]{new CellStroke(0,.1,.1,.5,.5,true,.08,.1)},Cmd(),Rev),29000);
            byte[] mask=game.Snapshot.CurrentTicket.Scratch.ToBytes();Stock("small_prize_box",23000);Ok(game.EquipTool("small_prize_box",0,Cmd(),Rev),23000);
            Assert.That(game.Snapshot.CurrentTicket.ConfigurationSnapshot,Is.Empty);Assert.That(game.Snapshot.CurrentTicket.Scratch.ToBytes(),Is.EqualTo(mask));Reload();Reveal(23000);
            Assert.That(game.Snapshot.CurrentTicket.RawPrizeMinor,Is.EqualTo(5000));Stock("copy_paper",20000);Ok(game.UpgradeTool("small_prize_box",Cmd(),Rev),11000);
            Ok(game.UseConsumable(t1,0,new int[0],Cmd(),Rev),11000);Assert.That(game.Snapshot.CurrentTicket.CopyMinor,Is.EqualTo(5000));
            long claimRev=Rev;string claimId=Cmd();Ok(game.Claim(t1,claimId,claimRev),21000);string claimHash=store.ConfirmedHash;Ok(game.Claim(t1,claimId,claimRev),21000);Assert.That(store.ConfirmedHash,Is.EqualTo(claimHash));
            Buy("number",20000);Assert.That(game.Snapshot.CurrentTicket.ConfigurationSnapshot.Single().Level,Is.EqualTo(2));Reveal(20000);Ok(game.UpgradeTool("small_prize_box",Cmd(),Rev),6500);Ok(game.Claim(Ticket,Cmd(),Rev),8200);
            Assert.That(game.Snapshot.Settlements.Last().Entries.Single(x=>x.Source=="small_prize_box").AmountMinor,Is.EqualTo(700));
            Buy("challenge",7200);Ok(game.SelectChallengeCell(Ticket,0,Cmd(),Rev),7200);Reload();Assert.That(game.Snapshot.CurrentTicket.SelectedCell,Is.EqualTo(0));Reveal(7200);
            Stock("inspection_lamp",3200);Ok(game.EquipTool("inspection_lamp",1,Cmd(),Rev),3200);
            Assert.That(game.BuyStock("g3-day-qafixture-001:day1:large_prize_stamp","",Cmd(),Rev).Code,Is.EqualTo("INSUFFICIENT_CASH"));
            Assert.That(game.UseLamp(Ticket,2,Cmd(),Rev).Code,Is.EqualTo("LAMP_NOT_IN_CURRENT_SNAPSHOT"));
            Ok(game.SelectChallengeCell(Ticket,1,Cmd(),Rev),3200);Reveal(3200);Ok(game.Claim(Ticket,Cmd(),Rev),5200);
            Buy("challenge",4200);Ok(game.UseLamp(Ticket,2,Cmd(),Rev),4200);Assert.That(game.Snapshot.CurrentTicket.PeekedCells[2],Is.True);Assert.That(game.Snapshot.CurrentTicket.RevealedCells.Any(x=>x),Is.False);
            Assert.That(game.UseLamp(Ticket,3,Cmd(),Rev).Code,Is.EqualTo("INFORMATION_SOURCE_USED"));Ok(game.SelectChallengeCell(Ticket,2,Cmd(),Rev),4200);Reload();Reveal(4200);Assert.That(game.Snapshot.CurrentTicket.Busted,Is.True);Ok(game.Claim(Ticket,Cmd(),Rev),4200);
            long[] buys={3200,2200,4700,3700,7700,6700,7700,11700};long[] claims={3200,5700,4700,8700,7700,8700,12700,11700};
            for(int i=0;i<8;i++){Buy("number",buys[i]);Reveal(buys[i]);Ok(game.Claim(Ticket,Cmd(),Rev),claims[i]);}
            Assert.That(game.Snapshot.Phase,Is.EqualTo(DayPhase.CLOSING_PREP));Assert.That(game.BuyNumberTicket(Cmd(),Rev).Code,Is.EqualTo("DAY_LIMIT"));
            Stock("large_prize_stamp",4200);Ok(game.EquipTool("large_prize_stamp",2,Cmd(),Rev),4200);Ok(game.RepayPrincipal(3000,Cmd(),Rev),1200);
            Assert.That(game.PreviewNightBill().InterestUnpaidMinor,Is.EqualTo(1500));Ok(game.EnterNightBill(Cmd(),Rev),1200);Assert.That(game.PreviewNightBill().ShortfallMinor,Is.EqualTo(300));
            Assert.That(game.PayNightBill(false,Cmd(),Rev).Code,Is.EqualTo("INSUFFICIENT_CASH"));Assert.That(game.Snapshot.Phase,Is.EqualTo(DayPhase.NIGHT_BILL));
            Ok(game.Borrow("mother",10000,Cmd(),Rev),11200);Assert.That(game.Borrow("mother",50000,Cmd(),Rev).Code,Is.EqualTo("LOAN_LIMIT"));Ok(game.RepayLoan("mother",5000,Cmd(),Rev),6200);
            string pay=Cmd();long payRev=Rev;Ok(game.PayNightBill(false,pay,payRev),4700);string finalHash=store.ConfirmedHash;Ok(game.PayNightBill(false,pay,payRev),4700);Reload();Assert.That(store.ConfirmedHash,Is.EqualTo(finalHash));
            var s=game.Snapshot;Assert.That(s.PrincipalMinor,Is.EqualTo(297000));Assert.That(s.InterestPaidMinor,Is.EqualTo(1500));Assert.That(game.PreviewNightBill().NextDayInterestMinor,Is.EqualTo(1485));
            Assert.That(s.Loans.Single().RemainingMinor,Is.EqualTo(5000));Assert.That(s.Loans.Single().DueNight,Is.EqualTo(7));Assert.That(LoanRules.RemainingLimit(s,"mother"),Is.EqualTo(40000));
            Assert.That(s.Settlements.Select(x=>x.TotalMinor),Is.EqualTo(new long[]{10000,1700,2000,0,0,3500,0,5000,0,2000,5000,0}));
            Assert.That(s.Settlements.Sum(x=>x.TotalMinor),Is.EqualTo(29200));Assert.That(s.Ledger.Count,Is.EqualTo(29));Assert.That(s.LifetimeEffectiveTickets,Is.EqualTo(12));Assert.That(s.EconomicCounter,Is.EqualTo(10));
            Assert.That(s.DayNumber,Is.EqualTo(1));Assert.That(s.Phase,Is.EqualTo(DayPhase.DAY_COMPLETE));Assert.That(s.Stock.All(x=>x.Quantity==0),Is.True);Assert.That(s.Ad,Is.Null);
            Assert.That(game.BuyNumberTicket(Cmd(),Rev).Code,Is.EqualTo("G3_DAY_BOUNDARY"));
        }
    }
}

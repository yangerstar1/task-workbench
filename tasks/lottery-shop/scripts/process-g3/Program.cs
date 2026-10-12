// Genuine Linux/.NET SIGKILL probe. These marked fixtures are not Unity/device input.
using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using Lottery.G3.Core;
using Lottery.G3.Persistence;
static class Program
{
    const string Attempt="kill-attempt";
    static string check="ARGUMENTS";
    static readonly string[] Scenarios={"challenge","consumable","replacement","borrow","repay","night"};
    static int Main(string[] args)
    {
        try {
            if(args.Length!=4 || !Scenarios.Contains(args[1])) throw new InvalidOperationException();
            string mode=args[0],scenario=args[1],point=args[2],directory=args[3];
            if(mode=="prepare") Prepare(scenario,directory);
            else if(mode=="crash") {
                check="CRASH_APPLY";
                using(var store=new FileStateStore(Path.Combine(directory,"actual"),Initial(scenario),new PauseAt(point,Path.Combine(directory,"ready"))))
                    MustCommit(Apply(scenario,store,store.Read().Revision));
                check="KILL_POINT_NOT_REACHED";throw new InvalidOperationException();
            } else if(mode=="verify") Verify(scenario,point,directory);
            else throw new InvalidOperationException();
            return 0;
        } catch(Exception e) { Console.Error.WriteLine("G3_PROBE_ERROR "+check+" "+e.GetType().Name);return 1; }
    }
    static RunState Initial(string scenario) => scenario=="replacement" ? RunFactory.CreateInventoryBoundaryFixture("g3-process-"+scenario) : RunFactory.CreateDiagnostic("g3-process-"+scenario);
    static string Hash(RunState state) => StateCodec.HashBytes(StateCodec.SerializeCanonical(state));
    static void MustCommit(CommandResult result) { if(!result.Success) throw new InvalidOperationException(); }
    static void Setup(string scenario,FileStateStore store)
    {
        check="SETUP";var svc=new DayGameService(store);
        if(scenario=="challenge") MustCommit(svc.BuyChallengeTicket("setup-buy",store.Read().Revision));
        if(scenario=="consumable") {
            MustCommit(svc.BuyNumberTicket("setup-buy",store.Read().Revision));
            var stock=store.Read().Stock.Single(x=>x.ItemId=="copy_paper");
            MustCommit(svc.BuyStock(stock.StockId,"","setup-paper",store.Read().Revision));
            MustCommit(svc.QuickReveal(store.Read().CurrentTicket.Id,"setup-reveal",store.Read().Revision));
            if(store.Read().CurrentTicket.RawPrizeMinor!=5000 || store.Read().CashMinor!=26000) throw new InvalidOperationException();
        }
        if(scenario=="replacement" || scenario=="repay") MustCommit(svc.Borrow("mother",scenario=="replacement"?20000:10000,"setup-borrow",store.Read().Revision));
        if(scenario=="night") {
            MustCommit(svc.BeginClosing("setup-close",store.Read().Revision));
            MustCommit(svc.EnterNightBill("setup-bill",store.Read().Revision));
        }
    }
    static CommandResult Apply(string scenario,FileStateStore store,long revision)
    {
        var svc=new DayGameService(store);var state=store.Read();
        if(scenario=="challenge") return svc.SelectChallengeCell(state.CurrentTicket.Id,0,Attempt,revision);
        if(scenario=="consumable") return svc.UseConsumable(state.CurrentTicket.Id,0,new int[0],Attempt,revision);
        if(scenario=="replacement") return svc.BuyStock(state.Stock.Single(x=>x.ItemId=="alternating_stamp").StockId,"loss_mat",Attempt,revision);
        if(scenario=="borrow") return svc.Borrow("mother",10000,Attempt,revision);
        if(scenario=="repay") return svc.RepayLoan("mother",5000,Attempt,revision);
        return svc.PayNightBill(false,Attempt,revision);
    }
    static void Prepare(string scenario,string directory)
    {
        check="PREPARE_DIRECTORY";if(Directory.Exists(directory)) throw new InvalidOperationException();Directory.CreateDirectory(directory);
        string before,expected;
        using(var store=new FileStateStore(Path.Combine(directory,"actual"),Initial(scenario))) {Setup(scenario,store);before=Hash(store.Read());}
        using(var store=new FileStateStore(Path.Combine(directory,"expected"),Initial(scenario))) {
            Setup(scenario,store);check="PREPARE_EQUAL";if(Hash(store.Read())!=before) throw new InvalidOperationException();
            check="PREPARE_APPLY";MustCommit(Apply(scenario,store,store.Read().Revision));AssertIndependent(scenario,store.Read());expected=Hash(store.Read());
        }
        File.WriteAllText(Path.Combine(directory,"expected.json"),JsonSerializer.Serialize(new {before,expected}));
    }
    static object Observe(RunState s) => new {
        cashMinor=s.CashMinor,principalMinor=s.PrincipalMinor,interestDueMinor=s.InterestDueMinor,interestPaidMinor=s.InterestPaidMinor,
        motherBorrowedMinor=s.Contacts.Single(x=>x.ContactId=="mother").BorrowedLifetimeMinor,
        motherOutstandingMinor=s.Loans.Where(x=>x.ContactId=="mother").Sum(x=>x.RemainingMinor),
        motherLoanCount=s.Loans.Count(x=>x.ContactId=="mother"),motherDueNight=s.Loans.Where(x=>x.ContactId=="mother").Select(x=>x.DueNight).DefaultIfEmpty(0).Max(),
        toolCount=s.Tools.Count,drawerCount=s.Drawers.Count(x=>x!=null),phase=s.Phase.ToString(),
        selectedCell=s.CurrentTicket==null ? -1 : s.CurrentTicket.SelectedCell,
        safeCount=s.CurrentTicket==null ? 0 : s.CurrentTicket.SafeCount,
        copyMinor=s.CurrentTicket==null ? 0 : s.CurrentTicket.CopyMinor,
        fixtureLabel=s.FixtureLabel
    };
    static void AssertIndependent(string scenario,RunState s)
    {
        check="INDEPENDENT_INVARIANTS";StateInvariants.Validate(s);
        int commands=scenario=="borrow"?1:scenario=="consumable"?4:scenario=="night"?3:2;
        if(s.Commands.Count!=commands)throw new InvalidOperationException();
        long cash=scenario=="challenge"?29000:scenario=="consumable"?26000:scenario=="replacement"?8000:scenario=="borrow"?40000:scenario=="repay"?35000:28500;
        if(s.CashMinor!=cash || s.PrincipalMinor!=300000 || s.InterestDueMinor!=1500 || s.InterestPaidMinor!=(scenario=="night"?1500:0)) throw new InvalidOperationException();
        long borrowed=s.Contacts.Single(x=>x.ContactId=="mother").BorrowedLifetimeMinor;
        long outstanding=s.Loans.Where(x=>x.ContactId=="mother").Sum(x=>x.RemainingMinor);
        if(borrowed!=(scenario=="replacement"?20000:(scenario=="borrow"||scenario=="repay")?10000:0) || outstanding!=(scenario=="repay"?5000:borrowed)) throw new InvalidOperationException();
        if(s.Loans.Count(x=>x.ContactId=="mother")!=(borrowed>0?1:0) || s.Loans.Any(x=>x.ContactId=="mother"&&x.DueNight!=7))throw new InvalidOperationException();
        if(scenario=="challenge" && (s.CurrentTicket.SelectedCell!=0 || s.CurrentTicket.SelectionId=="" || s.CurrentTicket.SafeCount!=0 || s.CurrentTicket.RevealedCells.Any(x=>x) || s.CurrentTicket.Scratch.RevealedCellCount!=0)) throw new InvalidOperationException();
        if(scenario=="consumable" && (s.CurrentTicket.CopyMinor!=5000 || s.CurrentTicket.ConsumableCostMinor!=3000 || s.CurrentTicket.UsedConsumableTypes.Count!=1 || s.CurrentTicket.UsedConsumableTypes[0]!="copy_paper" || s.Drawers.Any(x=>x!=null) || s.Stock.Single(x=>x.ItemId=="copy_paper").Quantity!=0 || s.CurrentTicket.Phase!=TicketPhase.REVEALED_UNCLAIMED)) throw new InvalidOperationException();
        if(scenario=="replacement" && (s.Tools.Count!=6 || s.Tools.Any(x=>x.ItemId=="loss_mat") || s.Tools.Count(x=>x.ItemId=="alternating_stamp")!=1 || s.Stock.Single(x=>x.ItemId=="alternating_stamp").Quantity!=0 || s.FixtureLabel!="SYNTHETIC_INVENTORY_BOUNDARY_FIXTURE")) throw new InvalidOperationException();
        if(scenario=="night" && (s.Phase!=DayPhase.DAY_COMPLETE || s.DayNumber!=1)) throw new InvalidOperationException();
    }
    static void Verify(string scenario,string point,string directory)
    {
        using(var doc=JsonDocument.Parse(File.ReadAllText(Path.Combine(directory,"expected.json"))))
        using(var store=new FileStateStore(Path.Combine(directory,"actual"),Initial(scenario))) {
            check="RECOVERY_BOUNDARY";
            string before=doc.RootElement.GetProperty("before").GetString(),expected=doc.RootElement.GetProperty("expected").GetString();
            var recovered=store.Recover(Attempt);bool published=point=="AfterPublish"||point=="BeforeResponse";string recoveredHash=Hash(store.Read());
            if(recovered.CommitStatus!=(published?CommitStatus.COMMITTED:CommitStatus.PROVEN_NOT_COMMITTED) || recoveredHash!=(published?expected:before) || !store.CanMutate) throw new InvalidOperationException();
            check="RECOVERY_REPLAY";MustCommit(Apply(scenario,store,store.Read().Revision));string finalHash=Hash(store.Read());
            check="STALE_REPLAY";MustCommit(Apply(scenario,store,-999));var state=store.Read();
            check="EXACTLY_ONCE";if(Hash(state)!=finalHash || finalHash!=expected || state.Commands.Count(c=>c.CommandId==Attempt)!=1) throw new InvalidOperationException();
            AssertIndependent(scenario,state);check="RESULT_WRITE";
            File.WriteAllText(Path.Combine(directory,"result.json"),JsonSerializer.Serialize(new {status="PASS",scenario,point,recoveryStatus=recovered.CommitStatus.ToString(),beforeHash=before,expectedHash=expected,recoveredHash,finalHash,finalCashMinor=state.CashMinor,finalCommands=state.Commands.Count,attemptCommandOccurrences=1,staleRevisionReplayUnchanged=true,observation=Observe(state)}));
        }
    }
    sealed class PauseAt:IStoreFaultInjector {
        readonly StoreFaultPoint target;readonly string marker;
        public PauseAt(string point,string marker) {target=(StoreFaultPoint)Enum.Parse(typeof(StoreFaultPoint),point);this.marker=marker;}
        public void OnPoint(StoreFaultPoint point) {
            if(point!=target)return;
            File.WriteAllText(marker,point.ToString());while(true)Thread.Sleep(100);
        }
    }
}

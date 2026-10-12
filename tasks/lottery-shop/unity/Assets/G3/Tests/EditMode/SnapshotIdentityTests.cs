using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Persistence;
using NUnit.Framework;
namespace Lottery.G3.EditMode.Tests
{
    // Candidate 002 regressions. These call the production service/store; no UI projection is assumed.
    public sealed class SnapshotIdentityTests
    {
        string root; readonly List<FileStateStore> stores=new List<FileStateStore>(); int sequence;
        [SetUp]public void Start(){root=Path.Combine(Path.GetTempPath(),"g3-snapshot-identity-"+Guid.NewGuid().ToString("N"));}
        [TearDown]public void End(){foreach(var store in stores)store.Dispose();if(Directory.Exists(root))Directory.Delete(root,true);}
        DayGameService Open(string name="snapshot")
        {var store=new FileStateStore(Path.Combine(root,name),RunFactory.CreateDiagnostic("A"));stores.Add(store);Assert.That(store.CanMutate,Is.True);return new DayGameService(store);}
        string Cmd()=>"identity-"+(++sequence);
        static void Ok(CommandResult result){Assert.That(result.Success,Is.True,result.Code);StateInvariants.Validate(result.State);}
        void BuyTool(DayGameService g,string item){Ok(g.BuyStock(g.Snapshot.Stock.Single(x=>x.ItemId==item).StockId,"",Cmd(),g.Snapshot.Revision));}
        void Close(DayGameService g){Ok(g.BeginClosing(Cmd(),g.Snapshot.Revision));Ok(g.EnterNightBill(Cmd(),g.Snapshot.Revision));Ok(g.PayNightBill(false,Cmd(),g.Snapshot.Revision));}
        void Claim(DayGameService g){string t=g.Snapshot.CurrentTicket.Id;Ok(g.QuickReveal(t,Cmd(),g.Snapshot.Revision));Ok(g.Claim(t,Cmd(),g.Snapshot.Revision));}
        static void Snapshot(RunState s,params string[] expected)
        {Assert.That(s.CurrentTicket.ConfigurationSnapshot.OrderBy(x=>x.TableSlot).Select(x=>x.TableSlot+":"+x.ItemId+":"+x.Level),Is.EqualTo(expected));}
        [Test]public void EmptyCurrentSnapshotNeverAcquiresNextTicketTools()
        {
            var g=Open();Ok(g.BuyNumberTicket(Cmd(),0));BuyTool(g,"small_prize_box");Ok(g.EquipTool("small_prize_box",2,Cmd(),g.Snapshot.Revision));
            Snapshot(g.Snapshot);Assert.That(g.Snapshot.NextToolIds,Is.EqualTo(new[]{"","","small_prize_box"}));
            Claim(g);Ok(g.BuyNumberTicket(Cmd(),g.Snapshot.Revision));Snapshot(g.Snapshot,"2:small_prize_box:1");
        }
        [Test]public void SparseSlotAndOldLevelSurviveUpgradeSwapNewToolAndColdRecovery()
        {
            var g=Open();BuyTool(g,"small_prize_box");Ok(g.EquipTool("small_prize_box",2,Cmd(),g.Snapshot.Revision));Ok(g.BuyNumberTicket(Cmd(),g.Snapshot.Revision));
            Snapshot(g.Snapshot,"2:small_prize_box:1");Ok(g.UpgradeTool("small_prize_box",Cmd(),g.Snapshot.Revision));Ok(g.EquipTool("small_prize_box",0,Cmd(),g.Snapshot.Revision));BuyTool(g,"inspection_lamp");Ok(g.EquipTool("inspection_lamp",1,Cmd(),g.Snapshot.Revision));
            Snapshot(g.Snapshot,"2:small_prize_box:1");Assert.That(g.Snapshot.NextToolIds,Is.EqualTo(new[]{"small_prize_box","inspection_lamp",""}));
            string before=StateCodec.ComputeHash(g.Snapshot);g.Dispose();g=Open();Assert.That(StateCodec.ComputeHash(g.Snapshot),Is.EqualTo(before));Snapshot(g.Snapshot,"2:small_prize_box:1");
            Claim(g);Ok(g.BuyChallengeTicket(Cmd(),g.Snapshot.Revision));Snapshot(g.Snapshot,"0:small_prize_box:2","1:inspection_lamp:1");
        }
        [Test]public void TwoSparseSlotsRemainDistinctWhenNextArrangementSwapsThem()
        {
            var g=Open();BuyTool(g,"small_prize_box");BuyTool(g,"inspection_lamp");Ok(g.EquipTool("small_prize_box",0,Cmd(),g.Snapshot.Revision));Ok(g.EquipTool("inspection_lamp",2,Cmd(),g.Snapshot.Revision));Ok(g.BuyChallengeTicket(Cmd(),g.Snapshot.Revision));
            Ok(g.EquipTool("inspection_lamp",0,Cmd(),g.Snapshot.Revision));Snapshot(g.Snapshot,"0:small_prize_box:1","2:inspection_lamp:1");Assert.That(g.Snapshot.NextToolIds,Is.EqualTo(new[]{"inspection_lamp","","small_prize_box"}));
            g.Dispose();g=Open();Snapshot(g.Snapshot,"0:small_prize_box:1","2:inspection_lamp:1");
        }
        [Test]public void SnapshotSlotsAreHashBoundDetachedAndRejectDuplicateOrOutOfRange()
        {
            var g=Open();BuyTool(g,"small_prize_box");BuyTool(g,"inspection_lamp");Ok(g.EquipTool("small_prize_box",0,Cmd(),g.Snapshot.Revision));Ok(g.EquipTool("inspection_lamp",2,Cmd(),g.Snapshot.Revision));Ok(g.BuyNumberTicket(Cmd(),g.Snapshot.Revision));
            string hash=StateCodec.ComputeHash(g.Snapshot);var s=g.Snapshot;s.CurrentTicket.ConfigurationSnapshot[0].TableSlot=1;Assert.That(StateCodec.ComputeHash(s),Is.Not.EqualTo(hash));Assert.That(StateCodec.ComputeHash(g.Snapshot),Is.EqualTo(hash));
            s=g.Snapshot;s.CurrentTicket.ConfigurationSnapshot[1].TableSlot=0;Assert.Throws<InvalidOperationException>(()=>StateInvariants.Validate(s));
            s=g.Snapshot;s.CurrentTicket.ConfigurationSnapshot[0].TableSlot=3;Assert.Throws<InvalidOperationException>(()=>StateInvariants.Validate(s));
        }
        [Test]public void RestartCannotReuseOriginalRunIdentityAfterItsPurchasedStockWasArchived()
        {
            var g=Open();BuyTool(g,"small_prize_box");Close(g);string restartId=Cmd();long revision=g.Snapshot.Revision;Ok(g.RestartDay("B","seed-B",restartId,revision));
            string after=StateCodec.ComputeHash(g.Snapshot);Ok(g.RestartDay("B","seed-B",restartId,revision));Assert.That(StateCodec.ComputeHash(g.Snapshot),Is.EqualTo(after));Close(g);
            string before=StateCodec.ComputeHash(g.Snapshot);CommandResult result=null;Assert.DoesNotThrow(()=>result=g.RestartDay("A","new-seed-for-A",Cmd(),g.Snapshot.Revision));
            Assert.That(result.Code,Is.EqualTo("RUN_ID_REUSED"));Assert.That(result.CommitStatus,Is.EqualTo(CommitStatus.PROVEN_NOT_COMMITTED));Assert.That(StateCodec.ComputeHash(g.Snapshot),Is.EqualTo(before));
            Assert.That(g.Snapshot.UsedRunIds,Is.EqualTo(new[]{"A","B"}));Ok(g.RestartDay("C","seed-C",Cmd(),g.Snapshot.Revision));Assert.That(g.Snapshot.UsedRunIds,Is.EqualTo(new[]{"A","B","C"}));
        }
        [Test]public void CompleteRunIdentityHistorySurvivesColdRecoveryAndRejectsEveryPriorTarget()
        {
            var g=Open();Close(g);Ok(g.RestartDay("B","seed-B",Cmd(),g.Snapshot.Revision));Close(g);Ok(g.RestartDay("C","seed-C",Cmd(),g.Snapshot.Revision));Close(g);
            string before=StateCodec.ComputeHash(g.Snapshot);g.Dispose();g=Open();Assert.That(StateCodec.ComputeHash(g.Snapshot),Is.EqualTo(before));
            foreach(string id in new[]{"A","B","C"}){CommandResult result=null;Assert.DoesNotThrow(()=>result=g.RestartDay(id,"other-seed",Cmd(),g.Snapshot.Revision));Assert.That(result.Code,Is.EqualTo("RUN_ID_REUSED"));Assert.That(StateCodec.ComputeHash(g.Snapshot),Is.EqualTo(before));}
            Ok(g.RestartDay("D","seed-D",Cmd(),g.Snapshot.Revision));Assert.That(g.Snapshot.CashMinor,Is.EqualTo(30000));Assert.That(g.Snapshot.Stock.All(x=>x.Quantity==1),Is.True);Assert.That(g.Snapshot.UsedRunIds,Is.EqualTo(new[]{"A","B","C","D"}));
        }
        [Test]public void RunHistoryCannotDropDuplicateOrReorderArchivedIdentities()
        {
            var g=Open();Close(g);Ok(g.RestartDay("B","seed-B",Cmd(),g.Snapshot.Revision));Close(g);Ok(g.RestartDay("C","seed-C",Cmd(),g.Snapshot.Revision));
            var s=g.Snapshot;s.UsedRunIds.RemoveAt(0);Assert.Throws<InvalidOperationException>(()=>StateInvariants.Validate(s));
            s=g.Snapshot;s.UsedRunIds[0]="B";Assert.Throws<InvalidOperationException>(()=>StateInvariants.Validate(s));
            s=g.Snapshot;s.UsedRunIds.Reverse();Assert.Throws<InvalidOperationException>(()=>StateInvariants.Validate(s));
        }
    }
}

using System;
using System.Collections.Generic;
using System.Linq;
using Lottery.G2.Core;
namespace Lottery.G3.Core
{
    public static class FixtureAccess
    {
        public static bool Enabled
        {
            get
            {
#if UNITY_EDITOR || DEVELOPMENT_BUILD || LOTTERY_G3_TEST_FIXTURE
                return true;
#else
                return false;
#endif
            }
        }
        public static void Require() { if(!Enabled) throw new InvalidOperationException("G3 diagnostic fixtures require an explicit development/test build"); }
    }
    public static class RunFactory
    {
        public const string DiagnosticLabel="G3_DIAGNOSTIC_VECTOR_NOT_NATURAL";
        public static RunState Create(string runId,string seed)
        {
            if(string.IsNullOrWhiteSpace(runId)||runId.Length>128||runId.Any(char.IsControl)||string.IsNullOrWhiteSpace(seed)||seed.Length>256||seed.Any(char.IsControl))throw new ArgumentException("Invalid run identity");
            var s=new RunState{RunId=runId,Seed=seed};
            s.Contacts.Add(new ContactState{ContactId="mother"});s.Contacts.Add(new ContactState{ContactId="girlfriend"});
            foreach(var t in DayRules.Tools)s.ToolCounters.Add(new ToolCounter{ItemId=t.Id});
            var random=new DeterministicStream(seed,"shop-supply-v1");
            var selected=new HashSet<string>();
            for(int slot=0;slot<3;slot++)
            {
                int roll=slot<2?0:random.Next(1000000);string rarity=DayRules.ShopRarityForSample(roll);
                var pool=DayRules.Tools.Where(t=>t.Rarity==rarity&&!selected.Contains(t.Id)).ToArray();
                if(pool.Length==0)continue; // Empty rarity never upgraded or redistributed.
                var item=pool[random.Next(pool.Length)];selected.Add(item.Id);s.Stock.Add(ToolStock(runId,item.Id));
            }
            var batch=DayRules.ConsumableIds.ToArray();
            for(int i=batch.Length-1;i>0;i--){int j=random.Next(i+1);string tmp=batch[i];batch[i]=batch[j];batch[j]=tmp;}
            s.ConsumableBatch=batch;int qroll=random.Next(1000000);string quality=DayRules.ConsumableQualityForSample(qroll);
            s.Stock.Add(ConsumableStock(runId,batch[0],quality));s.ShopCounter=random.Counter;
            StateInvariants.Validate(s);return s;
        }
        public static RunState CreateDiagnostic(string runId)
        {
            FixtureAccess.Require();var s=Create(runId,"g3-day-scenario-v1-000250");s.FixtureLabel=DiagnosticLabel;
            s.Stock=new List<StockItem>{ToolStock(runId,"small_prize_box"),ToolStock(runId,"inspection_lamp"),ToolStock(runId,"large_prize_stamp"),ConsumableStock(runId,"copy_paper","common")};
            s.ConsumableBatch=new[]{"copy_paper","reveal_film","seal_sticker","boost_coupon"};
            s.DiagnosticChallengeArrangements.Add(new[]{true,true,false,true,true,false,true,true});
            s.DiagnosticChallengeArrangements.Add(new[]{true,true,false,true,true,false,true,true});
            StateInvariants.Validate(s);return s;
        }
        public static RunState CreateConsumableFixture(string runId,string itemId,string quality)
        {
            FixtureAccess.Require();DayRules.ConsumablePrice(itemId,quality);
            var s=Create(runId,"g3-consumable-boundary-v1");s.FixtureLabel="SYNTHETIC_CONSUMABLE_BOUNDARY_FIXTURE";
            s.ConsumableBatch=new[]{itemId}.Concat(DayRules.ConsumableIds.Where(x=>x!=itemId)).ToArray();
            s.Stock=s.Stock.Where(x=>!x.IsConsumable).ToList();s.Stock.Add(ConsumableStock(runId,itemId,quality));
            StateInvariants.Validate(s);return s;
        }
        // Capacity-only initial resource fixture: six initial purchases are debited, not free assets or cash.
        // It does not claim first-day natural attainability (normal daily stock has only three tools).
        public static RunState CreateInventoryBoundaryFixture(string runId)
        {
            FixtureAccess.Require();var s=Create(runId,"g3-inventory-boundary-v1");s.FixtureLabel="SYNTHETIC_INVENTORY_BOUNDARY_FIXTURE";
            var six=DayRules.Tools.Where(t=>t.Rarity=="common").ToArray();
            foreach(var t in six)
            {
                s.Tools.Add(new OwnedTool{ItemId=t.Id,Level=1,InitialPaymentMinor=t.PriceMinor});
                s.CashMinor-=t.PriceMinor;s.Ledger.Add(new LedgerEntry{CommandId="fixture-purchase:"+t.Id,Kind="FIXTURE_PRIOR_PURCHASE",ReferenceId=t.Id,DeltaMinor=-t.PriceMinor,BalanceMinor=s.CashMinor});
            }
            // Six common prices total 2950 coins; remaining 50 is genuine starting cash remainder.
            s.NextToolIds=six.Take(3).Select(t=>t.Id).ToArray();
            s.Stock=new List<StockItem>{ToolStock(runId,"alternating_stamp"),ToolStock(runId,"last_tickets_stamp"),ConsumableStock(runId,s.ConsumableBatch[0],"common")};
            StateInvariants.Validate(s);return s;
        }
        public static StockItem ToolStock(string runId,string id)
        {var t=DayRules.Tool(id);return new StockItem{StockId=runId+":day1:"+id,ItemId=id,Quality=t.Rarity,PriceMinor=t.PriceMinor,Quantity=1};}
        public static StockItem ConsumableStock(string runId,string id,string quality)
        {return new StockItem{StockId=runId+":day1:"+id,ItemId=id,Quality=quality,IsConsumable=true,PriceMinor=DayRules.ConsumablePrice(id,quality),Quantity=1};}
    }
}

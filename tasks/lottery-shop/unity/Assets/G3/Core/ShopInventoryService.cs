using System;
using System.Linq;
namespace Lottery.G3.Core
{
    public sealed partial class DayGameService
    {
        public CommandResult BuyStock(string stockId,string sellToolId,string commandId,long expectedRevision)
        {
            return Execute("BUY_STOCK",commandId,expectedRevision,w=>{w.Write(stockId??"");w.Write(sellToolId??"");},s=>
            {
                RequireShopping(s);var stock=s.Stock.SingleOrDefault(x=>x.StockId==stockId);if(stock==null)throw new RuleViolation("STOCK_NOT_FOUND");
                if(stock.Quantity!=1)throw new RuleViolation("OUT_OF_STOCK");if(AdReservations.StockReserved(s,stockId))throw new RuleViolation("STOCK_RESERVED");
                if(stock.IsConsumable)
                {
                    if(!string.IsNullOrEmpty(sellToolId))throw new RuleViolation("INVALID_REPLACEMENT");RequireCash(s,stock.PriceMinor);
                    int drawer=Array.FindIndex(s.Drawers,x=>x==null);if(drawer>=0&&AdReservations.DrawerReserved(s,drawer))drawer=Enumerable.Range(0,2).Where(i=>s.Drawers[i]==null&&!AdReservations.DrawerReserved(s,i)).DefaultIfEmpty(-1).First();
                    if(drawer<0)throw new RuleViolation("DRAWER_FULL");
                    s.Drawers[drawer]=new DrawerItem{StockId=stock.StockId,ItemId=stock.ItemId,Quality=stock.Quality,PurchasePriceMinor=stock.PriceMinor};
                }
                else
                {
                    if(s.Tools.Any(x=>x.ItemId==stock.ItemId))throw new RuleViolation("ALREADY_OWNED");
                    OwnedTool sale=null;long salePrice=0;
                    if(!string.IsNullOrEmpty(sellToolId)){sale=RequireSellable(s,sellToolId);salePrice=DayRules.Ratio(sale.InitialPaymentMinor,1,2);}
                    if(s.Tools.Count==6&&sale==null)throw new RuleViolation("SELECT_REPLACEMENT");
                    if(checked(s.AvailableCashMinor+salePrice)<stock.PriceMinor)throw new RuleViolation("INSUFFICIENT_CASH");
                    if(sale!=null){RemoveTool(s,sale.ItemId);s.CashMinor=checked(s.CashMinor+salePrice);}
                    s.Tools.Add(new OwnedTool{ItemId=stock.ItemId,Level=1,InitialPaymentMinor=stock.PriceMinor});
                    if(s.Tools.Count-s.NextToolIds.Count(x=>x!="")>3)
                    {int free=Array.IndexOf(s.NextToolIds,"");if(free<0)throw new RuleViolation("TOOL_CAPACITY");s.NextToolIds[free]=stock.ItemId;}
                }
                s.CashMinor-=stock.PriceMinor;stock.Quantity=0;return stock.StockId;
            });
        }
        public CommandResult UpgradeTool(string itemId,string commandId,long expectedRevision)
        {
            return Execute("UPGRADE_TOOL",commandId,expectedRevision,w=>w.Write(itemId??""),s=>
            {RequireShopping(s);var owned=s.Tools.SingleOrDefault(x=>x.ItemId==itemId);if(owned==null)throw new RuleViolation("TOOL_NOT_OWNED");var rule=DayRules.Tool(itemId);
                if(owned.Level>=rule.LevelCap)throw new RuleViolation("MAX_LEVEL");long cost=rule.UpgradePricesMinor[owned.Level-1];RequireCash(s,cost);s.CashMinor-=cost;owned.Level++;return itemId;});
        }
        public CommandResult SellTool(string itemId,string commandId,long expectedRevision)
        {
            return Execute("SELL_TOOL",commandId,expectedRevision,w=>w.Write(itemId??""),s=>
            {RequireStable(s);var owned=RequireSellable(s,itemId);long price=DayRules.Ratio(owned.InitialPaymentMinor,1,2);RemoveTool(s,itemId);s.CashMinor=checked(s.CashMinor+price);return itemId;});
        }
        internal static OwnedTool RequireSellable(RunState s,string id)
        {
            var item=s.Tools.SingleOrDefault(x=>x.ItemId==id);if(item==null)throw new RuleViolation("TOOL_NOT_OWNED");
            if(s.HasUnsettledTicket&&s.CurrentTicket.ConfigurationSnapshot.Any(x=>x.ItemId==id))throw new RuleViolation("CURRENT_TICKET_TOOL_LOCKED");return item;
        }
        static void RemoveTool(RunState s,string id)
        {s.Tools.RemoveAll(x=>x.ItemId==id);for(int i=0;i<3;i++)if(s.NextToolIds[i]==id)s.NextToolIds[i]="";}
        public CommandResult EquipTool(string itemId,int tableSlot,string commandId,long expectedRevision)
        {
            return Execute("EQUIP_TOOL",commandId,expectedRevision,w=>{w.Write(itemId??"");w.Write(tableSlot);},s=>
            {
                RequireShopping(s);if(tableSlot<0||tableSlot>=3||itemId==null)throw new RuleViolation("INVALID_SLOT");
                if(itemId!=""&&!s.Tools.Any(x=>x.ItemId==itemId))throw new RuleViolation("TOOL_NOT_OWNED");
                if(s.NextToolIds[tableSlot]==itemId)throw new RuleViolation("NO_CHANGE");
                int oldSlot=itemId==""?-1:Array.IndexOf(s.NextToolIds,itemId);string displaced=s.NextToolIds[tableSlot];
                s.NextToolIds[tableSlot]=itemId;if(oldSlot>=0)s.NextToolIds[oldSlot]=displaced;
                if(s.Tools.Count-s.NextToolIds.Count(x=>x!="")>3)throw new RuleViolation("RESERVE_FULL");return itemId;
            });
        }
        static DrawerItem RequireDrawer(RunState s,int slot)
        {if(slot<0||slot>=2)throw new RuleViolation("INVALID_DRAWER_SLOT");if(AdReservations.DrawerReserved(s,slot))throw new RuleViolation("DRAWER_RESERVED");return s.Drawers[slot]??throw new RuleViolation("DRAWER_EMPTY");}
        public CommandResult UseLamp(string ticketId,int targetCell,string commandId,long expectedRevision)
        {
            return Execute("USE_LAMP",commandId,expectedRevision,w=>{w.Write(ticketId??"");w.Write(targetCell);},s=>
            {
                var t=RequireActive(s,ticketId);RequireChallengeStable(t);var snap=t.ConfigurationSnapshot.SingleOrDefault(x=>x.ItemId=="inspection_lamp");
                if(snap==null)throw new RuleViolation("LAMP_NOT_IN_CURRENT_SNAPSHOT");if(t.LampUsed||t.InformationSource!="")throw new RuleViolation("INFORMATION_SOURCE_USED");
                var counter=s.ToolCounters.Single(x=>x.ItemId=="inspection_lamp");if(counter.UsedToday>=snap.Level)throw new RuleViolation("LAMP_DAILY_LIMIT");
                if(targetCell<0||targetCell>=8||t.RevealedCells[targetCell])throw new RuleViolation("INVALID_CELL");
                counter.UsedToday++;t.LampUsed=true;t.InformationSource="inspection_lamp";t.PeekedCells[targetCell]=true;return t.Id;
            });
        }
        public CommandResult UseConsumable(string ticketId,int drawerSlot,int[] targetCells,string commandId,long expectedRevision)
        {
            return Execute("USE_CONSUMABLE",commandId,expectedRevision,w=>{w.Write(ticketId??"");w.Write(drawerSlot);w.Write(targetCells==null?-1:targetCells.Length);if(targetCells!=null)foreach(int cell in targetCells)w.Write(cell);},s=>
            {
                var t=RequireActive(s,ticketId);var item=RequireDrawer(s,drawerSlot);int q=DayRules.QualityIndex(item.Quality);
                if(t.UsedConsumableTypes.Contains(item.ItemId))throw new RuleViolation("CONSUMABLE_TYPE_ALREADY_USED");if(t.UsedConsumableTypes.Count>=2)throw new RuleViolation("CONSUMABLE_TYPE_LIMIT");
                if(item.ItemId=="reveal_film")
                {
                    RequireChallengeStable(t);if(t.InformationSource!="")throw new RuleViolation("INFORMATION_SOURCE_USED");int count=Math.Min(q+1,t.RevealedCells.Count(x=>!x));
                    if(targetCells==null||targetCells.Length!=count||targetCells.Distinct().Count()!=count||targetCells.Any(c=>c<0||c>=8||t.RevealedCells[c]))throw new RuleViolation("INVALID_INFORMATION_TARGETS");
                    foreach(int c in targetCells)t.PeekedCells[c]=true;t.InformationSource="reveal_film";
                }
                else
                {
                    if(targetCells!=null&&targetCells.Length!=0)throw new RuleViolation("UNEXPECTED_TARGETS");
                    if(item.ItemId=="seal_sticker")
                    {RequireChallengeStable(t);if(t.SafeCount<1)throw new RuleViolation("NEED_SAFE_CELL");t.ProtectionMinor=Math.Min(DayRules.Ratio(t.RawPrizeMinor,new long[]{1,3,1}[q],new long[]{2,4,1}[q]),new long[]{3000,6000,12000}[q]);}
                    else if(item.ItemId=="copy_paper")
                    {if(t.TicketType!="number"||t.Phase!=TicketPhase.REVEALED_UNCLAIMED||!t.Scratch.IsFullyRevealed)throw new RuleViolation("COPY_REQUIRES_REVEALED_NUMBER");if(t.RawPrizeMinor<=0)throw new RuleViolation("COPY_REQUIRES_POSITIVE_PRIZE");t.CopyMinor=Math.Min(DayRules.Ratio(t.RawPrizeMinor,new long[]{1,3,2}[q],new long[]{1,2,1}[q]),new long[]{10000,15000,20000}[q]);}
                    else if(item.ItemId=="boost_coupon")throw new RuleViolation("BOOST_REQUIRES_NEXT_PURCHASE");else throw new RuleViolation("UNKNOWN_CONSUMABLE");
                }
                t.UsedConsumableTypes.Add(item.ItemId);t.ConsumableUses.Add(new ConsumableUse{ItemId=item.ItemId,Quality=item.Quality,StockId=item.StockId,PurchasePriceMinor=item.PurchasePriceMinor,LockedAmountMinor=item.ItemId=="copy_paper"?t.CopyMinor:item.ItemId=="seal_sticker"?t.ProtectionMinor:0,TargetCells=targetCells==null?new int[0]:(int[])targetCells.Clone()});t.ConsumableCostMinor=checked(t.ConsumableCostMinor+item.PurchasePriceMinor);s.Drawers[drawerSlot]=null;return t.Id;
            });
        }
    }
}

using System;
using System.Globalization;
using System.Linq;
namespace Lottery.G3.Core
{
    public sealed class ToolDefinition
    {
        public string Id, Name, Rarity; public long PriceMinor; public long[] UpgradePricesMinor; public int LevelCap;
        public ToolDefinition(string id,string name,string rarity,long price,long[] upgrades)
        { Id=id; Name=name; Rarity=rarity; PriceMinor=price; UpgradePricesMinor=upgrades; LevelCap=upgrades.Length+1; }
    }
    // Exact, reviewable projection of frozen G1 rules hash. Only initially offerable eight tools.
    public static class DayRules
    {
        public const long TicketPriceMinor=1000, InitialCashMinor=30000, OriginalPrincipalMinor=300000;
        public const int DailyTicketLimit=12;
        public static readonly ToolDefinition[] Tools = {
            new ToolDefinition("small_prize_box","零钱兑奖匣","common",6000,new long[]{9000,13500}),
            new ToolDefinition("ticket_clip","票根夹","common",4500,new long[]{6750,10500}),
            new ToolDefinition("large_prize_stamp","大额兑奖章","common",7500,new long[]{12000,18000}),
            new ToolDefinition("loss_mat","止损垫","common",3000,new long[]{4500,7000}),
            new ToolDefinition("inspection_lamp","检票灯","common",4000,new long[]{6000,9000}),
            new ToolDefinition("cashout_stamp","收手章","common",4500,new long[]{6500,10000}),
            new ToolDefinition("alternating_stamp","双面章","rare",14000,new long[0]),
            new ToolDefinition("last_tickets_stamp","尾票加印章","precious",14000,new long[0])
        };
        public static readonly string[] ConsumableIds={"reveal_film","seal_sticker","copy_paper","boost_coupon"};
        public static readonly string[] Qualities={"common","rare","precious"};
        public static readonly long[] ChallengePrizes={1000,2000,3000,5000,9000,18000};
        public static ToolDefinition Tool(string id) => Tools.FirstOrDefault(t=>t.Id==id) ?? throw new RuleViolation("UNKNOWN_TOOL");
        public static int QualityIndex(string quality) { int i=Array.IndexOf(Qualities,quality); if(i<0) throw new RuleViolation("UNKNOWN_QUALITY"); return i; }
        public static long ConsumablePrice(string id,string quality)
        {
            int q=QualityIndex(quality);
            switch(id) { case "reveal_film":return new long[]{1000,3000,6000}[q]; case "seal_sticker":return new long[]{500,1000,2000}[q]; case "copy_paper":return new long[]{3000,4500,6000}[q]; case "boost_coupon":return new long[]{800,1600,3200}[q]; default:throw new RuleViolation("UNKNOWN_CONSUMABLE"); }
        }
        public static string ConsumableName(string id)
        { switch(id) {case "reveal_film":return "显影片";case "seal_sticker":return "封存贴";case "copy_paper":return "中奖复写纸";case "boost_coupon":return "冲奖券";default:throw new RuleViolation("UNKNOWN_CONSUMABLE");} }
        public static string Money(long minor) => (minor/10m).ToString("0.#",CultureInfo.InvariantCulture);
        public static long Ratio(long value,long numerator,long denominator)
        { if(value<0||numerator<0||denominator<=0)throw new ArgumentOutOfRangeException();return checked((checked(value*numerator)+denominator/2)/denominator); }
        public static long Interest(long principal) => Ratio(principal,1,200);
        public static long PrincipalDue(int day,long cumulativePaid)
        { if(day<1||day>18||cumulativePaid<0)throw new ArgumentOutOfRangeException(); long target=day==6?30000:day==12?150000:day==18?300000:0;return Math.Max(0,target-cumulativePaid); }
        public static long ContactLimit(string id) => id=="mother"?50000:id=="girlfriend"?30000:throw new RuleViolation("UNKNOWN_CONTACT");
        public static int ContactDueOffset(string id) => id=="mother"?6:id=="girlfriend"?3:throw new RuleViolation("UNKNOWN_CONTACT");
    }
}

using System;
using System.Collections.Generic;
using Lottery.G3.Core;

namespace Lottery.G3.Interaction
{
    public enum G3Mode { WALK,TABLE_SCRATCH,CELL_REVEAL,PANEL,COMMITTING,NIGHT_BILL }
    public enum G3Panel { None,Settlement,Tickets,Shop,StockDetail,Inventory,ToolDetail,Drawer,Phone,Contact,CustomAmount,Bill,Rules,Settings,Confirm,InformationTargets,QaEvidence,PhoneAmount,PhoneRequest,PhonePacket,PhoneRecords,PhoneRepay,PhoneOptions }
    public enum G3ActionKind { None,CancelBoost,ResumeNext,CancelNext,Open,Close,Stand,Sit,InspectStock,InspectTool,InspectContact,BuyTicket,Claim,ClaimThenBuy,QuickReveal,BuyStock,Upgrade,Sell,Equip,Remove,UseDrawer,UseLamp,TargetCell,ConfirmTargets,Borrow,RepayLoan,RepayPrincipal,BeginClosing,EnterNight,PayNight,Restart,Retry,Confirm,Cancel,Digit,Backspace,AmountAccept,ToggleQuick,ToggleFlash,ToggleVibration,CopyEvidence,ScrollEvidence,MoveForward,MoveBack,MoveLeft,MoveRight,TurnLeft,TurnRight,ToggleMore,PhoneChoose,PhoneSend,PhoneClaim,PhoneBack,PhoneRecords,PhoneRepay,PhonePage,PhoneCancelRequest,CycleAudioVolume }
    public readonly struct G3Action
    {
        public readonly G3ActionKind Kind;public readonly string Key;public readonly int Slot;public readonly long Amount;
        public G3Action(G3ActionKind kind,string key="",int slot=-1,long amount=0){Kind=kind;Key=key??"";Slot=slot;Amount=amount;}
        public string Id=>Kind+":"+Key+":"+Slot+":"+Amount;
    }
    public sealed class G3Card
    {
        public string Id,Text;public G3Action Action;public bool Enabled=true;
        public G3Card(string id,string text,G3Action action,bool enabled=true){Id=id;Text=text;Action=action;Enabled=enabled;}
    }
    public sealed class G3PanelModel
    {
        public string Title="",Body="";public readonly List<G3Card> Cards=new List<G3Card>();
        public readonly List<G3PhoneMessage> Messages=new List<G3PhoneMessage>();
        public bool Grid,LargeGrid,Evidence;public string Footnote="";
        public void Add(string id,string text,G3Action action,bool enabled=true)=>Cards.Add(new G3Card(id,text,action,enabled));
    }
    public sealed class G3PhoneMessage
    {
        public string Id,Text,Caption;public bool Player,Packet;public G3Action Action;public bool Enabled;
        public G3PhoneMessage(string id,string text,bool player=false,bool packet=false,string caption="",G3Action action=default,bool enabled=false)
        {Id=id;Text=text;Player=player;Packet=packet;Caption=caption;Action=action;Enabled=enabled;}
    }
    public static class G3Text
    {
        public static string Quality(string quality)=>quality=="rare"?"稀有":quality=="precious"?"珍品":"普通";
        public static string Ticket(string type)=>type=="challenge"?"挑战票":"号码票";
        public static string Contact(string id)=>id=="mother"?"妈妈":"女友";
        public static string Tool(string id)=>string.IsNullOrEmpty(id)?"空位":DayRules.Tool(id).Name;
        public static string Money(long amount)=>DayRules.Money(amount);
        public static string Signed(long amount)=>(amount>0?"+":"")+Money(amount);
        public static string ConsumableHint(string id,string q)
        {
            int n=q=="precious"?2:q=="rare"?1:0;
            switch(id)
            {
                case "reveal_film":return "挑战稳定点查看 "+(n+1)+" 格；与检票灯同票二选一";
                case "seal_sticker":return "已有安全格时锁定 "+new[]{"50%","75%","100%"}[n]+" 可收奖，上限 "+new[]{300,600,1200}[n]+"；后续不追涨";
                case "copy_paper":return "号码全揭未领且原奖为正：复制 "+new[]{"100%","150%","200%"}[n]+" 原奖，上限 "+new[]{1000,1500,2000}[n];
                case "boost_coupon":return "下一号码票 "+new[]{2,3,5}[n]+" 次独立原奖取最高；确认买票才扣物";
                default:return "查看具体使用条件后确认";
            }
        }
        public static string ToolHint(string id,int level)
        {
            int l=Math.Max(0,Math.Min(2,level-1));
            switch(id)
            {
                case "small_prize_box":return "号码原奖 0＜P≤票价×2 追加 "+new[]{30,70,150}[l];
                case "ticket_clip":return "每 3 张原始正奖票追加 "+new[]{75,150,300}[l]+"；余格保留";
                case "large_prize_stamp":return "号码原奖 ≥票价×5 追加 "+new[]{"50%","100%","200%"}[l]+"，上限 "+new[]{300,600,1200}[l];
                case "loss_mat":return "原奖为零返票款 "+new[]{"20%","35%","50%"}[l]+"，上限 "+new[]{20,35,50}[l];
                case "inspection_lamp":return "每天 "+level+" 次，指定挑战未揭格看安全/危险；每票一次";
                case "cashout_stamp":return "挑战恰好 2 / 3 格安全主动收手，追加 "+new[]{40,80,150}[l];
                case "alternating_stamp":return "与上张已结算票不同类型且原奖为正，追加 75%，上限 600";
                case "last_tickets_stamp":return "第 10 / 11 / 12 张原奖为正，追加 200%，上限 3000";
                default:return "只按购票时的本张配置生效";
            }
        }
    }
}

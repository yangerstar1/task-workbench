using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Rendering;
using UnityEngine;

namespace Lottery.G3.Interaction
{
    // Sole UI command gateway: every physical/quick entry shares this presenter.
    public sealed class G3Presenter : MonoBehaviour
    {
        DayGameService service;G3SceneView view;RunState confirmed;
        readonly List<CellStroke> strokes=new List<CellStroke>();
        Func<CommandResult> retry;string pendingId;bool unknown;float lastFlush;
        G3Action confirmation,customAction;long confirmationRevision;G3Panel confirmationReturn;
        string selectedStock="",selectedTool="",selectedContact="mother",customAmount="",confirmText="";
        int boostSlot=-1,informationDrawer=-1,informationCount;bool informationLamp,ticketRulesReturn;string boostStockId="",boostRunId="";
        public int SelectedBoostSlot=>boostSlot;
        readonly HashSet<int> informationCells=new HashSet<int>();
        Action afterCommit;
        public G3InputRouter Router {get;set;}
        public DayGameService Service=>service;
        public RunState Snapshot=>confirmed??(confirmed=service.Snapshot);
        public G3SceneView View=>view;
        public G3Panel Panel {get;private set;}
        public bool Walking {get;private set;}
        public bool IsCommitting=>retry!=null||!service.CanMutate||Snapshot.RecoveryRequired;
        public bool QuickEnabled {get;private set;}=true;
        public bool ReduceFlash {get;private set;}=true;
        public bool Vibration {get;private set;}
        public string Status {get;private set;}="第 1 天开店。所有钱款、刮痕和选择确认保存后才显示。";
        public G3Mode Mode=>IsCommitting?G3Mode.COMMITTING:Panel!=G3Panel.None?(Panel==G3Panel.Bill?G3Mode.NIGHT_BILL:G3Mode.PANEL):Walking?G3Mode.WALK:Snapshot.CurrentTicket?.SelectedCell>=0?G3Mode.CELL_REVEAL:G3Mode.TABLE_SCRATCH;
        public bool CanScratch=>!IsCommitting&&!Walking&&Panel==G3Panel.None&&Snapshot.CurrentTicket?.Phase==TicketPhase.ACTIVE;
        public void Initialize(DayGameService core,G3SceneView scene){service=core;view=scene;if(PendingIntent()!=null){Panel=G3Panel.Tickets;Status="上张已收下，下张购买尚未完成；请按原意图继续或取消。";}Refresh();}
        ClaimBuyIntent PendingIntent()=>Snapshot.ClaimBuyIntents.LastOrDefault(x=>!x.Cancelled&&!Snapshot.Commands.Any(c=>c.CommandId==x.BuyCommandId));
        void Update(){if(service!=null&&strokes.Count>0&&Time.unscaledTime-lastFlush>=.075f)FlushScratch();}
        public void QueueBrush(CellBrushProposal proposal)
        {
            if(!CanScratch)return;
            var t=Snapshot.CurrentTicket;if(t.TicketType=="challenge"&&t.SelectedCell!=proposal.CoreIndex)return;
            strokes.Add(new CellStroke(proposal.CoreIndex,proposal.FromLocal.U,proposal.FromLocal.V,proposal.ToLocal.U,proposal.ToLocal.V,proposal.HasFrom,proposal.RadiusLocalU,proposal.RadiusLocalV));
            if(strokes.Count>=64)FlushScratch();
        }
        public void FlushScratch()
        {
            if(strokes.Count==0||IsCommitting)return;var t=Snapshot.CurrentTicket;
            if(t==null){strokes.Clear();return;}var batch=strokes.ToArray();strokes.Clear();lastFlush=Time.unscaledTime;
            Run((id,rev)=>service.ApplyCellScratch(t.Id,batch,id,rev));
        }
        public void SelectCell(int core)
        {
            if(IsCommitting||Panel!=G3Panel.None||Walking)return;
            FlushScratch();if(IsCommitting)return;
            var t=Snapshot.CurrentTicket;if(t==null||t.TicketType!="challenge"||t.Phase!=TicketPhase.ACTIVE||t.SelectedCell>=0)return;
            Run((id,rev)=>service.SelectChallengeCell(t.Id,core,id,rev));
        }
        public void OpenPanel(G3Panel panel)
        {
            ticketRulesReturn=Panel==G3Panel.Tickets&&panel==G3Panel.Rules;
            FlushScratch();if(IsCommitting)return;Router?.ReleaseCapture();
            var t=Snapshot.CurrentTicket;
            if(t!=null&&t.TicketType=="challenge"&&t.SelectedCell>=0)
            {
                // Opening a panel completes only the already-committed cell.
                // It never chooses another cell or abandons the commitment.
                afterCommit=()=>{Panel=panel;Refresh();};Run((id,rev)=>service.QuickReveal(t.Id,id,rev));return;
            }
            Panel=panel;Refresh();
        }
        public void Execute(G3Action a)
        {
            if(a.Kind==G3ActionKind.Retry){RetryOrRecover();return;}
            if(a.Kind==G3ActionKind.Close||a.Kind==G3ActionKind.Cancel){ClosePanel();return;}
            if(IsCommitting)return;
            if(a.Kind==G3ActionKind.CancelBoost){ClearBoost();Status="已取消冲奖预选，耗材未消耗。";Refresh();return;}
            if(a.Kind==G3ActionKind.Open){OpenPanel((G3Panel)a.Slot);return;}
            if(a.Kind==G3ActionKind.Stand){OpenStable(()=>{Walking=true;view.SetWalking(true);Panel=G3Panel.None;Refresh();});return;}
            if(a.Kind==G3ActionKind.Sit){Walking=false;view.SetWalking(false);Panel=G3Panel.None;Router?.ReleaseCapture();Refresh();return;}
            if(a.Kind==G3ActionKind.InspectStock){selectedStock=a.Key;Panel=G3Panel.StockDetail;Refresh();return;}
            if(a.Kind==G3ActionKind.InspectTool){selectedTool=a.Key;Panel=G3Panel.ToolDetail;Refresh();return;}
            if(a.Kind==G3ActionKind.InspectContact){selectedContact=a.Key;Panel=G3Panel.Contact;Refresh();return;}
            if(a.Kind==G3ActionKind.TargetCell){if(informationCells.Contains(a.Slot))informationCells.Remove(a.Slot);else if(informationCells.Count<informationCount)informationCells.Add(a.Slot);Refresh();return;}
            if(a.Kind==G3ActionKind.ConfirmTargets){ConfirmInformation();return;}
            if(a.Kind==G3ActionKind.UseLamp){BeginInformation(true,-1);return;}
            if(a.Kind==G3ActionKind.UseDrawer){UseDrawer(a.Slot);return;}
            if(a.Kind==G3ActionKind.Digit){if(customAmount.Length<10&&!(a.Key=="."&&customAmount.Contains(".")))customAmount+=a.Key;Refresh();return;}
            if(a.Kind==G3ActionKind.Backspace){if(customAmount.Length>0)customAmount=customAmount.Substring(0,customAmount.Length-1);Refresh();return;}
            if(a.Kind==G3ActionKind.AmountAccept){if(TryAmount(out long amount))Ask(new G3Action(customAction.Kind,customAction.Key,customAction.Slot,amount),DescribePayment(customAction.Kind,customAction.Key,amount));else Status="请输入正数，最多一位小数。";Refresh();return;}
            if((a.Kind==G3ActionKind.Borrow||a.Kind==G3ActionKind.RepayLoan||a.Kind==G3ActionKind.RepayPrincipal)&&a.Amount<0){customAction=a;customAmount="";Panel=G3Panel.CustomAmount;Refresh();return;}
            if(a.Kind==G3ActionKind.ToggleQuick){QuickEnabled=!QuickEnabled;Refresh();return;}
            if(a.Kind==G3ActionKind.ToggleFlash){ReduceFlash=!ReduceFlash;Refresh();return;}
            if(a.Kind==G3ActionKind.ToggleVibration){Vibration=!Vibration;Refresh();return;}
            if(a.Kind==G3ActionKind.Confirm){var c=confirmation;var rev=confirmationRevision;Panel=confirmationReturn;Perform(c,rev);return;}
            if(a.Kind==G3ActionKind.Claim&&Snapshot.CurrentTicket?.TicketType=="challenge"&&!Snapshot.CurrentTicket.Busted)
            {var award=service.PreviewSettlement();if(award==null){Status="请先完成已选格，再决定收手。";Refresh();return;}Ask(a,"现在收手，确认领取 "+G3Text.Money(award.TotalMinor)+" 金币？收手后本票不能再选格。");return;}
            if(a.Kind==G3ActionKind.QuickReveal||a.Kind==G3ActionKind.Claim||a.Kind==G3ActionKind.Equip||a.Kind==G3ActionKind.Remove){Perform(a);return;}
            switch(a.Kind)
            {
                case G3ActionKind.ResumeNext:Perform(a);break;
                case G3ActionKind.CancelNext:Ask(a,"取消尚未完成的下一张购买？已经收到的奖金保留，未消耗的物品保留。");break;
                case G3ActionKind.BuyTicket:Ask(a,"购买"+G3Text.Ticket(a.Key)+"，票价 100 金币。购后可用现金 "+G3Text.Money(Snapshot.AvailableCashMinor-1000)+"。"+(a.Slot>=0?"同时消耗所选冲奖券。":""));break;
                case G3ActionKind.ClaimThenBuy:
                    var preview=service.PreviewSettlement();if(preview==null){Status="当前票还不能收下。";break;}
                    Ask(a,"先唯一收下 "+G3Text.Money(preview.TotalMinor)+"，再买一张"+G3Text.Ticket(a.Key)+"，售价 100；购后可用现金 "+G3Text.Money(Snapshot.AvailableCashMinor+preview.TotalMinor-1000)+"。下一张不使用耗材。若购票失败，已收奖保留。");break;
                case G3ActionKind.BuyStock:
                    var stock=Snapshot.Stock.FirstOrDefault(x=>x.StockId==a.Key);if(stock==null)return;
                    Ask(a,"支付 "+G3Text.Money((stock.PriceMinor-(a.Slot>=0?Snapshot.Tools[a.Slot].InitialPaymentMinor/2:0)))+" 金币净支付购买 "+ItemName(stock)+"。购买不会自动使用。"+(a.Slot>=0?"同时出售所选备用工具。":""));break;
                case G3ActionKind.Upgrade:
                    var own=Snapshot.Tools.FirstOrDefault(x=>x.ItemId==a.Key);if(own==null)return;var def=DayRules.Tool(a.Key);
                    if(own.Level>=def.LevelCap){Status="已经达到最高等级。";break;}
                    Ask(a,"支付 "+G3Text.Money(def.UpgradePricesMinor[own.Level-1])+" 升级 "+def.Name+" 至 "+(own.Level+1)+" 级，仅下一张起生效。");break;
                case G3ActionKind.Sell:
                    var tool=Snapshot.Tools.FirstOrDefault(x=>x.ItemId==a.Key);if(tool!=null)Ask(a,"出售 "+G3Text.Tool(a.Key)+"，收回 "+G3Text.Money(tool.InitialPaymentMinor/2)+"。升级费用不退，当日货架不补货。");break;
                case G3ActionKind.Borrow:case G3ActionKind.RepayLoan:case G3ActionKind.RepayPrincipal:Ask(a,DescribePayment(a.Kind,a.Key,a.Amount));break;
                case G3ActionKind.BeginClosing:
                    var bill=service.PreviewNightBill();Ask(a,"确认提前关店？放弃剩余 "+bill.RemainingOpportunities+" 张机会。本夜主债应付 "+G3Text.Money(bill.TotalDueMinor)+"，其中利息 "+G3Text.Money(bill.InterestUnpaidMinor)+"。关店后仍可处理余货、布置和借还款。");break;
                case G3ActionKind.EnterNight:Ask(a,"进入夜间账单，不再采购或买票。仍可借款、还款、出售允许出售的工具救急。");break;
                case G3ActionKind.PayNight:
                    var night=service.PreviewNightBill();Ask(new G3Action(a.Kind,slot:night.ShortfallMinor>0?1:0),night.ShortfallMinor>0?"当前还差 "+G3Text.Money(night.ShortfallMinor)+"。可取消后借款或卖物；若仍确认，将记录本局失败，现金不会部分扣除。":"支付今晚主债 "+G3Text.Money(night.TotalDueMinor)+"（本金 "+G3Text.Money(night.PrincipalDueMinor)+"，利息 "+G3Text.Money(night.InterestUnpaidMinor)+"）。");break;
                case G3ActionKind.Restart:Ask(a,"开启新的 G3 首日。当前日末收据保留；新局重置现金、库存、工具和借款。");break;
            }
            Refresh();
        }
        void OpenStable(Action action)
        {
            FlushScratch();if(IsCommitting)return;Router?.ReleaseCapture();var t=Snapshot.CurrentTicket;
            if(t!=null&&t.SelectedCell>=0){afterCommit=action;Run((id,rev)=>service.QuickReveal(t.Id,id,rev));}else action();
        }
        void Ask(G3Action action,string text){confirmation=action;confirmText=text;confirmationRevision=Snapshot.Revision;confirmationReturn=Panel;Panel=G3Panel.Confirm;Router?.ReleaseCapture();Refresh();}
        bool TryAmount(out long minor)
        {minor=0;if(!decimal.TryParse(customAmount,NumberStyles.AllowDecimalPoint,CultureInfo.InvariantCulture,out decimal value)||value<=0||value>100000||value*10!=decimal.Truncate(value*10))return false;minor=(long)(value*10);return true;}
        string DescribePayment(G3ActionKind kind,string contact,long amount)
        {
            if(kind==G3ActionKind.RepayPrincipal)return "主动归还主债本金 "+G3Text.Money(amount)+"。今晚已经计提的利息不退；减少的本金用于次日利息预览。";
            if(kind==G3ActionKind.RepayLoan)return "归还 "+G3Text.Contact(contact)+" "+G3Text.Money(amount)+"，优先最早到期；已用累计额度不恢复。";
            var c=Snapshot.Contacts.First(x=>x.ContactId==contact);long remaining=(contact=="mother"?50000:30000)-c.BorrowedLifetimeMinor-amount;int due=Snapshot.DayNumber+(contact=="mother"?6:3);
            return "向"+G3Text.Contact(contact)+"借入 "+G3Text.Money(amount)+"，第 "+Snapshot.DayNumber+" 天到账，第 "+due+" 晚到期，无息。借后剩余累计额度 "+G3Text.Money(remaining)+"。";
        }
        void Perform(G3Action a,long revision=-1)
        {
            FlushScratch();if(IsCommitting)return;string ticket=Snapshot.CurrentTicket?.Id;
            switch(a.Kind)
            {
                case G3ActionKind.ResumeNext:Run((id,r)=>service.ResumeClaimThenBuy(a.Key),revision,()=>Panel=G3Panel.None);break;
                case G3ActionKind.CancelNext:Run((id,r)=>service.CancelNextPurchase(a.Key,id,r),revision);break;
                case G3ActionKind.BuyTicket:Run((id,r)=>service.BuyTicket(a.Key,a.Slot,id,r),revision,()=>{ClearBoost();Panel=G3Panel.None;});break;
                case G3ActionKind.QuickReveal:if(ticket!=null)Run((id,r)=>service.QuickReveal(ticket,id,r),revision);break;
                case G3ActionKind.Claim:if(ticket!=null)Run((id,r)=>service.Claim(ticket,id,r),revision);break;
                case G3ActionKind.ClaimThenBuy:if(ticket!=null)Run((id,r)=>service.ClaimThenBuy(ticket,a.Key,-1,id,r),revision,()=>Panel=G3Panel.None);break;
                case G3ActionKind.BuyStock:
                    string sell=a.Slot>=0&&a.Slot<Snapshot.Tools.Count?Snapshot.Tools[a.Slot].ItemId:"";Run((id,r)=>service.BuyStock(a.Key,sell,id,r),revision);break;
                case G3ActionKind.Upgrade:Run((id,r)=>service.UpgradeTool(a.Key,id,r),revision);break;
                case G3ActionKind.Sell:Run((id,r)=>service.SellTool(a.Key,id,r),revision,()=>Panel=G3Panel.Inventory);break;
                case G3ActionKind.Equip:Run((id,r)=>service.EquipTool(a.Key,a.Slot,id,r),revision);break;
                case G3ActionKind.Remove:Run((id,r)=>service.EquipTool("",a.Slot,id,r),revision);break;
                case G3ActionKind.UseDrawer:if(ticket!=null)Run((id,r)=>service.UseConsumable(ticket,a.Slot,new int[0],id,r),revision,()=>Panel=G3Panel.None);break;
                case G3ActionKind.Borrow:Run((id,r)=>service.Borrow(a.Key,a.Amount,id,r),revision);break;
                case G3ActionKind.RepayLoan:Run((id,r)=>service.RepayLoan(a.Key,a.Amount,id,r),revision);break;
                case G3ActionKind.RepayPrincipal:Run((id,r)=>service.RepayPrincipal(a.Amount,id,r),revision);break;
                case G3ActionKind.BeginClosing:Run((id,r)=>service.BeginClosing(id,r),revision,()=>Panel=G3Panel.Bill);break;
                case G3ActionKind.EnterNight:Run((id,r)=>service.EnterNightBill(id,r),revision,()=>Panel=G3Panel.Bill);break;
                case G3ActionKind.PayNight:Run((id,r)=>service.PayNightBill(a.Slot==1,id,r),revision,()=>Panel=G3Panel.Bill);break;
                case G3ActionKind.Restart:
                    string run=Guid.NewGuid().ToString("N"),seed=Guid.NewGuid().ToString("N");Run((id,r)=>service.RestartDay(run,seed,id,r),revision,()=>{ClearBoost();Panel=G3Panel.None;Walking=false;view.SetWalking(false);});break;
            }
        }
        void UseDrawer(int slot)
        {
            var d=slot>=0&&slot<2?Snapshot.Drawers[slot]:null;if(d==null)return;
            if(d.ItemId=="boost_coupon"){boostSlot=slot;boostStockId=d.StockId;boostRunId=Snapshot.RunId;Panel=G3Panel.Tickets;Status="已预选冲奖券。返回取消不扣物，确认买号码票才消耗。";Refresh();return;}
            if(d.ItemId=="reveal_film"){BeginInformation(false,slot);return;}
            Ask(new G3Action(G3ActionKind.UseDrawer,slot:slot),"使用 "+G3Text.Quality(d.Quality)+DayRules.ConsumableName(d.ItemId)+"？"+G3Text.ConsumableHint(d.ItemId,d.Quality)+"。按确认时状态扣除，同票同类限一次。");
        }
        void BeginInformation(bool lamp,int drawer)
        {
            var t=Snapshot.CurrentTicket;if(t==null||t.TicketType!="challenge"||t.SelectedCell>=0||t.Phase!=TicketPhase.ACTIVE){Status="查看信息需要挑战票的未选格稳定点。";Refresh();return;}
            informationLamp=lamp;informationDrawer=drawer;informationCells.Clear();int n=1;
            if(!lamp){var d=Snapshot.Drawers[drawer];n=d.Quality=="precious"?3:d.Quality=="rare"?2:1;}
            informationCount=Math.Min(n,Enumerable.Range(0,8).Count(i=>!t.RevealedCells[i]&&!t.PeekedCells[i]));Panel=G3Panel.InformationTargets;Refresh();
        }
        void ConfirmInformation()
        {
            if(informationCells.Count!=informationCount||informationCount==0)return;var t=Snapshot.CurrentTicket;if(t==null)return;var targets=informationCells.OrderBy(x=>x).ToArray();
            if(informationLamp)Run((id,r)=>service.UseLamp(t.Id,targets[0],id,r),-1,()=>Panel=G3Panel.None);
            else Run((id,r)=>service.UseConsumable(t.Id,informationDrawer,targets,id,r),-1,()=>Panel=G3Panel.None);
        }
        void Run(Func<string,long,CommandResult> call,long revision=-1,Action success=null)
        {
            if(IsCommitting)return;string id="g3-ui-"+Guid.NewGuid().ToString("N");long rev=revision<0?Snapshot.Revision:revision;
            pendingId=id;retry=()=>call(id,rev);unknown=false;if(success!=null)afterCommit=success;
            Handle(retry());
        }
        void Handle(CommandResult result)
        {
            bool repeated=result.Success&&(unknown||(result.Receipt!=null&&Snapshot.Commands.Any(c=>c.CommandId==result.Receipt.CommandId)));
            confirmed=result.State??service.Snapshot;
            if(result.CommitStatus==CommitStatus.COMMIT_UNKNOWN){unknown=true;if(!string.IsNullOrEmpty(result.State?.PendingCommandId))pendingId=result.State.PendingCommandId;Status="正在确认上笔保存。请点「确认交易」，不会重复扣款或展示未确认结果。";view.InvalidateTicket();}
            else if(result.Code=="SAVE_NOT_COMMITTED"){unknown=false;Status="保存失败，已证实未提交。可原样重试。";}
            else
            {
                retry=null;pendingId=null;unknown=false;var continuation=afterCommit;afterCommit=null;
                Status=result.Success?(repeated?"上笔交易已确认，没有重复扣款或重复奖励。":ReadyMessage()):Describe(result.Code);
                if(result.Success){if(result.Receipt?.Kind=="CLAIM"){view.SettlementFeedback(ReduceFlash);if(Vibration)Handheld.Vibrate();}continuation?.Invoke();}
                if(PendingIntent()!=null){Panel=G3Panel.Tickets;Status="原票已收下，下张购买未完成。请继续原购买，或取消下张购买。";}
            }
            Refresh();
        }
        void RetryOrRecover()
        {
            if(string.IsNullOrEmpty(pendingId)){pendingId=Snapshot.PendingCommandId;unknown=true;}
            if(string.IsNullOrEmpty(pendingId)){Status="存档需要人工恢复，请保留原件；不会自动清档。";Refresh();return;}
            if(unknown)
            {
                var result=service.Recover(pendingId);
                if(result.CommitStatus==CommitStatus.PROVEN_NOT_COMMITTED&&result.Code=="SAVE_NOT_COMMITTED"&&retry==null){pendingId=null;unknown=false;Status="已确认上笔未提交，请重新操作。";Refresh();return;}
                Handle(result);
            }
            else if(retry!=null)Handle(retry());
        }
        string ReadyMessage()
        {
            var s=Snapshot;var t=s.CurrentTicket;
            if(s.Phase==DayPhase.DAY_COMPLETE)return "首日账单已支付，日末收据已保存。G3 切片在第二日开店前结束。";
            if(s.Phase==DayPhase.RUN_FAILED)return "已确认主债不足，本局失败；未作部分扣款。";
            if(s.Phase==DayPhase.CLOSING_PREP)return "进入关店准备。余货、布置、借还款仍可处理，然后确认夜账。";
            if(t==null)return "开店状态已保存。可看规则、购物或购买两种票。";
            if(t.Phase==TicketPhase.SETTLED)return "本票已唯一结算入账，可继续选择下一笔开销。";
            if(t.SelectedCell>=0)return "本格选择已保存，请擦开；退出也不会撤回。";
            if(t.Phase==TicketPhase.REVEALED_UNCLAIMED)return "票已揭晓，奖金尚未入账；可先处理合法耗材。";
            return "进度已保存。可以继续刮，或在稳定点打开面板。";
        }
        static string Describe(string code)
        {
            switch(code)
            {
                case "INSUFFICIENT_CASH":return "可用现金不足，未扣款。可查看手机或保留现金。";
                case "REVISION_CONFLICT":case "STALE_REVISION":return "状态已变化，这次未执行。请核对最新金额后重新选择。";
                case "DAY_LIMIT":return "今天已购买 12 张。完成当前票后处理关店。";
                case "TICKET_OCCUPIED":return "先完成并收下桌上这一张票。";
                case "CURRENT_TICKET_TOOL_LOCKED":case "SNAPSHOT_LOCKED":case "TOOL_SNAPSHOT_LOCKED":return "本张正在使用这件工具，结束前不能出售。";
                case "RECOVERY_REQUIRED":return "存档需要恢复，已停止交易，请保留原存档。";
                case "G3_FULL_CLEAR_BOUNDARY":case "G4_CLEAR_BOUNDARY":case "G4_BOUNDARY":return "提前全清债属于下一阶段，当前单日切片未扣款。";
                case "OUT_OF_STOCK":case "STOCK_UNAVAILABLE":return "今日这件商品已经售出，不会因重开面板补货。";
                case "LAMP_NOT_IN_CURRENT_SNAPSHOT":return "本张购票时没有启用检票灯；摆上后只能供下一张使用。";
                case "G3_DAY_BOUNDARY":return "已到 G3 首日边界，请查看日末收据。第二日尚未开放。";
                case "NEXT_PURCHASE_INTENT_PENDING":return "原票已收下，先处理尚未完成的下一张购买。";
                case "SCRATCH_JOURNAL_CAPACITY_USE_QUICK_REVEAL":return "本日刮擦记录接近容量，请用快揭完成当前票；交易和存档未丢失。";
                case "SAVE_CAPACITY_REACHED":return "存档容量已达上限，本次未提交。请保留存档，不要清除数据。";
                case "NO_CHANGE":return "状态没有变化，未产生新交易。";
                case "DRAWERS_FULL":case "DRAWER_FULL":return "两格抽屉已满，未扣款；可以先合法使用已有耗材。";
                case "INFORMATION_SOURCE_USED":return "本票已经使用过信息来源，检票灯与显影片不能叠用。";
                case "COPY_REQUIRES_POSITIVE_PRIZE":return "原始奖为零，不能使用中奖复写纸；耗材没有消耗。";
                case "COPY_REQUIRES_REVEALED_NUMBER":return "复写纸只可用于号码票全揭后、领取前；耗材没有消耗。";
                case "NEED_SAFE_CELL":return "至少先完整揭出一格安全，再贴封存；耗材没有消耗。";
                case "LAMP_DAILY_LIMIT":return "检票灯今天的可用次数已用完，换位不会恢复。";
                case "CONSUMABLE_TYPE_ALREADY_USED":return "本票已经用过同类耗材，不能叠用。";
                case "CONSUMABLE_TYPE_LIMIT":return "本票已用两种耗材，不能再添加第三种。";
                case "RESERVE_FULL":return "备用三格已满，请交换一个桌面位置或先出售允许出售的工具。";
                case "DRAWER_EMPTY":return "该抽屉已经空了，请重新选择现有耗材。";
                case "REVEAL_PENDING":return "请先完成已经承诺的当前格，再进行这项操作。";
                case "NOT_READY_TO_CLAIM":return "当前票尚不能结算，请先完成必要揭晓。";
                case "SHOP_CLOSED":return "已进入夜间，采购与换位结束；仍可借还款或出售允许出售的工具。";
                case "REPAY_EXCEEDS_DEBT":return "归还金额超过目前欠款，未扣款。请按尚欠金额重新输入。";
                case "BOOST_REQUIRES_NEXT_PURCHASE":return "冲奖券需要先预选，再确认购买下一张号码票；本张不消耗。";
                case "ALREADY_SETTLED":return "本票已经入账，这次未重复发奖。";
                case "ALREADY_REVEALED":return "这张票已经完成揭晓，本次没有新增刮痕或交易。";
                case "LOAN_LIMIT":case "BORROW_LIMIT":return "本局累计可借额度不足；还款不会恢复已用额度。";
                default:return "本次未执行："+code+"。现金与物品以已保存状态为准。";
            }
        }
        void ClearBoost(){boostSlot=-1;boostStockId="";boostRunId="";}
        void ClosePanel()
        {
            if(IsCommitting)return;
            if(Panel==G3Panel.Rules&&ticketRulesReturn){Panel=G3Panel.Tickets;ticketRulesReturn=false;}
            else if(Panel==G3Panel.Confirm){if(confirmation.Kind==G3ActionKind.BuyTicket)ClearBoost();Panel=confirmationReturn;}
            else{if(Panel==G3Panel.Tickets)ClearBoost();Panel=G3Panel.None;ticketRulesReturn=false;}
            informationCells.Clear();Router?.ReleaseCapture();Refresh();
        }
        public void Back(){if(IsCommitting)return;FlushScratch();if(IsCommitting)return;if(Panel!=G3Panel.None)ClosePanel();else OpenPanel(G3Panel.Settings);}
        public void Refresh()
        {
            if(service==null||view==null)return;
            if(boostSlot>=0&&(boostRunId!=Snapshot.RunId||boostSlot>=Snapshot.Drawers.Length||Snapshot.Drawers[boostSlot]?.StockId!=boostStockId))ClearBoost();
            view.Show(this,BuildPanel());
        }
        static string ItemName(StockItem s)=>s.IsConsumable?DayRules.ConsumableName(s.ItemId):DayRules.Tool(s.ItemId).Name;
        public G3PanelModel BuildPanel()
        {
            var m=new G3PanelModel();var s=Snapshot;var t=s.CurrentTicket;var bill=service.PreviewNightBill();
            bool terminal=s.Phase==DayPhase.DAY_COMPLETE||s.Phase==DayPhase.RUN_FAILED;
            switch(Panel)
            {
                case G3Panel.None:return m;
                case G3Panel.Settlement:
                    var details=service.PreviewSettlement()??s.Settlements.LastOrDefault(x=>x.TicketId==t?.Id);m.Title="本票逐项结算";
                    if(details==null){m.Body="请完成当前揭晓后查看。";break;}
                    m.Body=string.Join("\n",details.Entries.Select(x=>(x.Source=="raw_prize"?"原始票奖":x.Source=="copy_paper"?"中奖复写纸":x.Source=="seal_sticker"?"封存赔付":G3Text.Tool(x.Source))+"："+G3Text.Money(x.AmountMinor)))+"\n合计 "+G3Text.Money(details.TotalMinor)+"；票款 "+G3Text.Money(details.TicketPriceMinor)+"；本票耗材成本 "+G3Text.Money(details.ConsumableCostMinor)+"\n净收支 "+G3Text.Signed(details.NetMinor)+(t?.Phase==TicketPhase.SETTLED?"，已唯一入账。":"，尚未入账。");break;
                case G3Panel.Tickets:
                    m.Grid=true;m.Title="购票 · 两种均为 100 金币";m.Body="今天已购 "+s.TicketsPurchasedToday+" / 12；现金 "+G3Text.Money(s.AvailableCashMinor)+"\n号码票：六格全揭后兑奖。\n挑战票：选一格先保存承诺，再擦开；安全后可收手。\n"+(boostSlot>=0?"已预选冲奖券，仅下方号码票确认后消耗。":"不使用耗材。概率与完整说明见规则。");
                    var intent=PendingIntent();if(intent!=null){m.Body+="\n上张已收下：待完成 "+G3Text.Ticket(intent.NextTicketType)+"，售价 100。";m.Add("resume-next","继续原购买",new G3Action(G3ActionKind.ResumeNext,intent.IntentId));m.Add("cancel-next","取消下张购买",new G3Action(G3ActionKind.CancelNext,intent.IntentId));break;}
                    m.Add("buy-number","号码票\n100 金币",new G3Action(G3ActionKind.BuyTicket,"number",boostSlot),!s.HasUnsettledTicket&&s.Phase==DayPhase.DAY_OPEN&&s.TicketsPurchasedToday<12);
                    m.Add("buy-challenge","挑战票\n100 金币",new G3Action(G3ActionKind.BuyTicket,"challenge"),!s.HasUnsettledTicket&&s.Phase==DayPhase.DAY_OPEN&&s.TicketsPurchasedToday<12);
                    if(boostSlot>=0)m.Add("cancel-boost","取消冲奖预选（不消耗）",new G3Action(G3ActionKind.CancelBoost));
                    m.Add("ticket-rules",boostSlot>=0?"查看规则 · 保留预选":"完整规则与概率",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Rules));break;
                case G3Panel.Shop:
                    m.Title="今日货架 · 三道具与一耗材";m.Body="现金 "+G3Text.Money(s.AvailableCashMinor)+"；持有工具 "+s.Tools.Count+" / 6；抽屉 "+s.Drawers.Count(x=>x!=null)+" / 2\n查看、起身与返回都不换货。购买工具仅下一张起生效。";m.Grid=true;
                    foreach(var stock in s.Stock)m.Add("stock-"+stock.StockId,ItemName(stock)+" · "+G3Text.Quality(stock.Quality)+"\n"+G3Text.Money(stock.PriceMinor)+" 金币 · 库存 "+stock.Quantity,new G3Action(G3ActionKind.InspectStock,stock.StockId));break;
                case G3Panel.StockDetail:
                    var selected=s.Stock.FirstOrDefault(x=>x.StockId==selectedStock);if(selected==null){m.Title="商品不存在";break;}
                    m.Title=ItemName(selected)+" · "+G3Text.Quality(selected.Quality);
                    m.Body="售价 "+G3Text.Money(selected.PriceMinor)+" 金币；库存 "+selected.Quantity+"\n"+(selected.IsConsumable?G3Text.ConsumableHint(selected.ItemId,selected.Quality):G3Text.ToolHint(selected.ItemId,1))+"\n购买不等于使用；新工具仅下一张生效。\n教学首日不展示广告抵价。";
                    if(!selected.IsConsumable&&s.Tools.Count>=6)
                    {
                        m.Body+="\n已满六件。请明确选择售旧买新，当前票工具不能出售。";m.Grid=true;
                        for(int i=0;i<s.Tools.Count;i++){var tool=s.Tools[i];bool locked=t!=null&&t.Phase!=TicketPhase.SETTLED&&t.ConfigurationSnapshot.Any(x=>x.ItemId==tool.ItemId);m.Add("replace-"+i,"出售 "+G3Text.Tool(tool.ItemId)+"\n净支付 "+G3Text.Money(selected.PriceMinor-tool.InitialPaymentMinor/2),new G3Action(G3ActionKind.BuyStock,selected.StockId,i),!locked&&selected.Quantity>0&&!terminal&&s.Phase!=DayPhase.NIGHT_BILL);}
                    }
                    else m.Add("stock-buy","购买 · "+G3Text.Money(selected.PriceMinor),new G3Action(G3ActionKind.BuyStock,selected.StockId),selected.Quantity>0&&!terminal&&s.Phase!=DayPhase.NIGHT_BILL);
                    m.Add("back-shop","返回货架",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Shop));break;
                case G3Panel.Inventory:
                    m.Title="收纳 · 三启用＋三备用";m.Grid=true;
                    m.Body="本张生效："+CurrentConfiguration(s)+"\n下一张布置："+NextConfiguration(s)+"\n点击工具可查看、升级、出售或调整下一张位置。";
                    foreach(var tool in s.Tools){int slot=Array.IndexOf(s.NextToolIds,tool.ItemId);m.Add("tool-"+tool.ItemId,G3Text.Tool(tool.ItemId)+" · "+tool.Level+" 级\n"+(slot>=0?"下张桌面 "+(slot+1):"备用柜"),new G3Action(G3ActionKind.InspectTool,tool.ItemId));}
                    if(s.Tools.Count==0)m.Body+="\n还没有工具，可去货架按实际价格购买。";break;
                case G3Panel.ToolDetail:
                    var owned=s.Tools.FirstOrDefault(x=>x.ItemId==selectedTool);if(owned==null){m.Title="工具已售出";break;}var def=DayRules.Tool(owned.ItemId);var counter=s.ToolCounters.FirstOrDefault(x=>x.ItemId==owned.ItemId);
                    m.Title=def.Name+" · "+owned.Level+" 级";m.Grid=true;
                    m.Body=G3Text.ToolHint(owned.ItemId,owned.Level)+"\n本张生效："+CurrentConfiguration(s)+"\n下一张布置："+NextConfiguration(s)+"\n已用次数 "+(counter?.UsedToday??0)+"；票根余格 "+(counter?.ClipTicks??0)+"，换位不重置。";
                    for(int i=0;i<3;i++)m.Add("equip-"+i,"摆到桌面 "+(i+1)+"\n替换 "+G3Text.Tool(s.NextToolIds[i]),new G3Action(G3ActionKind.Equip,owned.ItemId,i),!terminal);
                    int existing=Array.IndexOf(s.NextToolIds,owned.ItemId);if(existing>=0)m.Add("remove-tool","放入备用柜",new G3Action(G3ActionKind.Remove,slot:existing),!terminal);
                    m.Add("upgrade-tool",owned.Level<def.LevelCap?"升级 · "+G3Text.Money(def.UpgradePricesMinor[owned.Level-1]):"已达最高等级",new G3Action(G3ActionKind.Upgrade,owned.ItemId),owned.Level<def.LevelCap&&!terminal&&s.Phase!=DayPhase.NIGHT_BILL);
                    bool lockedTool=t!=null&&t.Phase!=TicketPhase.SETTLED&&t.ConfigurationSnapshot.Any(x=>x.ItemId==owned.ItemId);
                    m.Add("sell-tool",lockedTool?"本张锁定，暂不可售":"出售 · 收回 "+G3Text.Money(owned.InitialPaymentMinor/2),new G3Action(G3ActionKind.Sell,owned.ItemId),!lockedTool&&!terminal);break;
                case G3Panel.Drawer:
                    m.Title="耗材抽屉 · 两个位置";m.Body="每张最多两种，同种限一次。购买与使用分别确认。\n新工具只作用下一张；合法耗材可以用于当前票。";
                    for(int i=0;i<2;i++){var d=s.Drawers[i];m.Add("drawer-"+i,d==null?"抽屉 "+(i+1)+" · 空位":G3Text.Quality(d.Quality)+DayRules.ConsumableName(d.ItemId)+"\n"+(d.ItemId=="boost_coupon"?"预选下一号码票使用":"查看并确认本票使用"),new G3Action(G3ActionKind.UseDrawer,slot:i),d!=null&&!terminal);}
                    bool hasLamp=t!=null&&t.ConfigurationSnapshot.Any(x=>x.ItemId=="inspection_lamp");
                    m.Add("lamp",!hasLamp?"本张无灯 · 下张才生效":t.LampUsed?"本票已用检票灯":"使用本张检票灯",new G3Action(G3ActionKind.UseLamp),hasLamp&&t.TicketType=="challenge"&&!t.LampUsed&&t.SelectedCell<0&&t.Phase==TicketPhase.ACTIVE);break;
                case G3Panel.Phone:
                    m.Title="手机 · 游戏中的虚构联系人";m.Body="今晚主债 "+G3Text.Money(bill.TotalDueMinor)+"；可用现金 "+G3Text.Money(s.AvailableCashMinor)+"\n亲友欠款无息。到期当晚可处理，次日逾期才冻结该人新增借款。";
                    foreach(var contact in s.Contacts){long debt=s.Loans.Where(x=>x.ContactId==contact.ContactId).Sum(x=>x.RemainingMinor),cap=contact.ContactId=="mother"?50000:30000;m.Add("contact-"+contact.ContactId,G3Text.Contact(contact.ContactId)+" · 尚欠 "+G3Text.Money(debt)+"\n未用累计额度 "+G3Text.Money(cap-contact.BorrowedLifetimeMinor),new G3Action(G3ActionKind.InspectContact,contact.ContactId));}
                    m.Add("principal","主动归还主债本金",new G3Action(G3ActionKind.RepayPrincipal,amount:-1),!terminal);m.Add("phone-bill","查看今晚账单",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Bill));break;
                case G3Panel.Contact:
                    var c=s.Contacts.First(x=>x.ContactId==selectedContact);var loans=s.Loans.Where(x=>x.ContactId==selectedContact&&x.RemainingMinor>0).OrderBy(x=>x.DueNight).ToArray();long outstanding=loans.Sum(x=>x.RemainingMinor);long capacity=(selectedContact=="mother"?50000:30000)-c.BorrowedLifetimeMinor;
                    m.Title=G3Text.Contact(selectedContact)+" · 借还款";m.Grid=true;m.Body="尚欠 "+G3Text.Money(outstanding)+"；累计已借 "+G3Text.Money(c.BorrowedLifetimeMinor)+"；剩余额度 "+G3Text.Money(capacity)+"\n"+(loans.Length==0?"当前没有未还借款。":"最近到期：第 "+loans[0].DueNight+" 晚；该笔尚欠 "+G3Text.Money(loans[0].RemainingMinor))+"\n"+PhoneHistory(s,selectedContact);
                    m.Add("borrow-1000","借入 1000",new G3Action(G3ActionKind.Borrow,selectedContact,amount:10000),!terminal);m.Add("borrow-2000","借入 2000",new G3Action(G3ActionKind.Borrow,selectedContact,amount:20000),!terminal);
                    m.Add("borrow-custom","自定借入金额",new G3Action(G3ActionKind.Borrow,selectedContact,amount:-1),!terminal);m.Add("repay-1000","归还 1000",new G3Action(G3ActionKind.RepayLoan,selectedContact,amount:10000),!terminal&&outstanding>0);m.Add("repay-custom","自定归还金额",new G3Action(G3ActionKind.RepayLoan,selectedContact,amount:-1),!terminal&&outstanding>0);break;
                case G3Panel.CustomAmount:
                    m.Title="输入准确金币金额";m.Body="金额："+(customAmount.Length==0?"0":customAmount)+"\n最多一位小数，确认后再显示完整交易说明。";m.Grid=true;m.LargeGrid=true;
                    foreach(var digit in new[]{"1","2","3","4","5","6","7","8","9",".","0"})m.Add("digit-"+digit,digit,new G3Action(G3ActionKind.Digit,digit));m.Add("digit-del","退格",new G3Action(G3ActionKind.Backspace));m.Add("amount-accept","核对金额",new G3Action(G3ActionKind.AmountAccept));break;
                case G3Panel.Bill:
                    m.Title=terminal?(s.Phase==DayPhase.DAY_COMPLETE?"首日完成 · 已保存收据":"本局失败 · 已保存收据"):"今晚账单";
                    m.Body=(s.Phase==DayPhase.DAY_COMPLETE?"已付利息 "+G3Text.Money(s.InterestPaidMinor)+"；":"")+"可用现金 "+G3Text.Money(bill.AvailableCashMinor)+"\n本夜本金 "+G3Text.Money(bill.PrincipalDueMinor)+"；利息 "+G3Text.Money(bill.InterestUnpaidMinor)+"；共计 "+G3Text.Money(bill.TotalDueMinor)+"\n主债余额 "+G3Text.Money(s.PrincipalMinor)+"；累计已还本金 "+G3Text.Money(s.PrincipalRepaidMinor)+"\n亲友尚欠：妈妈 "+G3Text.Money(s.Loans.Where(x=>x.ContactId=="mother").Sum(x=>x.RemainingMinor))+"（第 7 晚）；女友 "+G3Text.Money(s.Loans.Where(x=>x.ContactId=="girlfriend").Sum(x=>x.RemainingMinor))+"（第 4 晚）\n次日利息预览 "+G3Text.Money(bill.NextDayInterestMinor)+"；今日已结算 "+s.SettledTicketCount+" / 12。";
                    if(terminal){m.Body+="\n下一日耗材预告："+DayRules.ConsumableName(s.ConsumableBatch[1])+"。\nG3 一日白盒边界：不执行第二日供货，不代表完整游戏结局。";m.Add("restart","重新开始首日",new G3Action(G3ActionKind.Restart));}
                    else{m.Add("bill-phone","手机 · 借还款",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Phone));m.Add("bill-inventory","收纳 · 可售工具",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Inventory));
                    if(s.Phase==DayPhase.DAY_OPEN)m.Add("begin-closing","提前关店 · 先确认",new G3Action(G3ActionKind.BeginClosing),!s.HasUnsettledTicket);
                    else if(s.Phase==DayPhase.CLOSING_PREP)m.Add("enter-night","确认进入夜间",new G3Action(G3ActionKind.EnterNight));
                    else m.Add("pay-night",bill.ShortfallMinor>0?"不足款 · 核对后结束":"支付今晚主债",new G3Action(G3ActionKind.PayNight));}break;
                case G3Panel.InformationTargets:
                    m.Title=(informationLamp?"检票灯":"显影片")+" · 选择信息格";m.Body="本次查看 "+informationCount+" 格，已选 "+informationCells.Count+"。\n查看只给安全/危险信息，不计揭格、不增加可收奖。确认前可以取消。";m.Grid=true;m.LargeGrid=true;
                    if(t!=null)for(int visual=0;visual<8;visual++){int i=(visual+4)%8;m.Add("info-target-"+i,(informationCells.Contains(i)?"已选格 ":"格 ")+(visual+1)+" · "+(visual<4?"上排":"下排")+(visual%4+1),new G3Action(G3ActionKind.TargetCell,slot:i),!t.RevealedCells[i]&&!t.PeekedCells[i]);}
                    m.Add("information-confirm","确认查看 "+informationCount+" 格",new G3Action(G3ActionKind.ConfirmTargets),informationCount>0&&informationCells.Count==informationCount);break;
                case G3Panel.Rules:
                    m.Title=string.IsNullOrEmpty(s.FixtureLabel)?"规则 · 虚构金币，不能兑换现金":"QA 固定诊断局 · 不代表自然中奖概率";m.Body="号码票先锁一个原始奖，六格只有一格匹配或全部不匹配。\n奖额：0 / 50 / 100 / 200 / 500 / 2000 / 10000 / 100000\n概率：40% / 20% / 22% / 13% / 4.7% / 0.28% / 0.018% / 0.002%\n挑战票：8 格、6 安全 2 危险，无放回。安全 1～6 格可收 100 / 200 / 300 / 500 / 900 / 1800。\n危险原奖为 0；封存只按之前锁定金额赔付。每次继续都须主动选格。\n首日利息 150，白天还本不退当日利息。所有花费、选择和刮痕确认保存后显示。";break;
                case G3Panel.Settings:
                    m.Title="操作与可访问性";m.Body="可自由走动或原位采购，价格与效果相同。\n挑战快揭只完成已选格。完整品质尚未验收。";
                    m.Add("settings-rules","完整规则与概率",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Rules));
                    m.Add("setting-quick","快揭按钮："+(QuickEnabled?"显示":"隐藏"),new G3Action(G3ActionKind.ToggleQuick));m.Add("setting-flash","减弱闪光："+(ReduceFlash?"开":"关"),new G3Action(G3ActionKind.ToggleFlash));m.Add("setting-vibration","结算震动："+(Vibration?"开":"关"),new G3Action(G3ActionKind.ToggleVibration));break;
                case G3Panel.Confirm:
                    m.Title="请核对这笔操作";m.Body=confirmText;m.Add("confirm-action","确认",new G3Action(G3ActionKind.Confirm));m.Add("cancel-action","取消",new G3Action(G3ActionKind.Cancel));break;
            }
            m.Footnote=ticketRulesReturn&&Panel==G3Panel.Rules?"返回将继续这次购票，冲奖预选保留。":Panel==G3Panel.Rules&&!string.IsNullOrEmpty(s.FixtureLabel)?"诊断标记："+s.FixtureLabel:Status;return m;
        }
        static string PhoneHistory(RunState s,string contact)
        {
            var events=s.PhoneEvents.Where(x=>x.ContactId==contact).Reverse().Take(2).Reverse();
            return string.Join("\n",events.Select(x=>(x.Kind=="REPAID"?"已归还 ":"借款到账 ")+G3Text.Money(x.AmountMinor)+(x.DueNight>0?" · 第 "+x.DueNight+" 晚到期":"")));
        }
        public static string CurrentConfiguration(RunState s)=>s.CurrentTicket==null?"尚未购票":string.Join(" / ",Enumerable.Range(0,3).Select(i=>{var t=s.CurrentTicket.ConfigurationSnapshot.SingleOrDefault(x=>x.TableSlot==i);return (i+1)+":"+(t==null?"空":G3Text.Tool(t.ItemId)+t.Level);}));
        public static string NextConfiguration(RunState s)=>string.Join(" / ",s.NextToolIds.Select((id,i)=>(i+1)+":"+(string.IsNullOrEmpty(id)?"空":G3Text.Tool(id)+s.Tools.First(x=>x.ItemId==id).Level)));
    }
}

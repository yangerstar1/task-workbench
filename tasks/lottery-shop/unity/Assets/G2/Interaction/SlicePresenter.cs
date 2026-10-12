using System;
using System.Collections.Generic;
using Lottery.G2.Core;
using Lottery.G2.Ads;
using UnityEngine;

namespace Lottery.G2.Interaction
{
    // The presentation owns gestures, never balances, outcomes, or revealed bits.
    public sealed class SlicePresenter : MonoBehaviour
    {
        TicketService service; G2SceneView view; AdPurchaseService ads; FakeRewardedAdService fake;
        readonly List<ScratchStroke> queue=new List<ScratchStroke>();
        Func<CommandResult> retry;
        string pendingId;
        bool unknown,resumeChain;
        float lastFlush;
        string message="购买后擦开银层；每一笔已显示进度均已保存";
        public InputRouter Router { get; set; }
        public TicketService Service => service;
        public RunState Snapshot => service.Snapshot;
        public G2SceneView View => view;
        public bool PanelOpen { get; private set; }
        public bool IsCommitting => retry!=null || !service.CanMutate || Snapshot.Ad?.Phase==AdPhase.RECOVERY_CONFLICT;
        public bool CanScratch => !PanelOpen && !IsCommitting && Snapshot.CurrentTicket!=null && Snapshot.CurrentTicket.Phase==TicketPhase.ACTIVE;
        public void Initialize(TicketService core,G2SceneView scene,AdPurchaseService shop=null,FakeRewardedAdService provider=null) { service=core; view=scene; ads=shop; fake=provider; Refresh(); }
        void Update()
        {
            if(service==null) return;
            if(queue.Count>0 && Time.unscaledTime-lastFlush>=.10f) FlushScratch();
        }
        public void QueueBrush(Vector2 from,Vector2 to,bool hasFrom)
        {
            if(!CanScratch) return;
            queue.Add(new ScratchStroke(from.x,from.y,to.x,to.y,hasFrom,7));
            if(queue.Count>=128) FlushScratch();
        }
        public void FlushScratch()
        {
            if(queue.Count==0 || IsCommitting) return;
            var ticket=Snapshot.CurrentTicket; if(ticket==null) { queue.Clear(); return; }
            var strokes=queue.ToArray(); queue.Clear(); lastFlush=Time.unscaledTime;
            string id=NewCommand("scratch"),ticketId=ticket.Id; long revision=Snapshot.Revision;
            Commit(id,()=>service.ApplyScratch(ticketId,id,revision,strokes));
        }
        public void Execute(SliceAction action)
        {
            if(action==SliceAction.Retry) { RetryOrRecover(); return; }
            if(action==SliceAction.ClosePanel) { PanelOpen=false; Router?.CancelGesture(); Refresh(); return; }
            if(IsCommitting) return;
            if(action==SliceAction.OpenPanel) { FlushScratch(); if(IsCommitting) return; PanelOpen=true; Router?.CancelGesture(); Refresh(); return; }
            if(action==SliceAction.Buy)
            {
                string id=NewCommand("buy"); long revision=Snapshot.Revision; Commit(id,()=>service.BuyNumberTicket(id,revision));
            }
            else if(action==SliceAction.BuyStock && ads!=null)
            {
                string id=NewCommand("stock"); long revision=Snapshot.Revision; Commit(id,()=>ads.BuyNormally(id,revision));
            }
            else if(action==SliceAction.BeginFakeAd && ads!=null)
            {
                string id=NewCommand("ad"),request=NewCommand("request"); long revision=Snapshot.Revision,elapsed=(long)Time.realtimeSinceStartup;
                Commit(id,()=>ads.BeginAd(request,id,revision,elapsed),true);
            }
            else if((action==SliceAction.FakeClose || action==SliceAction.FakeReward) && fake!=null && Snapshot.Ad!=null)
            {
                string request=Snapshot.Ad.RequestId,run=Snapshot.RunId,eventId=NewCommand("event"),poll=NewCommand("poll");
                var kind=action==SliceAction.FakeClose?AdEventKind.Closed:AdEventKind.Reward;
                Commit("fake-event:"+eventId,()=>
                {
                    var queued=fake.QueueEvent(request,run,kind,eventId);
                    return queued.Committed?ads.PollAd(request,poll,Snapshot.Revision):queued;
                },true);
            }
            else if(action==SliceAction.PollAd && ads!=null && Snapshot.Ad!=null)
            {
                string id=NewCommand("poll"),request=Snapshot.Ad.RequestId; long revision=Snapshot.Revision;
                Commit(id,()=>ads.PollAd(request,id,revision),true);
            }
            else if(action==SliceAction.Claim)
            {
                FlushScratch(); if(IsCommitting) return; var ticket=Snapshot.CurrentTicket; if(ticket==null) return;
                string id=NewCommand("claim"),ticketId=ticket.Id; long revision=Snapshot.Revision; Commit(id,()=>service.Claim(ticketId,id,revision));
            }
        }
        public void Back()
        {
            FlushScratch(); if(IsCommitting) return;
            PanelOpen=!PanelOpen; Refresh();
        }
        void Commit(string id,Func<CommandResult> command,bool continueChain=false)
        {
            pendingId=id; retry=command; unknown=false; resumeChain=continueChain;
            Handle(command());
        }
        void Handle(CommandResult result)
        {
            if(result.CommitStatus==CommitStatus.COMMIT_UNKNOWN)
            {
                unknown=true; if(!string.IsNullOrEmpty(result.State?.PendingCommandId)) pendingId=result.State.PendingCommandId; message="正在确认交易；请点确认，勿重复购买或领奖";
            }
            else if(result.Code=="SAVE_NOT_COMMITTED")
            {
                unknown=false; message="保存失败，已确认未提交；可原样重试";
            }
            else
            {
                retry=null; pendingId=null; unknown=false;
                message=result.Code=="SUCCESS"?(result.Receipt?.Kind=="BUY_STOCK"?"冲奖券已按原价入库，扣款 80 金币":ReadyMessage()):Describe(result.Code);
            }
            Refresh();
        }
        void RetryOrRecover()
        {
            if(pendingId==null)
            {
                pendingId=Snapshot.PendingCommandId;
                if(string.IsNullOrEmpty(pendingId)) { message="存档需要恢复，交易已阻止；请保留存档"; Refresh(); return; }
                unknown=true;
            }
            if(unknown)
            {
                var result=service.Recover(pendingId);
                if(result.Committed && resumeChain && retry!=null) { Handle(retry()); return; }
                if(result.CommitStatus==CommitStatus.PROVEN_NOT_COMMITTED && result.Code=="SAVE_NOT_COMMITTED" && retry==null)
                {
                    pendingId=null; unknown=false; message="已确认上次未提交，请重新操作"; Refresh(); return;
                }
                Handle(result);
            }
            else if(retry!=null) Handle(retry());
        }
        string ReadyMessage()
        {
            var state=Snapshot; var ticket=state.CurrentTicket;
            if(ticket==null) return "购买后擦开银层";
            if(ticket.Phase==TicketPhase.REVEALED_UNCLAIMED) return "六格已揭晓；奖金尚未入账，请点收下";
            if(ticket.Phase==TicketPhase.SETTLED) return state.TicketsPurchasedToday>=12?"已达本日 12 票探针边界；本切片不进入下一天":"奖金已收下，可购买下一张";
            return "结果已锁定；可以随时打开面板，再返回继续刮";
        }
        static string Describe(string code)
        {
            switch(code)
            {
                case "NO_CHANGE": return "这片银层已经擦开";
                case "INSUFFICIENT_CASH": return "现金不足，未购买";
                case "TICKET_OCCUPIED": return "请先完成并收下当前彩票";
                case "DAY_LIMIT": return "已达本日 12 票技术探针边界";
                case "NOT_FULLY_REVEALED": return "请先擦开全部六格";
                case "ALREADY_SETTLED": return "这张票已经收下，不会再次入账";
                case "RECOVERY_REQUIRED": return "存档需要恢复，交易已阻止；请保留存档";
                default: return "操作未提交（"+code+"）";
            }
        }
        public void Refresh()
        {
            if(service==null) return;
            if(Snapshot.RecoveryRequired || Snapshot.Ad?.Phase==AdPhase.RECOVERY_CONFLICT) message="存档需要恢复，交易已阻止；请保留存档";
            var state=Snapshot;
            var availability=ads?.GetAvailability((long)Time.realtimeSinceStartup);
            string adInfo=availability==null?"开发服务未配置": "冲奖券 · 普通 · 库存 "+(state.StockAvailable?"1":"0")+" · 抽屉空位 "+availability.FreeDrawerSlots+" / 2\n"+
                (state.Ad==null?AdReason(availability.Reason):"模拟事务："+AdState(state.Ad.Phase))+"\n本切片只检验购买入库；道具使用留待后续阶段";
            view.Show(state,PanelOpen,IsCommitting,message,adInfo,availability?.CanBuyNormally??false,availability?.CanWatchAd??false,state.Ad!=null && fake!=null && fake.IsAvailable);
        }
        static string AdReason(string reason)
        {
            switch(reason)
            {
                case "": return "可自愿使用开发模拟广告抵价";
                case "AD_TUTORIAL_DAY": return "教学首日不开放广告抵价";
                case "AD_FIRST_LAUNCH_DELAY": return "启动满 60 秒后才有广告资格";
                case "AD_MINIMUM_SETTLEMENTS": return "完成 12 张有效票后才有广告资格";
                case "STOCK_UNAVAILABLE": return "这件固定库存已经售出";
                case "INSUFFICIENT_CASH": return "现金不足，不能预留商品";
                default: return "当前不可用："+reason;
            }
        }
        static string AdState(AdPhase phase)
        {
            switch(phase)
            {
                case AdPhase.CLOSED_AWAITING_REWARD: return "已关闭，等待可能迟到的奖励；资源仍预留";
                case AdPhase.COMMITTED: return "已抵价购买入库，只扣款一次";
                case AdPhase.RECOVERY_CONFLICT: return "恢复冲突，保留原承诺并停止交易";
                case AdPhase.ABORTED_NO_REWARD: return "已确认无奖励，未抵价购买";
                case AdPhase.REWARD_CONFIRMED: return "奖励已确认，等待提交购买";
                default: return phase.ToString();
            }
        }
        static string NewCommand(string kind) => "ui-"+kind+"-"+Guid.NewGuid().ToString("N");
    }
}

using System;
using System.Collections.Generic;
using System.Linq;
using Lottery.G3.Core;

namespace Lottery.G3.Interaction
{
    public sealed partial class G3Presenter
    {
        // Saved proposals are non-economic. Only explicit Open invokes Borrow;
        // both pending packets and confirmed history are reconstructed from the save.
        sealed class PhoneProposal { public long Amount; public bool Sent; public string CommandId; }
        readonly Dictionary<string,PhoneProposal> phoneProposals=new Dictionary<string,PhoneProposal>();
        string phoneRun="";int phoneRecordPage;
        public bool PhoneVisible=>G3PhoneDisplay.HandlesPanel(Panel)||(Panel==G3Panel.CustomAmount&&(customAction.Kind==G3ActionKind.Borrow||customAction.Kind==G3ActionKind.RepayLoan||customAction.Kind==G3ActionKind.RepayPrincipal))||(Panel==G3Panel.Confirm&&(G3PhoneDisplay.HandlesPanel(confirmationReturn)||confirmationReturn==G3Panel.CustomAmount&&(customAction.Kind==G3ActionKind.RepayLoan||customAction.Kind==G3ActionKind.RepayPrincipal)));
        public string PhoneContact=>selectedContact;
        PhoneProposal Proposal=>phoneProposals.TryGetValue(selectedContact,out var p)?p:null;
        void SyncPhoneRun()
        {
            var s=Snapshot;if(phoneRun!=s.RunId){phoneProposals.Clear();phoneRecordPage=0;phoneRun=s.RunId;}
            string prefix=s.RunId+":loan:";
            foreach(var contact in s.Contacts)
            {
                var request=s.PhoneEvents.LastOrDefault(x=>x.Kind=="BORROW_REQUESTED"&&x.ContactId==contact.ContactId&&!s.PhoneEvents.Any(c=>(c.Kind=="BORROWED"||c.Kind=="BORROW_CANCELLED")&&c.LoanId==x.LoanId));
                if(request!=null&&request.LoanId.StartsWith(prefix,StringComparison.Ordinal))phoneProposals[contact.ContactId]=new PhoneProposal{Amount=request.AmountMinor,Sent=true,CommandId=request.LoanId.Substring(prefix.Length)};
                else if(phoneProposals.TryGetValue(contact.ContactId,out var p)&&p.Sent)phoneProposals.Remove(contact.ContactId);
            }
        }
        bool ExecutePhone(G3Action a)
        {
            if(service==null)return false;SyncPhoneRun();
            if(a.Kind==G3ActionKind.Confirm&&PhoneVisible&&Panel!=G3Panel.Confirm)return true;
            if(a.Kind==G3ActionKind.PhoneBack){if(!IsCommitting)ClosePhonePage();return true;}
            if(a.Kind==G3ActionKind.Close&&a.Key=="phone"){if(!IsCommitting){Panel=G3Panel.None;Router?.ReleaseCapture();Refresh();}return true;}
            if(a.Kind==G3ActionKind.InspectContact){if(!IsCommitting){selectedContact=a.Key=="mother"?"mother":"girlfriend";phoneRecordPage=0;Panel=G3Panel.Contact;Refresh();}return true;}
            if(IsCommitting)return a.Kind>=G3ActionKind.PhoneChoose;
            if(a.Kind==G3ActionKind.PhoneChoose){Panel=G3Panel.PhoneAmount;Refresh();return true;}
            if(a.Kind==G3ActionKind.PhoneRecords){phoneRecordPage=0;Panel=G3Panel.PhoneRecords;Refresh();return true;}
            if(a.Kind==G3ActionKind.PhonePage){phoneRecordPage=Math.Max(0,phoneRecordPage+a.Slot);Refresh();return true;}
            if(a.Kind==G3ActionKind.Borrow&&a.Amount>0){PreparePhoneRequest(a.Key,a.Amount);return true;}
            if(a.Kind==G3ActionKind.AmountAccept&&PhoneVisible&&customAction.Kind==G3ActionKind.Borrow)
            {if(TryAmount(out long amount))PreparePhoneRequest(customAction.Key,amount);else{Status="请输入正数，最多一位小数。";Refresh();}return true;}
            if(a.Kind==G3ActionKind.PhoneSend)
            {
                var p=Proposal;if(Panel!=G3Panel.PhoneRequest||p==null||p.Sent)return true;
                string contact=selectedContact;long amount=p.Amount;string claimId=p.CommandId;
                Run((command,revision)=>service.RequestPhoneLoan(contact,amount,claimId,command,revision),-1,()=>{Panel=G3Panel.Contact;Status="转账已发来，确认收款后入账。";},"g3-phone-request-"+Guid.NewGuid().ToString("N"));return true;
            }
            if(a.Kind==G3ActionKind.PhoneClaim)
            {
                var p=Proposal;if(Panel!=G3Panel.PhonePacket||p==null||!p.Sent)return true;
                string contact=selectedContact;long amount=p.Amount;string id=p.CommandId;
                Run((command,revision)=>service.Borrow(contact,amount,command,revision),-1,()=>{phoneProposals.Remove(contact);Panel=G3Panel.Contact;Status=G3Text.Money(amount)+" 元已到账，借款记录已保存。";},id);
                return true;
            }
            if(a.Kind==G3ActionKind.PhoneCancelRequest)
            {
                var p=Proposal;if(p==null||!p.Sent)return true;string contact=selectedContact,loanId=Snapshot.RunId+":loan:"+p.CommandId;
                Run((command,revision)=>service.CancelPhoneLoanRequest(loanId,command,revision),-1,()=>{phoneProposals.Remove(contact);Panel=G3Panel.Contact;Status="未收款的转账已取消，余额和借款没有变化。";},"g3-phone-cancel-"+Guid.NewGuid().ToString("N"));return true;
            }
            if(a.Kind==G3ActionKind.PhoneRepay)
            {
                Panel=G3Panel.PhoneRepay;Refresh();
                return true;
            }
            return false;
        }
        void PreparePhoneRequest(string contact,long amount)
        {
            selectedContact=contact=="mother"?"mother":"girlfriend";
            if(Proposal!=null&&Proposal.Sent){Panel=G3Panel.Contact;Status="先处理聊天中尚未收款的转账。";Refresh();return;}
            if(amount<=0||amount>LoanRules.RemainingLimit(Snapshot,selectedContact)){Status="这次想借的金额超过剩余累计额度，还款不会恢复额度。";Panel=G3Panel.PhoneAmount;Refresh();return;}
            if(LoanRules.IsFrozen(Snapshot,selectedContact,Snapshot.DayNumber)){Status="这位联系人有逾期借款，先归还后再申请。";Panel=G3Panel.Contact;Refresh();return;}
            phoneProposals[selectedContact]=new PhoneProposal{Amount=amount,CommandId="g3-phone-claim-"+Guid.NewGuid().ToString("N")};Panel=G3Panel.PhoneRequest;Refresh();
        }
        void ClosePhonePage()
        {
            if(Panel==G3Panel.Phone)Panel=G3Panel.None;
            else if(Panel==G3Panel.Contact)Panel=G3Panel.Phone;
            else if(Panel==G3Panel.Confirm)Panel=confirmationReturn;
            else Panel=G3Panel.Contact;
            Router?.ReleaseCapture();Refresh();
        }
        G3PanelModel BuildPhonePanel()
        {
            SyncPhoneRun();var m=new G3PanelModel();var s=Snapshot;var proposal=Proposal;
            bool terminal=s.Phase==DayPhase.DAY_COMPLETE||s.Phase==DayPhase.RUN_FAILED;
            bool stable=s.CurrentTicket==null||s.CurrentTicket.SelectedCell<0;
            bool canBorrow=!terminal&&stable&&!LoanRules.IsFrozen(s,selectedContact,s.DayNumber);
            string name=G3Text.Contact(selectedContact);int days=DayRules.ContactDueOffset(selectedContact);
            m.Title=Panel==G3Panel.Phone?"聊天":name;
            if(IsCommitting){m.Title="正在确认保存";m.Body=Status+"\n确认之前不会展示已到账。";m.Add("retry","确认交易",new G3Action(G3ActionKind.Retry));m.Footnote="请保留当前存档";return m;}
            m.Footnote=IsCommitting?Status:"";
            if(Panel==G3Panel.Phone)
            {
                foreach(var c in s.Contacts)
                {
                    var last=s.PhoneEvents.LastOrDefault(x=>x.ContactId==c.ContactId&&(x.Kind=="BORROWED"||x.Kind=="REPAID"));bool pending=phoneProposals.TryGetValue(c.ContactId,out var draft)&&draft.Sent;
                    string recent=pending?"[转账] 待收款":last==null?(c.ContactId=="mother"?"吃饭了吗？":"店里好吗？"):(last.Kind=="REPAID"?"收到了，谢谢。":"[转账] 已收款");
                    m.Add("contact-"+c.ContactId,G3Text.Contact(c.ContactId)+"\n"+recent,new G3Action(G3ActionKind.InspectContact,c.ContactId));
                }
                m.Add("principal","归还主债本金",new G3Action(G3ActionKind.RepayPrincipal,amount:-1),!terminal&&stable);
                m.Add("phone-bill","查看今晚账单",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Bill));return m;
            }
            if(Panel==G3Panel.PhoneOptions)
            {
                m.Title="聊天工具";m.Body="选择一句话或查看记录";
                m.Add("phone-choose","借点周转钱",new G3Action(G3ActionKind.PhoneChoose),canBorrow&&(proposal==null||!proposal.Sent));
                m.Add("phone-repay","归还借款",new G3Action(G3ActionKind.PhoneRepay),!terminal&&stable&&s.Loans.Any(x=>x.ContactId==selectedContact&&x.RemainingMinor>0));
                m.Add("phone-records","借还记录",new G3Action(G3ActionKind.PhoneRecords));return m;
            }
            if(Panel==G3Panel.PhoneRepay)
            {
                long debt=s.Loans.Where(x=>x.ContactId==selectedContact).Sum(x=>x.RemainingMinor);
                m.Title="归还给"+name;m.Body="目前尚欠 "+G3Text.Money(debt)+" 元\n持有 "+G3Text.Money(s.AvailableCashMinor)+" 元";
                m.Add("repay-1000","归还 1000 元",new G3Action(G3ActionKind.RepayLoan,selectedContact,amount:10000),debt>=10000&&!terminal&&stable);
                m.Add("repay-custom","填写其他归还金额",new G3Action(G3ActionKind.RepayLoan,selectedContact,amount:-1),debt>0&&!terminal&&stable);
                m.Add("repay-all","归还全部 "+G3Text.Money(debt),new G3Action(G3ActionKind.RepayLoan,selectedContact,amount:debt),debt>0&&!terminal&&stable);return m;
            }
            if(Panel==G3Panel.PhoneRecords)
            {
                var records=s.PhoneEvents.Where(x=>x.ContactId==selectedContact&&(x.Kind=="BORROWED"||x.Kind=="REPAID")).Reverse().ToArray();int pages=Math.Max(1,records.Length);phoneRecordPage=Math.Min(phoneRecordPage,pages-1);
                m.Title=name+" · 借还记录";
                m.Body="累计已借\n"+G3Text.Money(s.Contacts.First(x=>x.ContactId==selectedContact).BorrowedLifetimeMinor)+" / "+G3Text.Money(DayRules.ContactLimit(selectedContact))+" 元\n还款不恢复额度";
                foreach(var e in records.Skip(phoneRecordPage).Take(1))
                {var loan=s.Loans.FirstOrDefault(x=>x.LoanId==e.LoanId);m.Messages.Add(new G3PhoneMessage(e.EventId,"第 "+e.Day+" 天 "+(e.Kind=="REPAID"?"已归还":"已收款")+"\n"+G3Text.Money(e.AmountMinor)+" 元\n"+G3Text.LoanDue(loan,s.DayNumber)+(loan!=null&&loan.RemainingMinor>0?"\n尚欠 "+G3Text.Money(loan.RemainingMinor):""),e.Kind=="REPAID"));}
                if(records.Length==0)m.Messages.Add(new G3PhoneMessage("empty-records","暂时没有借还记录。"));
                m.Add("phone-prev","上一页",new G3Action(G3ActionKind.PhonePage,slot:-1),phoneRecordPage>0);m.Add("phone-next","下一页",new G3Action(G3ActionKind.PhonePage,slot:1),phoneRecordPage+1<pages);return m;
            }
            if(Panel==G3Panel.PhonePacket)
            {
                m.Title=name+"的转账";
                m.Body=proposal==null?"这份转账已经处理。":G3Text.Money(proposal.Amount)+" 元\n请确认收款\n第 "+(s.DayNumber+days)+" 晚前归还\n期限 "+days+" 天 · 无息";
                bool fits=proposal!=null&&proposal.Amount<=LoanRules.RemainingLimit(s,selectedContact);
                if(!fits||!canBorrow)m.Body=G3Text.Money(proposal?.Amount??0)+" 元\n目前不能收款\n额度不足或受限\n可取消重新商量";
                m.Add("phone-claim",IsCommitting?"正在确认保存":"确认收款",new G3Action(G3ActionKind.PhoneClaim),proposal!=null&&proposal.Sent&&canBorrow&&fits&&!IsCommitting);
                m.Add("phone-cancel-request","退回这笔转账",new G3Action(G3ActionKind.PhoneCancelRequest),proposal!=null&&proposal.Sent&&!terminal);
                if(IsCommitting)m.Add("retry","确认交易",new G3Action(G3ActionKind.Retry));return m;
            }
            if(Panel==G3Panel.CustomAmount)
            {
                m.Title=customAction.Kind==G3ActionKind.Borrow?"想借多少？":"想归还多少？";m.Body="金额（元）："+(customAmount.Length==0?"0":customAmount)+"\n最多一位小数";m.Grid=true;
                foreach(var d in new[]{"1","2","3","4","5","6","7","8","9",".","0"})m.Add("digit-"+d,d,new G3Action(G3ActionKind.Digit,d));m.Add("digit-del","退格",new G3Action(G3ActionKind.Backspace));m.Add("amount-accept","选好这句话",new G3Action(G3ActionKind.AmountAccept));return m;
            }
            if(Panel==G3Panel.Confirm)
            {m.Title="确认归还";m.Body=confirmText+"\n持有 "+G3Text.Money(s.AvailableCashMinor)+" 元";m.Add("confirm-action","确认归还",new G3Action(G3ActionKind.Confirm));m.Add("cancel-action","再想想",new G3Action(G3ActionKind.Cancel));return m;}
            m.Messages.Add(new G3PhoneMessage("hello",selectedContact=="mother"?"吃饭了吗？":"店里好吗？"));
            foreach(var e in s.PhoneEvents.Where(x=>x.ContactId==selectedContact&&(x.Kind=="BORROWED"||x.Kind=="REPAID")))
            {
                if(e.Kind=="BORROWED")
                {
                    m.Messages.Add(new G3PhoneMessage("request-"+e.EventId,"借我周转一下\n"+G3Text.Money(e.AmountMinor)+" 元",true));
                    m.Messages.Add(new G3PhoneMessage("reply-"+e.EventId,(e.DueNight-e.Day)+"天后还我。"));
                    m.Messages.Add(new G3PhoneMessage(e.EventId,"转账\n"+G3Text.Money(e.AmountMinor)+" 元",false,true,"已收款 · "+G3Text.LoanDue(s.Loans.FirstOrDefault(x=>x.LoanId==e.LoanId),s.DayNumber),new G3Action(G3ActionKind.PhoneRecords),true));
                }
                m.Messages.Add(new G3PhoneMessage("receipt-"+e.EventId,(e.Kind=="REPAID"?"归还":"到账")+G3Text.Money(e.AmountMinor)+"元",true));
                if(e.Kind=="REPAID")m.Messages.Add(new G3PhoneMessage("thanks-"+e.EventId,selectedContact=="mother"?"收到了，踏实经营。":"收到了，量力而行。"));
            }
            if(proposal!=null&&proposal.Sent)
            {
                m.Messages.Add(new G3PhoneMessage("request","借我周转一下\n"+G3Text.Money(proposal.Amount)+" 元",true));
                m.Messages.Add(new G3PhoneMessage("reply",days+"天后还我。"));
                m.Messages.Add(new G3PhoneMessage("packet-pending","转账\n"+G3Text.Money(proposal.Amount)+" 元",false,true,"待收款 · 借款需归还",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.PhonePacket),true));
            }
            if(Panel==G3Panel.PhoneRequest)
            {
                m.Body=proposal==null?"请选择一句话。":"待发送：想借 "+G3Text.Money(proposal.Amount)+" 元，"+days+" 个游戏日内还你。";
                m.Add("phone-send","发送这句话",new G3Action(G3ActionKind.PhoneSend),proposal!=null&&!proposal.Sent&&canBorrow);return m;
            }
            if(Panel==G3Panel.PhoneAmount)
            {
                m.Body="想借多少？\n剩余累计可借\n"+G3Text.Money(LoanRules.RemainingLimit(s,selectedContact))+" 元";
                if(Status.StartsWith("这次",StringComparison.Ordinal))m.Body=Status;
                foreach(long amount in new[]{10000L,20000L})m.Add("borrow-"+(amount/10),"想借 "+G3Text.Money(amount)+" 元",new G3Action(G3ActionKind.Borrow,selectedContact,amount:amount),canBorrow&&amount<=LoanRules.RemainingLimit(s,selectedContact));
                m.Add("borrow-custom","说一个其他金额",new G3Action(G3ActionKind.Borrow,selectedContact,amount:-1),canBorrow);return m;
            }
            if(!stable)m.Body="先回桌面完成已选格，再收款或归还。";
            else if(Status.StartsWith("这次",StringComparison.Ordinal)||Status.StartsWith("这位",StringComparison.Ordinal)||Status.StartsWith("本次未执行",StringComparison.Ordinal))m.Body=Status;
            if(m.Body.Length>0){m.Messages.Add(new G3PhoneMessage("phone-notice",m.Body));m.Body="";}
            m.Add("phone-choose","想借点周转钱",new G3Action(G3ActionKind.PhoneChoose),canBorrow&&(proposal==null||!proposal.Sent));
            m.Add("phone-more","更多聊天操作",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.PhoneOptions));return m;
        }
    }
}

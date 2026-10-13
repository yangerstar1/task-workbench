using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Persistence;
using NUnit.Framework;

namespace Lottery.G3.EditMode.Tests
{
    public sealed class PhoneLoanTests
    {
        string root;readonly List<FileStateStore> stores=new List<FileStateStore>();
        [SetUp]public void SetUp(){root=Path.Combine(Path.GetTempPath(),"g3-phone-"+Guid.NewGuid().ToString("N"));}
        [TearDown]public void TearDown(){foreach(var store in stores)store.Dispose();stores.Clear();if(Directory.Exists(root))Directory.Delete(root,true);}
        DayGameService Open(IStoreFaultInjector fault=null){var store=new FileStateStore(root,RunFactory.Create("phone-run","phone-seed"),fault);stores.Add(store);return new DayGameService(store);}
        static void Ok(CommandResult result){Assert.That(result.Success,Is.True,result.Code);StateInvariants.Validate(result.State);}
        static void SameEconomy(RunState a,RunState b)
        {
            Assert.That(b.CashMinor,Is.EqualTo(a.CashMinor));Assert.That(b.AvailableCashMinor,Is.EqualTo(a.AvailableCashMinor));Assert.That(b.Loans.Count,Is.EqualTo(a.Loans.Count));Assert.That(b.Ledger.Count,Is.EqualTo(a.Ledger.Count));
            Assert.That(b.Contacts.Select(x=>x.BorrowedLifetimeMinor),Is.EqualTo(a.Contacts.Select(x=>x.BorrowedLifetimeMinor)));
            Assert.That(b.EconomicCounter,Is.EqualTo(a.EconomicCounter));Assert.That(b.ChallengeCounter,Is.EqualTo(a.ChallengeCounter));Assert.That(b.ShopCounter,Is.EqualTo(a.ShopCounter));Assert.That(b.DayNumber,Is.EqualTo(a.DayNumber));Assert.That(b.Phase,Is.EqualTo(a.Phase));
            if(a.CurrentTicket!=null){Assert.That(b.CurrentTicket.Id,Is.EqualTo(a.CurrentTicket.Id));Assert.That(b.CurrentTicket.Phase,Is.EqualTo(a.CurrentTicket.Phase));Assert.That(b.CurrentTicket.Scratch.ToBytes(),Is.EqualTo(a.CurrentTicket.Scratch.ToBytes()));}
        }
        [Test]public void RequestPersistsWithoutCashDebtQuotaDeadlineOrRandomChange()
        {
            var game=Open();Ok(game.BuyNumberTicket("buy",0));var before=game.Snapshot;Ok(game.RequestPhoneLoan("mother",10000,"claim","request",before.Revision));var pending=game.Snapshot;SameEconomy(before,pending);
            Assert.That(pending.Revision,Is.EqualTo(before.Revision+1));Assert.That(pending.Commands.Count,Is.EqualTo(before.Commands.Count+1));var request=pending.PhoneEvents.Single();Assert.That(request.Kind,Is.EqualTo("BORROW_REQUESTED"));Assert.That(request.DueNight,Is.Zero);
            string hash=StateCodec.ComputeHash(pending);game.Dispose();game=Open();Assert.That(StateCodec.ComputeHash(game.Snapshot),Is.EqualTo(hash));SameEconomy(before,game.Snapshot);
        }
        [Test]public void RepeatedSendAndRepeatedOpenProduceOneRequestAndOneLoan()
        {
            var game=Open();Ok(game.RequestPhoneLoan("mother",10000,"claim","request",0));Ok(game.RequestPhoneLoan("mother",10000,"claim","request",0));long revision=game.Snapshot.Revision;
            Ok(game.Borrow("mother",10000,"claim",revision));string hash=StateCodec.ComputeHash(game.Snapshot);game.Dispose();game=Open();Ok(game.Borrow("mother",10000,"claim",revision));Assert.That(StateCodec.ComputeHash(game.Snapshot),Is.EqualTo(hash));
            Assert.That(game.Snapshot.PhoneEvents.Count(x=>x.Kind=="BORROW_REQUESTED"),Is.EqualTo(1));Assert.That(game.Snapshot.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(1));Assert.That(game.Snapshot.Loans.Count,Is.EqualTo(1));Assert.That(game.Snapshot.Ledger.Count,Is.EqualTo(1));Assert.That(game.Snapshot.CashMinor,Is.EqualTo(40000));Assert.That(game.Snapshot.Loans.Single().DueNight,Is.EqualTo(7));
        }
        [Test]public void ClaimIdentityCannotBeReusedByAnotherRequestOrChangedRecipient()
        {
            var game=Open();Ok(game.RequestPhoneLoan("mother",10000,"claim","request",0));string hash=StateCodec.ComputeHash(game.Snapshot);
            Assert.That(game.RequestPhoneLoan("mother",10000,"other-claim","claim",1).Code,Is.EqualTo("PHONE_REQUEST_EXISTS"));Assert.That(game.RequestPhoneLoan("girlfriend",10000,"claim","other",1).Code,Is.EqualTo("PHONE_REQUEST_EXISTS"));Assert.That(game.Borrow("girlfriend",10000,"claim",1).Code,Is.EqualTo("PHONE_REQUEST_MISMATCH"));Assert.That(game.Borrow("mother",20000,"claim",1).Code,Is.EqualTo("PHONE_REQUEST_MISMATCH"));Assert.That(StateCodec.ComputeHash(game.Snapshot),Is.EqualTo(hash));
        }
        [Test]public void UnreservedProposalRechecksQuotaAndCanBeCancelledWithoutMoney()
        {
            var game=Open();Ok(game.RequestPhoneLoan("mother",20000,"claim","request",0));Ok(game.Borrow("mother",40000,"other-borrow",1));var before=game.Snapshot;
            Assert.That(game.Borrow("mother",20000,"claim",before.Revision).Code,Is.EqualTo("LOAN_LIMIT"));Assert.That(game.Snapshot.PhoneEvents.Count(x=>x.Kind=="BORROW_REQUESTED"),Is.EqualTo(1));
            string loanId=before.PhoneEvents.First(x=>x.Kind=="BORROW_REQUESTED").LoanId;Ok(game.CancelPhoneLoanRequest(loanId,"cancel",before.Revision));SameEconomy(before,game.Snapshot);
            Ok(game.RequestPhoneLoan("mother",10000,"replacement-claim","replacement-request",game.Snapshot.Revision));Ok(game.Borrow("mother",10000,"replacement-claim",game.Snapshot.Revision));Assert.That(LoanRules.RemainingLimit(game.Snapshot,"mother"),Is.Zero);
        }
        [Test]public void CancelledPacketCannotClaimAndCancellationReplayIsIdempotent()
        {
            var game=Open();Ok(game.RequestPhoneLoan("girlfriend",10000,"claim","request",0));string loan=game.Snapshot.PhoneEvents.Single().LoanId;Ok(game.CancelPhoneLoanRequest(loan,"cancel",1));string cancelledHash=StateCodec.ComputeHash(game.Snapshot);game.Dispose();game=Open();Assert.That(StateCodec.ComputeHash(game.Snapshot),Is.EqualTo(cancelledHash));Ok(game.CancelPhoneLoanRequest(loan,"cancel",1));
            Assert.That(game.Borrow("girlfriend",10000,"claim",2).Code,Is.EqualTo("PHONE_REQUEST_CLOSED"));Assert.That(game.Snapshot.CashMinor,Is.EqualTo(30000));Assert.That(game.Snapshot.Loans,Is.Empty);Assert.That(game.Snapshot.PhoneEvents.Count,Is.EqualTo(2));
        }
        [Test]public void ClaimedPacketCannotBeCancelledAndRepaymentKeepsLifetimeLimit()
        {
            var game=Open();Ok(game.RequestPhoneLoan("girlfriend",1234,"claim","request",0));Ok(game.Borrow("girlfriend",1234,"claim",1));string loan=game.Snapshot.Loans.Single().LoanId;
            Assert.That(game.CancelPhoneLoanRequest(loan,"cancel",2).Code,Is.EqualTo("PHONE_REQUEST_CLOSED"));Ok(game.RepayLoan("girlfriend",1234,"repay",2));Assert.That(game.Snapshot.Loans.Single().RemainingMinor,Is.Zero);Assert.That(LoanRules.RemainingLimit(game.Snapshot,"girlfriend"),Is.EqualTo(28766));Assert.That(game.Snapshot.Loans.Single().DueNight,Is.EqualTo(4));
        }
        [Test]public void ExistingLoanWithoutChatProposalRemainsCompatible()
        {
            var game=Open();Ok(game.Borrow("mother",10000,"legacy-borrow",0));string hash=StateCodec.ComputeHash(game.Snapshot);game.Dispose();game=Open();Assert.That(StateCodec.ComputeHash(game.Snapshot),Is.EqualTo(hash));Assert.That(game.Snapshot.PhoneEvents.Single().Kind,Is.EqualTo("BORROWED"));Ok(game.RepayLoan("mother",10000,"legacy-repay",game.Snapshot.Revision));
        }
        [Test]public void SendingWhileChallengeCellSelectedDoesNotRevealOrAlterTicket()
        {
            var game=Open();Ok(game.BuyChallengeTicket("buy",0));Ok(game.SelectChallengeCell(game.Snapshot.CurrentTicket.Id,0,"select",1));var before=game.Snapshot;
            Assert.That(game.RequestPhoneLoan("mother",10000,"claim","request",before.Revision).Code,Is.EqualTo("REVEAL_PENDING"));Assert.That(StateCodec.ComputeHash(game.Snapshot),Is.EqualTo(StateCodec.ComputeHash(before)));
        }
        sealed class Faults:IStoreFaultInjector
        {public StoreFaultPoint? Point;public bool BlockRecovery;public void OnPoint(StoreFaultPoint point){if(point==StoreFaultPoint.BeforeRecoveryRead&&BlockRecovery)throw new IOException("Synthetic phone recovery unavailable");if(Point==point){Point=null;throw new IOException("Synthetic phone write interruption");}}}
        public static IEnumerable<TestCaseData> AtomicWindows
        {
            get{foreach(string operation in new[]{"Request","Claim","Cancel"})foreach(var point in new[]{StoreFaultPoint.BeforeWrite,StoreFaultPoint.TempHalfWritten,StoreFaultPoint.TempFlushed,StoreFaultPoint.BeforePublish,StoreFaultPoint.AfterPublish,StoreFaultPoint.BeforeResponse})foreach(bool cold in new[]{false,true})yield return new TestCaseData(operation,point,cold).SetName("PhoneAtomic_"+operation+"_"+point+(cold?"_cold":"_live"));}
        }
        [TestCaseSource(nameof(AtomicWindows))]public void RequestAndClaimAtomicWindowsExposeOnlyConfirmedState(string operation,StoreFaultPoint point,bool cold)
        {
            bool claim=operation=="Claim",cancel=operation=="Cancel";var faults=new Faults();var game=Open(faults);if(claim||cancel)Ok(game.RequestPhoneLoan("mother",10000,"claim","request",0));var before=game.Snapshot;string beforeHash=StateCodec.ComputeHash(before);string id=claim?"claim":cancel?"cancel":"request";string loanId="phone-run:loan:claim";
            faults.Point=point;faults.BlockRecovery=cold;
            var result=cancel?game.CancelPhoneLoanRequest(loanId,"cancel",before.Revision):claim?game.Borrow("mother",10000,"claim",before.Revision):game.RequestPhoneLoan("mother",10000,"claim","request",before.Revision);
            bool published=point==StoreFaultPoint.AfterPublish||point==StoreFaultPoint.BeforeResponse;
            if(cold){Assert.That(result.CommitStatus,Is.EqualTo(CommitStatus.COMMIT_UNKNOWN));Assert.That(StateCodec.ComputeHash(result.State),Is.EqualTo(beforeHash));game.Dispose();game=Open();result=game.Recover(id);}
            Assert.That(result.CommitStatus,Is.EqualTo(published?CommitStatus.COMMITTED:CommitStatus.PROVEN_NOT_COMMITTED));
            if(!published)Assert.That(StateCodec.ComputeHash(game.Snapshot),Is.EqualTo(beforeHash));
            var retried=cancel?game.CancelPhoneLoanRequest(loanId,"cancel",before.Revision):claim?game.Borrow("mother",10000,"claim",before.Revision):game.RequestPhoneLoan("mother",10000,"claim","request",before.Revision);Ok(retried);
            Assert.That(game.Snapshot.Commands.Count(x=>x.CommandId==id),Is.EqualTo(1));Assert.That(game.Snapshot.PhoneEvents.Count(x=>x.Kind=="BORROW_REQUESTED"),Is.EqualTo(1));Assert.That(game.Snapshot.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(claim?1:0));Assert.That(game.Snapshot.PhoneEvents.Count(x=>x.Kind=="BORROW_CANCELLED"),Is.EqualTo(cancel?1:0));Assert.That(game.Snapshot.CashMinor,Is.EqualTo(claim?40000:30000));
        }
    }
}

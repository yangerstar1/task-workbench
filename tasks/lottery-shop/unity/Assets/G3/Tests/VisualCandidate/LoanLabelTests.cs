using System;
using System.IO;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
using Lottery.G3.Persistence;
using NUnit.Framework;
using UnityEngine;

namespace Lottery.G3.VisualCandidate.Tests
{
    // Targeted display-only fixture, outside the canonical G3 gate identity lists.
    // Run with -testFilter Lottery.G3.VisualCandidate.Tests.LoanLabelTests.
    public sealed class LoanLabelTests
    {
        [TestCase(0L,0L,1,"未借款")]
        [TestCase(1234L,0L,1,"已还清")]
        [TestCase(1234L,1234L,1,"123.4（第 9 晚）")]
        [TestCase(1234L,1234L,9,"123.4（第 9 晚）")]
        [TestCase(1234L,1234L,10,"123.4（第 9 晚 · 已逾期）")]
        public void DebtLabelOnlyShowsDeadlineForOutstandingDebt(long borrowed,long remaining,int day,string expected)
        {
            var s=RunFactory.Create("loan-label","loan-label-seed");s.DayNumber=day;
            s.Contacts.Single(x=>x.ContactId=="girlfriend").BorrowedLifetimeMinor=borrowed;
            if(borrowed>0)s.Loans.Add(new LoanRecord{LoanId="display-fixture",ContactId="girlfriend",BorrowedMinor=borrowed,RemainingMinor=remaining,BorrowedDay=6,DueNight=9});
            string before=StateCodec.ComputeHash(s);
            Assert.That(G3Text.ContactDebt(s,"girlfriend"),Is.EqualTo(expected));
            Assert.That(G3Text.ContactDebt(s,"girlfriend").Contains("晚"),Is.EqualTo(remaining>0));
            Assert.That(G3Text.LoanDue(s.Loans.FirstOrDefault(),day).Contains("晚"),Is.EqualTo(remaining>0));
            Assert.That(StateCodec.ComputeHash(s),Is.EqualTo(before),"Formatting must not mutate saved loans or lifetime totals");
        }
        [Test]public void MultipleLoansUseEarliestUnpaidActualDeadlineAndIgnoreSettledLoans()
        {
            var s=RunFactory.Create("loan-label","loan-label-seed");s.DayNumber=10;
            s.Loans.Add(new LoanRecord{ContactId="mother",RemainingMinor=0,DueNight=7});
            s.Loans.Add(new LoanRecord{ContactId="mother",RemainingMinor=10000,DueNight=12});
            s.Loans.Add(new LoanRecord{ContactId="mother",RemainingMinor=5000,DueNight=9});
            s.Loans.Add(new LoanRecord{ContactId="girlfriend",RemainingMinor=5000,DueNight=4});
            string before=StateCodec.ComputeHash(s);
            Assert.That(G3Text.ContactDebt(s,"mother"),Is.EqualTo("1500（最早第 9 晚 · 已逾期）"));
            Assert.That(StateCodec.ComputeHash(s),Is.EqualTo(before));
        }
        [Test]public void MissingLoanOrContactDoesNotInventDeadlineOrBorrowingHistory()
        {
            var s=RunFactory.Create("loan-label","loan-label-seed");s.Contacts.Clear();
            Assert.That(G3Text.ContactDebt(s,"mother"),Is.EqualTo("无欠款"));
            Assert.That(G3Text.LoanDue(null,1),Is.EqualTo("无欠款"));
        }
        [Test]public void BillAndPhoneProjectConfirmedRepaymentWithoutChangingHistory()
        {
            string directory=Path.Combine(Path.GetTempPath(),"g3-loan-label-"+Guid.NewGuid().ToString("N"));
            var host=new GameObject("Loan label fixture");
            try
            {
                using(var store=new FileStateStore(directory,RunFactory.Create("loan-label","loan-label-seed")))
                {
                    var game=new DayGameService(store);var presenter=host.AddComponent<G3Presenter>();presenter.Initialize(game,null);
                    presenter.OpenPanel(G3Panel.Bill);
                    StringAssert.Contains("亲友尚欠：妈妈 未借款；女友 未借款",presenter.BuildPanel().Body);
                    Assert.That(game.Borrow("mother",10000,"borrow",game.Snapshot.Revision).Success,Is.True);
                    // Refresh the presenter's confirmed snapshot through its normal initialization path.
                    presenter=host.AddComponent<G3Presenter>();presenter.Initialize(game,null);presenter.OpenPanel(G3Panel.Bill);
                    StringAssert.Contains("妈妈 1000（第 7 晚）；女友 未借款",presenter.BuildPanel().Body);
                    Assert.That(game.RepayLoan("mother",10000,"repay",game.Snapshot.Revision).Success,Is.True);
                    presenter=host.AddComponent<G3Presenter>();presenter.Initialize(game,null);string hash=StateCodec.ComputeHash(game.Snapshot);
                    presenter.OpenPanel(G3Panel.Bill);StringAssert.Contains("妈妈 已还清；女友 未借款",presenter.BuildPanel().Body);
                    presenter.OpenPanel(G3Panel.Contact);var chat=presenter.BuildPanel();
                    Assert.That(chat.Messages.Single(x=>x.Packet).Caption,Is.EqualTo("已收款 · 已还清"));
                    Assert.That(chat.Messages.Any(x=>x.Text=="6天后还我。"),Is.True,"Historical dialogue is preserved");
                    presenter.OpenPanel(G3Panel.PhoneRecords);var records=presenter.BuildPanel();
                    Assert.That(records.Messages.Single().Text,Does.Contain("已还清").And.Not.Contain("晚"));
                    Assert.That(game.Snapshot.Loans.Single().DueNight,Is.EqualTo(7),"Saved historical deadline is preserved");
                    Assert.That(StateCodec.ComputeHash(game.Snapshot),Is.EqualTo(hash));
                }
            }
            finally { UnityEngine.Object.DestroyImmediate(host);if(Directory.Exists(directory))Directory.Delete(directory,true); }
        }
    }
}

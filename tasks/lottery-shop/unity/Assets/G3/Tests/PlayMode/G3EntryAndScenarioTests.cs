using System;
using System.Collections;
using System.IO;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
using Lottery.G3.Persistence;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.TestTools;
using Object=UnityEngine.Object;

namespace Lottery.G3.PlayMode.Tests
{
    public sealed partial class G3PlayTests
    {
        IEnumerator FreshEntry(bool diagnostic)
        {
            // Dispose only the isolated setup fixture, then exercise the shipped chooser.
            // There is no injected initial state on either route below.
            ReleasePresentationTarget();Object.Destroy(app.gameObject);yield return null;testStore?.Dispose();testStore=null;
            Directory.Delete(directory,true);directory=Path.Combine(Path.GetTempPath(),"lottery-g3-entry-"+Guid.NewGuid().ToString("N"));
            app=new GameObject("G3 real new-run entry").AddComponent<G3SliceBootstrap>();app.ShowStartMenu(directory);
            Assert.That(app.Presenter,Is.Null);Assert.That(G3SliceBootstrap.HasStoredData(directory),Is.False);
            var menu=app.StartScreen;menu.PollAutomatically=false;
            var target=new RenderTexture(1280,720,24);target.Create();menu.SceneCamera.targetTexture=target;menu.Layout();
            try
            {
                InputSystem.QueueStateEvent(mouse,new MouseState{position=Vector2.zero});PumpInput();menu.PollInput();
                var point=menu.ButtonRect(diagnostic).center;
                InputSystem.QueueStateEvent(mouse,new MouseState{position=point,buttons=1});PumpInput();menu.PollInput();
                Assert.That(app.Presenter,Is.Not.Null,"The shipped start button must create the run");Assert.That(Router.AwaitingRelease,Is.True,"The entry press must not become a game action");Assert.That(State.CurrentTicket,Is.Null);
                InputSystem.QueueStateEvent(mouse,new MouseState{position=point});PumpInput();menu.PollInput();
            }
            finally{menu.SceneCamera.targetTexture=null;target.Release();Object.Destroy(target);}
            Router.PollAutomatically=false;BindPresentationTarget();Physics.SyncTransforms();yield return null;
            Router.NotifyPause(false);Router.NotifyFocus(true);MouseEvent(Vector2.zero,false);MouseEvent(Vector2.zero,false);
            Assert.That(State.FixtureLabel,Is.EqualTo(diagnostic?RunFactory.DiagnosticLabel:""));
            Assert.That(app.TryStartNew(!diagnostic,directory),Is.False,"An existing run cannot be replaced by the other entry route");
        }
        IEnumerator ReloadSameStore()
        {
            string before=StateCodec.ComputeHash(State),run=State.RunId;
            Router.NotifyPause(true);ReleasePresentationTarget();Object.Destroy(app.gameObject);yield return null;testStore?.Dispose();testStore=null;
            app=new GameObject("G3 same-store session relaunch").AddComponent<G3SliceBootstrap>();app.ShowStartMenu(directory);
            Assert.That(app.StartScreen,Is.Null,"Existing stores must bypass both new-run buttons");
            Assert.That(State.RunId,Is.EqualTo(run));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(before));
            Router.PollAutomatically=false;BindPresentationTarget();Physics.SyncTransforms();yield return null;
            Router.NotifyPause(false);Router.NotifyFocus(true);MouseEvent(Vector2.zero,false);MouseEvent(Vector2.zero,false);
            TestContext.Out.WriteLine("SIMULATED_SESSION_RELOAD, not Android Home/SIGKILL: "+run+" "+before);
        }
        void RevealNumberByPointer()
        {
            for(int i=0;i<6;i++)if(State.CurrentTicket.Scratch.CellCoverage(i)<1)ScratchCell(i);
            Assert.That(State.CurrentTicket.Phase,Is.EqualTo(TicketPhase.REVEALED_UNCLAIMED));
        }
        void Amount(string number){foreach(char c in number)Click("digit-"+c);Click("amount-accept");Confirm();}
        void Slot(int index,string item,int level)
        {
            string expected="本张"+(index+1)+" "+(item==""?"空位":G3Text.Tool(item)+" "+level);
            Assert.That(P.View.VisibleToolSlot(index),Is.EqualTo(expected));
            Assert.That(P.View.VisibleToolColor(index),Is.EqualTo(item==""?new Color(.48f,.48f,.38f):new Color(.78f,.65f,.30f)));
        }
        [UnityTest]
        public IEnumerator CurrentAndNextConfigurationKeepExactSparseSlotsAndLevelsAcrossReload()
        {
            Buy("number");BuyStock("small_prize_box");Equip("small_prize_box",2);
            for(int i=0;i<3;i++)Slot(i,"",0);
            Assert.That(G3Presenter.CurrentConfiguration(State),Is.EqualTo("1:空 / 2:空 / 3:空"));
            Assert.That(G3Presenter.NextConfiguration(State),Does.EndWith("3:"+G3Text.Tool("small_prize_box")+"1"));
            yield return ReloadSameStore();for(int i=0;i<3;i++)Slot(i,"",0);
            RevealNumberByPointer();Claim();Buy("number");Slot(0,"",0);Slot(1,"",0);Slot(2,"small_prize_box",1);
            Tool("small_prize_box");Click("upgrade-tool");Confirm();Close();Equip("small_prize_box",0);BuyStock("inspection_lamp");Equip("inspection_lamp",2);
            Slot(0,"",0);Slot(1,"",0);Slot(2,"small_prize_box",1);
            yield return ReloadSameStore();Slot(0,"",0);Slot(1,"",0);Slot(2,"small_prize_box",1);
            Click("quick");Claim();Buy("challenge");Slot(0,"small_prize_box",2);Slot(1,"",0);Slot(2,"inspection_lamp",1);
            Assert.That(State.CurrentTicket.ConfigurationSnapshot.Select(x=>x.TableSlot),Is.EqualTo(new[]{0,2}));
        }
        [UnityTest]
        public IEnumerator NormalNewRunUsesUninjectedStartupRandomStockWholeDayAndSavedResume()
        {
            yield return FreshEntry(false);
            Assert.That(State.CashMinor,Is.EqualTo(30000));Assert.That(State.CurrentTicket,Is.Null);Assert.That(State.Drawers.All(x=>x==null),Is.True);
            Assert.That(State.Stock.Count,Is.EqualTo(4));Assert.That(State.Stock.Count(x=>!x.IsConsumable),Is.EqualTo(3));
            Assert.That(State.DiagnosticChallengeArrangements,Is.Empty);string seed=State.Seed,run=State.RunId;
            string stock=StateCodec.ComputeHash(State);yield return ReloadSameStore();Assert.That(State.Seed,Is.EqualTo(seed));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stock));
            string tool=State.Stock.Where(x=>!x.IsConsumable).OrderBy(x=>x.PriceMinor).First().ItemId;BuyStock(tool);Equip(tool,2);
            Buy("number");ScratchCell(3);string ticket=State.CurrentTicket.Id;yield return ReloadSameStore();Assert.That(State.CurrentTicket.Id,Is.EqualTo(ticket));
            RevealNumberByPointer();Claim();Buy("challenge");RevealSelected(0);Claim();
            while(State.TicketsPurchasedToday<12){Buy("number");Click("quick");Claim();}
            Assert.That(State.Tickets.Count(x=>x.TicketType=="challenge"),Is.EqualTo(1));Assert.That(State.SettledTicketCount,Is.EqualTo(12));
            Click("open-phone");Click("contact-mother");long cash=State.CashMinor;Click("borrow-1000");Confirm();Click("repay-1000");Confirm();Assert.That(State.CashMinor,Is.EqualTo(cash));Close();
            Click("open-bill");Click("enter-night");Confirm();Assert.That(P.Service.PreviewNightBill().ShortfallMinor,Is.Zero);Click("pay-night");Confirm();
            Assert.That(State.Phase,Is.EqualTo(DayPhase.DAY_COMPLETE));Assert.That(State.InterestPaidMinor,Is.EqualTo(1500));
            yield return ReloadSameStore();Assert.That(State.RunId,Is.EqualTo(run));Assert.That(State.Seed,Is.EqualTo(seed));Assert.That(State.FixtureLabel,Is.Empty);Assert.That(State.Phase,Is.EqualTo(DayPhase.DAY_COMPLETE));
        }
        [UnityTest]
        public IEnumerator BoostPreselectionCancelsExplicitlyOnBackAndRestartButRulesRetainIntent()
        {
            yield return ReplaceRun(RunFactory.CreateConsumableFixture("g3-boost-ui-lifetime","boost_coupon","common"));BuyStock("boost_coupon");
            string before=StateCodec.ComputeHash(State);
            Click("open-drawer");Click("drawer-0");Assert.That(P.SelectedBoostSlot,Is.Zero);Click("ticket-rules");Close();Assert.That(P.Panel,Is.EqualTo(G3Panel.Tickets));Assert.That(P.SelectedBoostSlot,Is.Zero);
            Click("cancel-boost");Assert.That(P.SelectedBoostSlot,Is.EqualTo(-1));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(before));Close();
            Click("open-drawer");Click("drawer-0");Close();Assert.That(P.SelectedBoostSlot,Is.EqualTo(-1));
            Click("open-drawer");Click("drawer-0");KeyboardEvent(Key.Escape);KeyboardEvent();Assert.That(P.SelectedBoostSlot,Is.EqualTo(-1));
            Click("open-drawer");Click("drawer-0");Click("buy-number");Click("cancel-action");Assert.That(P.SelectedBoostSlot,Is.EqualTo(-1));Close();
            Click("open-drawer");Click("drawer-0");Click("buy-number");KeyboardEvent(Key.Escape);KeyboardEvent();Assert.That(P.SelectedBoostSlot,Is.EqualTo(-1));Close();
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(before));Buy("number");Assert.That(State.CurrentTicket.EconomicDrawCount,Is.EqualTo(1));Assert.That(State.Drawers[0],Is.Not.Null);Click("quick");
            Click("open-drawer");Click("drawer-0");Close();Click("open-phone");Close();Assert.That(P.SelectedBoostSlot,Is.EqualTo(-1));
            faults.AfterPublish=true;faults.SkipAfterPublish=1;faults.BlockRecovery=true;
            Click("claim-next");Confirm();Assert.That(P.IsCommitting,Is.True);Assert.That(State.SettledTicketCount,Is.EqualTo(1));Assert.That(State.Drawers[0],Is.Not.Null);
            Assert.That(State.ClaimBuyIntents.Single().BoostDrawerSlot,Is.EqualTo(-1));faults.BlockRecovery=false;Click("retry");
            Assert.That(P.IsCommitting,Is.False);Assert.That(State.TicketsPurchasedToday,Is.EqualTo(2));Assert.That(State.SettledTicketCount,Is.EqualTo(1));Assert.That(State.CurrentTicket.EconomicDrawCount,Is.EqualTo(1));Assert.That(State.Drawers[0],Is.Not.Null);Assert.That(P.SelectedBoostSlot,Is.EqualTo(-1));Click("quick");Claim();
            Click("open-drawer");Click("drawer-0");Click("ticket-rules");Close();Click("buy-number");Confirm();Assert.That(State.Drawers[0],Is.Null);Assert.That(State.CurrentTicket.EconomicDrawCount,Is.EqualTo(2));Assert.That(P.SelectedBoostSlot,Is.EqualTo(-1));Click("quick");Claim();
            Click("open-bill");Click("begin-closing");Confirm();Click("enter-night");Confirm();Click("pay-night");Confirm();string run=State.RunId;Click("restart");Confirm();
            Assert.That(State.RunId,Is.Not.EqualTo(run));Assert.That(P.SelectedBoostSlot,Is.EqualTo(-1));Assert.That(State.FixtureLabel,Is.Empty);Buy("number");Assert.That(State.CurrentTicket.EconomicDrawCount,Is.EqualTo(1));
        }
        [UnityTest]
        public IEnumerator NoChangeRejectionAndRecoveredReceiptHaveDistinctAccurateFeedback()
        {
            BuyStock("small_prize_box");Equip("small_prize_box",0);Tool("small_prize_box");string before=StateCodec.ComputeHash(State);Click("equip-0");
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(before));Assert.That(P.Status,Does.Contain("没有变化").And.Not.Contain("揭"));Close();
            faults.AfterPublish=true;faults.BlockRecovery=true;Click("open-tickets");Click("buy-number");Confirm();Assert.That(P.IsCommitting,Is.True);Assert.That(P.View.Surface.IsVisible,Is.False);
            faults.BlockRecovery=false;Click("retry");Assert.That(P.IsCommitting,Is.False);Assert.That(State.TicketsPurchasedToday,Is.EqualTo(1));Assert.That(P.Status,Does.Contain("上笔交易已确认").And.Contain("没有重复"));
            Click("open-shop");Click("stock-"+StockId("large_prize_stamp"));Click("stock-buy");Confirm();Close();
            // A positive-prize but still-covered number is an explicit rejected copy use.
            BuyStock("copy_paper");string unchanged=StateCodec.ComputeHash(State);Click("open-drawer");Click("drawer-0");Confirm();Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(unchanged));Assert.That(P.Status,Does.Contain("全揭后").And.Contain("没有消耗"));
            yield return null;
        }
        [UnityTest]
        public IEnumerator ExistingStoreOrIncompleteFilesCannotBeReplacedByDiagnosticStart()
        {
            string hash=StateCodec.ComputeHash(State);Assert.That(app.TryStartNew(true,directory),Is.False);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            yield return ReloadSameStore();Assert.That(app.StartScreen,Is.Null);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            string blocker=Path.Combine(Path.GetTempPath(),"lottery-g3-entry-blocked-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(blocker);var other=new GameObject("Rejected entry only").AddComponent<G3SliceBootstrap>();
            try{File.WriteAllText(Path.Combine(blocker,"intent.record"),"incomplete original evidence");Assert.That(other.TryStartNew(true,blocker),Is.False);Assert.That(other.Presenter,Is.Null);Assert.That(File.ReadAllText(Path.Combine(blocker,"intent.record")),Is.EqualTo("incomplete original evidence"));}
            finally{Object.Destroy(other.gameObject);Directory.Delete(blocker,true);}
        }
        void TraceStep(int step,long cash,string coverage="INPUT_SYSTEM_UI")
        {
            Assert.That(State.CashMinor,Is.EqualTo(cash),"Fixed scenario S"+step.ToString("000"));
            Assert.That(State.FixtureLabel,Is.EqualTo(RunFactory.DiagnosticLabel));
            TestContext.Out.WriteLine("G3_FIXED_DAY S"+step.ToString("000")+" cashMinor="+cash+" runId="+State.RunId+" revision="+State.Revision+" stateSha256="+StateCodec.ComputeHash(State)+" coverage="+coverage);
        }
        void ScratchByTouch(int core,float extent=.97f)
        {
            const int id=701;TouchEvent(id,UnityEngine.InputSystem.TouchPhase.Began,CellPoint(core,.02f,.02f));bool right=true;
            for(float v=.02f;v<.99f;v+=.1f){TouchEvent(id,UnityEngine.InputSystem.TouchPhase.Moved,CellPoint(core,right?extent:.02f,v));TouchEvent(id,UnityEngine.InputSystem.TouchPhase.Moved,CellPoint(core,right?extent:.02f,Mathf.Min(.99f,v+.1f)));right=!right;}
            TouchEvent(id,UnityEngine.InputSystem.TouchPhase.Ended,CellPoint(core,extent,.99f));PumpInput();Router.PollInput();
        }
        void RevealByTouch()
        {for(int i=0;i<6;i++)if(State.CurrentTicket.Scratch.CellCoverage(i)<1)ScratchByTouch(i);Assert.That(State.CurrentTicket.Phase,Is.EqualTo(TicketPhase.REVEALED_UNCLAIMED));}
        IEnumerator PhysicalShelf()
        {
            Close();Click("stand");Assert.That(P.Walking,Is.True);var rack=GameObject.Find("Tool shelf");
            yield return FaceTargetWithKeyboard(rack.transform.position+Vector3.up*.6f);
            var point=P.View.WorldToPresentationPoint(rack.transform.position+Vector3.up*.6f);Assert.That(P.View.WorldTarget(point)?.Panel,Is.EqualTo(G3Panel.Shop));MouseEvent(point,true);MouseEvent(point,false);Assert.That(P.Panel,Is.EqualTo(G3Panel.Shop));
        }
        [UnityTest]
        public IEnumerator FixedSeventyFiveStepDayRunsContinuouslyFromMarkedApkEntryThroughInputSystem()
        {
            // This is the frozen scenario's order and ledger, not the separate 14-frame tour.
            // Lifecycle S010/S023/S039/S075 are declared simulated session reloads here.
            // They DO NOT satisfy the distinct physical Android Home/process-kill gate.
            yield return FreshEntry(true);Assert.That(State.RunId,Is.EqualTo("g3-day-qafixture-001"));TraceStep(1,30000);
            Click("stand");var pose=P.View.Walk.SavedPosition;for(int i=0;i<12;i++){KeyboardEvent(Key.A);yield return null;}KeyboardEvent();Assert.That(Vector3.Distance(pose,P.View.Walk.SavedPosition),Is.GreaterThan(.01f));Click("stand");Assert.That(P.Walking,Is.False);TraceStep(2,30000);
            Buy("number");Assert.That(State.CurrentTicket.ConfigurationSnapshot,Is.Empty);TraceStep(3,29000);
            ScratchByTouch(3);ScratchByTouch(4);ScratchByTouch(5);Assert.That(State.CurrentTicket.Scratch.RevealedCellCount,Is.EqualTo(3));string first=State.CurrentTicket.Id;byte[] half=State.CurrentTicket.Scratch.ToBytes();TraceStep(4,29000,"SIMULATED_TOUCHSCREEN_CONFIRMED_MASK");
            yield return PhysicalShelf();TraceStep(5,29000);
            Click("stock-"+StockId("small_prize_box"));Click("stock-buy");Confirm();Assert.That(State.NextToolIds.All(x=>x==""),Is.True);Close();TraceStep(6,23000);
            Equip("small_prize_box",0);TraceStep(7,23000);
            Click("open-phone");Assert.That(P.BuildPanel().Cards.Any(x=>x.Id=="contact-mother"),Is.True);Assert.That(P.BuildPanel().Cards.Any(x=>x.Id=="contact-girlfriend"),Is.True);Close();Assert.That(State.Loans,Is.Empty);TraceStep(8,23000);
            Click("stand");Assert.That(State.CurrentTicket.Id,Is.EqualTo(first));Assert.That(State.CurrentTicket.Scratch.ToBytes(),Is.EqualTo(half));Assert.That(State.CurrentTicket.ConfigurationSnapshot,Is.Empty);for(int i=0;i<3;i++)Slot(i,"",0);TraceStep(9,23000);
            ScratchByTouch(0,.32f);yield return ReloadSameStore();Assert.That(State.CurrentTicket.Id,Is.EqualTo(first));TraceStep(10,23000,"SIMULATED_SESSION_RELOAD_NOT_DEVICE_HOME_OR_SIGKILL");
            RevealByTouch();Assert.That(State.CurrentTicket.RawPrizeMinor,Is.EqualTo(5000));TraceStep(11,23000);
            BuyStock("copy_paper");TraceStep(12,20000);
            Tool("small_prize_box");Click("upgrade-tool");Confirm();Close();Assert.That(State.CurrentTicket.ConfigurationSnapshot,Is.Empty);TraceStep(13,11000);
            Click("open-drawer");Click("drawer-0");Confirm();Assert.That(State.CurrentTicket.CopyMinor,Is.EqualTo(5000));TraceStep(14,11000);
            var claimPoint=P.View.ButtonRect("claim").center;MouseEvent(claimPoint,true);MouseEvent(claimPoint,false);TraceStep(15,21000);
            MouseEvent(claimPoint,true);MouseEvent(claimPoint,false);Assert.That(State.Settlements.Count,Is.EqualTo(1));Assert.That(State.LifetimeEffectiveTickets,Is.EqualTo(1));TraceStep(16,21000,"INPUT_SYSTEM_DUPLICATE_PRESS_UI_GUARD_NOT_SERVICE_IDEMPOTENCY_PROOF");
            Buy("number");Assert.That(State.CurrentTicket.ConfigurationSnapshot.Single().Level,Is.EqualTo(2));TraceStep(17,20000);
            RevealByTouch();TraceStep(18,20000);
            Tool("small_prize_box");Click("upgrade-tool");Confirm();Close();Assert.That(State.CurrentTicket.ConfigurationSnapshot.Single().Level,Is.EqualTo(2));TraceStep(19,6500);
            Claim();Assert.That(State.Settlements.Last().TotalMinor,Is.EqualTo(1700));TraceStep(20,8200);
            Buy("challenge");for(int visual=0;visual<8;visual++){Assert.That(P.View.Surface.CellNumberLabels[visual].Text,Is.EqualTo((visual+1).ToString()));Assert.That(P.View.Surface.Layout.Cells[visual].CoreIndex,Is.EqualTo((visual+4)%8));}TraceStep(21,7200);Select(0);string selection=State.CurrentTicket.SelectionId;TraceStep(22,7200);
            yield return ReloadSameStore();Assert.That(State.CurrentTicket.SelectedCell,Is.Zero);Assert.That(State.CurrentTicket.SelectionId,Is.EqualTo(selection));TraceStep(23,7200,"SIMULATED_SESSION_RELOAD_NOT_DEVICE_HOME");
            ScratchByTouch(0);Assert.That(State.CurrentTicket.SafeCount,Is.EqualTo(1));TraceStep(24,7200);
            var cameraPose=app.SceneCamera.transform.rotation;Click("open-shop");Assert.That(P.Walking,Is.False);Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(cameraPose));TraceStep(25,7200);
            Click("stock-"+StockId("inspection_lamp"));Click("stock-buy");Confirm();Close();TraceStep(26,3200);
            Equip("inspection_lamp",1);TraceStep(27,3200);
            string rejected=StateCodec.ComputeHash(State);Click("open-shop");Click("stock-"+StockId("large_prize_stamp"));Click("stock-buy");Confirm();Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(rejected));Assert.That(P.Status,Does.Contain("现金不足"));Close();TraceStep(28,3200);
            yield return PhysicalShelf();Assert.That(State.Stock.Single(x=>x.ItemId=="large_prize_stamp").Quantity,Is.EqualTo(1));Assert.That(State.Stock.Where(x=>x.ItemId!="large_prize_stamp").All(x=>x.Quantity==0),Is.True);Close();Click("stand");TraceStep(29,3200);
            rejected=StateCodec.ComputeHash(State);Click("open-drawer");Assert.That(P.BuildPanel().Cards.Single(x=>x.Id=="lamp").Text,Does.Contain("本张无灯"));Click("lamp");Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(rejected));Close();TraceStep(30,3200,"INPUT_SYSTEM_DISABLED_LAMP_EXPLAINS_SNAPSHOT_NO_CORE_COMMAND");
            Select(1);TraceStep(31,3200);ScratchByTouch(1);Assert.That(State.CurrentTicket.SafeCount,Is.EqualTo(2));TraceStep(32,3200);
            Click("claim");Assert.That(P.Panel,Is.EqualTo(G3Panel.Confirm));TraceStep(33,3200);Confirm();TraceStep(34,5200);
            Buy("challenge");TraceStep(35,4200);
            Click("open-drawer");Click("lamp");Assert.That(P.BuildPanel().Cards.Single(x=>x.Id=="info-target-2").Text,Is.EqualTo("格 7 · 下排3"));Click("info-target-2");Click("information-confirm");Assert.That(State.CurrentTicket.PeekedCells[2],Is.True);Assert.That(State.CurrentTicket.RevealedCells.Count(x=>x),Is.Zero);Assert.That(State.CurrentTicket.SafeCount,Is.Zero);Assert.That(State.CurrentTicket.ChallengeSafe[2],Is.False);TraceStep(36,4200);
            rejected=StateCodec.ComputeHash(State);Click("open-drawer");Assert.That(P.BuildPanel().Cards.Single(x=>x.Id=="lamp").Text,Does.Contain("已用"));Click("lamp");Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(rejected));Close();TraceStep(37,4200,"INPUT_SYSTEM_DISABLED_LAMP_EXPLAINS_USED_NO_CORE_COMMAND");
            Select(2);selection=State.CurrentTicket.SelectionId;TraceStep(38,4200);yield return ReloadSameStore();Assert.That(State.CurrentTicket.SelectedCell,Is.EqualTo(2));Assert.That(State.CurrentTicket.SelectionId,Is.EqualTo(selection));TraceStep(39,4200,"SIMULATED_SESSION_RELOAD_NOT_DEVICE_HOME");
            ScratchByTouch(2);Assert.That(State.CurrentTicket.Busted,Is.True);TraceStep(40,4200);Claim();TraceStep(41,4200);
            long[] bought={3200,2200,4700,3700,7700,6700,7700,11700},claimed={3200,5700,4700,8700,7700,8700,12700,11700};
            for(int i=0;i<8;i++){Buy("number");TraceStep(42+3*i,bought[i]);RevealByTouch();TraceStep(43+3*i,bought[i]);Claim();TraceStep(44+3*i,claimed[i]);}
            rejected=StateCodec.ComputeHash(State);Click("open-tickets");Click("buy-number");Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(rejected));Assert.That(State.Phase,Is.EqualTo(DayPhase.CLOSING_PREP));Close();TraceStep(66,11700,"INPUT_SYSTEM_DISABLED_DAY_LIMIT_NO_CORE_COMMAND");
            BuyStock("large_prize_stamp");TraceStep(67,4200);Equip("large_prize_stamp",2);TraceStep(68,4200);
            Click("open-phone");Click("principal");Amount("300");Assert.That(State.PrincipalMinor,Is.EqualTo(297000));Close();TraceStep(69,1200);
            Click("open-bill");Click("enter-night");Confirm();Assert.That(P.Service.PreviewNightBill().ShortfallMinor,Is.EqualTo(300));Assert.That(State.Phase,Is.EqualTo(DayPhase.NIGHT_BILL));TraceStep(70,1200);
            Click("bill-phone");Click("contact-mother");Click("borrow-1000");Confirm();Assert.That(State.Loans.Single().DueNight,Is.EqualTo(7));TraceStep(71,11200);
            rejected=StateCodec.ComputeHash(State);Click("borrow-custom");Amount("5000");Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(rejected));Assert.That(P.Status,Does.Contain("额度不足"));TraceStep(72,11200);
            // Custom amount confirmation returns to the amount panel. Re-open the contact,
            // never substitute a direct loan command or change the frozen ordering.
            Close();Click("open-phone");Click("contact-mother");Click("repay-custom");Amount("500");Assert.That(State.Loans.Single().RemainingMinor,Is.EqualTo(5000));Close();TraceStep(73,6200);
            Click("open-bill");Click("pay-night");var confirmPoint=P.View.ButtonRect("confirm-action").center;MouseEvent(confirmPoint,true);MouseEvent(confirmPoint,false);TraceStep(74,4700);
            MouseEvent(confirmPoint,true);MouseEvent(confirmPoint,false);yield return ReloadSameStore();TraceStep(75,4700,"INPUT_SYSTEM_DUPLICATE_PRESS_AND_SIMULATED_SESSION_RELOAD_NOT_ANDROID_SIGKILL");
            Assert.That(State.Phase,Is.EqualTo(DayPhase.DAY_COMPLETE));Assert.That(State.TicketsPurchasedToday,Is.EqualTo(12));Assert.That(State.SettledTicketCount,Is.EqualTo(12));Assert.That(State.Tickets.Count(x=>x.TicketType=="number"),Is.EqualTo(10));Assert.That(State.Ledger.Count,Is.EqualTo(29));Assert.That(State.EconomicCounter,Is.EqualTo(10));Assert.That(State.InterestPaidMinor,Is.EqualTo(1500));Assert.That(State.PrincipalMinor,Is.EqualTo(297000));Assert.That(State.Stock.All(x=>x.Quantity==0),Is.True);Assert.That(P.Service.PreviewNightBill().NextDayInterestMinor,Is.EqualTo(1485));
        }
    }
}

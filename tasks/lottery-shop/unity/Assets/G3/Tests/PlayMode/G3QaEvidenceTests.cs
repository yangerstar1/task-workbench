using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
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
        void OpenEvidenceByInput()
        {
            if(P.View.HasButton("qa-settings"))Click("qa-settings");
            else Click("open-settings");
            Assert.That(P.Panel,Is.EqualTo(G3Panel.Settings));Click("settings-evidence");
            Assert.That(P.Panel,Is.EqualTo(G3Panel.QaEvidence));
        }
        static Dictionary<string,string> EvidenceFields(string text)
        {
            return text.Split('\n').Where(x=>x.Contains("=")).ToDictionary(x=>x.Substring(0,x.IndexOf('=')),x=>x.Substring(x.IndexOf('=')+1));
        }
        static Dictionary<string,string> FileHashes(string dir)=>Directory.GetFiles(dir).Where(path=>Path.GetFileName(path)!="writer.lock").ToDictionary(path=>Path.GetFileName(path),path=>StateCodec.HashBytes(File.ReadAllBytes(path)));
        void AssertEvidenceNoWrites(string hash,long revision,int ledger,Dictionary<string,string> files)
        {
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));Assert.That(State.Revision,Is.EqualTo(revision));Assert.That(State.Ledger.Count,Is.EqualTo(ledger));
            Assert.That(FileHashes(directory),Is.EquivalentTo(files));
        }
        [UnityTest]
        public IEnumerator QaEvidenceNumberCopyPreservesConfirmedMaskConfigurationAndStore()
        {
            Buy("number");ScratchCell(3);BuyStock("small_prize_box");Equip("small_prize_box",2);
            string hash=StateCodec.ComputeHash(State),ticket=State.CurrentTicket.Id;long rev=State.Revision;int ledger=State.Ledger.Count;var files=FileHashes(directory);
            Vector3 position=app.SceneCamera.transform.position;Quaternion rotation=app.SceneCamera.transform.rotation;
            string oldClipboard=GUIUtility.systemCopyBuffer;
            try
            {
                GUIUtility.systemCopyBuffer="QA untouched clipboard sentinel";OpenEvidenceByInput();
                Assert.That(GUIUtility.systemCopyBuffer,Is.EqualTo("QA untouched clipboard sentinel"),"Opening must not touch the clipboard");
                var fields=EvidenceFields(P.EvidenceText);
                Assert.That(fields["stateStatus"],Is.EqualTo("CONFIRMED"));Assert.That(fields["confirmedStateSha256"],Is.EqualTo(hash));Assert.That(fields["confirmedStateSha256"],Is.EqualTo(testStore.ConfirmedHash));Assert.That(fields["ticketId"],Is.EqualTo(ticket));
                Assert.That(fields["maskSha256"],Is.EqualTo(StateCodec.HashBytes(State.CurrentTicket.Scratch.ToBytes())));
                Assert.That(fields["maskFullyRevealedCellCount"],Is.EqualTo("1"));Assert.That(fields["currentConfig.slot3"],Is.EqualTo("EMPTY"));Assert.That(fields["nextConfig.slot3"],Is.EqualTo("small_prize_box;level=1"));
                Assert.That(fields["sourceSha256"],Does.StartWith("UNKNOWN_"));Assert.That(fields["apkSha256"],Does.StartWith("UNKNOWN_"));
                Assert.That(fields["presentationPixels"],Is.EqualTo("1280x720"));Assert.That(fields["inputMode"],Is.EqualTo("MOUSE"));
                foreach(var key in new[]{"appVersion","buildGUID","package","snapshotUtc","deviceModel","deviceOS","systemMemoryMB","screenSafeAreaXYWH","scaledCameraPixels"})Assert.That(fields.ContainsKey(key),Is.True,key);
                Assert.That(DateTime.TryParse(fields["snapshotUtc"],null,System.Globalization.DateTimeStyles.RoundtripKind,out var stamp),Is.True);Assert.That(stamp.Kind,Is.EqualTo(DateTimeKind.Utc));
                Assert.That(P.EvidenceText,Does.Not.Contain(State.Seed));Assert.That(fields.Keys.Any(x=>x.Contains("RawPrize")||x.Contains("WinningNumber")||x.Contains("ChallengeSafe")||x=="seed"),Is.False);
                Click("evidence-copy");Assert.That(GUIUtility.systemCopyBuffer,Is.EqualTo(P.EvidenceText));
                Click("evidence-copy");KeyboardEvent(Key.Escape);KeyboardEvent();Assert.That(P.Panel,Is.EqualTo(G3Panel.Settings));Close();
                Assert.That(P.Panel,Is.EqualTo(G3Panel.None));Assert.That(app.SceneCamera.transform.position,Is.EqualTo(position));Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(rotation));
                AssertEvidenceNoWrites(hash,rev,ledger,files);
                yield return ReloadSameStore();OpenEvidenceByInput();Assert.That(EvidenceFields(P.EvidenceText)["confirmedStateSha256"],Is.EqualTo(hash));
            }
            finally{GUIUtility.systemCopyBuffer=oldClipboard;}
        }
        [UnityTest]
        public IEnumerator QaEvidenceSelectedChallengeKeepsCommitmentAndHidesUnrevealedOutcomes()
        {
            Buy("challenge");Select(0);string selection=State.CurrentTicket.SelectionId;
            Assert.That(P.View.VisibleStatus,Does.Contain("QA r"+State.Revision).And.Contain(G3QaEvidence.SelectionMarker(State.CurrentTicket)));
            string hash=StateCodec.ComputeHash(State);long rev=State.Revision;int ledger=State.Ledger.Count;var files=FileHashes(directory);byte[] mask=State.CurrentTicket.Scratch.ToBytes();
            var position=app.SceneCamera.transform.position;var rotation=app.SceneCamera.transform.rotation;string oldClipboard=GUIUtility.systemCopyBuffer;
            try
            {
                OpenEvidenceByInput();var fields=EvidenceFields(P.EvidenceText);
                Assert.That(fields["selectionId"],Is.EqualTo(selection));Assert.That(fields["selectedCoreCell"],Is.EqualTo("0"));Assert.That(fields["selectedVisibleCell"],Is.EqualTo("5"));
                Assert.That(fields["selectionMarkerSha256_16"],Is.EqualTo(G3QaEvidence.SelectionMarker(State.CurrentTicket)));
                Assert.That(fields["lockedLayoutSha256"],Does.Match("^[0-9a-f]{64}$"));string layoutHash=fields["lockedLayoutSha256"];
                Assert.That(P.EvidenceText,Does.Not.Contain(State.Seed));
                Assert.That(fields.Keys.Any(x=>x.Contains("ChallengeSafe")||x.Contains("RawPrize")||x.Contains("SafeCount")||x.Contains("Busted")||x.Contains("EconomicCounter")||x=="seed"),Is.False);
                Assert.That(fields.Keys.Any(x=>x.Contains("face")||x.Contains("outcome")||x.Contains("prize")),Is.False);
                Click("evidence-copy");Assert.That(GUIUtility.systemCopyBuffer,Is.EqualTo(P.EvidenceText));Close();Close();
                Assert.That(State.CurrentTicket.SelectedCell,Is.Zero);Assert.That(State.CurrentTicket.SelectionId,Is.EqualTo(selection));Assert.That(State.CurrentTicket.RevealedCells.All(x=>!x),Is.True);Assert.That(State.CurrentTicket.Scratch.ToBytes(),Is.EqualTo(mask));
                Assert.That(P.CanScratch,Is.True);Assert.That(Router.CapturedPointerId,Is.EqualTo(-1));AssertEvidenceNoWrites(hash,rev,ledger,files);
                Assert.That(app.SceneCamera.transform.position,Is.EqualTo(position));Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(rotation));
                yield return ReloadSameStore();OpenEvidenceByInput();var reloaded=EvidenceFields(P.EvidenceText);
                Assert.That(reloaded["selectionId"],Is.EqualTo(selection));Assert.That(reloaded["confirmedStateSha256"],Is.EqualTo(hash));Assert.That(reloaded["lockedLayoutSha256"],Is.EqualTo(layoutHash));
                Close();Close();Click("quick");Assert.That(State.CurrentTicket.RevealedCells[0],Is.True);Assert.That(State.CurrentTicket.SelectedCell,Is.EqualTo(-1));
                OpenEvidenceByInput();Assert.That(EvidenceFields(P.EvidenceText)["lockedLayoutSha256"],Is.EqualTo(layoutHash));
            }
            finally{GUIUtility.systemCopyBuffer=oldClipboard;}
        }
        [UnityTest]
        public IEnumerator QaEvidenceTouchScrollAndControlsFitBothLandscapeSafeAreasWithoutScratch()
        {
            Buy("challenge");Select(0);string hash=StateCodec.ComputeHash(State);long rev=State.Revision;int ledger=State.Ledger.Count;var files=FileHashes(directory);
            foreach(int width in new[]{1280,1600})
            {
                BindPresentationTarget(width,720);P.View.SimulatedSafeArea=new Rect(36,18,width-72,684);P.View.Layout();
                var cameraPos=app.SceneCamera.transform.position;var cameraRot=app.SceneCamera.transform.rotation;
                var point=P.View.ButtonRect("open-settings").center;TouchEvent(811,UnityEngine.InputSystem.TouchPhase.Began,point);TouchEvent(811,UnityEngine.InputSystem.TouchPhase.Ended,point);PumpInput();Router.PollInput();
                point=P.View.ButtonRect("settings-evidence").center;TouchEvent(812,UnityEngine.InputSystem.TouchPhase.Began,point);TouchEvent(812,UnityEngine.InputSystem.TouchPhase.Ended,point);PumpInput();Router.PollInput();
                Assert.That(P.Panel,Is.EqualTo(G3Panel.QaEvidence));Assert.That(EvidenceFields(P.EvidenceText)["inputMode"],Is.EqualTo("TOUCHSCREEN"));
                Assert.That(EvidenceFields(P.EvidenceText)["presentationPixels"],Is.EqualTo(width+"x720"));
                foreach(string id in new[]{"close-panel","evidence-up","evidence-down","evidence-copy"}){var r=P.View.ButtonRect(id);Assert.That(P.View.PresentationSafeArea.Contains(r.min),Is.True,id);Assert.That(P.View.PresentationSafeArea.Contains(r.max-Vector2.one*.01f),Is.True,id);Assert.That(r.height,Is.GreaterThan(70));}
                P.View.RefreshGlyphGeometry();Assert.That(P.View.AllHudLabelsFit,Is.True,string.Join("\n",P.View.OverflowingHudLabels));
                var start=P.View.EvidenceBodyRect.center;TouchEvent(813,UnityEngine.InputSystem.TouchPhase.Began,start);TouchEvent(813,UnityEngine.InputSystem.TouchPhase.Moved,start+Vector2.up*180);
                // A second finger on the background cannot become a scratch or camera gesture.
                TouchEvent(814,UnityEngine.InputSystem.TouchPhase.Began,CellPoint(1));TouchEvent(814,UnityEngine.InputSystem.TouchPhase.Moved,CellPoint(2));TouchEvent(814,UnityEngine.InputSystem.TouchPhase.Ended,CellPoint(2));
                TouchEvent(813,UnityEngine.InputSystem.TouchPhase.Ended,start+Vector2.up*180);PumpInput();Router.PollInput();Assert.That(P.EvidenceScrollOffset,Is.GreaterThan(0));
                int firstOffset=P.EvidenceScrollOffset;Click("evidence-down");Assert.That(P.EvidenceScrollOffset,Is.GreaterThan(firstOffset));
                while(P.EvidenceScrollOffset+G3Presenter.EvidencePageLines<P.EvidenceLineCount){P.View.RefreshGlyphGeometry();Assert.That(P.View.AllHudLabelsFit,Is.True,string.Join("\n",P.View.OverflowingHudLabels));Click("evidence-down");}
                P.View.RefreshGlyphGeometry();Assert.That(P.View.AllHudLabelsFit,Is.True,string.Join("\n",P.View.OverflowingHudLabels));
                Close();Close();Assert.That(Router.CapturedPointerId,Is.EqualTo(-1));Assert.That(app.SceneCamera.transform.position,Is.EqualTo(cameraPos));Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(cameraRot));AssertEvidenceNoWrites(hash,rev,ledger,files);
            }
            yield return null;
        }
        [UnityTest]
        public IEnumerator QaEvidenceUnknownCommitAndCorruptStoreWithholdStateWithoutRecoveryWrites()
        {
            faults.AfterPublish=true;faults.BlockRecovery=true;Click("open-tickets");Click("buy-number");Confirm();Assert.That(P.IsCommitting,Is.True);
            string hash=StateCodec.ComputeHash(State);long revision=State.Revision;int ledger=State.Ledger.Count;var files=FileHashes(directory);string oldClipboard=GUIUtility.systemCopyBuffer;
            try
            {
                OpenEvidenceByInput();var fields=EvidenceFields(P.EvidenceText);
                Assert.That(fields["stateStatus"],Is.EqualTo("UNAVAILABLE_COMMIT_OR_RECOVERY_PENDING"));Assert.That(fields["confirmedStateSha256"],Is.EqualTo("UNAVAILABLE"));
                Assert.That(fields.ContainsKey("runId")||fields.ContainsKey("cashMinor")||fields.ContainsKey("ledgerCount"),Is.False);Click("evidence-copy");Assert.That(GUIUtility.systemCopyBuffer,Is.EqualTo(P.EvidenceText));Close();Close();AssertEvidenceNoWrites(hash,revision,ledger,files);
                faults.BlockRecovery=false;Click("retry");Assert.That(P.IsCommitting,Is.False);Assert.That(State.TicketsPurchasedToday,Is.EqualTo(1));
                // A physically corrupt on-disk payload must retain its bytes and must
                // never expose the bootstrap's fallback new-run object as evidence.
                ReleasePresentationTarget();Object.Destroy(app.gameObject);yield return null;testStore.Dispose();testStore=null;
                var statePath=Path.Combine(directory,"state.bin");File.WriteAllText(statePath,"deliberately corrupt test fixture; preserve these bytes");
                app=new GameObject("QA corrupt-store evidence").AddComponent<G3SliceBootstrap>();app.ShowStartMenu(directory);Router.PollAutomatically=false;BindPresentationTarget();yield return null;
                Router.NotifyPause(false);Router.NotifyFocus(true);MouseEvent(Vector2.zero,false);MouseEvent(Vector2.zero,false);Assert.That(State.RecoveryRequired,Is.True);files=FileHashes(directory);
                OpenEvidenceByInput();fields=EvidenceFields(P.EvidenceText);Assert.That(fields["stateStatus"],Is.EqualTo("UNAVAILABLE_COMMIT_OR_RECOVERY_PENDING"));Assert.That(fields.ContainsKey("ticketId")||fields.ContainsKey("runId"),Is.False);Click("evidence-copy");Close();Close();
                Assert.That(FileHashes(directory),Is.EquivalentTo(files));Assert.That(File.ReadAllText(statePath),Is.EqualTo("deliberately corrupt test fixture; preserve these bytes"));
            }
            finally{GUIUtility.systemCopyBuffer=oldClipboard;}
        }
        [UnityTest]
        public IEnumerator QaEvidenceInvalidSchemaAndInvariantSnapshotsFailClosed()
        {
            var invalid=State.Copy();invalid.SchemaVersion++;var schema=G3QaEvidence.Capture(invalid,false,P.View,Router);
            Assert.That(schema.Available,Is.False);Assert.That(schema.Text,Does.Contain("stateStatus=UNAVAILABLE_INVALID_STATE").And.Not.Contain("runId="));
            invalid=State.Copy();invalid.CashMinor++;var money=G3QaEvidence.Capture(invalid,false,P.View,Router);
            Assert.That(money.Available,Is.False);Assert.That(money.Text,Does.Contain("stateDetails=WITHHELD_FAIL_CLOSED").And.Not.Contain("cashMinor="));
            Assert.That(State.CashMinor,Is.EqualTo(30000));Assert.That(State.Revision,Is.Zero);yield return null;
        }
        [UnityTest]
        public IEnumerator QaEvidenceDayEndExportsAllTwentyNineLedgerRowsAndCommandReceipts()
        {
            // Reuse the frozen 75-step input flow verbatim, then observe its final
            // persisted state. Evidence access adds no economic scenario steps.
            yield return FixedSeventyFiveStepDayRunsContinuouslyFromMarkedApkEntryThroughInputSystem();
            Assert.That(State.Ledger.Count,Is.EqualTo(29));string hash=StateCodec.ComputeHash(State);long rev=State.Revision;var files=FileHashes(directory);string oldClipboard=GUIUtility.systemCopyBuffer;
            try
            {
                OpenEvidenceByInput();Click("evidence-copy");var fields=EvidenceFields(GUIUtility.systemCopyBuffer);
                Assert.That(fields["ledgerCount"],Is.EqualTo("29"));Assert.That(fields["cashMinor"],Is.EqualTo("4700"));Assert.That(fields["dayPhase"],Is.EqualTo("DAY_COMPLETE"));
                Assert.That(fields["commandReceiptCount"],Is.EqualTo(State.Commands.Count.ToString()));
                for(int i=0;i<State.Ledger.Count;i++){var row=State.Ledger[i];Assert.That(fields["ledger."+i+".commandId"],Is.EqualTo(row.CommandId));Assert.That(fields["ledger."+i+".deltaMinor"],Is.EqualTo(row.DeltaMinor.ToString()));Assert.That(fields["ledger."+i+".balanceMinor"],Is.EqualTo(row.BalanceMinor.ToString()));}
                for(int i=0;i<State.Commands.Count;i++){var receipt=State.Commands[i];Assert.That(fields["receipt."+i+".commandId"],Is.EqualTo(receipt.CommandId));Assert.That(fields["receipt."+i+".revision"],Is.EqualTo(receipt.Revision.ToString()));Assert.That(fields["receipt."+i+".requestDigest"],Is.EqualTo(receipt.RequestDigest));}
                Assert.That(fields["rejectedCommandReceipts"],Does.StartWith("UNAVAILABLE_NOT_PERSISTED"));Close();Close();AssertEvidenceNoWrites(hash,rev,29,files);
            }
            finally{GUIUtility.systemCopyBuffer=oldClipboard;}
        }
    }
}

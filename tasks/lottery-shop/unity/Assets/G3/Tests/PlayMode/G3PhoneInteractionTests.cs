using System.Collections;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
using Lottery.G3.Rendering;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using Object=UnityEngine.Object;

namespace Lottery.G3.PlayMode.Tests
{
    // Reuses the real scene, manual Input System devices and isolated save fixture.
    // These tests require Unity; their presence is not a native execution receipt.
    public sealed partial class G3PlayTests
    {
        [UnityTest]public IEnumerator PhysicalPhoneProjectsRealGlassAndRestoresCameraWithoutChangingTicket()
        {
            Buy("number");var before=State;string hash=StateCodec.ComputeHash(before);var position=P.View.SceneCamera.transform.position;var rotation=P.View.SceneCamera.transform.rotation;float fov=P.View.SceneCamera.fieldOfView;
            SetupLocalPanel(G3Panel.Phone);Assert.That(P.View.Phone.IsFocused,Is.True);var corners=P.View.Phone.ScreenWorldCorners;Assert.That(corners.Length,Is.EqualTo(4));Assert.That(Vector3.Distance(corners[0],corners[1]),Is.GreaterThan(.09f));
            var screenCenter=corners.Aggregate(Vector3.zero,(a,b)=>a+b)/4;var camera=P.View.SceneCamera;
            Assert.That(Physics.Raycast(camera.ScreenPointToRay(camera.WorldToScreenPoint(screenCenter)),out var hit,30,~0,QueryTriggerInteraction.Ignore),Is.True);
            Assert.That(hit.collider.transform.IsChildOf(P.View.Phone.transform),Is.True,"Closest physical hit must be the phone glass, not an overlay proxy");
            MouseEvent(new Vector2(2,2),true);MouseEvent(new Vector2(2,2),false);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            Click("close-phone");Assert.That(P.Panel,Is.EqualTo(G3Panel.None));Assert.That(Vector3.Distance(camera.transform.position,position),Is.LessThan(.0001f));Assert.That(Quaternion.Angle(camera.transform.rotation,rotation),Is.LessThan(.001f));Assert.That(camera.fieldOfView,Is.EqualTo(fov));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            SetupLocalPanel(G3Panel.Phone);Click("contact-mother");Click("phone-choose");Click("borrow-1000");Click("phone-send");Click("packet-pending");
            long cashBeforeClaim=State.CashMinor;faults.AfterPublish=true;faults.BlockRecovery=true;Click("phone-claim");
            Assert.That(P.IsCommitting,Is.True);Assert.That(P.View.HasButton("retry"),Is.True,"Unknown packet commit must expose recovery on the physical screen");Assert.That(State.CashMinor,Is.EqualTo(cashBeforeClaim),"Unconfirmed save cannot show received cash");
            faults.BlockRecovery=false;Click("retry");Assert.That(P.IsCommitting,Is.False);Assert.That(State.CashMinor,Is.EqualTo(cashBeforeClaim+10000));Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(1));
            yield return ReloadSameStore();Assert.That(State.CashMinor,Is.EqualTo(cashBeforeClaim+10000));Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(1));
            SetupLocalPanel(G3Panel.Phone);Click("contact-mother");Click("phone-more");Click("phone-repay");Click("repay-1000");Click("confirm-action");Click("phone-back");
            Assert.That(P.Panel,Is.EqualTo(G3Panel.Phone));P.View.RefreshGlyphGeometry();Assert.That(P.View.AllHudLabelsFit,Is.True,string.Join("; ",P.View.OverflowingHudLabels));
            // The model owns the complete recent-message text; the narrow visible
            // contact summary deliberately elides it without changing that model.
            string fullPreview=P.BuildPanel().Cards.Single(x=>x.Id=="contact-mother").Text.Split('\n')[1];
            Assert.That(fullPreview,Is.EqualTo("收到了，谢谢。"));
            var preview=P.View.Phone.GetComponentsInChildren<BoundedGlyphLabel>().Single(x=>x.name=="contact-mother preview"&&x.gameObject.activeInHierarchy);
            AssertMeasuredPhoneSummary(preview,fullPreview);
            string afterRepayment=StateCodec.ComputeHash(State);
            string repaymentId=State.PhoneEvents.Last(x=>x.ContactId=="mother"&&x.Kind=="REPAID").EventId;
            Click("contact-mother");Assert.That(P.Panel,Is.EqualTo(G3Panel.Contact));
            Assert.That(P.BuildPanel().Messages.Single(x=>x.Id=="thanks-"+repaymentId).Text,Is.EqualTo("收到了，踏实经营。"));
            Click("phone-back");Assert.That(P.Panel,Is.EqualTo(G3Panel.Phone));
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(afterRepayment));
        }
        [UnityTest]public IEnumerator PhoneSendRequiresReleaseAndSavedPendingPacketSurvivesReload()
        {
            SetupLocalPanel(G3Panel.Phone);Click("contact-mother");Click("phone-choose");Click("borrow-1000");var before=State;var send=P.View.ButtonRect("phone-send").center;
            MouseEvent(send,true);Assert.That(State.PhoneEvents.Any(x=>x.Kind=="BORROW_REQUESTED"),Is.False);Router.CancelGesture();MouseEvent(send,false);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(StateCodec.ComputeHash(before)));
            MouseEvent(send,true);MouseEvent(new Vector2(2,2),false);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(StateCodec.ComputeHash(before)),"Release coordinates must be observed even without an intermediate mouse move");
            TouchEvent(501,UnityEngine.InputSystem.TouchPhase.Began,send);TouchEvent(501,UnityEngine.InputSystem.TouchPhase.Ended,new Vector2(2,2));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(StateCodec.ComputeHash(before)),"A touch ending off-screen cannot use the old press coordinate");
            MouseEvent(Vector2.zero,false);MouseEvent(Vector2.zero,false);
            AssertPhoneTapCancellationCases("phone-send");
            Click("phone-send");Assert.That(P.View.Phone.ChatViewportLogical.height,Is.GreaterThanOrEqualTo(500));
            CollectionAssert.IsSubsetOf(new[]{"request","reply","packet-pending"},P.View.Phone.WholeVisibleMessageIds,"Default pending conversation must show the complete request, reply and packet");
            Assert.That(P.View.HasButton("phone-more"),Is.True);Assert.That(P.View.HasButton("phone-repay"),Is.False);Assert.That(P.View.HasButton("phone-records"),Is.False,"No permanent finance button stack in the chat view");
            Assert.That(State.CashMinor,Is.EqualTo(before.CashMinor));Assert.That(State.Loans.Count,Is.EqualTo(before.Loans.Count));Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROW_REQUESTED"),Is.EqualTo(1));
            yield return ReloadSameStore();SetupLocalPanel(G3Panel.Phone);Click("contact-mother");Assert.That(P.View.HasButton("packet-pending"),Is.True);Click("packet-pending");
            AssertPhoneTapCancellationCases("phone-claim");Click("phone-claim");
            Assert.That(State.CashMinor,Is.EqualTo(before.CashMinor+10000));Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(1));Assert.That(P.View.HasButton("packet-pending"),Is.False);
            yield return ReloadSameStore();SetupLocalPanel(G3Panel.Phone);Click("contact-mother");Assert.That(P.View.HasButton("packet-pending"),Is.False);Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(1));
        }
        [UnityTest]public IEnumerator PhysicalPhoneKeysMeetProjectedReferenceTargetsAndOcclusionBlocksTap()
        {
            // The lower-left principal button projects through the non-physical ticket
            // selection volume. It must remain a world target without blocking glass.
            var roomBoxes=P.View.Environment.GetComponentsInChildren<BoxCollider>();
            var ticketTarget=roomBoxes.Single(x=>x.name=="Interaction_Tickets");
            Assert.That(ticketTarget.isTrigger,Is.True);
            Assert.That(roomBoxes.Where(x=>x.GetComponent<G3WorldTarget>()==null).All(x=>!x.isTrigger),Is.True,"Physical room boundaries must remain solid");
            foreach(string name in new[]{"Wall_West","Wall_East","Wall_North","Front_NoExit_Collider","Cashier_Base","Scratch_Desk_Top"})
                Assert.That(roomBoxes.Single(x=>x.name==name).enabled,Is.True,name+" physical collider must remain enabled");
            SetupLocalPanel(G3Panel.Phone);var principalPoint=P.View.ButtonRect("principal").center;
            var principalRay=P.View.SceneCamera.ScreenPointToRay(principalPoint);
            Assert.That(Physics.RaycastAll(principalRay,30,~0,QueryTriggerInteraction.Collide).Any(x=>x.collider==ticketTarget),Is.True,"The physics query includes authored triggers independently of player reach");
            var nearestTicket=ticketTarget.ClosestPoint(P.View.Walk.SavedPosition);var body=P.View.Walk.SavedPosition;
            Assert.That(new Vector2(nearestTicket.x-body.x,nearestTicket.z-body.z).magnitude,Is.GreaterThan(ticketTarget.GetComponent<G3WorldTarget>().ReachMeters));
            Assert.That(P.View.WorldTarget(principalPoint),Is.Null,"Local phone scenario setup does not make distant world targets reachable");
            Assert.That(Physics.Raycast(P.View.SceneCamera.ScreenPointToRay(principalPoint),out var principalHit,30,~0,QueryTriggerInteraction.Ignore),Is.True);
            Assert.That(principalHit.collider.name,Is.EqualTo("Physical portrait display 390 by 844"),"The real phone glass must be the nearest solid hit");
            string principalState=StateCodec.ComputeHash(State);Click("principal");Assert.That(P.Panel,Is.EqualTo(G3Panel.CustomAmount));
            Click("digit-3");Assert.That(P.BuildPanel().Body,Does.Contain("金额（元）：3"));
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(principalState),"Entering a principal amount alone must not transact");Close();
            SetupLocalPanel(G3Panel.Phone);Click("contact-mother");Click("phone-choose");Click("borrow-custom");float scale=P.View.PresentationSafeArea.height/720f;
            foreach(string id in new[]{"phone-back","close-phone","digit-1","digit-5","digit-0","digit-del","amount-accept"})
            {var r=P.View.ButtonRect(id);Assert.That(r.width,Is.GreaterThanOrEqualTo(96*scale-1),id+" projected width");Assert.That(r.height,Is.GreaterThanOrEqualTo(96*scale-1),id+" projected height");}
            AssertPhoneTypeSize("digit-5 label",scale);AssertPhoneTypeSize("Chosen amount",scale);
            var pixel=P.View.ButtonRect("digit-5").center;var ray=P.View.SceneCamera.ScreenPointToRay(pixel);var obstacle=GameObject.CreatePrimitive(PrimitiveType.Cube);obstacle.name="Phone occlusion test object";obstacle.transform.position=ray.GetPoint(.12f);obstacle.transform.localScale=Vector3.one*.04f;Physics.SyncTransforms();
            Assert.That(P.View.WorldTarget(pixel),Is.Null,"A nearer solid obstacle must prevent selecting any target behind it");
            string before=P.BuildPanel().Body;MouseEvent(pixel,true);MouseEvent(pixel,false);Assert.That(P.BuildPanel().Body,Is.EqualTo(before),"A closer physical blocker must prevent typing");Object.Destroy(obstacle);yield return null;Physics.SyncTransforms();Click("digit-5");Assert.That(P.BuildPanel().Body,Does.Contain("5"));
            Click("phone-back");Click("phone-more");Click("phone-records");AssertPhoneTypeSize("phone-prev label",scale);AssertPhoneTypeSize("phone-next label",scale);AssertPhoneTypeSize("Records summary",scale);
            Click("phone-back");Click("phone-choose");Click("borrow-1000");Click("phone-send");AssertPhoneTypeSize("packet-pending value line 0",scale);AssertPhoneTypeSize("packet-pending status line 0",scale);
            foreach(string id in new[]{"phone-choose","phone-more"}){var rect=P.View.ButtonRect(id);Assert.That(rect.width,Is.GreaterThanOrEqualTo(96*scale-1));Assert.That(rect.height,Is.GreaterThanOrEqualTo(96*scale-1));}
            AssertPhoneTypeSize("request text line 0",scale);AssertPhoneTypeSize("reply text line 0",scale);
            foreach(var visibleLabel in P.View.Phone.GetComponentsInChildren<BoundedGlyphLabel>().Where(x=>x.gameObject.activeInHierarchy))AssertPhoneTypeSize(visibleLabel.name,scale);
        }
        void AssertPhoneTapCancellationCases(string control)
        {
            // Real simulated input through production glass and router. No service mutation setup.
            string stateHash=StateCodec.ComputeHash(State);var rect=P.View.ButtonRect(control);var center=rect.center;
            var inside=new Vector2(rect.xMin+2,rect.center.y);var outside=new Vector2(rect.xMin-2,rect.center.y);
            Assert.That(P.View.Phone.TryConsumeUi(inside,out var intended),Is.True);Assert.That(intended.Kind,Is.Not.EqualTo(G3ActionKind.None));
            P.View.Phone.TryConsumeUi(outside,out var other);Assert.That(other.Id,Is.Not.EqualTo(intended.Id),"Counterexample must actually leave the original physical control");
            MouseEvent(inside,true);MouseEvent(outside,true);MouseEvent(inside,true);MouseEvent(inside,false);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stateHash),control+" cannot fire after leaving and returning, even below drag slop");
            TouchEvent(611,UnityEngine.InputSystem.TouchPhase.Began,inside);TouchEvent(611,UnityEngine.InputSystem.TouchPhase.Moved,outside);TouchEvent(611,UnityEngine.InputSystem.TouchPhase.Moved,inside);TouchEvent(611,UnityEngine.InputSystem.TouchPhase.Ended,inside);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stateHash),control+" touch leave-and-return must cancel");
            MouseEvent(Vector2.zero,false);MouseEvent(Vector2.zero,false);
            MouseEvent(center,true);long revision=P.View.InteractionRevision;P.Refresh();Assert.That(P.View.InteractionRevision,Is.GreaterThan(revision));MouseEvent(center,false);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stateHash),control+" same-mode refresh invalidates a press");
            TouchEvent(612,UnityEngine.InputSystem.TouchPhase.Began,center);P.Refresh();TouchEvent(612,UnityEngine.InputSystem.TouchPhase.Ended,center);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stateHash),control+" touch refresh invalidates a press");
            MouseEvent(Vector2.zero,false);MouseEvent(Vector2.zero,false);
            MouseEvent(center,true);MouseEvent(new Vector2(-1,-1),false);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stateHash),control+" End outside safe bounds must cancel without Move");
            MouseEvent(center,true);MouseEvent(center+Vector2.up*24*P.View.TouchPixelsPerDp,true);MouseEvent(center,true);MouseEvent(center,false);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stateHash),control+" drag/scroll gesture cannot become a tap on return");
            TouchEvent(613,UnityEngine.InputSystem.TouchPhase.Began,center);TouchEvent(614,UnityEngine.InputSystem.TouchPhase.Began,outside);TouchEvent(614,UnityEngine.InputSystem.TouchPhase.Ended,center);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stateHash),"A secondary finger cannot release the primary phone control");
            TouchEvent(613,UnityEngine.InputSystem.TouchPhase.Canceled,center);MouseEvent(Vector2.zero,false);MouseEvent(Vector2.zero,false);
            MouseEvent(center,true);Router.NotifyFocus(false);Router.NotifyFocus(true);MouseEvent(center,false);MouseEvent(Vector2.zero,false);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stateHash),control+" focus round-trip cancels the pending tap");
        }
        void AssertMeasuredPhoneSummary(BoundedGlyphLabel label,string full)
        {
            var font=Resources.Load<Font>("ProbeChinese");Assert.That(font,Is.Not.Null);
            Assert.That(label.EmHeight,Is.EqualTo(42));Assert.That(label.BoxSize,Is.EqualTo(new Vector2(250,100)));
            const string ellipsis="…";font.RequestCharactersInTexture(full+ellipsis,80,FontStyle.Normal);
            float Width(string value)
            {
                float sum=0;foreach(char c in value){Assert.That(font.GetCharacterInfo(c,out var glyph,80,FontStyle.Normal),Is.True,"Every summary glyph must exist");sum+=glyph.advance*42f/80f;}return sum;
            }
            string expected=full;
            if(Width(full)>248)
            {
                Assert.That(Width(ellipsis),Is.LessThanOrEqualTo(248));
                string prefix="";var elements=System.Globalization.StringInfo.GetTextElementEnumerator(full);
                while(elements.MoveNext()){string next=prefix+elements.GetTextElement();if(Width(next+ellipsis)>248)break;prefix=next;}
                expected=prefix+ellipsis;
            }
            Assert.That(label.Text,Is.EqualTo(expected));Assert.That(label.Text.Contains("\n")||label.Text.Contains("\r"),Is.False);
            Assert.That(Width(label.Text),Is.LessThanOrEqualTo(248));Assert.That(label.Fits,Is.True);Assert.That(label.MissingGlyphCount,Is.Zero);
            Assert.That(label.LocalGlyphBounds.size.y,Is.LessThanOrEqualTo(label.EmHeight*1.16f),"Visible summary remains one glyph line");
        }
        void AssertPhoneTypeSize(string labelName,float scale)
        {
            var label=P.View.Phone.GetComponentsInChildren<BoundedGlyphLabel>().Single(x=>x.name==labelName&&x.gameObject.activeInHierarchy);var a=P.View.SceneCamera.WorldToScreenPoint(label.transform.position);var b=P.View.SceneCamera.WorldToScreenPoint(label.transform.position+label.transform.up*label.EmHeight*label.transform.lossyScale.y);
            Assert.That(Vector2.Distance(a,b),Is.GreaterThanOrEqualTo(32*scale-1),labelName+" actual projected type size");
        }
    }
}

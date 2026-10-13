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
            Click("open-phone");Assert.That(P.View.Phone.IsFocused,Is.True);var corners=P.View.Phone.ScreenWorldCorners;Assert.That(corners.Length,Is.EqualTo(4));Assert.That(Vector3.Distance(corners[0],corners[1]),Is.GreaterThan(.09f));
            var screenCenter=corners.Aggregate(Vector3.zero,(a,b)=>a+b)/4;var camera=P.View.SceneCamera;
            Assert.That(Physics.Raycast(camera.ScreenPointToRay(camera.WorldToScreenPoint(screenCenter)),out var hit,30,~0,QueryTriggerInteraction.Ignore),Is.True);
            Assert.That(hit.collider.transform.IsChildOf(P.View.Phone.transform),Is.True,"Closest physical hit must be the phone glass, not an overlay proxy");
            MouseEvent(new Vector2(2,2),true);MouseEvent(new Vector2(2,2),false);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            Click("close-phone");Assert.That(P.Panel,Is.EqualTo(G3Panel.None));Assert.That(Vector3.Distance(camera.transform.position,position),Is.LessThan(.0001f));Assert.That(Quaternion.Angle(camera.transform.rotation,rotation),Is.LessThan(.001f));Assert.That(camera.fieldOfView,Is.EqualTo(fov));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            Click("open-phone");Click("contact-mother");Click("phone-choose");Click("borrow-1000");Click("phone-send");Click("packet-pending");
            long cashBeforeClaim=State.CashMinor;faults.AfterPublish=true;faults.BlockRecovery=true;Click("phone-claim");
            Assert.That(P.IsCommitting,Is.True);Assert.That(P.View.HasButton("retry"),Is.True,"Unknown packet commit must expose recovery on the physical screen");Assert.That(State.CashMinor,Is.EqualTo(cashBeforeClaim),"Unconfirmed save cannot show received cash");
            faults.BlockRecovery=false;Click("retry");Assert.That(P.IsCommitting,Is.False);Assert.That(State.CashMinor,Is.EqualTo(cashBeforeClaim+10000));Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(1));
            yield return ReloadSameStore();Assert.That(State.CashMinor,Is.EqualTo(cashBeforeClaim+10000));Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(1));
            Click("open-phone");Click("contact-mother");Click("phone-more");Click("phone-repay");Click("repay-1000");Click("confirm-action");Click("phone-back");
            Assert.That(P.Panel,Is.EqualTo(G3Panel.Phone));P.View.RefreshGlyphGeometry();Assert.That(P.View.AllHudLabelsFit,Is.True,string.Join("; ",P.View.OverflowingHudLabels));
            Assert.That(P.View.Phone.GetComponentsInChildren<BoundedGlyphLabel>().Single(x=>x.name=="contact-mother preview"&&x.gameObject.activeInHierarchy).Text,Is.EqualTo("收到了，谢谢。"));
        }
        [UnityTest]public IEnumerator PhoneSendRequiresReleaseAndSavedPendingPacketSurvivesReload()
        {
            Click("open-phone");Click("contact-mother");Click("phone-choose");Click("borrow-1000");var before=State;var send=P.View.ButtonRect("phone-send").center;
            MouseEvent(send,true);Assert.That(State.PhoneEvents.Any(x=>x.Kind=="BORROW_REQUESTED"),Is.False);Router.CancelGesture();MouseEvent(send,false);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(StateCodec.ComputeHash(before)));
            MouseEvent(send,true);MouseEvent(new Vector2(2,2),false);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(StateCodec.ComputeHash(before)),"Release coordinates must be observed even without an intermediate mouse move");
            TouchEvent(501,UnityEngine.InputSystem.TouchPhase.Began,send);TouchEvent(501,UnityEngine.InputSystem.TouchPhase.Ended,new Vector2(2,2));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(StateCodec.ComputeHash(before)),"A touch ending off-screen cannot use the old press coordinate");
            MouseEvent(Vector2.zero,false);MouseEvent(Vector2.zero,false);
            Click("phone-send");Assert.That(P.View.Phone.ChatViewportLogical.height,Is.GreaterThanOrEqualTo(500));
            CollectionAssert.IsSubsetOf(new[]{"request","reply","packet-pending"},P.View.Phone.WholeVisibleMessageIds,"Default pending conversation must show the complete request, reply and packet");
            Assert.That(P.View.HasButton("phone-more"),Is.True);Assert.That(P.View.HasButton("phone-repay"),Is.False);Assert.That(P.View.HasButton("phone-records"),Is.False,"No permanent finance button stack in the chat view");
            Assert.That(State.CashMinor,Is.EqualTo(before.CashMinor));Assert.That(State.Loans.Count,Is.EqualTo(before.Loans.Count));Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROW_REQUESTED"),Is.EqualTo(1));
            yield return ReloadSameStore();Click("open-phone");Click("contact-mother");Assert.That(P.View.HasButton("packet-pending"),Is.True);Click("packet-pending");Click("phone-claim");
            Assert.That(State.CashMinor,Is.EqualTo(before.CashMinor+10000));Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(1));Assert.That(P.View.HasButton("packet-pending"),Is.False);
            yield return ReloadSameStore();Click("open-phone");Click("contact-mother");Assert.That(P.View.HasButton("packet-pending"),Is.False);Assert.That(State.PhoneEvents.Count(x=>x.Kind=="BORROWED"),Is.EqualTo(1));
        }
        [UnityTest]public IEnumerator PhysicalPhoneKeysMeetProjectedReferenceTargetsAndOcclusionBlocksTap()
        {
            Click("open-phone");Click("contact-mother");Click("phone-choose");Click("borrow-custom");float scale=P.View.PresentationSafeArea.height/720f;
            foreach(string id in new[]{"phone-back","close-phone","digit-1","digit-5","digit-0","digit-del","amount-accept"})
            {var r=P.View.ButtonRect(id);Assert.That(r.width,Is.GreaterThanOrEqualTo(96*scale-1),id+" projected width");Assert.That(r.height,Is.GreaterThanOrEqualTo(96*scale-1),id+" projected height");}
            AssertPhoneTypeSize("digit-5 label",scale);AssertPhoneTypeSize("Chosen amount",scale);
            var pixel=P.View.ButtonRect("digit-5").center;var ray=P.View.SceneCamera.ScreenPointToRay(pixel);var obstacle=GameObject.CreatePrimitive(PrimitiveType.Cube);obstacle.name="Phone occlusion test object";obstacle.transform.position=ray.GetPoint(.12f);obstacle.transform.localScale=Vector3.one*.04f;Physics.SyncTransforms();
            string before=P.BuildPanel().Body;MouseEvent(pixel,true);MouseEvent(pixel,false);Assert.That(P.BuildPanel().Body,Is.EqualTo(before),"A closer physical blocker must prevent typing");Object.Destroy(obstacle);yield return null;Physics.SyncTransforms();Click("digit-5");Assert.That(P.BuildPanel().Body,Does.Contain("5"));
            Click("phone-back");Click("phone-more");Click("phone-records");AssertPhoneTypeSize("phone-prev label",scale);AssertPhoneTypeSize("phone-next label",scale);AssertPhoneTypeSize("Records summary",scale);
            Click("phone-back");Click("phone-choose");Click("borrow-1000");Click("phone-send");AssertPhoneTypeSize("packet-pending value line 0",scale);AssertPhoneTypeSize("packet-pending status line 0",scale);
            foreach(string id in new[]{"phone-choose","phone-more"}){var rect=P.View.ButtonRect(id);Assert.That(rect.width,Is.GreaterThanOrEqualTo(96*scale-1));Assert.That(rect.height,Is.GreaterThanOrEqualTo(96*scale-1));}
            AssertPhoneTypeSize("request text line 0",scale);AssertPhoneTypeSize("reply text line 0",scale);
            foreach(var visibleLabel in P.View.Phone.GetComponentsInChildren<BoundedGlyphLabel>().Where(x=>x.gameObject.activeInHierarchy))AssertPhoneTypeSize(visibleLabel.name,scale);
        }
        void AssertPhoneTypeSize(string labelName,float scale)
        {
            var label=P.View.Phone.GetComponentsInChildren<BoundedGlyphLabel>().Single(x=>x.name==labelName&&x.gameObject.activeInHierarchy);var a=P.View.SceneCamera.WorldToScreenPoint(label.transform.position);var b=P.View.SceneCamera.WorldToScreenPoint(label.transform.position+label.transform.up*label.EmHeight*label.transform.lossyScale.y);
            Assert.That(Vector2.Distance(a,b),Is.GreaterThanOrEqualTo(32*scale-1),labelName+" actual projected type size");
        }
    }
}

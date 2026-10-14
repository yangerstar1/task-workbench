using System.Collections;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.TestTools;
using IPhase=UnityEngine.InputSystem.TouchPhase;

namespace Lottery.G3.PlayMode.Tests
{
    public sealed partial class G3PlayTests
    {
        // WORLD_INPUT_V2. Only DeclareWorldSpawn sets a pose, before a route starts.
        // Every subsequent displacement/look/activation is a real simulated touch event.
        void PrepareWorldInputViewport()
        {
            BindPresentationTarget(640,360);
            Assert.That(P.View.PresentationWidth,Is.EqualTo(640));Assert.That(P.View.PresentationHeight,Is.EqualTo(360));
            Assert.That(app.SceneCamera.aspect,Is.EqualTo(16f/9f).Within(.00001f));
            Assert.That(P.View.HasMeasuredAndroidDensity,Is.False,"This Editor fixture uses the declared fallback, not measured Android dp");
            Assert.That(P.View.TouchPixelsPerDp,Is.EqualTo(1));
            TestContext.Out.WriteLine("WORLD_INPUT_V2 640x360 SIMULATED_EDITOR_FALLBACK_DP NOT_ANDROID NOT_ORIGINAL_RESOLUTION_VISUAL_EVIDENCE");
        }
        void DeclareWorldSpawn(Vector3 position,float yaw)
        {
            Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            P.Execute(new G3Action(G3ActionKind.Stand));
            P.View.Walk.SetPose(position,yaw);Physics.SyncTransforms();
        }
        IEnumerator WorldNeutral()
        {yield return null;PumpInput();Router.PollInput();Assert.That(Router.AwaitingRelease,Is.False);}
        void WorldTouches(params TouchState[] states)
        {foreach(var state in states)UnityEngine.InputSystem.InputSystem.QueueStateEvent(touch,state);PumpInput();Router.PollInput();}
        static TouchState Finger(int id,IPhase phase,Vector2 point)=>new TouchState{touchId=id,phase=phase,position=point,pressure=phase==IPhase.Ended||phase==IPhase.Canceled?0:1};
        Vector2 LookOrigin=>new Vector2(P.View.PresentationSafeArea.xMin+P.View.PresentationSafeArea.width*.73f,P.View.PresentationSafeArea.center.y);
        IEnumerator TouchFace(Vector3 target)
        {
            yield return WorldNeutral();
            for(int i=0;i<24;i++)
            {
                Vector3 d=target-app.SceneCamera.transform.position;
                float desiredYaw=Mathf.Atan2(d.x,d.z)*Mathf.Rad2Deg,desiredPitch=-Mathf.Atan2(d.y,new Vector2(d.x,d.z).magnitude)*Mathf.Rad2Deg;
                float yaw=Mathf.DeltaAngle(app.SceneCamera.transform.eulerAngles.y,desiredYaw),pitch=Mathf.DeltaAngle(app.SceneCamera.transform.eulerAngles.x,desiredPitch);
                if(Mathf.Abs(yaw)<3&&Mathf.Abs(pitch)<3)yield break;
                Vector2 start=LookOrigin,delta=new Vector2(Mathf.Clamp(yaw,-25,25)/.26f,-Mathf.Clamp(pitch,-15,15)/.20f)*P.View.TouchPixelsPerDp;
                Vector2 end=start+delta;Assert.That(P.View.IsSafePointer(end),Is.True);
                WorldTouches(Finger(902,IPhase.Began,start));yield return null;
                WorldTouches(Finger(902,IPhase.Moved,end));yield return null;
                WorldTouches(Finger(902,IPhase.Ended,end));yield return WorldNeutral();
            }
            Assert.Fail("Real LOOK touch did not face the declared world target");
        }
        IEnumerator TouchWalkTo(Vector3 destination,bool proveConcurrentLook=false)
        {
            yield return WorldNeutral();Vector3 origin=P.View.Walk.SavedPosition;float started=Time.realtimeSinceStartup;
            Vector2 move=P.View.JoystickRect.center,look=LookOrigin;
            WorldTouches(Finger(901,IPhase.Began,move));
            if(proveConcurrentLook)WorldTouches(Finger(902,IPhase.Began,look));
            bool movedLook=false;Quaternion initialLook=app.SceneCamera.transform.rotation;
            while(Vector2.Distance(new Vector2(P.View.Walk.SavedPosition.x,P.View.Walk.SavedPosition.z),new Vector2(destination.x,destination.z))>.09f)
            {
                Assert.That(Time.realtimeSinceStartup-started,Is.LessThan(45),"Real joystick route stalled; never teleport or extend the native budget");
                Vector3 world=destination-P.View.Walk.SavedPosition;world.y=0;
                Vector3 local=Quaternion.Inverse(Quaternion.Euler(0,app.SceneCamera.transform.eulerAngles.y,0))*world.normalized;
                Vector2 point=move+new Vector2(local.x,local.z)*P.View.JoystickRect.width*.3f;
                yield return null;
                if(proveConcurrentLook&&!movedLook)
                {
                    look+=Vector2.right*12*P.View.TouchPixelsPerDp;
                    WorldTouches(Finger(901,IPhase.Moved,point),Finger(902,IPhase.Moved,look));
                    Assert.That(Router.MoveTouchId,Is.EqualTo(901));Assert.That(Router.LookTouchId,Is.EqualTo(902));Assert.That(Quaternion.Angle(initialLook,app.SceneCamera.transform.rotation),Is.GreaterThan(1));movedLook=true;
                }
                else WorldTouches(Finger(901,IPhase.Moved,point));
            }
            WorldTouches(Finger(901,IPhase.Ended,move));if(proveConcurrentLook)WorldTouches(Finger(902,IPhase.Ended,look));
            yield return WorldNeutral();Assert.That(Vector3.Distance(P.View.Walk.SavedPosition,origin),Is.GreaterThan(.05f));
        }
        IEnumerator TouchUiRelease(string id)
        {
            yield return WorldNeutral();Assert.That(P.View.HasButton(id),Is.True);
            var point=P.View.ButtonRect(id).center;WorldTouches(Finger(909,IPhase.Began,point));
            WorldTouches(Finger(909,IPhase.Ended,point));yield return WorldNeutral();
        }
        IEnumerator TouchWorldOpen(Vector3 target,G3Panel panel,bool table=false)
        {
            yield return TouchFace(target);Physics.SyncTransforms();var pixel=P.View.WorldToPresentationPoint(target);
            Assert.That(P.View.IsSafePointer(pixel),Is.True);var physical=P.View.WorldTarget(pixel);Assert.That(physical,Is.Not.Null,"Nearest unobstructed collider must be a reachable physical target. "+WorldRayDiagnostic(target,pixel));
            Assert.That(physical.IsTable,Is.EqualTo(table));if(!table)Assert.That(physical.Panel,Is.EqualTo(panel));
            var before=P.Panel;WorldTouches(Finger(903,IPhase.Began,pixel));Assert.That(P.Panel,Is.EqualTo(before),"Press is not activation");
            WorldTouches(Finger(903,IPhase.Ended,pixel));Assert.That(P.Panel,Is.EqualTo(panel));
            if(table)Assert.That(P.Walking,Is.False);yield return WorldNeutral();
        }
        // Fixed source-owned numeric observations only; not a replacement for the assertion.
        string WorldRayDiagnostic(Vector3 target,Vector2 pixel)
        {
            var ray=app.SceneCamera.ViewportPointToRay(new Vector3(pixel.x/P.View.PresentationWidth,pixel.y/P.View.PresentationHeight,0));
            bool hitAny=Physics.Raycast(ray,out RaycastHit hit,5,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Collide);
            var physical=hitAny?hit.collider.GetComponentInParent<G3WorldTarget>():null;
            string kind=!hitAny?"NONE":hit.collider is CharacterController?"CHARACTER_CONTROLLER":physical!=null?"WORLD_TARGET":"UNTARGETED_COLLIDER";
            var body=P.View.Walk.SavedPosition;
            float reach=hitAny?new Vector2(hit.point.x-body.x,hit.point.z-body.z).magnitude:-1;
            return "WORLD_RAY_V1 kind="+kind+" trigger="+(hitAny&&hit.collider.isTrigger)+" ownBody="+(hitAny&&hit.collider.transform.IsChildOf(P.View.Walk.transform))+
                " environment="+(hitAny&&hit.collider.transform.IsChildOf(P.View.Environment.transform))+" hitDistance="+(hitAny?hit.distance:-1).ToString("F4",System.Globalization.CultureInfo.InvariantCulture)+
                " horizontalReach="+reach.ToString("F4",System.Globalization.CultureInfo.InvariantCulture)+" body="+body.ToString("F4")+" camera="+app.SceneCamera.transform.position.ToString("F4")+
                " target="+target.ToString("F4")+" pixel="+pixel.ToString("F4")+" rayOrigin="+ray.origin.ToString("F4")+" rayDirection="+ray.direction.ToString("F4");
        }
        [UnityTest,Timeout(180000)]
        public IEnumerator WorldInputEntryToTicketRackAndTableUsesConcurrentMoveLookAndRelease()
        {
            PrepareWorldInputViewport();
            DeclareWorldSpawn(P.View.Environment.EntryPosition,P.View.Environment.EntryYaw);
            yield return TouchWalkTo(new Vector3(.65f,0,.25f),true);
            yield return TouchWorldOpen(new Vector3(1.64f,.91f,-.32f),G3Panel.Tickets);
            Click("buy-number");Confirm();Assert.That(State.CurrentTicket.TicketType,Is.EqualTo("number"));string hash=StateCodec.ComputeHash(State);Close();
            yield return TouchWalkTo(new Vector3(-.65f,0,.90f));
            yield return TouchWorldOpen(new Vector3(-1.35f,.85f,.45f),G3Panel.None,true);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));ScratchCell(3,.3f);Assert.That(State.CurrentTicket.Scratch.CellCoverage(3),Is.GreaterThan(0));
        }
        [UnityTest,Timeout(180000)]
        public IEnumerator WorldInputTableToPhysicalPhoneAndBackPreservesTicketAndCamera()
        {
            PrepareWorldInputViewport();
            // Explicit local transaction setup precedes the real spatial route.
            Buy("number");ScratchCell(3,.3f);string hash=StateCodec.ComputeHash(State);
            yield return TouchUiRelease("stand");
            yield return TouchWalkTo(new Vector3(.15f,0,.30f));yield return TouchWalkTo(new Vector3(1.20f,0,-.85f),true);
            var phone=P.View.Phone.ScreenWorldCorners;Vector3 phoneCenter=phone.Aggregate(Vector3.zero,(a,b)=>a+b)/phone.Length;
            yield return TouchFace(phoneCenter);Vector3 pos=app.SceneCamera.transform.position;Quaternion rot=app.SceneCamera.transform.rotation;
            yield return TouchWorldOpen(phoneCenter,G3Panel.Phone);Assert.That(P.View.Phone.IsFocused,Is.True);
            yield return TouchUiRelease("close-phone");Assert.That(P.View.Phone.IsFocused,Is.False);Assert.That(app.SceneCamera.transform.position,Is.EqualTo(pos));Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(rot));
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            yield return TouchWalkTo(new Vector3(.15f,0,.30f));yield return TouchWalkTo(new Vector3(-.65f,0,.90f));
            yield return TouchWorldOpen(new Vector3(-1.35f,.85f,.45f),G3Panel.None,true);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
        }
        [UnityTest,Timeout(180000)]
        public IEnumerator WorldInputStorageToolShelfDrawerAndPointerOwnershipArePhysical()
        {
            PrepareWorldInputViewport();
            // Declared local projection reference only, before the spatial route begins.
            SetupLocalPanel(G3Panel.Shop);string localStock=P.BuildPanel().Body;Close();
            string hash=StateCodec.ComputeHash(State);DeclareWorldSpawn(P.View.Environment.EntryPosition,P.View.Environment.EntryYaw);
            yield return TouchWalkTo(new Vector3(1.35f,0,1.40f),true);
            yield return TouchWorldOpen(new Vector3(2.345f,.75f,2.02f),G3Panel.Inventory);Close();
            yield return TouchWalkTo(new Vector3(.25f,0,.8f));yield return TouchWalkTo(new Vector3(-.08f,0,-1.20f));
            yield return TouchWorldOpen(P.View.Environment.ShelfTargetPosition,G3Panel.Shop);
            Assert.That(P.BuildPanel().Cards.Any(x=>x.Id.StartsWith("stock-")),Is.True);string physicalStock=P.BuildPanel().Body;Close();
            // Compare the public service projection without changing navigation state.
            Assert.That(State.Stock.Count,Is.GreaterThan(0));Assert.That(physicalStock,Is.EqualTo(localStock),"Physical entry and declared local projection show the identical stock");
            yield return TouchWalkTo(new Vector3(-.24f,0,-.08f));
            yield return TouchWorldOpen(new Vector3(-1.17f,.65f,0),G3Panel.Drawer);Close();
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            yield return WorldPointerRejectionChecks(new Vector3(-1.17f,.65f,0));
        }
        IEnumerator WorldPointerRejectionChecks(Vector3 target)
        {
            yield return TouchFace(target);var pixel=P.View.WorldToPresentationPoint(target);Assert.That(P.View.WorldTarget(pixel),Is.Not.Null);
            WorldTouches(Finger(903,IPhase.Began,pixel));WorldTouches(Finger(903,IPhase.Canceled,pixel));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));yield return WorldNeutral();
            WorldTouches(Finger(903,IPhase.Began,pixel));WorldTouches(Finger(903,IPhase.Ended,pixel+Vector2.right*9*P.View.TouchPixelsPerDp));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));yield return WorldNeutral();
            WorldTouches(Finger(903,IPhase.Began,pixel));WorldTouches(Finger(903,IPhase.Ended,new Vector2(-1,pixel.y)));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));yield return WorldNeutral();
            Assert.That(P.View.WorldTarget(new Vector2(-1,pixel.y)),Is.Null);Assert.That(P.View.WorldTarget(new Vector2(P.View.PresentationWidth,pixel.y)),Is.Null);
            // Two occupied movement roles cannot allow a third finger to open a world panel.
            var move=P.View.JoystickRect.center;var look=LookOrigin;
            WorldTouches(Finger(901,IPhase.Began,move),Finger(902,IPhase.Began,look));
            WorldTouches(Finger(904,IPhase.Began,pixel));WorldTouches(Finger(904,IPhase.Ended,pixel));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            WorldTouches(Finger(901,IPhase.Canceled,move),Finger(902,IPhase.Canceled,look));yield return WorldNeutral();
            // Settings is the one allowed third-finger safety action while MOVE + LOOK own their IDs.
            var safety=P.View.ButtonRect("open-settings").center;var stablePosition=P.View.Walk.SavedPosition;var stableRotation=app.SceneCamera.transform.rotation;
            string stableState=StateCodec.ComputeHash(State);
            WorldTouches(Finger(901,IPhase.Began,move),Finger(902,IPhase.Began,look));
            Assert.That(Router.MoveTouchId,Is.EqualTo(901));Assert.That(Router.LookTouchId,Is.EqualTo(902));
            WorldTouches(Finger(907,IPhase.Began,safety));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            WorldTouches(Finger(907,IPhase.Ended,safety));Assert.That(P.Panel,Is.EqualTo(G3Panel.Settings));
            WorldTouches(Finger(901,IPhase.Ended,move),Finger(902,IPhase.Ended,look));yield return WorldNeutral();
            Assert.That(Router.MoveTouchId,Is.EqualTo(-1));Assert.That(Router.LookTouchId,Is.EqualTo(-1));
            Assert.That(P.View.Walk.SavedPosition,Is.EqualTo(stablePosition));Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(stableRotation));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stableState));
            Close();yield return WorldNeutral();yield return null;Router.PollInput();Assert.That(P.View.Walk.SavedPosition,Is.EqualTo(stablePosition));
            // Generic non-continuous UI executes only at same-control release.
            var settings=P.View.ButtonRect("open-settings").center;
            WorldTouches(Finger(906,IPhase.Began,settings));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            WorldTouches(Finger(906,IPhase.Ended,settings+Vector2.down*20*P.View.TouchPixelsPerDp));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));yield return WorldNeutral();
            WorldTouches(Finger(906,IPhase.Began,settings));P.Refresh();
            WorldTouches(Finger(906,IPhase.Ended,settings));Assert.That(P.Panel,Is.EqualTo(G3Panel.None),"A refreshed layout invalidates the pending control");yield return WorldNeutral();
            WorldTouches(Finger(906,IPhase.Began,settings));WorldTouches(Finger(906,IPhase.Ended,settings));Assert.That(P.Panel,Is.EqualTo(G3Panel.Settings));
            string unchanged=StateCodec.ComputeHash(State);WorldTouches(Finger(906,IPhase.Ended,settings));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(unchanged));Close();yield return WorldNeutral();
            // An actual solid collider nearer than the target must block the production ray.
            var blocker=new GameObject("Declared temporary occlusion test wall");
            try
            {
                blocker.transform.position=(app.SceneCamera.transform.position+target)*.5f;blocker.transform.rotation=Quaternion.LookRotation(target-app.SceneCamera.transform.position);
                blocker.AddComponent<BoxCollider>().size=new Vector3(.7f,.7f,.05f);Physics.SyncTransforms();Assert.That(P.View.WorldTarget(pixel),Is.Null);
                WorldTouches(Finger(905,IPhase.Began,pixel));WorldTouches(Finger(905,IPhase.Ended,pixel));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            }
            finally{Object.Destroy(blocker);}yield return WorldNeutral();
        }
    }
}

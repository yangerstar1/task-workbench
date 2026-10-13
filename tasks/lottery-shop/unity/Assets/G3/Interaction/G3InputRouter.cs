using Lottery.G3.Rendering;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.EnhancedTouch;
using ETouch=UnityEngine.InputSystem.EnhancedTouch.Touch;
using IPhase=UnityEngine.InputSystem.TouchPhase;

namespace Lottery.G3.Interaction
{
    public sealed class G3InputRouter : MonoBehaviour
    {
        static bool costEnabled,costOverflow;static long pollCount,pollTicks,pollMax,frameSamples,frameTicks,frameMax,lastFrameTick;static int costFrame=-1;
        public static void BeginCostObservation(){costEnabled=true;costOverflow=false;pollCount=pollTicks=pollMax=frameSamples=frameTicks=frameMax=lastFrameTick=0;costFrame=-1;}
        public static void EndCostObservation(){costEnabled=false;}
        public static long[] CostObservation()=>new[]{pollCount,pollTicks,pollMax,frameSamples,frameTicks,frameMax,costOverflow?1L:0L};
        static void CostAdd(ref long value,long add,long limit){if(add<0||value>limit-add){value=limit;costOverflow=true;}else value+=add;}
        static void ObserveInputFrame(long tick)
        {if(costFrame==Time.frameCount)return;if(costFrame>=0){long delta=tick-lastFrameTick;CostAdd(ref frameSamples,1,1000000);CostAdd(ref frameTicks,delta,1000000000000000L);if(delta<0||delta>1000000000000000L)costOverflow=true;frameMax=System.Math.Max(frameMax,System.Math.Max(0,System.Math.Min(delta,1000000000000000L)));}costFrame=Time.frameCount;lastFrameTick=tick;}
        static void PollCostEnd(long start)
        {if(!costEnabled)return;long ticks=System.Diagnostics.Stopwatch.GetTimestamp()-start;CostAdd(ref pollCount,1,1000000);CostAdd(ref pollTicks,ticks,1000000000000000L);if(ticks<0||ticks>1000000000000000L)costOverflow=true;pollMax=System.Math.Max(pollMax,System.Math.Max(0,System.Math.Min(ticks,1000000000000000L)));}
        int moveTouch=-1,lookTouch=-1;Vector2 moveOrigin,lookStart,lookLast;bool lookDragged;G3WorldTarget touchTarget,worldPressed;Vector2 worldStart;bool worldDragged;G3Mode priorMode=G3Mode.TABLE_SCRATCH;
        public int MoveTouchId=>moveTouch;public int LookTouchId=>lookTouch;
        G3Action pendingUi;string pendingControl="";Vector2 uiStart;bool uiDragged;long pendingUiRevision;G3Mode pendingUiMode;
        G3Presenter presenter;G3SceneView view;RegionPointerTracker tracker;string layoutId="";
        int captured=-1;bool capturedTouch,uiCapture,touchGesture,requireRelease,focused=true,paused;
        Vector2 previous;G3Action held;float lastPoll,evidenceDrag;bool evidenceScrollCapture;
        public string LastInputSource {get;private set;}="NONE_OBSERVED";
        public bool PollAutomatically {get;set;}=true;
        public int CapturedPointerId=>captured;
        public bool IsFocused=>focused&&!paused;
        public bool AwaitingRelease=>requireRelease;
        public G3Mode Mode=>presenter==null?G3Mode.TABLE_SCRATCH:presenter.Mode;
        public string DiagnosticState=>"mode="+Mode+",capture="+captured+",release="+requireRelease+",focus="+IsFocused+",touches="+ETouch.activeTouches.Count+",viewport="+(view==null?"none":view.PresentationWidth+"x"+view.PresentationHeight);
        public void Initialize(G3Presenter owner,G3SceneView scene){presenter=owner;view=scene;}
        void OnEnable(){EnhancedTouchSupport.Enable();}
        void OnDisable(){CancelGesture();EnhancedTouchSupport.Disable();}
        void Update(){if(PollAutomatically)PollInput();}
        public void PollInput()
        {
            if(!costEnabled){PollInputObserved();return;}
            long start=System.Diagnostics.Stopwatch.GetTimestamp();ObserveInputFrame(start);
            try{PollInputObserved();}finally{PollCostEnd(start);}
        }
        void PollInputObserved()
        {
            if(presenter==null||!IsFocused)return;
            float dt=lastPoll>0?Mathf.Clamp(Time.unscaledTime-lastPoll,0,.05f):.016f;lastPoll=Time.unscaledTime;
            if(Mode!=priorMode)
            {
                // Cancel a gesture that actually began in the old mode. A completed
                // release or explicit scenario setup has no gesture to wait for;
                // do not swallow the next genuine press in the new mode.
                bool hadGesture=captured>=0||moveTouch>=0||lookTouch>=0||touchGesture;
                if(hadGesture)CancelGesture();else ClearWorldTouches();
                priorMode=Mode;
            }
            if(view.LayoutChanged){if(captured>=0||touchGesture)CancelGesture();view.Layout();}
            var keyboard=Keyboard.current;
            if(keyboard!=null&&keyboard.escapeKey.wasPressedThisFrame){CancelGesture();if(!view.CloseMore())presenter.Back();return;}
            var touches=ETouch.activeTouches;int live=0;for(int i=0;i<touches.Count;i++)if(touches[i].phase!=IPhase.Ended&&touches[i].phase!=IPhase.Canceled)live++;
            if(touches.Count>0||touchGesture)
            {
                ProcessTouches(touches,live,dt);return;
            }
            var mouse=Mouse.current;
            if(mouse!=null)
            {
                if(presenter.IsReadOnlyEvidence&&mouse.scroll.ReadValue().y!=0){LastInputSource="MOUSE";presenter.ScrollEvidence(mouse.scroll.ReadValue().y>0?-3:3);}
                if(requireRelease){if(!mouse.leftButton.isPressed)requireRelease=false;return;}
                if(mouse.leftButton.wasPressedThisFrame)Begin(0,false,mouse.position.ReadValue());
                else if(captured==0&&!capturedTouch&&mouse.leftButton.isPressed)Move(mouse.position.ReadValue());
                if(captured==0&&!capturedTouch&&!mouse.leftButton.isPressed)End(false,mouse.position.ReadValue());
            }
            MoveHeld(dt);
            if(Mode==G3Mode.WALK&&keyboard!=null&&!view.MoreVisible)
            {
                var v=new Vector2((keyboard.dKey.isPressed?1:0)-(keyboard.aKey.isPressed?1:0),(keyboard.wKey.isPressed?1:0)-(keyboard.sKey.isPressed?1:0));
                float turn=(keyboard.rightArrowKey.isPressed?1:0)-(keyboard.leftArrowKey.isPressed?1:0);if(v!=Vector2.zero||turn!=0)view.Walk.Move(v,turn,dt);
            }
        }
        void ClearWorldTouches(){moveTouch=lookTouch=-1;touchTarget=null;lookDragged=false;view?.SetJoystick(Vector2.zero);}
        void ActivateWorld(G3WorldTarget target)
        {
            if(target==null||presenter.IsCommitting)return;
            if(Mode!=G3Mode.WALK&&target.Panel!=G3Panel.Phone)return;
            ClearWorldTouches();
            if(target.IsTable)presenter.Execute(new G3Action(G3ActionKind.Sit));else presenter.OpenPanel(target.Panel);
        }
        void ProcessTouches(UnityEngine.InputSystem.Utilities.ReadOnlyArray<ETouch> touches,int live,float dt)
        {
            if(requireRelease){if(live==0){ClearWorldTouches();End(true);touchGesture=false;requireRelease=false;}return;}touchGesture=true;
            foreach(var t in touches)
            {
                if(t.phase!=IPhase.Began)continue;LastInputSource="TOUCHSCREEN";
                if(!view.IsSafePointer(t.screenPosition))continue;
                if(moveTouch>=0&&lookTouch>=0)
                {if(!view.ConsumeUi(t.screenPosition,out var third)||third.Kind!=G3ActionKind.Open||third.Slot!=(int)G3Panel.Settings)continue;}
                if(Mode==G3Mode.WALK&&view.JoystickRect.Contains(t.screenPosition)&&moveTouch<0)
                {moveTouch=t.touchId;moveOrigin=view.JoystickRect.center;continue;}
                if(Mode==G3Mode.WALK&&t.screenPosition.x>=view.PresentationSafeArea.center.x&&!view.ConsumeUi(t.screenPosition,out _)&&lookTouch<0)
                {lookTouch=t.touchId;lookStart=lookLast=t.screenPosition;lookDragged=false;touchTarget=view.WorldTarget(t.screenPosition);continue;}
                if(Mode==G3Mode.WALK&&t.screenPosition.x>=view.PresentationSafeArea.center.x&&!view.ConsumeUi(t.screenPosition,out _))continue;
                if(captured<0)Begin(t.touchId,true,t.screenPosition);
            }
            bool moveFound=false,lookFound=false,captureFound=false;Vector2 desiredMove=Vector2.zero,desiredLook=Vector2.zero;
            foreach(var t in touches)
            {
                bool ended=t.phase==IPhase.Ended||t.phase==IPhase.Canceled;
                if(t.touchId==moveTouch)
                {
                    moveFound=true;
                    if(ended||Mode!=G3Mode.WALK){moveTouch=-1;view.SetJoystick(Vector2.zero);}
                    else {var v=Vector2.ClampMagnitude((t.screenPosition-moveOrigin)/(view.JoystickRect.width*.3f),1);float length=v.magnitude;v=length<=.15f?Vector2.zero:v/length*((length-.15f)/.85f);view.SetJoystick(v);desiredMove=v;}
                }
                else if(t.touchId==lookTouch)
                {
                    lookFound=true;if(Vector2.Distance(t.screenPosition,lookStart)>8*view.TouchPixelsPerDp)lookDragged=true;
                    if(ended)
                    {var target=touchTarget;bool activate=t.phase==IPhase.Ended&&!lookDragged&&target!=null&&view.WorldTarget(t.screenPosition)==target;lookTouch=-1;touchTarget=null;if(activate)ActivateWorld(target);}
                    else if(Mode==G3Mode.WALK&&lookDragged&&t.phase==IPhase.Moved)desiredLook=(t.screenPosition-lookLast)/view.TouchPixelsPerDp*2;
                    lookLast=t.screenPosition;
                }
                else if(t.touchId==captured&&capturedTouch)
                {captureFound=true;if(ended)End(t.phase==IPhase.Canceled,t.screenPosition);else if(t.phase==IPhase.Moved)Move(t.screenPosition);}
            }
            if(moveTouch>=0&&!moveFound){moveTouch=-1;view.SetJoystick(Vector2.zero);}
            if(lookTouch>=0&&!lookFound){lookTouch=-1;touchTarget=null;}
            if(capturedTouch&&captured>=0&&!captureFound)End(true);
            if(Mode==G3Mode.WALK){if(desiredLook!=Vector2.zero)view.Walk.Look(desiredLook);if(moveTouch>=0&&desiredMove!=Vector2.zero)view.Walk.Move(desiredMove,0,dt);}
            if(live==0){ClearWorldTouches();touchGesture=false;requireRelease=false;}
        }
        static bool Movement(G3ActionKind k)=>k>=G3ActionKind.MoveForward&&k<=G3ActionKind.TurnRight;
        void Begin(int id,bool touch,Vector2 pixel)
        {
            if(captured>=0||!view.IsSafePointer(pixel))return;captured=id;capturedTouch=touch;previous=pixel;tracker?.Cancel();
            LastInputSource=touch?"TOUCHSCREEN":"MOUSE";evidenceDrag=0;
            evidenceScrollCapture=presenter.IsReadOnlyEvidence&&view.EvidenceBodyRect.Contains(pixel);
            if(view.Phone!=null&&view.Phone.IsFocused){uiCapture=true;view.Phone.BeginPointer(pixel);return;}
            uiCapture=view.ConsumeUi(pixel,out G3Action action);
            if(uiCapture){held=action;pendingUi=action;pendingControl=view.UiControlId(pixel);uiStart=pixel;uiDragged=false;pendingUiRevision=view.InteractionRevision;pendingUiMode=Mode;return;}
            if(Mode==G3Mode.WALK)
            {
                worldPressed=view.WorldTarget(pixel);worldStart=pixel;worldDragged=false;return;
            }
            var phone=view.WorldTarget(pixel);if(phone!=null&&phone.Panel==G3Panel.Phone){worldPressed=phone;worldStart=pixel;worldDragged=false;return;}
            if(!presenter.CanScratch){uiCapture=true;return;}
            if(view.TryScratchUv(pixel,out Uv uv))
            {
                int visual=view.Surface.Layout.HitTest(uv);
                if(visual>=0&&presenter.Snapshot.CurrentTicket.TicketType=="challenge"&&presenter.Snapshot.CurrentTicket.SelectedCell<0)
                {
                    presenter.SelectCell(view.Surface.Layout.Cells[visual].CoreIndex);
                    // No draw until the selection receipt is confirmed. A committed
                    // selection may receive the same pointer's next sample normally.
                }
            }
            Move(pixel);
        }
        void Move(Vector2 pixel)
        {
            if(uiCapture)
            {
                if(view.Phone!=null&&view.Phone.IsFocused){view.Phone.MovePointer(pixel);previous=pixel;return;}
                if(evidenceScrollCapture&&presenter.IsReadOnlyEvidence)
                {
                    evidenceDrag+=pixel.y-previous.y;previous=pixel;
                    float row=37.12f*view.PresentationSafeArea.height/720f;int lines=(int)(evidenceDrag/Mathf.Max(1,row));
                    if(lines!=0){presenter.ScrollEvidence(lines);evidenceDrag-=lines*row;}
                    return;
                }
                if(Vector2.Distance(pixel,uiStart)>8*view.TouchPixelsPerDp||view.UiControlId(pixel)!=pendingControl)uiDragged=true;
                // Moving off a held walk button cancels movement; it cannot become
                // a camera drag or a scratch in the same gesture.
                if(Movement(held.Kind)&&(!view.ConsumeUi(pixel,out var now)||now.Id!=held.Id))held=default;
                return;
            }
            if(Mode==G3Mode.WALK||worldPressed!=null){if(Vector2.Distance(pixel,worldStart)>8*view.TouchPixelsPerDp)worldDragged=true;if(Mode==G3Mode.WALK&&worldDragged&&(!capturedTouch||worldStart.x>=view.PresentationSafeArea.center.x)&&!view.ConsumeUi(pixel,out _))view.Walk.Look((pixel-previous)/view.TouchPixelsPerDp*2);previous=pixel;return;}
            if(!presenter.CanScratch){tracker?.Cancel();return;}
            if(view.ConsumeUi(pixel,out _)||!view.TryScratchUv(pixel,out Uv uv)){tracker?.Cancel();return;}
            var layout=view.Surface.Layout;if(tracker==null||layout.Id!=layoutId){tracker=new RegionPointerTracker(layout);layoutId=layout.Id;}
            // An approx 17-screen-pixel footprint at 1280x720, projected to paper
            // pixels. It becomes a cell-local ellipse and is clipped by authority.
            if(tracker.Sample(uv,34,out CellBrushProposal proposal))presenter.QueueBrush(proposal);
        }
        void MoveHeld(float dt)
        {
            if(Mode!=G3Mode.WALK||captured<0)return;Vector2 v=Vector2.zero;float turn=0;
            switch(held.Kind){case G3ActionKind.MoveForward:v.y=1;break;case G3ActionKind.MoveBack:v.y=-1;break;case G3ActionKind.MoveLeft:v.x=-1;break;case G3ActionKind.MoveRight:v.x=1;break;case G3ActionKind.TurnLeft:turn=-1;break;case G3ActionKind.TurnRight:turn=1;break;}
            if(v!=Vector2.zero||turn!=0)view.Walk.Move(v,turn,dt);
        }
        void End(bool cancelled=false,Vector2? releasePosition=null)
        {
            if(captured>=0&&view?.Phone!=null&&view.Phone.IsFocused&&releasePosition.HasValue)view.Phone.MovePointer(releasePosition.Value);
            var action=captured>=0&&view?.Phone!=null&&view.Phone.IsFocused?view.Phone.EndPointer(cancelled):default;
            var deferred=pendingUi;
            bool executeUi=uiCapture&&captured>=0&&!cancelled&&!uiDragged&&!string.IsNullOrEmpty(pendingControl)&&!Movement(deferred.Kind)&&deferred.Kind!=G3ActionKind.None&&releasePosition.HasValue&&view.IsSafePointer(releasePosition.Value)&&Vector2.Distance(releasePosition.Value,uiStart)<=8*view.TouchPixelsPerDp&&pendingUiMode==Mode&&pendingUiRevision==view.InteractionRevision&&view.UiControlId(releasePosition.Value)==pendingControl&&view.ConsumeUi(releasePosition.Value,out var released)&&released.Id==deferred.Id;
            var target=worldPressed;bool activate=!cancelled&&!worldDragged&&releasePosition.HasValue&&target!=null&&view.WorldTarget(releasePosition.Value)==target&&Vector2.Distance(releasePosition.Value,worldStart)<=8*view.TouchPixelsPerDp;
            ReleaseCapture();if(executeUi&&!view.HandleLocalAction(deferred))presenter.Execute(deferred);if(activate)ActivateWorld(target);if(action.Kind!=G3ActionKind.None)presenter?.Execute(action);presenter?.FlushScratch();
        }
        public void ReleaseCapture(){view?.Phone?.EndPointer(true);captured=-1;pendingUi=default;pendingControl="";uiDragged=false;worldPressed=null;worldDragged=false;uiCapture=false;evidenceScrollCapture=false;evidenceDrag=0;held=default;tracker?.Cancel();}
        public void CancelGesture(){ClearWorldTouches();End(true);requireRelease=true;}
        public void NotifyFocus(bool value){bool prior=IsFocused;focused=value;if(prior!=IsFocused){CancelGesture();if(!IsFocused)view?.InvalidateTicket();else presenter?.Refresh();}}
        public void NotifyPause(bool value){bool prior=IsFocused;paused=value;if(prior!=IsFocused){CancelGesture();if(!IsFocused)view?.InvalidateTicket();else presenter?.Refresh();}}
        void OnApplicationFocus(bool value){NotifyFocus(value);}
        void OnApplicationPause(bool value){NotifyPause(value);}
    }
}

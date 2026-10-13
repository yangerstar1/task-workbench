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
            if(presenter==null||!IsFocused)return;
            float dt=lastPoll>0?Mathf.Clamp(Time.unscaledTime-lastPoll,0,.05f):.016f;lastPoll=Time.unscaledTime;
            if(view.LayoutChanged){if(captured>=0||touchGesture)CancelGesture();view.Layout();}
            var keyboard=Keyboard.current;
            if(keyboard!=null&&keyboard.escapeKey.wasPressedThisFrame){CancelGesture();if(!view.CloseMore())presenter.Back();return;}
            var touches=ETouch.activeTouches;int live=0;for(int i=0;i<touches.Count;i++)if(touches[i].phase!=IPhase.Ended&&touches[i].phase!=IPhase.Canceled)live++;
            if(touches.Count>0||touchGesture)
            {
                if(!touchGesture&&!requireRelease)for(int i=0;i<touches.Count;i++)if(touches[i].phase==IPhase.Began){touchGesture=true;Begin(touches[i].touchId,true,touches[i].screenPosition);break;}
                if(captured>=0&&capturedTouch)
                {
                    bool found=false;for(int i=0;i<touches.Count;i++)if(touches[i].touchId==captured){found=true;var touch=touches[i];if(touch.phase==IPhase.Ended||touch.phase==IPhase.Canceled)End(touch.phase==IPhase.Canceled,touch.screenPosition);else if(touch.phase==IPhase.Moved)Move(touch.screenPosition);break;}if(!found)End(true);
                }
                if(live==0){End();touchGesture=false;requireRelease=false;}
                MoveHeld(dt);return;
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
        static bool Movement(G3ActionKind k)=>k>=G3ActionKind.MoveForward&&k<=G3ActionKind.TurnRight;
        void Begin(int id,bool touch,Vector2 pixel)
        {
            if(captured>=0)return;captured=id;capturedTouch=touch;previous=pixel;tracker?.Cancel();
            LastInputSource=touch?"TOUCHSCREEN":"MOUSE";evidenceDrag=0;
            evidenceScrollCapture=presenter.IsReadOnlyEvidence&&view.EvidenceBodyRect.Contains(pixel);
            if(view.Phone!=null&&view.Phone.IsFocused){uiCapture=true;view.Phone.BeginPointer(pixel);return;}
            uiCapture=view.ConsumeUi(pixel,out G3Action action);
            if(uiCapture){held=action;if(!Movement(action.Kind)&&action.Kind!=G3ActionKind.None&&!view.HandleLocalAction(action))presenter.Execute(action);return;}
            if(Mode==G3Mode.WALK)
            {
                var target=view.WorldTarget(pixel);if(target!=null){uiCapture=true;if(target.IsTable)presenter.Execute(new G3Action(G3ActionKind.Sit));else presenter.OpenPanel(target.Panel);}return;
            }
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
                // Moving off a held walk button cancels movement; it cannot become
                // a camera drag or a scratch in the same gesture.
                if(Movement(held.Kind)&&(!view.ConsumeUi(pixel,out var now)||now.Id!=held.Id))held=default;
                return;
            }
            if(Mode==G3Mode.WALK){if(!view.ConsumeUi(pixel,out _))view.Walk.Look(pixel-previous);previous=pixel;return;}
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
            ReleaseCapture();if(action.Kind!=G3ActionKind.None)presenter?.Execute(action);presenter?.FlushScratch();
        }
        public void ReleaseCapture(){view?.Phone?.EndPointer(true);captured=-1;uiCapture=false;evidenceScrollCapture=false;evidenceDrag=0;held=default;tracker?.Cancel();}
        public void CancelGesture(){End(true);requireRelease=true;}
        public void NotifyFocus(bool value){bool prior=IsFocused;focused=value;if(prior!=IsFocused){CancelGesture();if(!IsFocused)view?.InvalidateTicket();else presenter?.Refresh();}}
        public void NotifyPause(bool value){bool prior=IsFocused;paused=value;if(prior!=IsFocused){CancelGesture();if(!IsFocused)view?.InvalidateTicket();else presenter?.Refresh();}}
        void OnApplicationFocus(bool value){NotifyFocus(value);}
        void OnApplicationPause(bool value){NotifyPause(value);}
    }
}

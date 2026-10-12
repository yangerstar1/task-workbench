using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.EnhancedTouch;
using ETouch = UnityEngine.InputSystem.EnhancedTouch.Touch;
using IPhase = UnityEngine.InputSystem.TouchPhase;

namespace Lottery.G2.Interaction
{
    public enum SliceMode { TABLE, SCRATCH, PANEL, COMMITTING }
    public sealed class InputRouter : MonoBehaviour
    {
        SlicePresenter presenter; G2SceneView view;
        int captured=-1; bool capturedTouch,uiCapture,hasPrevious,touchGesture,requireRelease,focused=true,paused;
        Vector2 previous;
        public bool PollAutomatically { get; set; } = true;
        public int CapturedPointerId => captured;
        public bool IsFocused => focused && !paused;
        public bool AwaitingRelease => requireRelease;
        public string DiagnosticState => "focus="+focused+",paused="+paused+",release="+requireRelease+",capture="+captured+",touches="+ETouch.activeTouches.Count+",layoutChanged="+(view!=null && view.LayoutChanged)+",viewport="+Screen.width+"x"+Screen.height+",rawSafe="+Screen.safeArea;
        public SliceMode Mode => presenter==null?SliceMode.TABLE:presenter.IsCommitting?SliceMode.COMMITTING:presenter.PanelOpen?SliceMode.PANEL:presenter.CanScratch?SliceMode.SCRATCH:SliceMode.TABLE;
        public void Initialize(SlicePresenter owner,G2SceneView scene) { presenter=owner; view=scene; }
        void OnEnable() { EnhancedTouchSupport.Enable(); }
        void OnDisable() { CancelGesture(); EnhancedTouchSupport.Disable(); }
        void Update() { if(PollAutomatically) PollInput(); }
        public void PollInput()
        {
            if(presenter==null || !IsFocused) return;
            if(view.LayoutChanged)
            {
                // Reprojection cancels an existing gesture. A new press on the newly
                // laid-out screen must not be discarded when nothing was captured.
                if(captured>=0 || touchGesture) CancelGesture();
                view.Layout();
            }
            if(Keyboard.current!=null && Keyboard.current.escapeKey.wasPressedThisFrame) { CancelGesture(); presenter.Back(); return; }
            var touches=ETouch.activeTouches; int live=0;
            for(int i=0;i<touches.Count;i++) if(touches[i].phase!=IPhase.Ended && touches[i].phase!=IPhase.Canceled) live++;
            if(touches.Count>0 || touchGesture)
            {
                if(!touchGesture && !requireRelease)
                {
                    for(int i=0;i<touches.Count;i++) if(touches[i].phase==IPhase.Began) { touchGesture=true; Begin(touches[i].touchId,true,touches[i].screenPosition); break; }
                }
                if(captured>=0 && capturedTouch)
                {
                    bool found=false;
                    for(int i=0;i<touches.Count;i++) if(touches[i].touchId==captured)
                    {
                        found=true; var touch=touches[i];
                        if(touch.phase==IPhase.Ended || touch.phase==IPhase.Canceled) End();
                        else if(touch.phase==IPhase.Moved) Move(touch.screenPosition);
                        break;
                    }
                    if(!found) End();
                }
                if(live==0) { End(); touchGesture=false; requireRelease=false; }
                return;
            }
            var mouse=Mouse.current; if(mouse==null) return;
            if(requireRelease) { if(!mouse.leftButton.isPressed) requireRelease=false; return; }
            if(mouse.leftButton.wasPressedThisFrame) Begin(0,false,mouse.position.ReadValue());
            else if(captured==0 && !capturedTouch && mouse.leftButton.isPressed) Move(mouse.position.ReadValue());
            if(captured==0 && !capturedTouch && !mouse.leftButton.isPressed) End();
        }
        void Begin(int id,bool touch,Vector2 screen)
        {
            if(captured>=0) return;
            captured=id; capturedTouch=touch; hasPrevious=false;
            uiCapture=view.ConsumeUi(screen,out SliceAction action);
            if(uiCapture) { if(action!=SliceAction.None) presenter.Execute(action); return; }
            if(Mode!=SliceMode.SCRATCH) { uiCapture=true; return; }
            Move(screen);
        }
        void Move(Vector2 screen)
        {
            if(uiCapture || Mode!=SliceMode.SCRATCH) { hasPrevious=false; return; }
            // HUD takes priority on every sample, even when a scratch starts elsewhere.
            if(view.ConsumeUi(screen,out _) || !view.Surface.TryScreenUv(view.SceneCamera,screen,out Vector2 uv)) { hasPrevious=false; return; }
            presenter.QueueBrush(previous,uv,hasPrevious); previous=uv; hasPrevious=true;
        }
        void End() { captured=-1; uiCapture=false; hasPrevious=false; if(presenter!=null) presenter.FlushScratch(); }
        public void CancelGesture() { End(); requireRelease=true; }
        public void NotifyFocus(bool hasFocus)
        {
            bool before=IsFocused; focused=hasFocus;
            if(before!=IsFocused) CancelGesture();
        }
        public void NotifyPause(bool isPaused)
        {
            bool before=IsFocused; paused=isPaused;
            if(before!=IsFocused) CancelGesture();
        }
        void OnApplicationFocus(bool value) { NotifyFocus(value); }
        void OnApplicationPause(bool isPaused) { NotifyPause(isPaused); }
    }
}

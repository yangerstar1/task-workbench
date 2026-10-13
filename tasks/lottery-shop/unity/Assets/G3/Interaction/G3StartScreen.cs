using System;
using System.Collections.Generic;
using Lottery.G3.Rendering;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering.Universal;
using UnityEngine.InputSystem.EnhancedTouch;
using ETouch=UnityEngine.InputSystem.EnhancedTouch.Touch;
using IPhase=UnityEngine.InputSystem.TouchPhase;

namespace Lottery.G3.Interaction
{
    // Only a new-store chooser. It has no game state or authority to reset a save.
    public sealed class G3StartScreen : MonoBehaviour
    {
        readonly List<UnityEngine.Object> owned=new List<UnityEngine.Object>();
        Shader chrome;Camera camera;BoundedGlyphLabel title,body,normalLabel,qaLabel,status;Transform normalPlate,qaPlate,backdrop,titlePlate,brandRule;
        Func<bool,bool> choose;bool qaAllowed,started;int width,height;Rect safe,normalRect,qaRect;bool waitRelease;
        public bool PollAutomatically {get;set;}=true;
        public Camera SceneCamera=>camera;
        public int PresentationWidth=>camera.targetTexture!=null?camera.targetTexture.width:Mathf.Max(1,Screen.width);
        public int PresentationHeight=>camera.targetTexture!=null?camera.targetTexture.height:Mathf.Max(1,Screen.height);
        public void Initialize(Font font,Shader flat,Shader glyph,bool allowDiagnostic,Func<bool,bool> onChoose)
        {
            chrome=glyph;choose=onChoose;qaAllowed=allowDiagnostic;var go=new GameObject("G3 new-run chooser camera");go.transform.SetParent(transform,false);camera=go.AddComponent<Camera>();camera.orthographic=false;camera.fieldOfView=62;camera.nearClipPlane=.02f;camera.farClipPlane=30;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.35f,.43f,.48f);camera.GetUniversalAdditionalCameraData().renderPostProcessing=false;
            var room=new GameObject("Menu view of the same authored shop");room.transform.SetParent(transform,false);var environment=room.AddComponent<G3ShopEnvironment>();environment.Build(false);camera.transform.position=environment.EntryPosition+new Vector3(0,1.58f,0);camera.transform.rotation=Quaternion.Euler(7,environment.EntryYaw,0);
            backdrop=Plate("New-run information card",flat);titlePlate=Plate("Readable shop title card",flat);brandRule=Plate("Copper shop title rule",flat);
            var fontMaterial=Own(new Material(glyph));title=Label("New game title",font,fontMaterial);body=Label("New game scope",font,fontMaterial);status=Label("New game status",font,fontMaterial);
            normalLabel=Label("Normal route",font,fontMaterial,TextAnchor.MiddleCenter);qaLabel=Label("Explicit diagnostic route",font,fontMaterial,TextAnchor.MiddleCenter);
            normalPlate=Plate("Start normal new run",flat);qaPlate=Plate("Start marked diagnostic new run",flat);
            title.SetText("彩票小店");body.SetText("一间小店，一天经营。\n所有金额为虚构金币，不能兑换现金。\n普通新局随机生成票与今日货架。\nQA 诊断局固定种子，不代表自然概率。\n已有存档将直接恢复，不能在此替换。");
            normalLabel.SetText("开始普通新局");qaLabel.SetText("开始 QA 固定诊断新局");status.SetText("请选择开局方式。尚未创建存档。");title.SetColor(G3HudTheme.Paper);normalLabel.SetColor(G3HudTheme.Card);Layout();
        }
        T Own<T>(T o)where T:UnityEngine.Object{owned.Add(o);return o;}
        BoundedGlyphLabel Label(string name,Font font,Material material,TextAnchor anchor=TextAnchor.UpperLeft){var go=new GameObject(name);go.transform.SetParent(camera.transform,false);var l=go.AddComponent<BoundedGlyphLabel>();l.Initialize(font,material,G3HudTheme.Paper,anchor);return l;}
        Transform Plate(string name,Shader shader)=>G3HudSurface.Create(name,camera.transform,chrome,G3HudTheme.Ink,G3HudTheme.Rule);
        float Frustum(float z)=>2*Mathf.Tan(camera.fieldOfView*Mathf.Deg2Rad*.5f)*z;
        Vector3 Point(Vector2 p,float z)=>new Vector3((p.x/width-.5f)*Frustum(z)*camera.aspect,(p.y/height-.5f)*Frustum(z),z);
        void Place(BoundedGlyphLabel label,Rect r,float font){label.transform.localPosition=Point(r.center,.4f);label.SetBox(r.width/height*Frustum(.4f),r.height/height*Frustum(.4f),font/height*Frustum(.4f),true);}
        void Place(Transform plate,Rect r,float z=.5f){plate.localPosition=Point(r.center,z);plate.localScale=new Vector3(r.width/height*Frustum(z),r.height/height*Frustum(z),1);plate.GetComponent<G3HudSurface>().Configure(r.width,r.height,12*safe.height/720f,safe.height/720f);}
        public void Layout()
        {
            width=PresentationWidth;height=PresentationHeight;camera.aspect=(float)width/height;safe=camera.targetTexture!=null?new Rect(0,0,width,height):Screen.safeArea;if(safe.width<=0)safe=new Rect(0,0,width,height);float s=safe.height/720f;
            float panelWidth=Mathf.Min(736*s,safe.width-400*s),x=safe.xMax-panelWidth-24*s;
            var card=new Rect(x,safe.y+16*s,panelWidth,safe.height-32*s);Place(backdrop,card,.62f);backdrop.GetComponent<G3HudSurface>().Tint(G3HudTheme.Ink,G3HudTheme.Rule);
            float brandWidth=Mathf.Min(420*s,x-safe.x-40*s);var brand=new Rect(safe.x+24*s,safe.yMax-180*s,brandWidth,128*s);
            Place(titlePlate,brand,.58f);titlePlate.GetComponent<G3HudSurface>().Tint(G3HudTheme.Ink,G3HudTheme.Rule);
            Place(title,new Rect(brand.x+24*s,brand.y+32*s,brand.width-48*s,72*s),64*s);
            Place(brandRule,new Rect(brand.x+24*s,brand.y+20*s,72*s,3*s),.45f);brandRule.GetComponent<G3HudSurface>().Tint(G3HudTheme.Rule,G3HudTheme.Rule);
            Place(body,new Rect(x+28*s,safe.y+340*s,panelWidth-56*s,344*s),32*s);
            normalRect=new Rect(x+24*s,safe.y+220*s,panelWidth-48*s,96*s);qaRect=new Rect(x+24*s,safe.y+112*s,panelWidth-48*s,96*s);
            Place(normalPlate,new Rect(normalRect.x+4*s,normalRect.y+6*s,normalRect.width-8*s,84*s));normalPlate.GetComponent<G3HudSurface>().Tint(G3HudTheme.Action,G3HudTheme.Mint);
            Place(normalLabel,new Rect(normalRect.x+24*s,normalRect.y+24*s,normalRect.width-48*s,48*s),32*s);
            qaPlate.gameObject.SetActive(qaAllowed);qaLabel.gameObject.SetActive(qaAllowed);
            Place(qaPlate,new Rect(qaRect.x+4*s,qaRect.y+6*s,qaRect.width-8*s,84*s));qaPlate.GetComponent<G3HudSurface>().Tint(G3HudTheme.InkLift,G3HudTheme.Rule);
            Place(qaLabel,new Rect(qaRect.x+24*s,qaRect.y+24*s,qaRect.width-48*s,48*s),32*s);
            Place(status,new Rect(x+28*s,safe.y+28*s,panelWidth-56*s,76*s),32*s);status.SetColor(G3HudTheme.QuietInk);
        }
        public Rect ButtonRect(bool diagnostic)=>diagnostic?qaRect:normalRect;
        void OnEnable(){EnhancedTouchSupport.Enable();}
        void OnDisable(){EnhancedTouchSupport.Disable();}
        void Update()
        {
            if(PollAutomatically)PollInput();
            bool pressed=false;Vector2 point=Vector2.zero;
            if(EnhancedTouchSupport.enabled)foreach(var t in ETouch.activeTouches)if(t.phase!=IPhase.Ended&&t.phase!=IPhase.Canceled){pressed=true;point=t.screenPosition;break;}
            if(!pressed&&Mouse.current!=null&&Mouse.current.leftButton.isPressed){pressed=true;point=Mouse.current.position.ReadValue();}
            if(normalPlate!=null)normalPlate.GetComponent<G3HudSurface>().Tint(pressed&&normalRect.Contains(point)?G3HudTheme.InkLift:G3HudTheme.Action,G3HudTheme.Mint);
            if(qaPlate!=null)qaPlate.GetComponent<G3HudSurface>().Tint(pressed&&qaRect.Contains(point)?G3HudTheme.Action:G3HudTheme.InkLift,G3HudTheme.Rule);
        }
        public void PollInput()
        {
            if(started||choose==null)return;if(width!=PresentationWidth||height!=PresentationHeight||(camera.targetTexture==null&&Screen.safeArea.width>0&&safe!=Screen.safeArea))Layout();
            var touches=ETouch.activeTouches;
            if(touches.Count>0){if(!waitRelease)foreach(var t in touches)if(t.phase==IPhase.Began){waitRelease=true;Select(t.screenPosition);break;}int live=0;for(int i=0;i<touches.Count;i++)if(touches[i].phase!=IPhase.Ended&&touches[i].phase!=IPhase.Canceled)live++;if(live==0)waitRelease=false;return;}
            var mouse=Mouse.current;if(mouse==null)return;if(waitRelease){if(!mouse.leftButton.isPressed)waitRelease=false;return;}if(mouse.leftButton.wasPressedThisFrame){waitRelease=true;Select(mouse.position.ReadValue());}
        }
        void Select(Vector2 point)
        {
            bool diagnostic=qaAllowed&&qaRect.Contains(point);if(!diagnostic&&!normalRect.Contains(point))return;
            if(choose(diagnostic)){started=true;gameObject.SetActive(false);}else{status.SetText("没有创建新局：已存在存档或当前入口不可用。原存档保持不变。");}
        }
        void OnDestroy(){foreach(var item in owned)if(item!=null)Destroy(item);}
    }
}

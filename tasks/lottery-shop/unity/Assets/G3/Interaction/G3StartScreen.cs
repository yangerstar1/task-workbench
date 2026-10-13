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
        Camera camera;BoundedGlyphLabel title,body,normalLabel,qaLabel,status;Transform normalPlate,qaPlate,backdrop;
        Func<bool,bool> choose;bool qaAllowed,started;int width,height;Rect safe,normalRect,qaRect;bool waitRelease;
        public bool PollAutomatically {get;set;}=true;
        public Camera SceneCamera=>camera;
        public int PresentationWidth=>camera.targetTexture!=null?camera.targetTexture.width:Mathf.Max(1,Screen.width);
        public int PresentationHeight=>camera.targetTexture!=null?camera.targetTexture.height:Mathf.Max(1,Screen.height);
        public void Initialize(Font font,Shader flat,Shader glyph,bool allowDiagnostic,Func<bool,bool> onChoose)
        {
            choose=onChoose;qaAllowed=allowDiagnostic;var go=new GameObject("G3 new-run chooser camera");go.transform.SetParent(transform,false);camera=go.AddComponent<Camera>();camera.orthographic=false;camera.fieldOfView=62;camera.nearClipPlane=.02f;camera.farClipPlane=30;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.35f,.43f,.48f);camera.GetUniversalAdditionalCameraData().renderPostProcessing=false;
            var room=new GameObject("Menu view of the same authored shop");room.transform.SetParent(transform,false);var environment=room.AddComponent<G3ShopEnvironment>();environment.Build(false);camera.transform.position=environment.EntryPosition+new Vector3(0,1.58f,0);camera.transform.rotation=Quaternion.Euler(7,environment.EntryYaw,0);
            backdrop=Plate("New-run information card",flat);
            var fontMaterial=Own(new Material(glyph));title=Label("New game title",font,fontMaterial);body=Label("New game scope",font,fontMaterial);status=Label("New game status",font,fontMaterial);
            normalLabel=Label("Normal route",font,fontMaterial);qaLabel=Label("Explicit diagnostic route",font,fontMaterial);
            normalPlate=Plate("Start normal new run",flat);qaPlate=Plate("Start marked diagnostic new run",flat);
            title.SetText("彩票小店");body.SetText("一间小店，一天经营。\n所有金额为虚构金币，不能兑换现金。\n普通新局随机生成票与今日货架。\nQA 诊断局固定种子，不代表自然概率。\n已有存档将直接恢复，不能在此替换。");
            normalLabel.SetText("开始普通新局");qaLabel.SetText("开始 QA 固定诊断新局");status.SetText("请明确选择。本页尚未创建存档。");Layout();
        }
        T Own<T>(T o)where T:UnityEngine.Object{owned.Add(o);return o;}
        BoundedGlyphLabel Label(string name,Font font,Material material){var go=new GameObject(name);go.transform.SetParent(camera.transform,false);var l=go.AddComponent<BoundedGlyphLabel>();l.Initialize(font,material,Color.white,TextAnchor.UpperLeft);return l;}
        Transform Plate(string name,Shader shader){var go=GameObject.CreatePrimitive(PrimitiveType.Quad);go.name=name;go.transform.SetParent(camera.transform,false);Destroy(go.GetComponent<Collider>());var material=Own(new Material(shader));material.color=new Color(.13f,.16f,.17f);go.GetComponent<Renderer>().sharedMaterial=material;return go.transform;}
        float Frustum(float z)=>2*Mathf.Tan(camera.fieldOfView*Mathf.Deg2Rad*.5f)*z;
        Vector3 Point(Vector2 p,float z)=>new Vector3((p.x/width-.5f)*Frustum(z)*camera.aspect,(p.y/height-.5f)*Frustum(z),z);
        void Place(BoundedGlyphLabel label,Rect r,float font){label.transform.localPosition=Point(r.center,.4f);label.SetBox(r.width/height*Frustum(.4f),r.height/height*Frustum(.4f),font/height*Frustum(.4f),true);}
        void Place(Transform plate,Rect r){plate.localPosition=Point(r.center,.5f);plate.localScale=new Vector3(r.width/height*Frustum(.5f),r.height/height*Frustum(.5f),1);}
        public void Layout()
        {
            width=PresentationWidth;height=PresentationHeight;camera.aspect=(float)width/height;safe=camera.targetTexture!=null?new Rect(0,0,width,height):Screen.safeArea;if(safe.width<=0)safe=new Rect(0,0,width,height);float s=safe.height/720f;
            float panelWidth=Mathf.Min(720*s,safe.width-280*s),x=safe.xMax-panelWidth-24*s;
            var card=new Rect(x,safe.y+24*s,panelWidth,safe.height-48*s);Place(backdrop,card);backdrop.localPosition=Point(card.center,.62f);backdrop.localScale=new Vector3(card.width/height*Frustum(.62f),card.height/height*Frustum(.62f),1);backdrop.GetComponent<Renderer>().sharedMaterial.color=new Color(.075f,.09f,.10f);
            Place(title,new Rect(safe.x+32*s,safe.yMax-160*s,Mathf.Max(220*s,x-safe.x-52*s),92*s),64*s);
            Place(body,new Rect(x+24*s,safe.y+310*s,panelWidth-48*s,350*s),32*s);
            normalRect=new Rect(x+24*s,safe.y+184*s,panelWidth-48*s,96*s);qaRect=new Rect(x+24*s,safe.y+76*s,panelWidth-48*s,96*s);
            Place(normalPlate,normalRect);normalPlate.GetComponent<Renderer>().sharedMaterial.color=new Color(.43f,.28f,.1f);Place(normalLabel,new Rect(normalRect.x+24*s,normalRect.y+25*s,normalRect.width-48*s,56*s),32*s);
            qaPlate.gameObject.SetActive(qaAllowed);qaLabel.gameObject.SetActive(qaAllowed);Place(qaPlate,qaRect);Place(qaLabel,new Rect(qaRect.x+24*s,qaRect.y+25*s,qaRect.width-48*s,56*s),32*s);
            Place(status,new Rect(x+24*s,safe.y+32*s,panelWidth-48*s,36*s),24*s);
        }
        public Rect ButtonRect(bool diagnostic)=>diagnostic?qaRect:normalRect;
        void OnEnable(){EnhancedTouchSupport.Enable();}
        void OnDisable(){EnhancedTouchSupport.Disable();}
        void Update(){if(PollAutomatically)PollInput();}
        public void PollInput()
        {
            if(started||choose==null)return;if(width!=PresentationWidth||height!=PresentationHeight)Layout();
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

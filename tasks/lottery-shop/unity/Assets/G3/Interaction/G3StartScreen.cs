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
        Camera camera;BoundedGlyphLabel title,body,normalLabel,qaLabel,status;Transform normalPlate,qaPlate;
        Func<bool,bool> choose;bool qaAllowed,started;int width,height;Rect safe,normalRect,qaRect;bool waitRelease;
        public bool PollAutomatically {get;set;}=true;
        public Camera SceneCamera=>camera;
        public int PresentationWidth=>camera.targetTexture!=null?camera.targetTexture.width:Mathf.Max(1,Screen.width);
        public int PresentationHeight=>camera.targetTexture!=null?camera.targetTexture.height:Mathf.Max(1,Screen.height);
        public void Initialize(Font font,Shader flat,Shader glyph,bool allowDiagnostic,Func<bool,bool> onChoose)
        {
            choose=onChoose;qaAllowed=allowDiagnostic;var go=new GameObject("G3 new-run chooser camera");go.transform.SetParent(transform,false);camera=go.AddComponent<Camera>();camera.orthographic=true;camera.orthographicSize=1;camera.nearClipPlane=.02f;camera.farClipPlane=5;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.045f,.11f,.08f);camera.GetUniversalAdditionalCameraData().renderPostProcessing=false;
            var fontMaterial=Own(new Material(glyph));title=Label("New game title",font,fontMaterial);body=Label("New game scope",font,fontMaterial);status=Label("New game status",font,fontMaterial);
            normalLabel=Label("Normal route",font,fontMaterial);qaLabel=Label("Explicit diagnostic route",font,fontMaterial);
            normalPlate=Plate("Start normal new run",flat);qaPlate=Plate("Start marked diagnostic new run",flat);
            title.SetText("彩票小店 · G3 首日功能切片");body.SetText("所有金额都是虚构游戏金币，不能兑换现金。\n普通新局按正式规则随机生成票与每日货架。\n诊断新局使用固定种子和已标记的初始货架，\n用于复现验证，不代表自然中奖概率。\n已有存档只恢复，不能从此入口替换当前局。");
            normalLabel.SetText("开始普通新局");qaLabel.SetText("开始 QA 固定诊断新局");status.SetText("请明确选择。本页尚未创建存档。");Layout();
        }
        T Own<T>(T o)where T:UnityEngine.Object{owned.Add(o);return o;}
        BoundedGlyphLabel Label(string name,Font font,Material material){var go=new GameObject(name);go.transform.SetParent(camera.transform,false);var l=go.AddComponent<BoundedGlyphLabel>();l.Initialize(font,material,Color.white,TextAnchor.UpperLeft);return l;}
        Transform Plate(string name,Shader shader){var go=GameObject.CreatePrimitive(PrimitiveType.Quad);go.name=name;go.transform.SetParent(camera.transform,false);Destroy(go.GetComponent<Collider>());var material=Own(new Material(shader));material.color=new Color(.15f,.32f,.23f);go.GetComponent<Renderer>().sharedMaterial=material;return go.transform;}
        Vector3 Point(Vector2 p,float z)=>new Vector3((p.x/width-.5f)*2*camera.aspect,(p.y/height-.5f)*2,z);
        void Place(BoundedGlyphLabel label,Rect r,float font){label.transform.localPosition=Point(r.center,.4f);label.SetBox(r.width/height*2,r.height/height*2,font/height*2,true);}
        void Place(Transform plate,Rect r){plate.localPosition=Point(r.center,.5f);plate.localScale=new Vector3(r.width/height*2,r.height/height*2,1);}
        public void Layout()
        {
            width=PresentationWidth;height=PresentationHeight;camera.aspect=(float)width/height;safe=camera.targetTexture!=null?new Rect(0,0,width,height):Screen.safeArea;if(safe.width<=0)safe=new Rect(0,0,width,height);float s=safe.height/720f;
            Place(title,new Rect(safe.x+40*s,safe.yMax-100*s,safe.width-80*s,64*s),36*s);Place(body,new Rect(safe.x+40*s,safe.y+300*s,safe.width-80*s,280*s),32*s);
            normalRect=new Rect(safe.x+40*s,safe.y+174*s,safe.width-80*s,96*s);qaRect=new Rect(safe.x+40*s,safe.y+66*s,safe.width-80*s,96*s);
            Place(normalPlate,normalRect);Place(normalLabel,new Rect(normalRect.x+24*s,normalRect.y+25*s,normalRect.width-48*s,56*s),32*s);
            qaPlate.gameObject.SetActive(qaAllowed);qaLabel.gameObject.SetActive(qaAllowed);Place(qaPlate,qaRect);Place(qaLabel,new Rect(qaRect.x+24*s,qaRect.y+25*s,qaRect.width-48*s,56*s),32*s);
            Place(status,new Rect(safe.x+40*s,safe.y+12*s,safe.width-80*s,42*s),26*s);
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

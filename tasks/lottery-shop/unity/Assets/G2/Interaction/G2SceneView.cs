using System;
using System.Collections.Generic;
using Lottery.G2.Core;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace Lottery.G2.Interaction
{
    public enum SliceAction { None, Buy, Claim, OpenPanel, ClosePanel, Retry, BuyStock, BeginFakeAd, FakeClose, FakeReward, PollAd }
    public sealed class G2SceneView : MonoBehaviour
    {
        sealed class ButtonVisual
        {
            public SliceAction Action; public Rect Rect; public GameObject Root; public Transform Plate; public WorldLabel Label; public bool Enabled;
        }
        readonly List<UnityEngine.Object> owned = new List<UnityEngine.Object>();
        readonly List<WorldLabel> labels = new List<WorldLabel>();
        readonly Dictionary<SliceAction,ButtonVisual> buttons = new Dictionary<SliceAction,ButtonVisual>();
        Font font; Shader flatShader; Material fontMaterial;
        Transform hud; GameObject panel; Transform topPlate,bottomPlate,panelPlate;
        WorldLabel title,wallet,summary,status,panelTitle,panelInfo,publicNumber,emptyTicket;
        WorldLabel[] cells = new WorldLabel[6];
        GameObject ticketRoot;
        int lastWidth,lastHeight; Rect lastSafe,topRect,bottomRect,panelRect;
        long maskRevision = -1; string maskTicket;
        public Camera SceneCamera { get; private set; }
        public TicketScratchSurface Surface { get; private set; }
        public bool PanelVisible { get; private set; }
        public string VisibleSummary => summary.Text;
        public Rect ButtonRect(SliceAction action) => buttons[action].Rect;
        public bool LayoutChanged => lastWidth != Screen.width || lastHeight != Screen.height || lastSafe != Screen.safeArea;
        public void Initialize(Font source, Shader flat, Shader glyph, Shader scratch, Shader lit)
        {
            font=source; flatShader=flat;
            if(font==null || flat==null || glyph==null || scratch==null || lit==null) throw new InvalidOperationException("Missing G2 licensed font or URP shader");
            fontMaterial=Own(new Material(glyph) { name="G2 shared licensed Chinese atlas" });
            var cameraObject=new GameObject("G2 fixed table camera"); cameraObject.transform.SetParent(transform,false);
            SceneCamera=cameraObject.AddComponent<Camera>(); SceneCamera.orthographic=true; SceneCamera.orthographicSize=2.38f; SceneCamera.nearClipPlane=.05f; SceneCamera.farClipPlane=50;
            cameraObject.transform.position=new Vector3(0,5.8f,-4.1f); cameraObject.transform.LookAt(Vector3.zero);
            SceneCamera.clearFlags=CameraClearFlags.SolidColor; SceneCamera.backgroundColor=new Color(.065f,.10f,.11f);
            SceneCamera.GetUniversalAdditionalCameraData().renderPostProcessing=false;
            var lightObject=new GameObject("G2 shop light"); lightObject.transform.SetParent(transform,false); var light=lightObject.AddComponent<Light>(); light.type=LightType.Directional; light.intensity=1.25f; light.shadows=LightShadows.None; lightObject.transform.rotation=Quaternion.Euler(45,-35,0);
            RenderSettings.ambientLight=new Color(.6f,.64f,.63f);
            MakeBox("Table",new Vector3(0,-.17f,0),new Vector3(7,.34f,3.8f),new Color(.27f,.20f,.14f),lit);
            MakeBox("Shop back wall",new Vector3(0,.9f,2.25f),new Vector3(8,2.5f,.15f),new Color(.18f,.30f,.30f),lit);
            MakeBox("Left wall",new Vector3(-4,.9f,0),new Vector3(.15f,2.5f,4.5f),new Color(.22f,.32f,.31f),lit);
            MakeBox("Counter",new Vector3(2.95f,.16f,.9f),new Vector3(.7f,.35f,1.1f),new Color(.48f,.38f,.24f),lit);
            for(int i=0;i<3;i++) MakeBox("Empty tool stand "+i,new Vector3(-3.1f,.10f,-.85f+i*.65f),new Vector3(.5f,.18f,.5f),new Color(.42f,.38f,.29f),lit);
            var shopSign=Label("Shop sign",transform,.26f,new Color(.88f,.88f,.71f),TextAnchor.MiddleCenter); shopSign.transform.position=new Vector3(0,1.2f,2.14f); shopSign.SetText("刮奖小店");
            ticketRoot=new GameObject("Current locked number ticket"); ticketRoot.transform.SetParent(transform,false);
            MakeBox("Paper",new Vector3(0,.065f,.02f),new Vector3(4.7f,.10f,3.35f),new Color(.94f,.90f,.75f),flat,ticketRoot.transform);
            publicNumber=Label("Public winning number",ticketRoot.transform,.24f,new Color(.12f,.25f,.23f),TextAnchor.MiddleCenter); publicNumber.transform.localPosition=new Vector3(0,.126f,1.43f); publicNumber.transform.localRotation=Quaternion.Euler(90,0,0);
            for(int i=0;i<6;i++)
            {
                int col=i%3,row=i/3;
                cells[i]=Label("Locked cell "+i,ticketRoot.transform,.245f,new Color(.13f,.19f,.17f),TextAnchor.MiddleCenter);
                cells[i].transform.localPosition=new Vector3((col-1)*TicketScratchSurface.Width/3,.125f,-.14f+(row-.5f)*TicketScratchSurface.Depth/2); cells[i].transform.localRotation=Quaternion.Euler(90,0,0);
            }
            var scratchObject=new GameObject("Committed scratch coating"); scratchObject.transform.SetParent(ticketRoot.transform,false); scratchObject.transform.localPosition=new Vector3(0,.138f,-.14f);
            Surface=scratchObject.AddComponent<TicketScratchSurface>(); Surface.Initialize(Own(new Material(scratch)));
            emptyTicket=Label("Empty table invitation",transform,.29f,new Color(.95f,.9f,.73f),TextAnchor.MiddleCenter); emptyTicket.transform.position=new Vector3(0,.07f,0); emptyTicket.transform.rotation=Quaternion.Euler(90,0,0); emptyTicket.SetText("买一张号码票\n用手指或鼠标擦开六格");
            hud=new GameObject("Camera-space HUD rendered by URP").transform; hud.SetParent(SceneCamera.transform,false);
            topPlate=Plate("Header",hud,new Color(.055f,.11f,.12f)); bottomPlate=Plate("Footer",hud,new Color(.055f,.11f,.12f));
            title=Label("Probe scope",hud,.12f,new Color(.96f,.79f,.35f),TextAnchor.UpperLeft);
            wallet=Label("Committed wallet",hud,.12f,Color.white,TextAnchor.UpperLeft);
            summary=Label("Ticket settlement breakdown",hud,.12f,Color.white,TextAnchor.UpperLeft);
            status=Label("Operation status",hud,.11f,new Color(.73f,.84f,.81f),TextAnchor.UpperLeft);
            panel=new GameObject("Minimal state panel"); panel.transform.SetParent(hud,false);
            panelPlate=Plate("Panel backing",panel.transform,new Color(.07f,.16f,.17f));
            panelTitle=Label("Panel title",panel.transform,.13f,new Color(.96f,.79f,.35f),TextAnchor.UpperLeft);
            panelInfo=Label("Panel committed state",panel.transform,.12f,Color.white,TextAnchor.UpperLeft);
            AddButton(SliceAction.Buy,"购买 · 100",hud); AddButton(SliceAction.Claim,"收下",hud); AddButton(SliceAction.OpenPanel,"查看面板",hud); AddButton(SliceAction.Retry,"确认 / 重试",hud);
            AddButton(SliceAction.ClosePanel,"返回刮票",panel.transform); AddButton(SliceAction.BuyStock,"原价购买 · 80",panel.transform); AddButton(SliceAction.BeginFakeAd,"模拟广告 · 40",panel.transform);
            AddButton(SliceAction.FakeClose,"模拟关闭",panel.transform); AddButton(SliceAction.FakeReward,"模拟奖励",panel.transform); AddButton(SliceAction.PollAd,"查询回执",panel.transform);
            Layout(); Physics.SyncTransforms();
        }
        T Own<T>(T value) where T:UnityEngine.Object { owned.Add(value); return value; }
        void MakeBox(string name,Vector3 position,Vector3 size,Color color,Shader shader,Transform parent=null)
        {
            var obj=GameObject.CreatePrimitive(PrimitiveType.Cube); obj.name=name; obj.transform.SetParent(parent??transform,false); obj.transform.localPosition=position; obj.transform.localScale=size;
            var collider=obj.GetComponent<Collider>(); if(collider!=null) Destroy(collider);
            var mat=Own(new Material(shader)); mat.color=color; obj.GetComponent<Renderer>().sharedMaterial=mat;
        }
        Transform Plate(string name,Transform parent,Color color)
        {
            var obj=GameObject.CreatePrimitive(PrimitiveType.Quad); obj.name=name; obj.transform.SetParent(parent,false); Destroy(obj.GetComponent<Collider>());
            var mat=Own(new Material(flatShader)); mat.color=color; obj.GetComponent<Renderer>().sharedMaterial=mat; return obj.transform;
        }
        WorldLabel Label(string name,Transform parent,float height,Color color,TextAnchor anchor)
        {
            var obj=new GameObject(name); obj.transform.SetParent(parent,false); var label=obj.AddComponent<WorldLabel>(); label.Initialize(font,fontMaterial,height,color,anchor); labels.Add(label); return label;
        }
        void AddButton(SliceAction action,string text,Transform parent)
        {
            var root=new GameObject("Button "+action); root.transform.SetParent(parent,false);
            var plate=Plate("Button plate",root.transform,new Color(.18f,.36f,.32f));
            var label=Label("Button label",root.transform,.11f,Color.white,TextAnchor.MiddleCenter); label.SetText(text);
            buttons.Add(action,new ButtonVisual {Action=action,Root=root,Plate=plate,Label=label});
        }
        Vector3 ScreenLocal(float x,float y,float depth) => new Vector3((x/Screen.width-.5f)*SceneCamera.orthographicSize*2*SceneCamera.aspect,(y/Screen.height-.5f)*SceneCamera.orthographicSize*2,depth);
        float WorldPixels(float pixels) => pixels/Screen.height*SceneCamera.orthographicSize*2;
        void PlacePlate(Transform item,Rect rect,float depth) { item.localPosition=ScreenLocal(rect.center.x,rect.center.y,depth); item.localScale=new Vector3(WorldPixels(rect.width),WorldPixels(rect.height),1); }
        void PlaceLabel(WorldLabel label,float x,float y,float pixels,float depth=.42f) { label.transform.localPosition=ScreenLocal(x,y,depth); label.SetText(label.Text,WorldPixels(pixels)); }
        void PlaceButton(SliceAction action,Rect rect,float depth=.5f)
        {
            var b=buttons[action]; b.Rect=rect; PlacePlate(b.Plate,rect,depth); PlaceLabel(b.Label,rect.center.x,rect.center.y,22*lastSafe.height/720f,depth-.03f);
        }
        public void Layout()
        {
            lastWidth=Mathf.Max(1,Screen.width); lastHeight=Mathf.Max(1,Screen.height); lastSafe=Screen.safeArea;
            if(lastSafe.width<=0 || lastSafe.height<=0) lastSafe=new Rect(0,0,lastWidth,lastHeight);
            SceneCamera.aspect=(float)lastWidth/lastHeight;
            float s=lastSafe.height/720f,m=16*s,bw=184*s;
            topRect=new Rect(lastSafe.x+m,lastSafe.yMax-94*s,lastSafe.width-2*m,78*s);
            bottomRect=new Rect(lastSafe.x+m,lastSafe.y+m,lastSafe.width-2*m,108*s);
            panelRect=new Rect(lastSafe.x+lastSafe.width*.09f,lastSafe.y+lastSafe.height*.20f,lastSafe.width*.82f,lastSafe.height*.61f);
            PlacePlate(topPlate,topRect,.58f); PlacePlate(bottomPlate,bottomRect,.58f); PlacePlate(panelPlate,panelRect,.36f);
            PlaceLabel(title,topRect.x+16*s,topRect.yMax-10*s,23*s); PlaceLabel(wallet,topRect.x+16*s,topRect.yMax-43*s,22*s);
            PlaceLabel(summary,bottomRect.x+16*s,bottomRect.yMax-13*s,21*s); PlaceLabel(status,bottomRect.x+16*s,bottomRect.y+29*s,19*s);
            var actionRect=new Rect(bottomRect.xMax-bw-12*s,bottomRect.y+24*s,bw,60*s);
            PlaceButton(SliceAction.Buy,actionRect); PlaceButton(SliceAction.Claim,actionRect); PlaceButton(SliceAction.Retry,actionRect);
            PlaceButton(SliceAction.OpenPanel,new Rect(topRect.xMax-bw-12*s,topRect.y+12*s,bw,54*s));
            PlaceLabel(panelTitle,panelRect.x+25*s,panelRect.yMax-22*s,25*s,.28f);
            PlaceLabel(panelInfo,panelRect.x+25*s,panelRect.yMax-74*s,21*s,.28f);
            PlaceButton(SliceAction.ClosePanel,new Rect(panelRect.xMax-bw-20*s,panelRect.yMax-72*s,bw,48*s),.31f);
            PlaceButton(SliceAction.BuyStock,new Rect(panelRect.x+25*s,panelRect.y+88*s,bw+15*s,50*s),.31f);
            PlaceButton(SliceAction.BeginFakeAd,new Rect(panelRect.x+245*s,panelRect.y+88*s,bw+15*s,50*s),.31f);
            PlaceButton(SliceAction.FakeClose,new Rect(panelRect.x+25*s,panelRect.y+20*s,150*s,48*s),.31f);
            PlaceButton(SliceAction.FakeReward,new Rect(panelRect.x+190*s,panelRect.y+20*s,150*s,48*s),.31f);
            PlaceButton(SliceAction.PollAd,new Rect(panelRect.x+355*s,panelRect.y+20*s,150*s,48*s),.31f);
        }
        void ButtonState(SliceAction action,bool show,bool enabled)
        {
            var b=buttons[action]; b.Root.SetActive(show); b.Enabled=enabled;
            b.Plate.GetComponent<Renderer>().sharedMaterial.color=enabled?new Color(.18f,.40f,.32f):new Color(.17f,.22f,.22f);
        }
        public bool ConsumeUi(Vector2 screen,out SliceAction action)
        {
            foreach(var b in buttons.Values) if(b.Root.activeInHierarchy && (!PanelVisible || b.Action==SliceAction.Retry || b.Root.transform.IsChildOf(panel.transform)) && b.Rect.Contains(screen)) { action=b.Enabled?b.Action:SliceAction.None; return true; }
            action=SliceAction.None; return PanelVisible || topRect.Contains(screen) || bottomRect.Contains(screen);
        }
        public void Show(RunState state,bool panelOpen,bool committing,string message,string adInfo,bool canNormal,bool canAd,bool hasAdRequest)
        {
            if(LayoutChanged) Layout(); PanelVisible=panelOpen; panel.SetActive(panelOpen);
            var ticket=state.CurrentTicket; bool active=ticket!=null && ticket.Phase==TicketPhase.ACTIVE; bool revealed=ticket!=null && ticket.Phase==TicketPhase.REVEALED_UNCLAIMED;
            title.SetText("G2 技术探针 · 号码票 100 · 非最终成品");
            wallet.SetText(state.RecoveryRequired?"存档需要恢复 · 余额与票面暂不展示":"现金 "+Money(state.CashMinor)+"    今日已购 "+state.TicketsPurchasedToday+" / 12    已结算 "+state.SettledTicketCount);
            ticketRoot.SetActive(ticket!=null && !state.RecoveryRequired); emptyTicket.gameObject.SetActive(ticket==null && !state.RecoveryRequired);
            if(ticket!=null)
            {
                publicNumber.SetText("中奖号码  "+ticket.Face.WinningNumber.ToString("00")+"      相同号码得对应奖金");
                for(int i=0;i<6;i++) cells[i].SetText(ticket.Face.Cells[i].Number.ToString("00")+"\n"+Money(ticket.Face.Cells[i].PrizeMinor)+" 金币");
                if(maskTicket!=ticket.Id || maskRevision!=state.Revision) { Surface.ShowCommitted(ticket.Scratch); maskTicket=ticket.Id; maskRevision=state.Revision; }
                summary.SetText(active ? "擦开六格银层，完成后收下\n已揭开 "+ticket.Scratch.RevealedCellCount+" / 6 格" : "原奖 "+Money(ticket.RawPrizeMinor)+"   追加 0   "+(revealed?"待收 ":"已收 ")+Money(ticket.RawPrizeMinor)+"\n票价 "+Money(ticket.PriceMinor)+"   净额 "+SignedMoney(ticket.RawPrizeMinor-ticket.PriceMinor));
            }
            else summary.SetText("100 金币一张 · 六格号码票\n号码相同中奖，完整揭晓后兑奖");
            if(state.RecoveryRequired) summary.SetText("交易已暂停，保留存档等待恢复\n不会自动清档或重新生成彩票");
            status.SetText(message);
            panelTitle.SetText("状态面板 · 返回后继续同一张票");
            panelInfo.SetText((state.RecoveryRequired?"余额与票面等待恢复确认":"现金 "+Money(state.CashMinor)+"   今日已购 "+state.TicketsPurchasedToday+" / 12")+"\n"+(ticket==null?"桌上还没有彩票": "本票已揭开 "+ticket.Scratch.RevealedCellCount+" / 6 格，结果与进度已保存")+"\n\n开发模拟广告（FakeAd），不代表真实广告 SDK\n"+adInfo);
            ButtonState(SliceAction.Buy,!committing && !active && !revealed,!state.RecoveryRequired && state.TicketsPurchasedToday<12);
            ButtonState(SliceAction.Claim,!committing && (active||revealed),revealed && !state.RecoveryRequired);
            ButtonState(SliceAction.Retry,committing,true); ButtonState(SliceAction.OpenPanel,true,!committing); ButtonState(SliceAction.ClosePanel,true,true);
            ButtonState(SliceAction.BuyStock,true,!committing && canNormal); ButtonState(SliceAction.BeginFakeAd,true,!committing && canAd);
            ButtonState(SliceAction.FakeClose,hasAdRequest,!committing); ButtonState(SliceAction.FakeReward,hasAdRequest,!committing); ButtonState(SliceAction.PollAd,hasAdRequest,!committing);
        }
        public void RefreshGlyphGeometry() { foreach(var label in labels) label.RebuildIfNeeded(); }
        public static string Money(long minor) => (minor/10m).ToString("0.#",System.Globalization.CultureInfo.InvariantCulture);
        static string SignedMoney(long minor) => (minor>0?"+":"")+Money(minor);
        void OnDestroy() { foreach(var obj in owned) if(obj!=null) Destroy(obj); }
    }
}

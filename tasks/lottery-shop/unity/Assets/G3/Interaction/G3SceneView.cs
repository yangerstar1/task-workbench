using System;
using System.Collections.Generic;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Rendering;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace Lottery.G3.Interaction
{
    public sealed class G3SceneView : MonoBehaviour
    {
        sealed class ButtonVisual {public string Id;public GameObject Root;public Transform Plate;public BoundedGlyphLabel Label;public Rect Rect;public G3Action Action;public bool Enabled;}
        readonly List<UnityEngine.Object> owned=new List<UnityEngine.Object>();readonly List<BoundedGlyphLabel> labels=new List<BoundedGlyphLabel>();readonly List<ButtonVisual> pool=new List<ButtonVisual>();
        Font font;Shader flat;Material fontMat;Transform hud,header,footer,modal;BoundedGlyphLabel headerText,statusText,resultText,panelTitle,panelBody,panelFoot,emptyText;
        readonly List<Renderer> toolObjects=new List<Renderer>();readonly List<BoundedGlyphLabel> toolLabels=new List<BoundedGlyphLabel>();
        ConfirmedTicketSurface number,challenge;G3Presenter current;G3PanelModel panelModel;
        float settlementPulse;bool pulseReduced;int lastWidth,lastHeight,used;Rect lastSafe,headerRect,footerRect,modalRect,evidenceBodyRect;bool walking;
        public Camera SceneCamera {get;private set;}
        public G3ShopWalk Walk {get;private set;}
        public ConfirmedTicketSurface Surface=>current?.Snapshot.CurrentTicket?.TicketType=="challenge"?challenge:number;
        public bool PanelVisible=>current!=null&&current.Panel!=G3Panel.None;
        public string VisibleSummary=>resultText.Text;
        public string VisibleStatus=>statusText.Text;
        public string VisibleToolSlot(int slot)=>toolLabels[slot].Text;
        public Color VisibleToolColor(int slot)=>toolObjects[slot].sharedMaterial.color;
        public int PresentationWidth=>SceneCamera!=null&&SceneCamera.targetTexture!=null?SceneCamera.targetTexture.width:Mathf.Max(1,Screen.width);
        public int PresentationHeight=>SceneCamera!=null&&SceneCamera.targetTexture!=null?SceneCamera.targetTexture.height:Mathf.Max(1,Screen.height);
        public Rect? SimulatedSafeArea {get;set;}
        public Rect PresentationSafeArea=>Safe;
        public Rect EvidenceBodyRect=>evidenceBodyRect;
        Rect Safe=>SimulatedSafeArea??(SceneCamera!=null&&SceneCamera.targetTexture!=null?new Rect(0,0,PresentationWidth,PresentationHeight):(Screen.safeArea.width>0?Screen.safeArea:new Rect(0,0,PresentationWidth,PresentationHeight)));
        public bool LayoutChanged=>lastWidth!=PresentationWidth||lastHeight!=PresentationHeight||lastSafe!=Safe;
        public void Initialize(Font chinese,Shader flatShader,Shader glyph,Shader lit,Shader paper,Shader silver,Shader maskedFont,ApprovedArtworkBinding numberArt,ApprovedArtworkBinding challengeArt)
        {
            font=chinese;flat=flatShader;if(font==null||flat==null||glyph==null||lit==null)throw new InvalidOperationException("Missing G3 licensed font or URP shaders");
            fontMat=Own(new Material(glyph));var go=new GameObject("G3 single scene camera");go.transform.SetParent(transform,false);SceneCamera=go.AddComponent<Camera>();SceneCamera.nearClipPlane=.02f;SceneCamera.farClipPlane=30;SceneCamera.fieldOfView=64;
            SceneCamera.clearFlags=CameraClearFlags.SolidColor;SceneCamera.backgroundColor=new Color(.48f,.58f,.62f);SceneCamera.GetUniversalAdditionalCameraData().renderPostProcessing=false;
            var lightGo=new GameObject("Shop warm daylight");lightGo.transform.SetParent(transform,false);var light=lightGo.AddComponent<Light>();light.type=LightType.Directional;light.intensity=1.1f;light.shadows=LightShadows.None;lightGo.transform.rotation=Quaternion.Euler(58,-35,0);RenderSettings.ambientLight=new Color(.68f,.67f,.62f);
            BuildShop(lit);
            var n=new GameObject("Approved number ticket");n.transform.SetParent(transform,false);n.transform.position=new Vector3(0,.843f,-.56f);number=n.AddComponent<ConfirmedTicketSurface>();number.Build(numberArt,font,paper,silver,maskedFont,glyph,1.2f);
            var c=new GameObject("Approved challenge ticket");c.transform.SetParent(transform,false);c.transform.position=n.transform.position;challenge=c.AddComponent<ConfirmedTicketSurface>();challenge.Build(challengeArt,font,paper,silver,maskedFont,glyph,1.2f);
            var empty=new GameObject("Empty table prompt");empty.transform.SetParent(transform,false);empty.transform.position=new Vector3(0,.85f,-.56f);empty.transform.rotation=Quaternion.Euler(90,0,0);emptyText=empty.AddComponent<BoundedGlyphLabel>();emptyText.Initialize(font,fontMat,new Color(.94f,.92f,.78f));emptyText.SetBox(1.15f,.5f,.07f,true);emptyText.SetText("先看今晚账单\n再选一张票，或到货架投资");labels.Add(emptyText);
            var walker=new GameObject("Player short-distance body");walker.transform.SetParent(transform,false);Walk=walker.AddComponent<G3ShopWalk>();Walk.Initialize(SceneCamera);
            hud=new GameObject("Same-camera readable HUD").transform;hud.SetParent(SceneCamera.transform,false);
            header=Plate("Header",hud,new Color(.055f,.12f,.105f));footer=Plate("Footer",hud,new Color(.055f,.12f,.105f));modal=Plate("Modal background",hud,new Color(.065f,.135f,.12f));
            headerText=Label("Cash interest and progress",hud,Color.white);statusText=Label("Confirmed operation feedback",hud,new Color(.81f,.86f,.80f));resultText=Label("Raw additions and net summary",hud,Color.white);
            panelTitle=Label("Panel title",hud,new Color(.97f,.80f,.39f));panelBody=Label("Panel explanation",hud,Color.white);panelFoot=Label("Panel status",hud,new Color(.78f,.85f,.77f));
            for(int i=0;i<32;i++){var root=new GameObject("Routed control "+i);root.transform.SetParent(hud,false);pool.Add(new ButtonVisual{Root=root,Plate=Plate("Button surface",root.transform,new Color(.17f,.34f,.28f)),Label=Label("Button text",root.transform,Color.white)});}
            SetWalking(false);Layout();Physics.SyncTransforms();
        }
        T Own<T>(T item)where T:UnityEngine.Object{owned.Add(item);return item;}
        GameObject Box(string name,Vector3 p,Vector3 size,Color color,Shader shader,bool collision=true)
        {
            var go=GameObject.CreatePrimitive(PrimitiveType.Cube);go.name=name;go.transform.SetParent(transform,false);go.transform.localPosition=p;go.transform.localScale=size;var mat=Own(new Material(shader));mat.color=color;if(mat.HasProperty("_Smoothness"))mat.SetFloat("_Smoothness",.15f);go.GetComponent<Renderer>().sharedMaterial=mat;
            if(!collision)Destroy(go.GetComponent<Collider>());return go;
        }
        void BuildShop(Shader lit)
        {
            var wall=new Color(.86f,.84f,.77f);var wood=new Color(.66f,.55f,.39f);
            Box("6 by 4 metre single-room floor",new Vector3(0,-.075f,0),new Vector3(6,.15f,4),new Color(.62f,.65f,.63f),lit);
            for(int x=-3;x<=3;x++)Box("Tile vertical grout",new Vector3(x,.002f,0),new Vector3(.014f,.003f,4),new Color(.43f,.46f,.44f),lit,false);
            for(int z=-2;z<=2;z++)Box("Tile horizontal grout",new Vector3(0,.003f,z),new Vector3(6,.003f,.014f),new Color(.43f,.46f,.44f),lit,false);
            Box("Warm white rear wall",new Vector3(0,1.4f,2.05f),new Vector3(6.2f,2.8f,.1f),wall,lit);Box("Left wall",new Vector3(-3.05f,1.4f,0),new Vector3(.1f,2.8f,4.2f),wall,lit);Box("Right wall",new Vector3(3.05f,1.4f,0),new Vector3(.1f,2.8f,4.2f),wall,lit);
            Box("Front low wall",new Vector3(0,.42f,-2.05f),new Vector3(6.2f,.84f,.1f),wall,lit);Box("Window glass",new Vector3(-1.6f,1.65f,1.985f),new Vector3(2.2f,1.3f,.015f),new Color(.50f,.66f,.69f),lit,false);
            for(int i=0;i<3;i++)Box("Window street silhouettes",new Vector3(-2.3f+i*.7f,1.4f,1.97f),new Vector3(.4f,.7f+.12f*i,.015f),new Color(.40f,.48f,.44f),lit,false);
            var counter=Box("Ticket sales counter",new Vector3(1.8f,.47f,1.35f),new Vector3(1.8f,.94f,.8f),wood,lit);Target(counter,G3Panel.Tickets);Sign("售票柜台 · 两种票均 100",new Vector3(1.8f,1.3f,1.75f),.10f,1.8f);
            var table=Box("Personal scratch table",new Vector3(0,.73f,-.56f),new Vector3(1.85f,.20f,1.25f),wood,lit);Target(table,G3Panel.None,true);Box("Deep green felt",new Vector3(0,.835f,-.56f),new Vector3(1.81f,.012f,1.21f),new Color(.055f,.23f,.17f),lit,false);
            foreach(float x in new[]{-.75f,.75f})foreach(float z in new[]{-1.0f,-.12f})Box("Table leg",new Vector3(x,.34f,z),new Vector3(.075f,.68f,.075f),wood,lit);
            var rack=Box("Tool shelf",new Vector3(-2.5f,.95f,.6f),new Vector3(.65f,1.9f,1.6f),wood,lit);Target(rack,G3Panel.Shop);Sign("今日货架",new Vector3(-2.35f,2.1f,.44f),.12f,.95f);
            for(int i=0;i<3;i++)Box("Shelf clear tier",new Vector3(-2.14f,.42f+i*.5f,.6f),new Vector3(.11f,.045f,1.55f),new Color(.85f,.79f,.65f),lit,false);
            var cabinet=Box("Three reserve cabinet",new Vector3(2.5f,.55f,-.75f),new Vector3(.6f,1.1f,1.25f),wood,lit);Target(cabinet,G3Panel.Inventory);Sign("备用收纳",new Vector3(2.36f,1.35f,-.76f),.11f,.9f);
            var drawers=Box("Two consumable drawers",new Vector3(.85f,.93f,-.56f),new Vector3(.22f,.18f,.43f),new Color(.38f,.28f,.19f),lit);Target(drawers,G3Panel.Drawer);
            var phone=Box("Phone on side table",new Vector3(-.77f,.90f,-.55f),new Vector3(.14f,.05f,.23f),new Color(.06f,.075f,.08f),lit);Target(phone,G3Panel.Phone);
            for(int i=0;i<3;i++)
            {
                var tool=Box("Enabled tool stand "+(i+1),new Vector3((i-1)*.45f,.90f,-.105f),new Vector3(.38f,.06f,.085f),new Color(.60f,.52f,.31f),lit,false);toolObjects.Add(tool.GetComponent<Renderer>());Target(tool,G3Panel.Inventory);
                var label=Label("Current tool name "+i,transform,new Color(.08f,.15f,.10f));label.transform.position=new Vector3((i-1)*.45f,.96f,-.105f);label.transform.rotation=Quaternion.Euler(90,0,0);label.SetBox(.42f,.07f,.036f,true);toolLabels.Add(label);
            }
        }
        void Target(GameObject go,G3Panel panel,bool table=false){var t=go.AddComponent<G3WorldTarget>();t.Panel=panel;t.IsTable=table;}
        void Sign(string text,Vector3 pos,float em,float width){var l=Label("Shop sign",transform,new Color(.17f,.24f,.16f));l.transform.position=pos;l.SetBox(width,.4f,em,true);l.SetText(text);}
        Transform Plate(string name,Transform parent,Color color)
        {var go=GameObject.CreatePrimitive(PrimitiveType.Quad);go.name=name;go.transform.SetParent(parent,false);Destroy(go.GetComponent<Collider>());var mat=Own(new Material(flat));mat.color=color;go.GetComponent<Renderer>().sharedMaterial=mat;return go.transform;}
        BoundedGlyphLabel Label(string name,Transform parent,Color color)
        {var go=new GameObject(name);go.transform.SetParent(parent,false);var label=go.AddComponent<BoundedGlyphLabel>();label.Initialize(font,fontMat,color,TextAnchor.UpperLeft);labels.Add(label);return label;}
        float HeightAt(float z)=>SceneCamera.orthographic?SceneCamera.orthographicSize*2:2*Mathf.Tan(SceneCamera.fieldOfView*Mathf.Deg2Rad*.5f)*z;
        Vector3 PixelPoint(float x,float y,float z){float h=HeightAt(z);return new Vector3((x/PresentationWidth-.5f)*h*SceneCamera.aspect,(y/PresentationHeight-.5f)*h,z);}
        void PlacePlate(Transform p,Rect r,float z){float h=HeightAt(z);p.localPosition=PixelPoint(r.center.x,r.center.y,z);p.localScale=new Vector3(r.width/PresentationHeight*h,r.height/PresentationHeight*h,1);}
        void PlaceLabel(BoundedGlyphLabel l,Rect r,float pixels,float z,bool wrap=true)
        {float h=HeightAt(z);l.transform.localPosition=PixelPoint(r.center.x,r.center.y,z);l.SetBox(r.width/PresentationHeight*h,r.height/PresentationHeight*h,pixels/PresentationHeight*h,wrap);}
        public void SetWalking(bool value)
        {
            walking=value;SceneCamera.orthographic=!value;
            if(value)Walk.ApplyCamera();else{SceneCamera.orthographicSize=.63f;SceneCamera.transform.position=new Vector3(0,2.3f,-.56f);SceneCamera.transform.rotation=Quaternion.Euler(90,0,0);}
            if(current!=null)Layout();
        }
        public void Layout()
        {
            lastWidth=PresentationWidth;lastHeight=PresentationHeight;lastSafe=Safe;SceneCamera.aspect=(float)lastWidth/lastHeight;
            // Framing depends on the actual render target + safe area, never the Editor window.
            if(!walking){SceneCamera.orthographicSize=.63f*PresentationHeight/Mathf.Max(1,lastSafe.height);SceneCamera.transform.position=new Vector3(-(lastSafe.center.x/PresentationWidth-.5f)*SceneCamera.orthographicSize*2*SceneCamera.aspect,2.3f,-.56f-(lastSafe.center.y/PresentationHeight-.5f)*SceneCamera.orthographicSize*2);}
            if(current!=null)Show(current,panelModel);
        }
        public void InvalidateTicket(){number?.Invalidate();challenge?.Invalidate();}
        public void Show(G3Presenter presenter,G3PanelModel model)
        {
            current=presenter;panelModel=model;if(LayoutChanged){Layout();return;}used=0;float s=lastSafe.height/720f,margin=12*s;
            headerRect=new Rect(lastSafe.x+margin,lastSafe.yMax-78*s,lastSafe.width-2*margin,66*s);footerRect=new Rect(lastSafe.x+margin,lastSafe.y+margin,lastSafe.width-2*margin,98*s);
            PlacePlate(header,headerRect,.55f);PlacePlate(footer,footerRect,.55f);
            var state=presenter.Snapshot;var t=state.CurrentTicket;var bill=presenter.Service.PreviewNightBill();
            headerText.SetText(state.RecoveryRequired?"存档恢复受阻 · 请保留原件 · 现金暂不可确认":"现金 "+G3Text.Money(state.CashMinor)+"    今晚 "+G3Text.Money(bill.TotalDueMinor)+"    已购 "+state.TicketsPurchasedToday+" / 12    已结算 "+state.SettledTicketCount+(string.IsNullOrEmpty(state.FixtureLabel)?"    G3 首日":"    QA 固定新局"));
            PlaceLabel(headerText,Inset(headerRect,14*s,11*s),27*s,.48f,false);
            string summary;
            if(state.RecoveryRequired)summary="存档待恢复，票面已隐藏";
            else if(t==null)summary="空桌 · 两种票均为 100 金币";
            else if(t.Phase==TicketPhase.SETTLED){var record=state.Settlements.LastOrDefault(x=>x.TicketId==t.Id);summary=record==null?"已结算": "原奖 "+G3Text.Money(record.RawPrizeMinor)+" · 已收 "+G3Text.Money(record.TotalMinor)+" · 净额 "+G3Text.Signed(record.NetMinor);}
            else{var p=presenter.Service.PreviewSettlement();summary=p==null?(t.TicketType=="number"?"号码票 · 已揭 "+t.Scratch.RevealedCellCount+" / 6":"挑战票 · 安全 "+t.SafeCount+" 格 · "+(t.SelectedCell>=0?"完成已选格":"请主动选格")):"原奖 "+G3Text.Money(p.RawPrizeMinor)+" · 追加 "+G3Text.Money(p.TotalMinor-p.RawPrizeMinor)+" · 待收 "+G3Text.Money(p.TotalMinor)+" · 净额 "+G3Text.Signed(p.NetMinor);}
            resultText.SetText(summary+(t!=null?" · 点此明细":""));PlaceLabel(resultText,new Rect(footerRect.x+14*s,footerRect.y+51*s,footerRect.width-28*s,34*s),28*s,.47f,false);
            string feedback=presenter.Status;
            if(G3QaEvidence.Enabled&&!presenter.IsCommitting&&!state.RecoveryRequired&&t!=null&&t.SelectedCell>=0&&!PanelVisible)
                feedback="已保存格 "+(((t.SelectedCell+4)%8)+1)+" · QA r"+state.Revision+" · selection="+G3QaEvidence.SelectionMarker(t);
            statusText.SetText(feedback);PlaceLabel(statusText,new Rect(footerRect.x+14*s,footerRect.y+10*s,footerRect.width-28*s,34*s),24*s,.47f,false);
            bool empty=t==null&&!state.RecoveryRequired;emptyText.gameObject.SetActive(empty);
            if(!presenter.IsCommitting&&!state.RecoveryRequired){number.Show(state);challenge.Show(state);}else InvalidateTicket();
            for(int i=0;i<3;i++)
            {
                // Current and next are different authorities. Preserve the original slot,
                // including holes. A purchased ticket never borrows a future tool or level.
                var live=t?.ConfigurationSnapshot.SingleOrDefault(x=>x.TableSlot==i);
                string id=t==null?state.NextToolIds[i]:live?.ItemId??"";
                int level=t==null?(string.IsNullOrEmpty(id)?0:state.Tools.Single(x=>x.ItemId==id).Level):live?.Level??0;
                toolLabels[i].SetText(state.RecoveryRequired?"存档待恢复":(t==null?"下张":"本张")+(i+1)+" "+(string.IsNullOrEmpty(id)?"空位":G3Text.Tool(id)+" "+level));
                toolObjects[i].sharedMaterial.color=state.RecoveryRequired||string.IsNullOrEmpty(id)?new Color(.48f,.48f,.38f):new Color(.78f,.65f,.30f);
            }
            if(!PanelVisible)
            {
                float w=184*s,h=96*s,x=lastSafe.x+16*s,y=lastSafe.yMax-178*s;
                AddButton("open-tickets","购票",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Tickets),new Rect(x,y,w,h));
                AddButton("open-shop","货架",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Shop),new Rect(x,y-98*s,w,h));
                AddButton("open-inventory","收纳",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Inventory),new Rect(x,y-196*s,w,h));
                AddButton("open-drawer","抽屉",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Drawer),new Rect(x,y-294*s,w,h));
                AddButton("stand",walking?"坐回票桌":"起身走动",new G3Action(walking?G3ActionKind.Sit:G3ActionKind.Stand),new Rect(x,y-392*s,w,h));
                x=lastSafe.xMax-w-16*s;
                AddButton("open-phone","手机",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Phone),new Rect(x,y,w,h));
                AddButton("open-bill","账单",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Bill),new Rect(x,y-98*s,w,h));
                AddButton("open-settings","设置 / 规则",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Settings),new Rect(x,y-196*s,w,h));
                if(presenter.IsCommitting)AddButton("retry","确认交易",new G3Action(G3ActionKind.Retry),new Rect(x,y-294*s,w,h));
                else if(!walking&&t!=null&&t.Phase!=TicketPhase.SETTLED)
                {
                    bool claim=presenter.Service.PreviewSettlement()!=null;
                    AddButton("claim",t.TicketType=="challenge"?"收手并结算":"收下奖金",new G3Action(G3ActionKind.Claim),new Rect(x,y-294*s,w,h),claim);
                    if(claim&&state.TicketsPurchasedToday<12)AddButton("claim-next","收下再买\n同型 100",new G3Action(G3ActionKind.ClaimThenBuy,t.TicketType),new Rect(x,y-392*s,w,h));
                    else if(presenter.QuickEnabled)AddButton("quick",t.TicketType=="challenge"?"快揭已选格":"快速揭晓",new G3Action(G3ActionKind.QuickReveal),new Rect(x,y-392*s,w,h),t.TicketType=="number"||t.SelectedCell>=0);
                }
                if(walking)WalkControls(s);
            }
            ShowModal(model,s);
            foreach(var b in pool.Skip(used))b.Root.SetActive(false);
        }
        void ShowModal(G3PanelModel model,float s)
        {
            modal.gameObject.SetActive(PanelVisible);panelTitle.gameObject.SetActive(PanelVisible);panelBody.gameObject.SetActive(PanelVisible);panelFoot.gameObject.SetActive(PanelVisible);
            if(!PanelVisible)return;
            modalRect=new Rect(lastSafe.x+12*s,lastSafe.y+12*s,lastSafe.width-24*s,lastSafe.height-24*s);PlacePlate(modal,modalRect,.33f);
            panelTitle.SetText(model.Title);PlaceLabel(panelTitle,new Rect(modalRect.x+24*s,modalRect.yMax-68*s,modalRect.width-250*s,50*s),32*s,.22f,false);
            bool pendingQa=G3QaEvidence.Enabled&&current.IsCommitting&&current.Panel!=G3Panel.QaEvidence&&current.Panel!=G3Panel.Settings;
            AddButton(pendingQa?"qa-settings":"close-panel",pendingQa?"QA 设置":"返回",pendingQa?new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Settings):new G3Action(G3ActionKind.Close),new Rect(modalRect.xMax-200*s,modalRect.yMax-106*s,176*s,88*s),true,.25f);
            panelBody.SetText(model.Body);panelFoot.SetText(model.Footnote);
            if(model.Evidence)
            {
                evidenceBodyRect=new Rect(modalRect.x+24*s,modalRect.y+184*s,modalRect.width-48*s,modalRect.height-302*s);
                PlaceLabel(panelBody,evidenceBodyRect,24*s,.22f,false);
                PlaceLabel(panelFoot,new Rect(modalRect.x+24*s,modalRect.y+18*s,modalRect.width-48*s,52*s),23*s,.22f,true);
                float gap=12*s,w=(modalRect.width-48*s-2*gap)/3;
                for(int i=0;i<model.Cards.Count;i++){var card=model.Cards[i];AddButton(card.Id,card.Text,card.Action,new Rect(modalRect.x+24*s+i*(w+gap),modalRect.y+80*s,w,88*s),card.Enabled,.25f,28);}
                return;
            }
            bool grid=model.Grid;float bodyHeight;
            if(model.Cards.Count==0)bodyHeight=modalRect.height-180*s;
            else if(grid)bodyHeight=(model.LargeGrid?92:172)*s;
            else bodyHeight=Mathf.Min(312*s,modalRect.height-(model.Cards.Count*102+180)*s);
            if(bodyHeight<96*s)bodyHeight=96*s;
            PlaceLabel(panelBody,new Rect(modalRect.x+24*s,modalRect.yMax-118*s-bodyHeight,modalRect.width-48*s,bodyHeight),grid?30*s:32*s,.22f,true);
            PlaceLabel(panelFoot,new Rect(modalRect.x+24*s,modalRect.y+18*s,modalRect.width-48*s,52*s),23*s,.22f,true);
            if(grid)
            {
                int cols=model.LargeGrid?4:model.Cards.Count>6?3:2;int rows=Mathf.CeilToInt((float)model.Cards.Count/cols);float gap=12*s,w=(modalRect.width-48*s-gap*(cols-1))/cols;
                float available=modalRect.height-118*s-bodyHeight-86*s,h=rows>0?Mathf.Min(96*s,(available-gap*(rows-1))/rows):96*s;
                for(int i=0;i<model.Cards.Count;i++){var card=model.Cards[i];float y=modalRect.y+80*s+(rows-1-i/cols)*(h+gap);AddButton(card.Id,card.Text,card.Action,new Rect(modalRect.x+24*s+(i%cols)*(w+gap),y,w,h),card.Enabled,.25f,model.LargeGrid?32:30);}
            }
            else
            {
                for(int i=0;i<model.Cards.Count;i++){var card=model.Cards[i];float y=modalRect.y+80*s+(model.Cards.Count-1-i)*102*s;AddButton(card.Id,card.Text,card.Action,new Rect(modalRect.x+24*s,y,modalRect.width-48*s,90*s),card.Enabled,.25f,28);}
            }
            if(current.IsCommitting)AddButton("retry","确认上笔交易",new G3Action(G3ActionKind.Retry),new Rect(modalRect.xMax-340*s,modalRect.y+80*s,310*s,96*s),true,.19f);
        }
        void AddButton(string id,string text,G3Action action,Rect rect,bool enabled=true,float z=.51f,float fontPixels=30)
        {
            if(used>=pool.Count)throw new InvalidOperationException("UI button capacity exceeded");var b=pool[used++];b.Id=id;b.Action=action;b.Rect=rect;bool evidenceControl=G3QaEvidence.Enabled&&(action.Kind==G3ActionKind.Open&&(action.Slot==(int)G3Panel.Settings||action.Slot==(int)G3Panel.QaEvidence)||(current.Panel==G3Panel.QaEvidence&&(action.Kind==G3ActionKind.CopyEvidence||action.Kind==G3ActionKind.ScrollEvidence))||(action.Kind==G3ActionKind.Close&&(current.Panel==G3Panel.QaEvidence||current.Panel==G3Panel.Settings)));
            b.Enabled=enabled&&(!current.IsCommitting||evidenceControl)||action.Kind==G3ActionKind.Retry;b.Root.SetActive(true);
            PlacePlate(b.Plate,rect,z);b.Plate.GetComponent<Renderer>().sharedMaterial.color=b.Enabled?new Color(.16f,.35f,.28f):new Color(.18f,.23f,.21f);
            b.Label.SetText(text);PlaceLabel(b.Label,Inset(rect,13*lastSafe.height/720f,10*lastSafe.height/720f),fontPixels*lastSafe.height/720f,z-.025f,true);
        }
        void WalkControls(float s)
        {
            float x=lastSafe.center.x,w=98*s,h=90*s,y=lastSafe.y+122*s;
            AddButton("walk-forward","前",new G3Action(G3ActionKind.MoveForward),new Rect(x-w*.5f,y+100*s,w,h));
            AddButton("walk-back","后",new G3Action(G3ActionKind.MoveBack),new Rect(x-w*.5f,y,w,h));
            AddButton("walk-left","左",new G3Action(G3ActionKind.MoveLeft),new Rect(x-w*1.6f,y,w,h));
            AddButton("walk-right","右",new G3Action(G3ActionKind.MoveRight),new Rect(x+w*.6f,y,w,h));
            AddButton("turn-left","转左",new G3Action(G3ActionKind.TurnLeft),new Rect(x-w*2.7f,y,w,h));
            AddButton("turn-right","转右",new G3Action(G3ActionKind.TurnRight),new Rect(x+w*1.7f,y,w,h));
        }
        static Rect Inset(Rect r,float x,float y)=>new Rect(r.x+x,r.y+y,Mathf.Max(.1f,r.width-2*x),Mathf.Max(.1f,r.height-2*y));
        public Rect ButtonRect(string id){foreach(var b in pool.Take(used))if(b.Root.activeInHierarchy&&b.Id==id)return b.Rect;throw new KeyNotFoundException(id);}
        public bool HasButton(string id)=>pool.Take(used).Any(b=>b.Root.activeInHierarchy&&b.Id==id);
        public bool ConsumeUi(Vector2 pixel,out G3Action action)
        {
            // Check frontmost controls first (confirmation/recovery overlays win).
            for(int i=used-1;i>=0;i--){var b=pool[i];if(b.Root.activeInHierarchy&&b.Rect.Contains(pixel)){action=b.Enabled?b.Action:default;return true;}}
            if(!PanelVisible&&footerRect.Contains(pixel)&&current.Snapshot.CurrentTicket!=null){action=new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Settlement);return true;}
            action=default;return PanelVisible||headerRect.Contains(pixel)||footerRect.Contains(pixel);
        }
        public bool TryScratchUv(Vector2 pixel,out Uv uv)
        {
            if(pixel.x<0||pixel.y<0||pixel.x>=PresentationWidth||pixel.y>=PresentationHeight){uv=default;return false;}
            return Surface.TryPaperUv(SceneCamera.ViewportPointToRay(new Vector3(pixel.x/PresentationWidth,pixel.y/PresentationHeight,0)),out uv);
        }
        public G3WorldTarget WorldTarget(Vector2 pixel)
        {
            var ray=SceneCamera.ViewportPointToRay(new Vector3(pixel.x/PresentationWidth,pixel.y/PresentationHeight,0));
            if(Physics.Raycast(ray,out RaycastHit hit,4))return hit.collider.GetComponent<G3WorldTarget>();return null;
        }
        public Vector2 WorldToPresentationPoint(Vector3 point){var v=SceneCamera.WorldToViewportPoint(point);return new Vector2(v.x*PresentationWidth,v.y*PresentationHeight);}
        public void RefreshGlyphGeometry(){foreach(var label in labels)label.RebuildIfNeeded();if(number.CellLabels!=null)foreach(var label in number.CellLabels)label.RebuildIfNeeded();if(challenge.CellLabels!=null)foreach(var label in challenge.CellLabels)label.RebuildIfNeeded();}
        public string[] OverflowingHudLabels=>labels.Where(x=>x.gameObject.activeInHierarchy&&x.transform.IsChildOf(hud)&&(!x.Fits||x.MissingGlyphCount>0)).Select(x=>x.name+": "+x.Text).ToArray();
        public bool AllHudLabelsFit=>labels.Where(x=>x.gameObject.activeInHierarchy&&x.transform.IsChildOf(hud)).All(x=>x.Fits&&x.MissingGlyphCount==0);
        public void SettlementFeedback(bool reduceFlash){pulseReduced=reduceFlash;settlementPulse=reduceFlash?0:.22f;}
        void Update()
        {
            if(footer==null||settlementPulse<=0)return;settlementPulse=Mathf.Max(0,settlementPulse-Time.unscaledDeltaTime);
            var baseColor=new Color(.055f,.12f,.105f);var tint=new Color(.18f,.22f,.12f);
            footer.GetComponent<Renderer>().sharedMaterial.color=Color.Lerp(baseColor,tint,settlementPulse/.22f);
        }
        void OnDestroy(){foreach(var item in owned)if(item!=null)Destroy(item);}
    }
}

using System;
using System.Collections.Generic;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Rendering;
using UnityEngine;
using UnityEngine.Rendering.Universal;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.EnhancedTouch;
using ETouch=UnityEngine.InputSystem.EnhancedTouch.Touch;

namespace Lottery.G3.Interaction
{
    public sealed class G3SceneView : MonoBehaviour
    {
        sealed class ButtonVisual
        {
            public string Id;public GameObject Root;public Transform Plate;public G3HudIcon Icon;
            public BoundedGlyphLabel Label,Title,Detail;public Rect Rect,FaceRect;public G3Action Action;
            public bool Enabled,Primary,Selected,Navigation,Movement,Pressed,Catalog;public G3HudSymbol Symbol;
        }
        readonly List<UnityEngine.Object> owned=new List<UnityEngine.Object>();readonly List<BoundedGlyphLabel> labels=new List<BoundedGlyphLabel>();readonly List<ButtonVisual> pool=new List<ButtonVisual>();
        Font font;Shader flat;Material fontMat;Transform hud,header,dayHeader,qaTag,headerDivider,footer,modal,feedbackPlate,modalRule;
        BoundedGlyphLabel headerText,cashValue,nightCaption,nightValue,dayText,qaText,statusText,resultText,panelTitle,panelBody,panelFoot,emptyText;
        G3HudIcon walletIcon,nightIcon;bool headerFallback,phoneOwnsCamera;Vector3 beforePhonePosition;Quaternion beforePhoneRotation;float beforePhoneFov;bool beforePhoneOrthographic;
        string lastFeedback="";float feedbackUntil;bool persistentFeedback;
        readonly List<G3ToolDisplay> toolDisplays=new List<G3ToolDisplay>();
        readonly List<BoundedGlyphLabel> shopPriceLabels=new List<BoundedGlyphLabel>();
        static readonly string[] DisplayStockIds={"small_prize_box","inspection_lamp","large_prize_stamp"};
        readonly List<Transform> toolChipPlates=new List<Transform>();readonly List<Rect> toolChipRects=new List<Rect>();
        readonly List<Renderer> toolObjects=new List<Renderer>();readonly List<BoundedGlyphLabel> toolLabels=new List<BoundedGlyphLabel>();
        ConfirmedTicketSurface number,challenge;G3Presenter current;G3PanelModel panelModel;
        float settlementPulse;bool pulseReduced;int lastWidth,lastHeight,used;Rect lastSafe,headerRect,dayRect,qaRect,footerRect,footerHitRect,modalRect,evidenceBodyRect,feedbackRect;bool walking,moreVisible;
        public Camera SceneCamera {get;private set;}
        public G3ShopWalk Walk {get;private set;}
        public G3ShopEnvironment Environment {get;private set;}
        public G3PhoneDisplay Phone {get;private set;}
        public Rect TableInteractionRect=>new Rect(Safe.center.x-360*Safe.height/720f,Safe.y+150*Safe.height/720f,760*Safe.height/720f,440*Safe.height/720f);
        public bool MoreVisible=>moreVisible;
        public string[] VisibleControlIds=>pool.Take(used).Where(b=>b.Root.activeInHierarchy).Select(b=>b.Id).Concat(Phone!=null?Phone.VisibleControlIds:new string[0]).Distinct().ToArray();
        public Rect ToolPresentationBounds(int slot)
        {
            var bounds=toolDisplays[slot].WorldBounds;var min=new Vector2(float.PositiveInfinity,float.PositiveInfinity);var max=new Vector2(float.NegativeInfinity,float.NegativeInfinity);
            for(int i=0;i<8;i++){var p=bounds.center+Vector3.Scale(bounds.extents,new Vector3((i&1)==0?-1:1,(i&2)==0?-1:1,(i&4)==0?-1:1));var q=WorldToPresentationPoint(p);min=Vector2.Min(min,q);max=Vector2.Max(max,q);}
            return Rect.MinMaxRect(min.x,min.y,max.x,max.y);
        }
        public float VisibleOpaqueHudAreaRatio
        {
            get
            {
                // Conservative visible-face coverage; translucent chrome is deliberately not counted as zero.
                var rects=pool.Take(used).Where(b=>b.Root.activeInHierarchy).Select(b=>b.FaceRect).ToList();
                for(int i=0;i<toolChipPlates.Count;i++)if(toolChipPlates[i].gameObject.activeInHierarchy)rects.Add(toolChipRects[i]);if(dayHeader.gameObject.activeInHierarchy)rects.Add(dayRect);if(qaTag.gameObject.activeInHierarchy)rects.Add(qaRect);if(feedbackPlate.gameObject.activeInHierarchy)rects.Add(feedbackRect);if(header.gameObject.activeInHierarchy)rects.Add(headerRect);if(footer.gameObject.activeInHierarchy)rects.Add(footerRect);if(modal.gameObject.activeInHierarchy)rects.Add(modalRect);
                var xs=rects.SelectMany(r=>new[]{Mathf.Clamp(r.xMin,Safe.xMin,Safe.xMax),Mathf.Clamp(r.xMax,Safe.xMin,Safe.xMax)}).Distinct().OrderBy(x=>x).ToArray();float area=0;
                for(int i=1;i<xs.Length;i++){float mid=(xs[i-1]+xs[i])*.5f,end=Safe.yMin,total=0;foreach(var r in rects.Where(r=>r.xMin<mid&&r.xMax>mid).OrderBy(r=>r.yMin)){float lo=Mathf.Max(end,Mathf.Max(Safe.yMin,r.yMin)),hi=Mathf.Min(Safe.yMax,r.yMax);if(hi>lo){total+=hi-lo;end=hi;}}area+=(xs[i]-xs[i-1])*total;}
                return area/(Safe.width*Safe.height);
            }
        }
        public ConfirmedTicketSurface Surface=>current?.Snapshot.CurrentTicket?.TicketType=="challenge"?challenge:number;
        public bool PanelVisible=>current!=null&&current.Panel!=G3Panel.None;
        public string VisibleSummary=>resultText.Text;
        public string VisibleStatus=>statusText.Text;
        // Normalize the deliberate two-line sign back to the same visible wording.
        public string VisibleToolSlot(int slot)=>toolLabels[slot].Text.Replace("\n"," ");
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
            BuildShop(lit);
            var phoneObject=new GameObject("Persistent physical chat phone");phoneObject.transform.SetParent(transform,false);Phone=phoneObject.AddComponent<G3PhoneDisplay>();Phone.Initialize(font,flat,glyph,lit,Environment);
            var n=new GameObject("Approved number ticket");n.transform.SetParent(transform,false);n.transform.position=Environment.TicketPosition;n.transform.rotation=Quaternion.Euler(0,180,0);number=n.AddComponent<ConfirmedTicketSurface>();number.Build(numberArt,font,paper,silver,maskedFont,glyph,Environment.TicketWidth);
            var c=new GameObject("Approved challenge ticket");c.transform.SetParent(transform,false);c.transform.position=n.transform.position;c.transform.rotation=n.transform.rotation;challenge=c.AddComponent<ConfirmedTicketSurface>();challenge.Build(challengeArt,font,paper,silver,maskedFont,glyph,Environment.TicketWidth);
            var empty=new GameObject("Empty table prompt");empty.transform.SetParent(transform,false);empty.transform.position=Environment.TicketPosition+Vector3.up*.005f;empty.transform.rotation=Quaternion.Euler(90,180,0);emptyText=empty.AddComponent<BoundedGlyphLabel>();emptyText.Initialize(font,fontMat,new Color(.94f,.92f,.78f));emptyText.SetBox(.38f,.14f,.022f,true);emptyText.SetText("今日的第一张好运\n从柜台挑一张票");labels.Add(emptyText);
            var walker=new GameObject("Player short-distance body");walker.transform.SetParent(transform,false);Walk=walker.AddComponent<G3ShopWalk>();Walk.Initialize(SceneCamera,Environment.StandPosition,Environment.StandYaw);
            hud=new GameObject("Same-camera readable HUD").transform;hud.SetParent(SceneCamera.transform,false);
            header=Plate("Header",hud,G3HudTheme.Ink);dayHeader=Plate("Compact day progress",hud,G3HudTheme.Ink);qaTag=Plate("Isolated diagnostic run badge",hud,G3HudTheme.Ink);headerDivider=Plate("Wallet separator",hud,G3HudTheme.Rule);
            footer=Plate("Compact ticket detail chip",hud,G3HudTheme.Ink);modal=Plate("Context drawer background",hud,G3HudTheme.Ink);
            feedbackPlate=Plate("High contrast saved operation message",hud,G3HudTheme.Ink);modalRule=Plate("Modal copper section rule",hud,G3HudTheme.Copper);modalRule.GetComponent<G3HudSurface>().Tint(G3HudTheme.Rule,G3HudTheme.Rule);
            headerText=Label("Wallet label",hud,G3HudTheme.Card);cashValue=Label("Confirmed cash value",hud,G3HudTheme.Card);nightCaption=Label("Tonight payable label",hud,G3HudTheme.Card);nightValue=Label("Confirmed tonight payable",hud,G3HudTheme.Copper);
            dayText=Label("Game day purchases and settlements",hud,G3HudTheme.Card);qaText=Label("Explicit QA marker",hud,G3HudTheme.QuietInk);
            walletIcon=G3HudIcon.Create(hud,flat);nightIcon=G3HudIcon.Create(hud,flat);statusText=Label("Confirmed operation feedback",hud,G3HudTheme.Card);resultText=Label("Live ticket progress and detail route",hud,G3HudTheme.Paper);
            panelTitle=Label("Panel title",hud,G3HudTheme.Card);panelBody=Label("Panel explanation",hud,G3HudTheme.Paper);panelFoot=Label("Panel status",hud,G3HudTheme.QuietInk);
            for(int i=0;i<32;i++){var root=new GameObject("Routed control "+i);root.transform.SetParent(hud,false);pool.Add(new ButtonVisual{Root=root,Plate=Plate("Button surface",root.transform,G3HudTheme.Ink),Icon=G3HudIcon.Create(root.transform,flat),Label=Label("Button text",root.transform,G3HudTheme.Card,TextAnchor.MiddleCenter),Title=Label("Catalog item name",root.transform,G3HudTheme.Card,TextAnchor.UpperLeft),Detail=Label("Catalog price stock or placement",root.transform,G3HudTheme.QuietInk,TextAnchor.MiddleLeft)});}
            for(int i=0;i<toolLabels.Count;i++){toolLabels[i].transform.SetParent(hud,false);toolLabels[i].transform.localRotation=Quaternion.identity;toolChipPlates.Add(Plate("Confirmed configuration chip "+(i+1),hud,G3HudTheme.Ink));toolChipRects.Add(new Rect());}
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
            var shop=new GameObject("Authored room and bounded navigation");shop.transform.SetParent(transform,false);
            Environment=shop.AddComponent<G3ShopEnvironment>();Environment.Build();
            for(int i=0;i<3;i++)
            {
                var anchor=Environment.AnchorPosition("ShopPrice"+(i+1),new Vector3(.2f+i*.24f,1.07f,-1.38f));
                Box("Confirmed stock price card "+(i+1),anchor+Vector3.forward*.001f,new Vector3(.204f,.09f,.0006f),new Color(.90f,.88f,.79f),lit,false);
                var label=Label("Live shop sample price "+(i+1),transform,new Color(.13f,.16f,.14f));label.transform.position=anchor+Vector3.forward*.0016f;label.transform.rotation=Quaternion.Euler(Environment.AnchorEulerAngles("ShopPrice"+(i+1),new Vector3(0,180,0)));label.SetBox(.19f,.075f,.014f,true);shopPriceLabels.Add(label);
            }
            for(int i=0;i<3;i++)
            {
                var anchor=Environment.AnchorPosition("tool_"+(i+1),Environment.TicketPosition+new Vector3((i-1)*.39f,.015f,-.59f));
                // The authored FBX owns the wooden/black tool base. Each small sign
                // carries a short semantic-color line, never a full yellow underlay.
                // Slot three's sign sits left of its tool to clear the phone-safe edge.
                var tagOffset=new Vector3(i==2 ? .11f : 0f,.001f,i==2 ? .051f : .059f);
                var stand=Box("Configuration stand "+(i+1),anchor+tagOffset+new Vector3(-.053f,.001f,0),new Vector3(.004f,.002f,.022f),new Color(.48f,.48f,.38f),lit,false);
                toolObjects.Add(stand.GetComponent<Renderer>());var display=new GameObject("Physical tool slot "+(i+1));display.transform.SetParent(transform,false);display.transform.position=anchor+Vector3.up*.0011f;
                var visual=display.AddComponent<G3ToolDisplay>();visual.Initialize(lit);toolDisplays.Add(visual);
                var label=Label("Current tool name "+i,transform,G3HudTheme.Card,TextAnchor.MiddleCenter);label.transform.position=anchor+tagOffset+Vector3.up*.001f;label.transform.rotation=Quaternion.Euler(90,180,0);label.SetBox(.100f,.029f,.013f,true);toolLabels.Add(label);
            }
        }
        void Target(GameObject go,G3Panel panel,bool table=false){var t=go.AddComponent<G3WorldTarget>();t.Panel=panel;t.IsTable=table;}
        void Sign(string text,Vector3 pos,float em,float width){var l=Label("Shop sign",transform,new Color(.17f,.24f,.16f));l.transform.position=pos;l.SetBox(width,.4f,em,true);l.SetText(text);}
        Transform Plate(string name,Transform parent,Color color)
        {return G3HudSurface.Create(name,parent,fontMat.shader,color,G3HudTheme.Rule);}
        BoundedGlyphLabel Label(string name,Transform parent,Color color,TextAnchor alignment=TextAnchor.UpperLeft)
        {var go=new GameObject(name);go.transform.SetParent(parent,false);var label=go.AddComponent<BoundedGlyphLabel>();label.Initialize(font,fontMat,color,alignment);labels.Add(label);return label;}
        float HeightAt(float z)=>SceneCamera.orthographic?SceneCamera.orthographicSize*2:2*Mathf.Tan(SceneCamera.fieldOfView*Mathf.Deg2Rad*.5f)*z;
        Vector3 PixelPoint(float x,float y,float z){float h=HeightAt(z);return new Vector3((x/PresentationWidth-.5f)*h*SceneCamera.aspect,(y/PresentationHeight-.5f)*h,z);}
        void PlacePlate(Transform p,Rect r,float z)
        {p.GetComponent<Renderer>().sortingOrder=30000;float h=HeightAt(z);p.localPosition=PixelPoint(r.center.x,r.center.y,z);p.localScale=new Vector3(r.width/PresentationHeight*h,r.height/PresentationHeight*h,1);p.GetComponent<G3HudSurface>()?.Configure(r.width,r.height,Mathf.Min(24*Safe.height/720f,r.height*.5f),Safe.height/720f);}
        void PlaceIcon(G3HudIcon icon,Rect r,float z)
        {float h=HeightAt(z);icon.transform.localPosition=PixelPoint(r.center.x,r.center.y,z);icon.transform.localScale=Vector3.one*(r.height/PresentationHeight*h);}
        void PlaceLabel(BoundedGlyphLabel l,Rect r,float pixels,float z,bool wrap=true)
        {l.GetComponent<Renderer>().sortingOrder=30001;float h=HeightAt(z);l.transform.localPosition=PixelPoint(r.center.x,r.center.y,z);l.SetBox(r.width/PresentationHeight*h,r.height/PresentationHeight*h,pixels/PresentationHeight*h,wrap);}
        public void SetWalking(bool value)
        {
            moreVisible=false;walking=value;SceneCamera.orthographic=false;SceneCamera.fieldOfView=value?64:32;
            if(value)Walk.ApplyCamera();else FrameTable();
            if(current!=null)Layout();
        }
        void FrameTable()
        {
            SceneCamera.orthographic=false;SceneCamera.fieldOfView=32;
            var focus=Environment.TableLookAt;var cameraPosition=focus+(Environment.TableCameraPosition-focus)*(PresentationHeight/Mathf.Max(1,Safe.height));
            // Constant oblique perspective keeps paper thickness and the room visible.
            SceneCamera.transform.position=cameraPosition;SceneCamera.transform.LookAt(focus);
            float d=Vector3.Distance(cameraPosition,focus),h=2*Mathf.Tan(SceneCamera.fieldOfView*Mathf.Deg2Rad*.5f)*d;
            var desired=TableInteractionRect.center;
            SceneCamera.transform.position-=SceneCamera.transform.right*((desired.x/PresentationWidth-.5f)*h*SceneCamera.aspect)+SceneCamera.transform.up*((desired.y/PresentationHeight-.5f)*h);
        }
        public void Layout()
        {
            lastWidth=PresentationWidth;lastHeight=PresentationHeight;lastSafe=Safe;SceneCamera.aspect=(float)lastWidth/lastHeight;
            if(!phoneOwnsCamera&&!walking)FrameTable();if(current!=null)Show(current,panelModel);
        }
        public void InvalidateTicket(){number?.Invalidate();challenge?.Invalidate();}
        public void Show(G3Presenter presenter,G3PanelModel model)
        {
            current=presenter;panelModel=model;if(LayoutChanged){Layout();return;}used=0;float s=lastSafe.height/720f;
            if(PanelVisible)moreVisible=false;
            SyncPhoneCamera(presenter,model);
            
            var state=presenter.Snapshot;var t=state.CurrentTicket;var bill=presenter.Service.PreviewNightBill();Environment.Sync(state);
            for(int i=0;i<shopPriceLabels.Count;i++)
            {
                var stock=state.Stock.FirstOrDefault(x=>x.ItemId==DisplayStockIds[i]&&!x.IsConsumable&&x.Quantity>0);
                shopPriceLabels[i].SetText(state.RecoveryRequired?"库存待确认":G3Text.Tool(DisplayStockIds[i])+"\n"+(stock==null?"样品 · 暂无现货":G3Text.Money(stock.PriceMinor)+" 金币 · 库存 "+stock.Quantity));
            }
            LayoutHeader(state,bill,s);
            string summary;
            if(state.RecoveryRequired)summary="存档待恢复";
            else if(t==null)summary="两种票 · 100 金币";
            else if(t.Phase==TicketPhase.SETTLED){var record=state.Settlements.LastOrDefault(x=>x.TicketId==t.Id);summary=record==null?"已结算":"已收 "+G3Text.Money(record.TotalMinor)+" · 明细";}
            else{var p=presenter.Service.PreviewSettlement();summary=p==null?(t.TicketType=="number"?"已揭 "+t.Scratch.RevealedCellCount+" / 6":"安全 "+t.SafeCount+" 格")+" · 明细":"可收 "+G3Text.Money(p.TotalMinor)+" · 明细";}
            resultText.SetText(summary);
            float summaryWidth=Mathf.Min(396*s,Mathf.Max(210*s,TextWidth(summary,32*s)+32*s));
            footerRect=new Rect(lastSafe.x+372*s,lastSafe.y+36*s,summaryWidth,Mathf.Max(48*s,TextHeight(summary,32*s,summaryWidth-32*s)+14*s));
            footerHitRect=new Rect(footerRect.x,lastSafe.y+12*s,footerRect.width,Mathf.Max(96*s,footerRect.yMax-lastSafe.y-8*s));
            PlacePlate(footer,footerRect,.55f);PlaceLabel(resultText,Inset(footerRect,16*s,7*s),32*s,.47f,true);
            string feedback=presenter.Status;
            if(G3QaEvidence.Enabled&&!string.IsNullOrEmpty(state.FixtureLabel)&&!presenter.IsCommitting&&!state.RecoveryRequired&&t!=null&&t.SelectedCell>=0&&!PanelVisible)
                feedback="已保存格 "+(((t.SelectedCell+4)%8)+1)+" · QA r"+state.Revision+" · selection="+G3QaEvidence.SelectionMarker(t);
            statusText.SetText(feedback);if(lastFeedback!=feedback){lastFeedback=feedback;feedbackUntil=Time.unscaledTime+5f;}
            persistentFeedback=presenter.IsCommitting||state.RecoveryRequired||(G3QaEvidence.Enabled&&!string.IsNullOrEmpty(state.FixtureLabel));
            float feedbackWidth=Mathf.Min(lastSafe.width-48*s,Mathf.Max(480*s,Mathf.Min(1000*s,TextWidth(feedback,32*s)))),feedbackHeight=TextHeight(feedback,32*s,feedbackWidth);
            feedbackRect=new Rect(lastSafe.center.x-feedbackWidth*.5f-16*s,headerRect.yMin-14*s-feedbackHeight-16*s,feedbackWidth+32*s,feedbackHeight+16*s);
            PlacePlate(feedbackPlate,feedbackRect,.55f);PlaceLabel(statusText,Inset(feedbackRect,16*s,8*s),32*s,.47f,true);
            bool empty=t==null&&!state.RecoveryRequired;emptyText.gameObject.SetActive(empty);
            if(!presenter.IsCommitting&&!state.RecoveryRequired){number.Show(state);challenge.Show(state);}else InvalidateTicket();
            for(int i=0;i<3;i++)
            {
                // Current and next are different authorities. Preserve the original slot,
                // including holes. A purchased ticket never borrows a future tool or level.
                var live=t?.ConfigurationSnapshot.SingleOrDefault(x=>x.TableSlot==i);
                string id=t==null?state.NextToolIds[i]:live?.ItemId??"";
                int level=t==null?(string.IsNullOrEmpty(id)?0:state.Tools.Single(x=>x.ItemId==id).Level):live?.Level??0;
                toolLabels[i].SetText(state.RecoveryRequired?"存档待恢复":(t==null?"下张":"本张")+(i+1)+"\n"+(string.IsNullOrEmpty(id)?"空位":G3Text.Tool(id)+" "+level));
                toolDisplays[i].Show(state.RecoveryRequired?"":id);
                toolObjects[i].sharedMaterial.color=state.RecoveryRequired||string.IsNullOrEmpty(id)?new Color(.48f,.48f,.38f):new Color(.78f,.65f,.30f);
            }
            LayoutToolChips(s);
            if(!PanelVisible)
            {
                // Four contract-required routes stay visible; secondary routes use a
                // real, input-routed More drawer instead of eight equal-weight blocks.
                float w=112*s,h=112*s,x=lastSafe.x+16*s,y=lastSafe.y+12*s;
                AddButton("stand",walking?"坐下":"起身",new G3Action(walking?G3ActionKind.Sit:G3ActionKind.Stand),new Rect(x,y+h,w,h));
                AddButton("open-shop","货架",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Shop),new Rect(x+w,y+h,w,h));
                AddButton("open-inventory","收纳",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Inventory),new Rect(x,y,w,h));
                AddButton("open-phone","手机",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Phone),new Rect(x+w,y,w,h));
                AddButton("open-more",moreVisible?"收起":"更多",new G3Action(G3ActionKind.ToggleMore),new Rect(x+2*w+8*s,y,112*s,96*s));
                if(moreVisible)
                {
                    float mx=x+2*w+8*s,mw=168*s;
                    AddButton("open-tickets","购票",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Tickets),new Rect(mx,y+104*s,mw,96*s));
                    AddButton("open-drawer","抽屉",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Drawer),new Rect(mx,y+208*s,mw,96*s));
                    AddButton("open-bill","账单",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Bill),new Rect(mx,y+312*s,mw,96*s));
                    AddButton("open-settings","设置",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Settings),new Rect(mx,y+416*s,mw,96*s));
                }
                x=lastSafe.xMax-244*s;y=lastSafe.y+12*s;w=232*s;h=96*s;
                if(presenter.IsCommitting)AddButton("retry","确认交易",new G3Action(G3ActionKind.Retry),new Rect(x,y,w,h));
                else if(!walking&&t!=null&&t.Phase!=TicketPhase.SETTLED)
                {
                    bool claim=presenter.Service.PreviewSettlement()!=null;
                    AddButton("claim",t.TicketType=="challenge"?(claim?"收手并结算":"完成当前格"):(claim?"收下奖金":"待刮完兑奖"),new G3Action(G3ActionKind.Claim),new Rect(x,y,w,h),claim);
                    if(claim&&state.TicketsPurchasedToday<12)AddButton("claim-next","收下再买\n同型 100",new G3Action(G3ActionKind.ClaimThenBuy,t.TicketType),new Rect(x-240*s,y,w,h));
                    else if(presenter.QuickEnabled)AddButton("quick",t.TicketType=="challenge"?"揭晓本格":"快速揭晓",new G3Action(G3ActionKind.QuickReveal),new Rect(x-240*s,y,w,h),t.TicketType=="number"||t.SelectedCell>=0);
                }
                if(walking&&!moreVisible)WalkControls(s);
            }
            bool clearHud=!PanelVisible;bool showFeedback=clearHud&&!moreVisible&&!string.IsNullOrEmpty(feedback)&&(persistentFeedback||Time.unscaledTime<feedbackUntil);
            feedbackPlate.gameObject.SetActive(showFeedback);statusText.gameObject.SetActive(showFeedback);
            header.gameObject.SetActive(clearHud);dayHeader.gameObject.SetActive(clearHud);headerText.gameObject.SetActive(clearHud);dayText.gameObject.SetActive(clearHud);
            cashValue.gameObject.SetActive(clearHud&&!headerFallback);nightCaption.gameObject.SetActive(clearHud&&!headerFallback);nightValue.gameObject.SetActive(clearHud&&!headerFallback);walletIcon.gameObject.SetActive(clearHud&&!headerFallback);nightIcon.gameObject.SetActive(clearHud&&!headerFallback);headerDivider.gameObject.SetActive(clearHud&&!headerFallback);
            bool qa=clearHud&&!string.IsNullOrEmpty(state.FixtureLabel);qaTag.gameObject.SetActive(qa);qaText.gameObject.SetActive(qa);
            footer.gameObject.SetActive(clearHud&&!moreVisible);resultText.gameObject.SetActive(clearHud&&!moreVisible);
            ShowModal(model,s);
            foreach(var b in pool.Skip(used))b.Root.SetActive(false);
        }
        void LayoutToolChips(float s)
        {
            var corners=new[]{new Uv(0,0),new Uv(0,1),new Uv(1,0),new Uv(1,1)}.Select(uv=>WorldToPresentationPoint(Surface.PaperUvToWorld(uv))).ToArray();
            float paperLeft=corners.Min(p=>p.x),paperRight=corners.Max(p=>p.x),w=216*s,h=84*s;
            for(int i=0;i<toolLabels.Count;i++)
            {
                bool show=!walking&&!PanelVisible&&!moreVisible;toolChipPlates[i].gameObject.SetActive(show);toolLabels[i].gameObject.SetActive(show);if(!show)continue;
                var p=WorldToPresentationPoint(Environment.AnchorPosition("tool_"+(i+1),Environment.TicketPosition)+Vector3.forward*.07f);
                bool left=i==1;float lo=left?Safe.x+12*s:paperRight+12*s,hi=left?paperLeft-12*s-w:Safe.xMax-12*s-w;
                float x=Mathf.Clamp(p.x-w*.5f,Mathf.Min(lo,hi),Mathf.Max(lo,hi));
                float y=Mathf.Clamp(p.y-h*.5f,Safe.y+(i==2?120:250)*s,Safe.yMax-164*s);
                var r=new Rect(x,y,w,h);toolChipRects[i]=r;PlacePlate(toolChipPlates[i],r,.57f);PlaceLabel(toolLabels[i],Inset(r,12*s,7*s),32*s,.47f,true);
                toolLabels[i].SetColor(toolLabels[i].Text.Contains("空位")?G3HudTheme.QuietInk:G3HudTheme.Paper);
            }
        }
        void SyncPhoneCamera(G3Presenter presenter,G3PanelModel model)
        {
            bool focused=presenter.PhoneVisible;
            if(focused&&!phoneOwnsCamera){beforePhonePosition=SceneCamera.transform.position;beforePhoneRotation=SceneCamera.transform.rotation;beforePhoneFov=SceneCamera.fieldOfView;beforePhoneOrthographic=SceneCamera.orthographic;phoneOwnsCamera=true;Walk.SetCameraWriteEnabled(false);}
            Phone.Show(presenter,model,SceneCamera,Safe);
            if(focused){Phone.GetFocusPose(SceneCamera,Safe,out var position,out var rotation,out var fov);SceneCamera.orthographic=false;SceneCamera.fieldOfView=fov;SceneCamera.transform.SetPositionAndRotation(position,rotation);}
            else if(phoneOwnsCamera){SceneCamera.transform.SetPositionAndRotation(beforePhonePosition,beforePhoneRotation);SceneCamera.fieldOfView=beforePhoneFov;SceneCamera.orthographic=beforePhoneOrthographic;phoneOwnsCamera=false;Walk.SetCameraWriteEnabled(true);}
        }
        void LayoutHeader(RunState state,NightBill bill,float s)
        {
            string cash=state.RecoveryRequired?"待确认":G3Text.Money(state.CashMinor),due=state.RecoveryRequired?"待确认":G3Text.Money(bill.TotalDueMinor);
            string progress=state.RecoveryRequired?"存档待恢复":"第 "+state.DayNumber+" 天 · 已购 "+state.TicketsPurchasedToday+"/12 · 已结 "+state.SettledTicketCount+"/12";
            dayText.SetText(progress);float dw=Mathf.Min(lastSafe.width*.46f,TextWidth(progress,32*s)+32*s);
            dayRect=new Rect(lastSafe.xMax-16*s-dw,lastSafe.yMax-80*s,dw,64*s);PlacePlate(dayHeader,dayRect,.55f);PlaceLabel(dayText,Inset(dayRect,16*s,15*s),32*s,.47f,false);
            float cashWidth=TextWidth(cash,40*s),dueWidth=TextWidth(due,32*s),first=152*s+cashWidth,total=first+214*s+dueWidth;
            float available=dayRect.x-lastSafe.x-32*s;headerFallback=total>available;
            headerRect=new Rect(lastSafe.x+16*s,lastSafe.yMax-80*s,Mathf.Min(total,available),64*s);
            if(headerFallback)
            {headerText.SetText("现金 "+cash+" · 今晚应付 "+due);headerRect.height=Mathf.Max(64*s,TextHeight(headerText.Text,32*s,headerRect.width-32*s)+24*s);headerRect.y=lastSafe.yMax-16*s-headerRect.height;PlaceLabel(headerText,Inset(headerRect,16*s,12*s),32*s,.47f,true);}
            else
            {
                headerText.SetText("钱包");cashValue.SetText(cash);nightCaption.SetText("今晚应付");nightValue.SetText(due);
                walletIcon.Show(G3HudSymbol.Wallet,G3HudTheme.Paper);nightIcon.Show(G3HudSymbol.Coins,G3HudTheme.Copper);
                PlaceIcon(walletIcon,new Rect(headerRect.x+16*s,headerRect.y+16*s,32*s,32*s),.47f);
                PlaceLabel(headerText,new Rect(headerRect.x+60*s,headerRect.y+16*s,64*s,34*s),32*s,.47f,false);
                PlaceLabel(cashValue,new Rect(headerRect.x+138*s,headerRect.y+11*s,cashWidth+2*s,44*s),40*s,.47f,false);
                PlacePlate(headerDivider,new Rect(headerRect.x+first,headerRect.y+14*s,s,36*s),.49f);
                PlaceIcon(nightIcon,new Rect(headerRect.x+first+16*s,headerRect.y+17*s,30*s,30*s),.47f);
                PlaceLabel(nightCaption,new Rect(headerRect.x+first+58*s,headerRect.y+16*s,128*s,34*s),32*s,.47f,false);
                PlaceLabel(nightValue,new Rect(headerRect.x+first+198*s,headerRect.y+16*s,dueWidth+2*s,34*s),32*s,.47f,false);
            }
            PlacePlate(header,headerRect,.55f);qaText.SetText("QA");qaRect=new Rect(lastSafe.xMax-84*s,dayRect.y-52*s,68*s,40*s);PlacePlate(qaTag,qaRect,.55f);PlaceLabel(qaText,Inset(qaRect,10*s,4*s),32*s,.47f,false);
        }
        static bool CatalogCard(G3Action action)=>action.Kind==G3ActionKind.InspectStock||action.Kind==G3ActionKind.InspectTool;
        G3HudSymbol CatalogSymbol(G3Action action)
        {
            string id=action.Kind==G3ActionKind.InspectStock?current.Snapshot.Stock.FirstOrDefault(x=>x.StockId==action.Key)?.ItemId:action.Key;
            switch(id){case "small_prize_box":return G3HudSymbol.CoinBox;case "inspection_lamp":return G3HudSymbol.Lamp;case "ticket_clip":return G3HudSymbol.Clip;case "loss_mat":return G3HudSymbol.Ticket;default:return action.Kind==G3ActionKind.InspectTool||id!=null&&id.EndsWith("stamp",StringComparison.Ordinal)?G3HudSymbol.Stamp:G3HudSymbol.Ticket;}
        }
        public string[] WrapEvidenceDisplayLines(string text)
        {
            // Wrap the immutable diagnostic snapshot for the narrower supported phone
            // width. Clipboard still uses the original full snapshot, not these lines.
            float scale=Safe.height/720f,width=Mathf.Min(1100,Safe.width/scale-72);var lines=new List<string>();
            font.RequestCharactersInTexture(text??"",80,FontStyle.Normal);
            foreach(string raw in (text??"").Split('\n'))
            {
                var line=new System.Text.StringBuilder();float usedWidth=0;
                foreach(char c in raw){float advance=font.GetCharacterInfo(c,out var glyph,80,FontStyle.Normal)?glyph.advance*32f/80:32;if(usedWidth+advance>width&&line.Length>0){lines.Add(line.ToString());line.Clear();usedWidth=0;}line.Append(c);usedWidth+=advance;}
                lines.Add(line.ToString());
            }
            return lines.ToArray();
        }
        float TextWidth(string text,float pixels)
        {font.RequestCharactersInTexture(text??"",80,FontStyle.Normal);float width=0;foreach(char c in text??"")if(font.GetCharacterInfo(c,out var info,80,FontStyle.Normal))width+=info.advance*pixels/80;return width;}
        public bool HandleLocalAction(G3Action action)
        {if(action.Kind==G3ActionKind.ToggleMore){moreVisible=!moreVisible;Show(current,panelModel);return true;}if(moreVisible){moreVisible=false;Show(current,panelModel);}return false;}
        public bool CloseMore(){if(!moreVisible)return false;moreVisible=false;Show(current,panelModel);return true;}
        float TextHeight(string text,float pixels,float width)
        {
            font.RequestCharactersInTexture(text??"",80,FontStyle.Normal);float line=0;int lines=1;
            foreach(char c in text??"")
            {
                if(c=='\n'){lines++;line=0;continue;}if(!font.GetCharacterInfo(c,out var info,80,FontStyle.Normal))continue;
                float advance=info.advance*pixels/80;if(line+advance>width&&line>0){lines++;line=0;}line+=advance;
            }
            return pixels+(lines-1)*pixels*1.16f+2;
        }
        void ShowModal(G3PanelModel model,float s)
        {
            bool visible=PanelVisible&&!current.PhoneVisible;modal.gameObject.SetActive(visible);modalRule.gameObject.SetActive(visible);panelTitle.gameObject.SetActive(visible);panelBody.gameObject.SetActive(visible);panelFoot.gameObject.SetActive(visible);
            if(!visible)return;
            // Context drawer keeps the left-hand room visible. Dense explanations may
            // expand rather than shrink the 16 sp body or 48 dp touch targets.
            float maxWidth=lastSafe.width-24*s,width=Mathf.Min(860*s,maxWidth),available=lastSafe.height-24*s;
            int cols=model.LargeGrid?4:model.Cards.Count>=5?3:model.Cards.Count>1?2:1;
            int rows=Mathf.CeilToInt((float)model.Cards.Count/cols);float bodyHeight=0,footHeight=0,required=0;float[] rowHeights=new float[rows];
            for(int attempt=0;attempt<6;attempt++)
            {
                bodyHeight=TextHeight(model.Body,32*s,width-40*s);footHeight=TextHeight(model.Footnote,32*s,width-40*s);
                float cardWidth=(width-40*s-(cols-1)*8*s)/cols;float cardsHeight=0;
                for(int row=0;row<rows;row++)
                {float rh=96*s;for(int col=0;col<cols;col++){int i=row*cols+col;if(i<model.Cards.Count)rh=Mathf.Max(rh,TextHeight(model.Cards[i].Text,32*s,cardWidth-(CatalogCard(model.Cards[i].Action)?108:32)*s)+28*s);}rowHeights[row]=rh;cardsHeight+=rh;}
                required=112*s+bodyHeight+16*s+cardsHeight+Mathf.Max(0,rows-1)*8*s+16*s+footHeight+16*s;
                if(required<=available||width>=maxWidth)break;width=Mathf.Min(maxWidth,width+100*s);
            }
            if(model.Evidence){width=maxWidth;required=available;}
            float height=Mathf.Min(available,Mathf.Max(440*s,required));
            modalRect=new Rect(lastSafe.xMax-12*s-width,lastSafe.center.y-height*.5f,width,height);PlacePlate(modal,modalRect,.33f);
            PlacePlate(modalRule,new Rect(modalRect.x+20*s,modalRect.yMax-103*s,modalRect.width-40*s,2*s),.30f);
            string title=model.Title;if(current.Panel==G3Panel.Bill&&current.Snapshot.Phase!=DayPhase.DAY_COMPLETE&&current.Snapshot.Phase!=DayPhase.RUN_FAILED)title+=" · 应付 "+G3Text.Money(current.Service.PreviewNightBill().TotalDueMinor);
            panelTitle.SetText(title);PlaceLabel(panelTitle,new Rect(modalRect.x+20*s,modalRect.yMax-96*s,modalRect.width-208*s,76*s),32*s,.22f,true);
            bool pendingQa=G3QaEvidence.Enabled&&current.IsCommitting&&current.Panel!=G3Panel.QaEvidence&&current.Panel!=G3Panel.Settings;
            AddButton(pendingQa?"qa-settings":"close-panel",pendingQa?"QA 设置":"返回",pendingQa?new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Settings):new G3Action(G3ActionKind.Close),new Rect(modalRect.xMax-176*s,modalRect.yMax-108*s,156*s,96*s),true,.25f);
            panelBody.SetText(model.Body);panelFoot.SetText(model.Footnote);
            if(model.Evidence)
            {
                evidenceBodyRect=new Rect(modalRect.x+24*s,modalRect.y+190*s,modalRect.width-48*s,modalRect.height-302*s);
                PlaceLabel(panelBody,evidenceBodyRect,32*s,.22f,false);PlaceLabel(panelFoot,new Rect(modalRect.x+24*s,modalRect.y+8*s,modalRect.width-48*s,76*s),32*s,.22f,true);
                float w=(modalRect.width-64*s)/3;for(int i=0;i<model.Cards.Count;i++){var c=model.Cards[i];AddButton(c.Id,c.Text,c.Action,new Rect(modalRect.x+24*s+i*(w+8*s),modalRect.y+88*s,w,96*s),c.Enabled,.25f);}
                return;
            }
            float top=modalRect.yMax-112*s;
            PlaceLabel(panelBody,new Rect(modalRect.x+20*s,top-bodyHeight,modalRect.width-40*s,bodyHeight),32*s,.22f,true);
            float cardTop=top-bodyHeight-16*s,cardW=(modalRect.width-40*s-(cols-1)*8*s)/cols;
            for(int row=0;row<rows;row++)
            {
                for(int col=0;col<cols;col++){int i=row*cols+col;if(i>=model.Cards.Count)break;var card=model.Cards[i];AddButton(card.Id,card.Text,card.Action,new Rect(modalRect.x+20*s+col*(cardW+8*s),cardTop-rowHeights[row],cardW,rowHeights[row]),card.Enabled,.25f);}
                cardTop-=rowHeights[row]+8*s;
            }
            PlaceLabel(panelFoot,new Rect(modalRect.x+20*s,modalRect.y+16*s,modalRect.width-40*s,footHeight),32*s,.22f,true);
            if(current.IsCommitting)AddButton("retry","确认上笔交易",new G3Action(G3ActionKind.Retry),new Rect(modalRect.xMax-340*s,modalRect.y+88*s,310*s,96*s),true,.19f);
        }
        void AddButton(string id,string text,G3Action action,Rect rect,bool enabled=true,float z=.51f,float fontPixels=32)
        {
            if(used>=pool.Count)throw new InvalidOperationException("UI button capacity exceeded");var b=pool[used++];b.Id=id;b.Action=action;b.Rect=rect;
            bool evidenceControl=G3QaEvidence.Enabled&&(action.Kind==G3ActionKind.Open&&(action.Slot==(int)G3Panel.Settings||action.Slot==(int)G3Panel.QaEvidence)||(current.Panel==G3Panel.QaEvidence&&(action.Kind==G3ActionKind.CopyEvidence||action.Kind==G3ActionKind.ScrollEvidence))||(action.Kind==G3ActionKind.Close&&(current.Panel==G3Panel.QaEvidence||current.Panel==G3Panel.Settings)));
            b.Enabled=enabled&&(!current.IsCommitting||evidenceControl)||action.Kind==G3ActionKind.Retry||action.Kind==G3ActionKind.ToggleMore;b.Root.SetActive(true);
            b.Primary=id=="quick"||id=="claim"||id=="confirm-action"||id=="buy-number"||id=="buy-challenge"||id=="pay-night"||id=="enter-night"||id=="information-confirm"||id=="amount-accept";
            b.Navigation=id=="stand"||id=="open-shop"||id=="open-inventory"||id=="open-phone"||id=="open-more";
            b.Movement=action.Kind>=G3ActionKind.MoveForward&&action.Kind<=G3ActionKind.TurnRight;
            b.Selected=(id=="open-more"&&moreVisible)||(action.Kind==G3ActionKind.Equip&&action.Slot>=0&&current.Snapshot.NextToolIds[action.Slot]==action.Key)||(action.Kind==G3ActionKind.TargetCell&&text.StartsWith("已选格",StringComparison.Ordinal))||(id=="setting-quick"&&current.QuickEnabled)||(id=="setting-flash"&&current.ReduceFlash)||(id=="setting-vibration"&&current.Vibration);
            float s=lastSafe.height/720f;b.Catalog=CatalogCard(action);b.Label.gameObject.SetActive(!b.Catalog);b.Title.gameObject.SetActive(b.Catalog);b.Detail.gameObject.SetActive(false);
            // C's small faces have their own honest, transparent 48 dp input padding.
            bool round=b.Navigation&&id!="open-more";
            b.FaceRect=round?Inset(rect,8*s,8*s):b.Movement?Inset(rect,12*s,12*s):Inset(rect,4*s,6*s);
            if(!PanelVisible&&!round&&!b.Movement)b.FaceRect=new Rect(rect.x+4*s,rect.center.y-32*s,rect.width-8*s,64*s);
            if(id=="claim-next")b.FaceRect=Inset(rect,4*s,6*s);
            if(id=="open-more")b.FaceRect=new Rect(rect.x+12*s,rect.center.y-24*s,rect.width-24*s,48*s);
            b.Symbol=NavigationSymbol(id);PlacePlate(b.Plate,b.FaceRect,z);
            if(round||b.Movement)b.Plate.GetComponent<G3HudSurface>().Configure(b.FaceRect.width,b.FaceRect.height,b.FaceRect.height*.5f,s);
            if(round)
            {
                b.Label.SetText(text);PlaceIcon(b.Icon,new Rect(rect.center.x-16*s,b.FaceRect.yMax-44*s,32*s,32*s),z-.025f);
                PlaceLabel(b.Label,new Rect(b.FaceRect.x+10*s,b.FaceRect.y+12*s,b.FaceRect.width-20*s,36*s),fontPixels*s,z-.025f,false);
            }
            else if(b.Catalog)
            {
                b.Symbol=CatalogSymbol(action);PlaceIcon(b.Icon,new Rect(b.FaceRect.x+16*s,b.FaceRect.center.y-25*s,50*s,50*s),z-.025f);
                string[] parts=text.Split(new[]{'\n'},2);b.Title.SetText(parts[0]);b.Detail.SetText(parts.Length>1?parts[1]:"");b.Detail.gameObject.SetActive(parts.Length>1);
                float contentW=b.FaceRect.width-96*s,titleH=TextHeight(parts[0],32*s,contentW),detailH=parts.Length>1?TextHeight(parts[1],32*s,contentW):0,total=titleH+(detailH>0?detailH+4*s:0),top=b.FaceRect.center.y+total*.5f;
                PlaceLabel(b.Title,new Rect(b.FaceRect.x+80*s,top-titleH,contentW,titleH),32*s,z-.025f,true);
                PlaceLabel(b.Detail,new Rect(b.FaceRect.x+80*s,top-titleH-4*s-detailH,contentW,Mathf.Max(1,detailH)),32*s,z-.025f,true);
            }
            else
            {
                b.Label.SetText(text);float inset=b.Movement?4*s:8*s,width=b.FaceRect.width-2*inset,textH=TextHeight(text,fontPixels*s,width);
                PlaceLabel(b.Label,Inset(b.FaceRect,inset,Mathf.Max(4*s,(b.FaceRect.height-textH)*.5f)),fontPixels*s,z-.025f,true);
                b.Symbol=id=="quick"?G3HudSymbol.FastForward:id=="claim"?(!b.Enabled?G3HudSymbol.Lock:G3HudSymbol.Check):G3HudSymbol.None;
                if(b.Symbol!=G3HudSymbol.None){float iconSize=TextWidth(text,32*s)>145*s?16*s:28*s;PlaceIcon(b.Icon,new Rect(b.FaceRect.x+8*s,b.FaceRect.center.y-iconSize*.5f,iconSize,iconSize),z-.025f);}
            }
            b.Pressed=false;StyleButton(b,false);
        }
        static G3HudSymbol NavigationSymbol(string id)
        {
            switch(id){case "stand":return G3HudSymbol.Seat;case "open-shop":return G3HudSymbol.Shop;case "open-inventory":return G3HudSymbol.Inventory;case "open-phone":return G3HudSymbol.Phone;case "open-more":return G3HudSymbol.More;default:return G3HudSymbol.None;}
        }
        void StyleButton(ButtonVisual b,bool pressed)
        {
            Color face,ink,edge;
            if(!b.Enabled){face=G3HudTheme.DisabledFace;ink=G3HudTheme.DisabledInk;edge=G3HudTheme.Rule;}
            else if(b.Primary){face=G3HudTheme.Action;ink=G3HudTheme.Card;edge=G3HudTheme.Mint;}
            else if(b.Selected){face=G3HudTheme.InkLift;ink=G3HudTheme.Card;edge=G3HudTheme.Mint;}
            else{face=b.Catalog?G3HudTheme.InkLift:G3HudTheme.Ink;ink=G3HudTheme.Paper;edge=G3HudTheme.Rule;}
            if(pressed&&b.Enabled){face=Color.Lerp(face,G3HudTheme.Action,.45f);edge=G3HudTheme.Mint;}
            b.Plate.GetComponent<G3HudSurface>().Tint(face,edge);b.Label.SetColor(ink);b.Title.SetColor(ink);b.Detail.SetColor(!b.Enabled?G3HudTheme.DisabledInk:G3HudTheme.QuietInk);
            b.Icon.Show(b.Symbol,!b.Enabled?G3HudTheme.DisabledInk:b.Catalog?G3HudTheme.Mint:ink);b.Pressed=pressed;
        }
        void RefreshPressedState()
        {
            bool down=false;Vector2 point=Vector2.zero;
            if(EnhancedTouchSupport.enabled)foreach(var touch in ETouch.activeTouches)if(touch.phase!=UnityEngine.InputSystem.TouchPhase.Ended&&touch.phase!=UnityEngine.InputSystem.TouchPhase.Canceled){down=true;point=touch.screenPosition;break;}
            if(!down&&Mouse.current!=null&&Mouse.current.leftButton.isPressed){down=true;point=Mouse.current.position.ReadValue();}
            for(int i=0;i<used;i++){var b=pool[i];bool pressed=down&&b.Enabled&&b.Root.activeInHierarchy&&b.Rect.Contains(point);if(pressed!=b.Pressed)StyleButton(b,pressed);}
        }
        void WalkControls(float s)
        {
            float x=lastSafe.x+12*s,w=96*s,h=96*s,y=lastSafe.y+252*s,gap=8*s;
            AddButton("walk-forward","前",new G3Action(G3ActionKind.MoveForward),new Rect(x+w+gap,y+h+gap,w,h));
            AddButton("walk-back","后",new G3Action(G3ActionKind.MoveBack),new Rect(x+w+gap,y,w,h));
            AddButton("walk-left","左",new G3Action(G3ActionKind.MoveLeft),new Rect(x,y,w,h));
            AddButton("walk-right","右",new G3Action(G3ActionKind.MoveRight),new Rect(x+2*(w+gap),y,w,h));
            AddButton("turn-left","转左",new G3Action(G3ActionKind.TurnLeft),new Rect(lastSafe.xMax-220*s,y,w,h));
            AddButton("turn-right","转右",new G3Action(G3ActionKind.TurnRight),new Rect(lastSafe.xMax-116*s,y,w,h));
        }
        static Rect Inset(Rect r,float x,float y)=>new Rect(r.x+x,r.y+y,Mathf.Max(.1f,r.width-2*x),Mathf.Max(.1f,r.height-2*y));
        public Rect ButtonRect(string id){if(Phone!=null&&Phone.HasButton(id))return Phone.ButtonRect(id);foreach(var b in pool.Take(used))if(b.Root.activeInHierarchy&&b.Id==id)return b.Rect;throw new KeyNotFoundException(id);}
        public bool HasButton(string id)=>(Phone!=null&&Phone.HasButton(id))||pool.Take(used).Any(b=>b.Root.activeInHierarchy&&b.Id==id);
        public bool ConsumeUi(Vector2 pixel,out G3Action action)
        {
            if(Phone!=null&&Phone.TryConsumeUi(pixel,out action))return true;
            // Check frontmost controls first (confirmation/recovery overlays win).
            for(int i=used-1;i>=0;i--){var b=pool[i];if(b.Root.activeInHierarchy&&b.Rect.Contains(pixel)){action=b.Enabled?b.Action:default;return true;}}
            if(!PanelVisible&&!moreVisible&&footerHitRect.Contains(pixel)&&current.Snapshot.CurrentTicket!=null){action=new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Settlement);return true;}
            for(int i=0;i<toolChipPlates.Count;i++)if(toolChipPlates[i].gameObject.activeInHierarchy&&toolChipRects[i].Contains(pixel)){action=default;return true;}
            action=default;return PanelVisible||moreVisible||headerRect.Contains(pixel)||dayRect.Contains(pixel)||(!moreVisible&&footerHitRect.Contains(pixel))||(feedbackPlate.gameObject.activeInHierarchy&&feedbackRect.Contains(pixel));
        }
        public bool TryScratchUv(Vector2 pixel,out Uv uv)
        {
            if(pixel.x<0||pixel.y<0||pixel.x>=PresentationWidth||pixel.y>=PresentationHeight){uv=default;return false;}
            return Surface.TryPaperUv(SceneCamera.ViewportPointToRay(new Vector3(pixel.x/PresentationWidth,pixel.y/PresentationHeight,0)),out uv);
        }
        public G3WorldTarget WorldTarget(Vector2 pixel)
        {
            var ray=SceneCamera.ViewportPointToRay(new Vector3(pixel.x/PresentationWidth,pixel.y/PresentationHeight,0));
            if(Physics.Raycast(ray,out RaycastHit hit,5))return hit.collider.GetComponent<G3WorldTarget>();return null;
        }
        public Vector2 WorldToPresentationPoint(Vector3 point){var v=SceneCamera.WorldToViewportPoint(point);return new Vector2(v.x*PresentationWidth,v.y*PresentationHeight);}
        public void RefreshGlyphGeometry(){Phone?.RefreshGlyphGeometry();foreach(var label in labels)label.RebuildIfNeeded();if(number.CellLabels!=null)foreach(var label in number.CellLabels)label.RebuildIfNeeded();if(challenge.CellLabels!=null)foreach(var label in challenge.CellLabels)label.RebuildIfNeeded();}
        public string[] OverflowingHudLabels=>labels.Where(x=>x.gameObject.activeInHierarchy&&x.transform.IsChildOf(hud)&&(!x.Fits||x.MissingGlyphCount>0)).Select(x=>x.name+": "+x.Text).Concat(Phone!=null?Phone.OverflowingLabels:new string[0]).ToArray();
        public bool AllHudLabelsFit=>(Phone==null||Phone.AllLabelsFit)&&labels.Where(x=>x.gameObject.activeInHierarchy&&x.transform.IsChildOf(hud)).All(x=>x.Fits&&x.MissingGlyphCount==0);
        public void SettlementFeedback(bool reduceFlash){pulseReduced=reduceFlash;settlementPulse=reduceFlash?0:.22f;}
        void Update()
        {
            if(footer==null)return;RefreshPressedState();if(!persistentFeedback&&Time.unscaledTime>=feedbackUntil){feedbackPlate.gameObject.SetActive(false);statusText.gameObject.SetActive(false);}if(settlementPulse<=0)return;settlementPulse=Mathf.Max(0,settlementPulse-Time.unscaledDeltaTime);
            var baseColor=G3HudTheme.Ink;var tint=G3HudTheme.InkLift;
            footer.GetComponent<G3HudSurface>().Tint(Color.Lerp(baseColor,tint,settlementPulse/.22f),G3HudTheme.Rule);
        }
        void OnDestroy(){foreach(var item in owned)if(item!=null)Destroy(item);}
    }
}

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
        readonly List<G3ToolDisplay> toolDisplays=new List<G3ToolDisplay>();
        readonly List<Renderer> toolObjects=new List<Renderer>();readonly List<BoundedGlyphLabel> toolLabels=new List<BoundedGlyphLabel>();
        ConfirmedTicketSurface number,challenge;G3Presenter current;G3PanelModel panelModel;
        float settlementPulse;bool pulseReduced;int lastWidth,lastHeight,used;Rect lastSafe,headerRect,footerRect,modalRect,evidenceBodyRect;bool walking;
        public Camera SceneCamera {get;private set;}
        public G3ShopWalk Walk {get;private set;}
        public G3ShopEnvironment Environment {get;private set;}
        public Rect TableInteractionRect=>new Rect(Safe.x+230*Safe.height/720f,Safe.y+196*Safe.height/720f,Safe.width-410*Safe.height/720f,Safe.height-276*Safe.height/720f);
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
            BuildShop(lit);
            var n=new GameObject("Approved number ticket");n.transform.SetParent(transform,false);n.transform.position=Environment.TicketPosition;number=n.AddComponent<ConfirmedTicketSurface>();number.Build(numberArt,font,paper,silver,maskedFont,glyph,1.2f);
            var c=new GameObject("Approved challenge ticket");c.transform.SetParent(transform,false);c.transform.position=n.transform.position;challenge=c.AddComponent<ConfirmedTicketSurface>();challenge.Build(challengeArt,font,paper,silver,maskedFont,glyph,1.2f);
            var empty=new GameObject("Empty table prompt");empty.transform.SetParent(transform,false);empty.transform.position=Environment.TicketPosition+Vector3.up*.005f;empty.transform.rotation=Quaternion.Euler(90,0,0);emptyText=empty.AddComponent<BoundedGlyphLabel>();emptyText.Initialize(font,fontMat,new Color(.94f,.92f,.78f));emptyText.SetBox(.95f,.28f,.055f,true);emptyText.SetText("今日的第一张好运\n从柜台挑一张票");labels.Add(emptyText);
            var walker=new GameObject("Player short-distance body");walker.transform.SetParent(transform,false);Walk=walker.AddComponent<G3ShopWalk>();Walk.Initialize(SceneCamera,Environment.StandPosition,Environment.StandYaw);
            hud=new GameObject("Same-camera readable HUD").transform;hud.SetParent(SceneCamera.transform,false);
            header=Plate("Header",hud,new Color(.07f,.085f,.092f));footer=Plate("Footer",hud,new Color(.07f,.085f,.092f));modal=Plate("Modal background",hud,new Color(.11f,.13f,.14f));
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
            var shop=new GameObject("Authored room and bounded navigation");shop.transform.SetParent(transform,false);
            Environment=shop.AddComponent<G3ShopEnvironment>();Environment.Build();
            for(int i=0;i<3;i++)
            {
                var anchor=Environment.AnchorPosition("tool_"+(i+1),Environment.TicketPosition+new Vector3((i-1)*.39f,.015f,-.59f));
                var stand=Box("Configuration stand "+(i+1),anchor,new Vector3(.34f,.018f,.25f),new Color(.48f,.48f,.38f),lit,false);
                toolObjects.Add(stand.GetComponent<Renderer>());var display=new GameObject("Physical tool slot "+(i+1));display.transform.SetParent(transform,false);display.transform.position=anchor+Vector3.up*.012f;
                var visual=display.AddComponent<G3ToolDisplay>();visual.Initialize(lit);toolDisplays.Add(visual);
                var label=Label("Current tool name "+i,transform,new Color(.88f,.83f,.68f));label.transform.position=anchor+new Vector3(0,.017f,-.145f);label.transform.rotation=Quaternion.Euler(90,0,0);label.SetBox(.38f,.08f,.03f,true);toolLabels.Add(label);
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
            walking=value;SceneCamera.orthographic=false;SceneCamera.fieldOfView=value?64:54;
            if(value)Walk.ApplyCamera();else FrameTable();
            if(current!=null)Layout();
        }
        void FrameTable()
        {
            SceneCamera.orthographic=false;SceneCamera.fieldOfView=54;
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
            if(!walking)FrameTable();if(current!=null)Show(current,panelModel);
        }
        public void InvalidateTicket(){number?.Invalidate();challenge?.Invalidate();}
        public void Show(G3Presenter presenter,G3PanelModel model)
        {
            current=presenter;panelModel=model;if(LayoutChanged){Layout();return;}used=0;float s=lastSafe.height/720f,margin=12*s;
            headerRect=new Rect(lastSafe.x+margin,lastSafe.yMax-64*s,lastSafe.width-2*margin,52*s);footerRect=new Rect(lastSafe.x+margin,lastSafe.y+110*s,lastSafe.width-2*margin,76*s);
            PlacePlate(header,headerRect,.55f);PlacePlate(footer,footerRect,.55f);
            var state=presenter.Snapshot;var t=state.CurrentTicket;var bill=presenter.Service.PreviewNightBill();Environment.Sync(state);
            headerText.SetText(state.RecoveryRequired?"存档恢复受阻 · 请保留原件 · 现金暂不可确认":"现金 "+G3Text.Money(state.CashMinor)+"    今晚 "+G3Text.Money(bill.TotalDueMinor)+"    已购 "+state.TicketsPurchasedToday+" / 12    已结算 "+state.SettledTicketCount+(string.IsNullOrEmpty(state.FixtureLabel)?"    G3 首日":"    QA 固定新局"));
            PlaceLabel(headerText,Inset(headerRect,16*s,8*s),32*s,.48f,false);
            string summary;
            if(state.RecoveryRequired)summary="存档待恢复，票面已隐藏";
            else if(t==null)summary="空桌 · 两种票均为 100 金币";
            else if(t.Phase==TicketPhase.SETTLED){var record=state.Settlements.LastOrDefault(x=>x.TicketId==t.Id);summary=record==null?"已结算": "原奖 "+G3Text.Money(record.RawPrizeMinor)+" · 已收 "+G3Text.Money(record.TotalMinor)+" · 净额 "+G3Text.Signed(record.NetMinor);}
            else{var p=presenter.Service.PreviewSettlement();summary=p==null?(t.TicketType=="number"?"号码票 · 已揭 "+t.Scratch.RevealedCellCount+" / 6":"挑战票 · 安全 "+t.SafeCount+" 格 · "+(t.SelectedCell>=0?"完成已选格":"请主动选格")):"原奖 "+G3Text.Money(p.RawPrizeMinor)+" · 追加 "+G3Text.Money(p.TotalMinor-p.RawPrizeMinor)+" · 待收 "+G3Text.Money(p.TotalMinor)+" · 净额 "+G3Text.Signed(p.NetMinor);}
            resultText.SetText(summary+(t!=null?" · 点此明细":""));PlaceLabel(resultText,new Rect(footerRect.x+14*s,footerRect.y+39*s,footerRect.width-28*s,35*s),32*s,.47f,false);
            string feedback=presenter.Status;
            if(G3QaEvidence.Enabled&&!presenter.IsCommitting&&!state.RecoveryRequired&&t!=null&&t.SelectedCell>=0&&!PanelVisible)
                feedback="已保存格 "+(((t.SelectedCell+4)%8)+1)+" · QA r"+state.Revision+" · selection="+G3QaEvidence.SelectionMarker(t);
            statusText.SetText(feedback);PlaceLabel(statusText,new Rect(footerRect.x+14*s,footerRect.y+3*s,footerRect.width-28*s,35*s),32*s,.47f,false);
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
                toolDisplays[i].Show(state.RecoveryRequired?"":id);
                toolObjects[i].sharedMaterial.color=state.RecoveryRequired||string.IsNullOrEmpty(id)?new Color(.48f,.48f,.38f):new Color(.78f,.65f,.30f);
            }
            if(!PanelVisible)
            {
                // Eight existing routes in one shallow dock. All hit boxes remain 48 dp
                // at the 720 px / 360 dp reference, instead of covering both scene edges.
                float gap=8*s,w=(lastSafe.width-24*s-7*gap)/8,h=96*s,x=lastSafe.x+12*s,y=lastSafe.y+12*s;
                AddButton("open-tickets","购票",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Tickets),new Rect(x,y,w,h));
                AddButton("open-shop","货架",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Shop),new Rect(x+(w+gap),y,w,h));
                AddButton("open-inventory","收纳",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Inventory),new Rect(x+2*(w+gap),y,w,h));
                AddButton("open-drawer","抽屉",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Drawer),new Rect(x+3*(w+gap),y,w,h));
                AddButton("stand",walking?"回票桌":"起身",new G3Action(walking?G3ActionKind.Sit:G3ActionKind.Stand),new Rect(x+4*(w+gap),y,w,h));
                AddButton("open-phone","手机",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Phone),new Rect(x+5*(w+gap),y,w,h));
                AddButton("open-bill","账单",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Bill),new Rect(x+6*(w+gap),y,w,h));
                AddButton("open-settings","设置",new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Settings),new Rect(x+7*(w+gap),y,w,h));
                x=lastSafe.xMax-194*s;y=lastSafe.y+198*s;w=182*s;h=104*s;
                if(presenter.IsCommitting)AddButton("retry","确认交易",new G3Action(G3ActionKind.Retry),new Rect(x,y,w,h));
                else if(!walking&&t!=null&&t.Phase!=TicketPhase.SETTLED)
                {
                    bool claim=presenter.Service.PreviewSettlement()!=null;
                    AddButton("claim",t.TicketType=="challenge"?"收手\n并结算":"收下奖金",new G3Action(G3ActionKind.Claim),new Rect(x,y,w,h),claim);
                    if(claim&&state.TicketsPurchasedToday<12)AddButton("claim-next","收下再买\n同型 100",new G3Action(G3ActionKind.ClaimThenBuy,t.TicketType),new Rect(x,y+108*s,w,h));
                    else if(presenter.QuickEnabled)AddButton("quick",t.TicketType=="challenge"?"快揭\n已选格":"快速揭晓",new G3Action(G3ActionKind.QuickReveal),new Rect(x,y+108*s,w,h),t.TicketType=="number"||t.SelectedCell>=0);
                }
                if(walking)WalkControls(s);
            }
            header.gameObject.SetActive(!PanelVisible);footer.gameObject.SetActive(!PanelVisible);headerText.gameObject.SetActive(!PanelVisible);statusText.gameObject.SetActive(!PanelVisible);resultText.gameObject.SetActive(!PanelVisible);
            ShowModal(model,s);
            foreach(var b in pool.Skip(used))b.Root.SetActive(false);
        }
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
            modal.gameObject.SetActive(PanelVisible);panelTitle.gameObject.SetActive(PanelVisible);panelBody.gameObject.SetActive(PanelVisible);panelFoot.gameObject.SetActive(PanelVisible);
            if(!PanelVisible)return;
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
                {float rh=96*s;for(int col=0;col<cols;col++){int i=row*cols+col;if(i<model.Cards.Count)rh=Mathf.Max(rh,TextHeight(model.Cards[i].Text,32*s,cardWidth-24*s)+28*s);}rowHeights[row]=rh;cardsHeight+=rh;}
                required=112*s+bodyHeight+16*s+cardsHeight+Mathf.Max(0,rows-1)*8*s+16*s+footHeight+16*s;
                if(required<=available||width>=maxWidth)break;width=Mathf.Min(maxWidth,width+100*s);
            }
            if(model.Evidence){width=maxWidth;required=available;}
            float height=Mathf.Min(available,Mathf.Max(440*s,required));
            modalRect=new Rect(lastSafe.xMax-12*s-width,lastSafe.center.y-height*.5f,width,height);PlacePlate(modal,modalRect,.33f);
            panelTitle.SetText(model.Title);PlaceLabel(panelTitle,new Rect(modalRect.x+20*s,modalRect.yMax-96*s,modalRect.width-208*s,76*s),32*s,.22f,true);
            bool pendingQa=G3QaEvidence.Enabled&&current.IsCommitting&&current.Panel!=G3Panel.QaEvidence&&current.Panel!=G3Panel.Settings;
            AddButton(pendingQa?"qa-settings":"close-panel",pendingQa?"QA 设置":"返回",pendingQa?new G3Action(G3ActionKind.Open,slot:(int)G3Panel.Settings):new G3Action(G3ActionKind.Close),new Rect(modalRect.xMax-176*s,modalRect.yMax-108*s,156*s,96*s),true,.25f);
            panelBody.SetText(model.Body);panelFoot.SetText(model.Footnote);
            if(model.Evidence)
            {
                evidenceBodyRect=new Rect(modalRect.x+24*s,modalRect.y+198*s,modalRect.width-48*s,modalRect.height-318*s);
                PlaceLabel(panelBody,evidenceBodyRect,24*s,.22f,false);PlaceLabel(panelFoot,new Rect(modalRect.x+24*s,modalRect.y+16*s,modalRect.width-48*s,64*s),24*s,.22f,true);
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
            if(used>=pool.Count)throw new InvalidOperationException("UI button capacity exceeded");var b=pool[used++];b.Id=id;b.Action=action;b.Rect=rect;bool evidenceControl=G3QaEvidence.Enabled&&(action.Kind==G3ActionKind.Open&&(action.Slot==(int)G3Panel.Settings||action.Slot==(int)G3Panel.QaEvidence)||(current.Panel==G3Panel.QaEvidence&&(action.Kind==G3ActionKind.CopyEvidence||action.Kind==G3ActionKind.ScrollEvidence))||(action.Kind==G3ActionKind.Close&&(current.Panel==G3Panel.QaEvidence||current.Panel==G3Panel.Settings)));
            b.Enabled=enabled&&(!current.IsCommitting||evidenceControl)||action.Kind==G3ActionKind.Retry;b.Root.SetActive(true);
            PlacePlate(b.Plate,rect,z);bool primary=id=="claim"||id=="confirm-action"||id=="buy-number"||id=="buy-challenge";b.Plate.GetComponent<Renderer>().sharedMaterial.color=!b.Enabled?new Color(.15f,.17f,.18f):primary?new Color(.44f,.28f,.09f):new Color(.16f,.19f,.20f);
            b.Label.SetText(text);PlaceLabel(b.Label,Inset(rect,12*lastSafe.height/720f,14*lastSafe.height/720f),fontPixels*lastSafe.height/720f,z-.025f,true);
        }
        void WalkControls(float s)
        {
            float x=lastSafe.x+12*s,w=96*s,h=96*s,y=lastSafe.y+192*s,gap=8*s;
            AddButton("walk-forward","前",new G3Action(G3ActionKind.MoveForward),new Rect(x+w+gap,y+h+gap,w,h));
            AddButton("walk-back","后",new G3Action(G3ActionKind.MoveBack),new Rect(x+w+gap,y,w,h));
            AddButton("walk-left","左",new G3Action(G3ActionKind.MoveLeft),new Rect(x,y,w,h));
            AddButton("walk-right","右",new G3Action(G3ActionKind.MoveRight),new Rect(x+2*(w+gap),y,w,h));
            AddButton("turn-left","转左",new G3Action(G3ActionKind.TurnLeft),new Rect(lastSafe.xMax-220*s,y,w,h));
            AddButton("turn-right","转右",new G3Action(G3ActionKind.TurnRight),new Rect(lastSafe.xMax-116*s,y,w,h));
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
            if(Physics.Raycast(ray,out RaycastHit hit,5))return hit.collider.GetComponent<G3WorldTarget>();return null;
        }
        public Vector2 WorldToPresentationPoint(Vector3 point){var v=SceneCamera.WorldToViewportPoint(point);return new Vector2(v.x*PresentationWidth,v.y*PresentationHeight);}
        public void RefreshGlyphGeometry(){foreach(var label in labels)label.RebuildIfNeeded();if(number.CellLabels!=null)foreach(var label in number.CellLabels)label.RebuildIfNeeded();if(challenge.CellLabels!=null)foreach(var label in challenge.CellLabels)label.RebuildIfNeeded();}
        public string[] OverflowingHudLabels=>labels.Where(x=>x.gameObject.activeInHierarchy&&x.transform.IsChildOf(hud)&&(!x.Fits||x.MissingGlyphCount>0)).Select(x=>x.name+": "+x.Text).ToArray();
        public bool AllHudLabelsFit=>labels.Where(x=>x.gameObject.activeInHierarchy&&x.transform.IsChildOf(hud)).All(x=>x.Fits&&x.MissingGlyphCount==0);
        public void SettlementFeedback(bool reduceFlash){pulseReduced=reduceFlash;settlementPulse=reduceFlash?0:.22f;}
        void Update()
        {
            if(footer==null||settlementPulse<=0)return;settlementPulse=Mathf.Max(0,settlementPulse-Time.unscaledDeltaTime);
            var baseColor=new Color(.07f,.085f,.092f);var tint=new Color(.18f,.22f,.12f);
            footer.GetComponent<Renderer>().sharedMaterial.color=Color.Lerp(baseColor,tint,settlementPulse/.22f);
        }
        void OnDestroy(){foreach(var item in owned)if(item!=null)Destroy(item);}
    }
}

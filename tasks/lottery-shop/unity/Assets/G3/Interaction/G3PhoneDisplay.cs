using System;
using System.Collections.Generic;
using System.Linq;
using Lottery.G3.Rendering;
using UnityEngine;

namespace Lottery.G3.Interaction
{
    // One persistent shop prop. Every chat pixel is geometry on its physical glass;
    // pointer input must first hit that glass in the real scene, never a HUD rectangle.
    public sealed class G3PhoneDisplay : MonoBehaviour
    {
        const float Scale=.000264f;const float Width=390,Height=844;
        readonly List<UnityEngine.Object> owned=new List<UnityEngine.Object>();
        readonly List<BoundedGlyphLabel> labels=new List<BoundedGlyphLabel>();
        readonly List<string> wholeMessages=new List<string>();
        readonly Dictionary<string,Hit> hits=new Dictionary<string,Hit>();
        sealed class Hit {public Rect Rect;public G3Action Action;public bool Enabled;}
        Transform body,screen,content;Collider glass;Camera camera;Font font;Shader flat,glyph;Material textMaterial;G3Presenter presenter;
        static readonly Color Ink=new Color(.08f,.10f,.11f),Quiet=new Color(.42f,.45f,.48f),Background=new Color(.925f,.93f,.935f),Green=new Color(.66f,.92f,.46f),Packet=new Color(1,.30f,.12f);
        string signature="";int drawOrder;float scrollOffset,maxScroll;bool gesture,dragging;Vector2 pointerStart,pointerLast;G3Action tapped;G3PanelModel lastModel;Rect lastSafe,scrollViewport;string scrollContact="";G3Panel scrollPanel;readonly Rect chatViewport=new Rect(0,164,390,514);
        public Rect ChatViewportLogical=>chatViewport;
        public string[] WholeVisibleMessageIds=>wholeMessages.ToArray();
        public bool IsFocused {get;private set;}
        public string[] VisibleControlIds=>IsFocused?hits.Keys.ToArray():new string[0];
        public bool AllLabelsFit=>labels.All(x=>x.Fits&&x.MissingGlyphCount==0);
        public string[] OverflowingLabels=>labels.Where(x=>!x.Fits||x.MissingGlyphCount>0).Select(x=>x.name+": "+x.Text).ToArray();
        public Vector3[] ScreenWorldCorners=>new[]{ScreenPoint(0,0),ScreenPoint(Width,0),ScreenPoint(Width,Height),ScreenPoint(0,Height)};
        public Bounds WorldBounds {get{var r=body.GetComponentsInChildren<Renderer>();var b=new Bounds(body.position,Vector3.zero);foreach(var x in r)b.Encapsulate(x.bounds);return b;}}
        public static bool HandlesPanel(G3Panel panel)=>panel==G3Panel.Phone||panel==G3Panel.Contact||panel==G3Panel.PhoneAmount||panel==G3Panel.PhoneRequest||panel==G3Panel.PhonePacket||panel==G3Panel.PhoneRecords||panel==G3Panel.PhoneRepay||panel==G3Panel.PhoneOptions;
        public void Initialize(Font chinese,Shader flatShader,Shader glyphShader,Shader lit,G3ShopEnvironment environment)
        {
            font=chinese;flat=flatShader;glyph=glyphShader;textMaterial=Own(new Material(glyph));
            body=new GameObject("Permanent physical shop phone").transform;body.SetParent(transform,false);
            body.position=environment.AnchorPosition("Phone",new Vector3(1.57f,1.10f,-1.68f));body.rotation=Quaternion.Euler(environment.AnchorEulerAngles("Phone",new Vector3(12,180,0)));
            // Beveled metallic side rail, inset rear plate and actual thickness.
            RoundedSolid("Anodized side rail",.115f,.235f,.013f,.011f,Vector3.zero,new Color(.21f,.23f,.25f),lit);
            RoundedSolid("Satin black rear glass",.111f,.231f,.002f,.010f,new Vector3(0,0,.0065f),new Color(.035f,.04f,.044f),lit);
            RoundedSolid("Front glass bezel",.111f,.231f,.0015f,.010f,new Vector3(0,0,-.0065f),new Color(.012f,.016f,.019f),lit);
            Cube("Side sleep switch",new Vector3(.058f,.046f,0),new Vector3(.002f,.027f,.004f),new Color(.28f,.3f,.31f),lit);
            Cube("Volume rocker",new Vector3(-.058f,.045f,0),new Vector3(.002f,.035f,.004f),new Color(.28f,.3f,.31f),lit);
            RoundedSolid("Rear camera island",.030f,.045f,.004f,.008f,new Vector3(-.034f,.080f,.009f),new Color(.075f,.082f,.09f),lit);
            foreach(float y in new[]{.071f,.089f}){var lens=GameObject.CreatePrimitive(PrimitiveType.Cylinder);lens.name="Optical rear lens";lens.transform.SetParent(body,false);lens.transform.localPosition=new Vector3(-.034f,y,.013f);lens.transform.localRotation=Quaternion.Euler(90,0,0);lens.transform.localScale=new Vector3(.011f,.002f,.011f);lens.GetComponent<Renderer>().sharedMaterial=Material(lit,new Color(.02f,.045f,.06f));Destroy(lens.GetComponent<Collider>());}
            // Stand is a real support behind the phone, not a frame painted over the view.
            Cube("Rubber phone cradle",new Vector3(0,-.123f,.010f),new Vector3(.125f,.010f,.024f),new Color(.075f,.083f,.078f),lit);
            Cube("Brass stand riser",new Vector3(0,-.081f,.040f),new Vector3(.024f,.083f,.012f),new Color(.33f,.26f,.15f),lit);
            var foot=Cube("Weighted stand base",new Vector3(0,-.139f,.038f),new Vector3(.15f,.014f,.12f),new Color(.18f,.17f,.14f),lit);
            foot.transform.rotation=Quaternion.identity;foot.transform.position=new Vector3(body.position.x,.965f,body.position.z-.018f);
            var caseCollider=body.gameObject.AddComponent<BoxCollider>();caseCollider.size=new Vector3(.115f,.235f,.013f);
            var target=body.gameObject.AddComponent<G3WorldTarget>();target.Panel=G3Panel.Phone;
            screen=new GameObject("Physical portrait display 390 by 844").transform;screen.SetParent(body,false);screen.localPosition=new Vector3(0,0,-.008f);screen.localScale=Vector3.one*Scale;
            var collider=screen.gameObject.AddComponent<BoxCollider>();collider.size=new Vector3(Width,Height,.1f);glass=collider;
            var screenTarget=screen.gameObject.AddComponent<G3WorldTarget>();screenTarget.Panel=G3Panel.Phone;
            content=new GameObject("Live chat screen geometry").transform;content.SetParent(screen,false);
            DrawIdle();Physics.SyncTransforms();
        }
        T Own<T>(T o)where T:UnityEngine.Object{owned.Add(o);return o;}
        Material Material(Shader shader,Color color){var m=Own(new Material(shader));m.color=color;if(m.HasProperty("_BaseColor"))m.SetColor("_BaseColor",color);if(m.HasProperty("_Smoothness"))m.SetFloat("_Smoothness",.58f);return m;}
        GameObject Cube(string name,Vector3 pos,Vector3 size,Color color,Shader shader)
        {var go=GameObject.CreatePrimitive(PrimitiveType.Cube);go.name=name;go.transform.SetParent(body,false);go.transform.localPosition=pos;go.transform.localScale=size;go.GetComponent<Renderer>().sharedMaterial=Material(shader,color);Destroy(go.GetComponent<Collider>());return go;}
        void RoundedSolid(string name,float w,float h,float d,float radius,Vector3 pos,Color color,Shader shader)
        {
            var go=new GameObject(name);go.transform.SetParent(body,false);go.transform.localPosition=pos;
            var v=new List<Vector3>();var triangles=new List<int>();int segments=32;
            for(int ring=0;ring<4;ring++)
            {
                float inset=ring==0||ring==3?.0008f:0,z=ring==0?-d*.5f:ring==1?-d*.5f+.0008f:ring==2?d*.5f-.0008f:d*.5f;
                for(int corner=0;corner<4;corner++)for(int step=0;step<8;step++)
                {float a=(corner*90+step*90f/7)*Mathf.Deg2Rad,cx=corner==0||corner==3?w*.5f-radius:-w*.5f+radius,cy=corner<2?h*.5f-radius:-h*.5f+radius;v.Add(new Vector3(cx+Mathf.Cos(a)*(radius-inset),cy+Mathf.Sin(a)*(radius-inset),z));}
            }
            for(int ring=0;ring<3;ring++)for(int i=0;i<segments;i++){int a=ring*segments+i,b=ring*segments+(i+1)%segments,c=a+segments,e=b+segments;triangles.AddRange(new[]{a,b,c,b,e,c});}
            int front=v.Count;v.Add(new Vector3(0,0,-d*.5f));int back=v.Count;v.Add(new Vector3(0,0,d*.5f));
            for(int i=0;i<segments;i++){triangles.AddRange(new[]{front,(i+1)%segments,i,back,3*segments+i,3*segments+(i+1)%segments});}
            var mesh=Own(new Mesh{name=name+" beveled mesh"});mesh.SetVertices(v);mesh.SetTriangles(triangles,0);mesh.RecalculateNormals();mesh.RecalculateBounds();go.AddComponent<MeshFilter>().sharedMesh=mesh;go.AddComponent<MeshRenderer>().sharedMaterial=Material(shader,color);
        }
        public void GetFocusPose(Camera sceneCamera,Rect safe,out Vector3 position,out Quaternion rotation,out float fov)
        {
            fov=28;float fullHeight=Mathf.Max(1,sceneCamera.targetTexture!=null?sceneCamera.targetTexture.height:Screen.height);
            float fullWidth=Mathf.Max(1,sceneCamera.targetTexture!=null?sceneCamera.targetTexture.width:Screen.width);
            float available=Mathf.Max(.2f,safe.height/fullHeight)*.96f;
            float distance=.235f/(2*Mathf.Tan(fov*Mathf.Deg2Rad*.5f)*available),viewHeight=2*distance*Mathf.Tan(fov*Mathf.Deg2Rad*.5f);
            rotation=body.rotation;position=body.position-body.forward*distance;
            position-=body.right*((safe.center.x/fullWidth-.5f)*viewHeight*fullWidth/fullHeight)+body.up*((safe.center.y/fullHeight-.5f)*viewHeight);
        }
        public void Show(G3Presenter owner,G3PanelModel model,Camera sceneCamera,Rect safe)
        {
            presenter=owner;camera=sceneCamera;lastModel=model;lastSafe=safe;IsFocused=owner.PhoneVisible;
            if(scrollContact!=owner.PhoneContact||scrollPanel!=owner.Panel){scrollOffset=0;scrollContact=owner.PhoneContact;scrollPanel=owner.Panel;}
            string next=IsFocused?owner.Panel+"|"+owner.PhoneContact+"|"+model.Title+"|"+model.Body+"|"+model.Footnote+"|"+string.Join("|",model.Cards.Select(c=>c.Id+c.Text+c.Enabled))+"|"+string.Join("|",model.Messages.Select(m=>m.Id+m.Text+m.Caption)):"idle";
            if(next==signature)return;signature=next;Clear();if(!IsFocused){DrawIdle();return;}
            Surface("Chat screen",new Rect(0,0,Width,Height),Background,22);
            Surface("Receiver aperture",new Rect(160,10,70,5),new Color(.20f,.23f,.24f),2.5f);
            Surface("Navigation",new Rect(0,30,390,124),new Color(.98f,.98f,.98f),0);
            Button("phone-back","‹",new G3Action(G3ActionKind.PhoneBack),new Rect(0,30,124,124),!owner.IsCommitting,new Color(.98f,.98f,.98f),Ink,52);
            Text("contact-title",(owner.Panel==G3Panel.Phone?"聊天":owner.PhoneContact=="mother"?"妈妈":"女友"),new Rect(124,30,142,124),42,Ink,TextAnchor.MiddleCenter);
            Button("close-phone","×",new G3Action(G3ActionKind.Close,"phone"),new Rect(266,30,124,124),!owner.IsCommitting,new Color(.98f,.98f,.98f),Ink,52);
            if(owner.IsCommitting)DrawConversation(model);
            else if(owner.Panel==G3Panel.Phone)DrawContacts(model);
            else if(owner.Panel==G3Panel.PhonePacket)DrawPacket(model);
            else if(owner.Panel==G3Panel.CustomAmount)DrawKeypad(model);
            else DrawConversation(model);
            Surface("Bottom home indicator",new Rect(157,832,76,4),new Color(.31f,.34f,.35f),2);
            RefreshGlyphGeometry();
        }
        void DrawIdle()
        {
            Surface("Resting screen",new Rect(0,0,390,844),new Color(.09f,.14f,.13f),22);
            Text("Idle title","聊天",new Rect(38,180,314,70),45,Color.white,TextAnchor.MiddleCenter);
            Text("Idle description","妈妈  ·  女友",new Rect(28,278,334,70),27,new Color(.78f,.87f,.81f),TextAnchor.MiddleCenter);
            Surface("Resting clock underline",new Rect(140,390,110,4),new Color(.62f,.79f,.66f),2);
            Text("Idle hint","轻触手机",new Rect(28,610,334,70),24,new Color(.78f,.87f,.81f),TextAnchor.MiddleCenter);
        }
        void DrawContacts(G3PanelModel model)
        {
            float y=174;foreach(var c in model.Cards.Where(x=>x.Id.StartsWith("contact-",StringComparison.Ordinal)))
            {
                var r=new Rect(8,y,374,172);Surface(c.Id+" row",r,new Color(.98f,.985f,.98f),6);Avatar(c.Id,new Rect(22,y+24,68,68));var parts=c.Text.Split('\n');
                Text(c.Id+" name",parts[0],new Rect(112,y+12,250,52),42,Ink);
                bool decision=parts.Length>1&&parts[1].Contains("红包");float previewSize=42;
                string preview=decision?(parts[1].Contains("待领取")?"红包待领":"红包已领"):(parts.Length>1?parts[1]:"");
                Text(c.Id+" preview",ContactSummary(preview,250,previewSize),new Rect(112,y+66,250,100),previewSize,Quiet,wordWrap:false);
                hits[c.Id]=new Hit{Rect=r,Action=c.Action,Enabled=c.Enabled};y+=180;
            }
            Surface("Contacts utility divider",new Rect(20,674,350,1),new Color(.83f,.85f,.85f),0);
            var principal=model.Cards.FirstOrDefault(x=>x.Id=="principal");if(principal!=null)Button(principal.Id,"主债",principal.Action,new Rect(8,684,180,124),principal.Enabled,Background,Quiet,42);
            var bill=model.Cards.FirstOrDefault(x=>x.Id=="phone-bill");if(bill!=null)Button(bill.Id,"账单",bill.Action,new Rect(202,684,180,124),bill.Enabled,Background,Quiet,42);
        }
        void DrawPacket(G3PanelModel model)
        {
            Surface("Packet opening face",new Rect(12,168,366,496),new Color(.82f,.17f,.10f),22);
            Text("Packet disclosure",model.Body,new Rect(30,184,330,300),42,new Color(1,.91f,.73f),TextAnchor.MiddleCenter);
            var claim=model.Cards.FirstOrDefault(x=>x.Id=="phone-claim");if(claim!=null)Button(claim.Id,claim.Text,claim.Action,new Rect(133,502,124,124),claim.Enabled,new Color(.96f,.77f,.39f),new Color(.49f,.16f,.08f),52,62);
            var cancel=model.Cards.FirstOrDefault(x=>x.Id=="phone-cancel-request");if(cancel!=null)Card(cancel,new Rect(8,678,374,124),"取消红包");
        }
        void DrawKeypad(G3PanelModel model)
        {
            Text("Chosen amount",model.Body.Split('\n')[0].Replace("游戏金币：",""),new Rect(12,156,366,44),42,Ink,TextAnchor.MiddleCenter);
            for(int i=0;i<model.Cards.Count;i++){var c=model.Cards[i];if(i<12)Button(c.Id,c.Text,c.Action,new Rect((i%3)*130,200+(i/3)*124,124,124),c.Enabled,Color.white,Ink,42);else Card(c,new Rect(3,704,384,124),"下一步",42);}
        }
        void DrawConversation(G3PanelModel model)
        {
            bool standard=presenter.Panel==G3Panel.Contact,records=presenter.Panel==G3Panel.PhoneRecords;
            float y=170;var cards=model.Cards;
            if(standard)
            {
                var heights=model.Messages.Select(m=>m.Packet?244:Wrap(m.Text,270,42).Count*(42)*1.16f+20).ToArray();
                scrollViewport=chatViewport;float total=heights.Sum()+Mathf.Max(0,heights.Length-1)*14;
                float naturalTop=Mathf.Max(0,total-chatViewport.height),alignedTop=0;
                // On entry show complete recent messages instead of a clipped last syllable.
                for(int i=0;i<heights.Length&&alignedTop<naturalTop;i++)alignedTop+=heights[i]+14;
                maxScroll=naturalTop>0?alignedTop:0;scrollOffset=Mathf.Clamp(scrollOffset,0,maxScroll);y=chatViewport.y-maxScroll+scrollOffset;
                for(int i=0;i<model.Messages.Count;i++)
                {
                    var msg=model.Messages[i];float size=42,h=heights[i],w=msg.Packet?300:Mathf.Clamp(Wrap(msg.Text,270,size).Max(line=>Measure(line,size))+30,112,300),x=msg.Player?324-w:66;var rect=new Rect(x,y,w,h);
                    if(rect.yMax>chatViewport.yMin&&rect.yMin<chatViewport.yMax)
                    {
                        if(rect.yMin>=chatViewport.yMin&&rect.yMax<=chatViewport.yMax)wholeMessages.Add(msg.Id);
                        var avatar=new Rect(msg.Player?336:8,y+4,46,46);if(avatar.yMin>=chatViewport.yMin&&avatar.yMax<=chatViewport.yMax)Avatar(msg.Player?"player":presenter.PhoneContact,avatar);
                        bool claimed=msg.Packet&&msg.Caption.StartsWith("已领取",StringComparison.Ordinal);Color packetColor=claimed?new Color(.82f,.46f,.29f):new Color(.96f,.34f,.15f);
                        Surface(msg.Id+" bubble",Clip(rect,chatViewport),msg.Packet?packetColor:msg.Player?Green:Color.white,msg.Packet?14:10);
                        if(msg.Packet)
                        {
                            if(y+12>=chatViewport.yMin&&y+60<=chatViewport.yMax)Envelope(msg.Id,new Rect(x+16,y+16,40,44),claimed);
                            ChatText(msg.Id+" heading",claimed?"已领取":"借款红包",new Rect(x+68,y+12,w-84,49),42,Color.white);
                            string amount=msg.Text.Split('\n').Last().Replace("游戏金币","金币");
                            ChatText(msg.Id+" value",amount,new Rect(x+18,y+66,w-36,49),42,Color.white);
                            string status=claimed&&msg.Caption.Contains("第")?msg.Caption.Substring(msg.Caption.IndexOf("第",StringComparison.Ordinal)):"拆开领取";
                            ChatText(msg.Id+" status",status,new Rect(x+18,y+120,w-36,49),42,Color.white);
                            if(y+177>=chatViewport.yMin&&y+178<=chatViewport.yMax)Surface(msg.Id+" footer rule",new Rect(x+14,y+177,w-28,1),new Color(1,.77f,.56f),0);
                            ChatText(msg.Id+" type","游戏虚拟红包",new Rect(x+18,y+184,w-36,49),42,new Color(1,.92f,.82f));
                        }
                        else ChatText(msg.Id+" text",msg.Text,new Rect(x+14,y+10,w-28,h-20),size,Ink);
                        if(msg.Enabled)hits[msg.Id]=new Hit{Rect=Clip(rect,chatViewport),Action=msg.Action,Enabled=true};
                    }
                    y+=h+14;
                }
                Surface("Fixed phrase composer bar",new Rect(0,680,390,132),new Color(.955f,.96f,.965f),0);
                Surface("Composer top hairline",new Rect(0,680,390,1),new Color(.82f,.84f,.85f),0);
                var phrase=cards.FirstOrDefault(c=>c.Id=="phone-choose");
                if(phrase!=null)
                {
                    Surface("Fixed phrase input",new Rect(8,702,242,80),Color.white,13);
                    Text("phone-choose label",phrase.Enabled?"说一句话":"待领红包",new Rect(20,707,218,68),42,phrase.Enabled?Quiet:new Color(.55f,.56f,.57f),TextAnchor.MiddleCenter);
                    hits[phrase.Id]=new Hit{Rect=new Rect(8,684,242,124),Action=phrase.Action,Enabled=phrase.Enabled};
                }
                var more=cards.FirstOrDefault(c=>c.Id=="phone-more");
                if(more!=null)
                {
                    Surface("Composer plus outline",new Rect(286,708,68,68),new Color(.70f,.74f,.74f),34);Surface("Composer plus inside",new Rect(289,711,62,62),new Color(.955f,.96f,.965f),31);
                    Text("phone-more label","＋",new Rect(286,708,68,68),52,Ink,TextAnchor.MiddleCenter);
                    hits[more.Id]=new Hit{Rect=new Rect(258,684,124,124),Action=more.Action,Enabled=more.Enabled};
                }
                return;
            }
            if(records)
            {
                Text("Records summary",model.Body,new Rect(14,166,362,196),42,Ink,TextAnchor.UpperLeft);y=380;
                foreach(var msg in model.Messages.Take(1)){Surface(msg.Id+" record",new Rect(10,y,370,276),Color.white,12);Text(msg.Id+" record text",msg.Text,new Rect(28,y+18,334,240),42,Ink,TextAnchor.UpperLeft);}
                for(int i=0;i<cards.Count;i++)Card(cards[i],new Rect(8+i*194,680,180,124),cards[i].Text,42);return;
            }
            float cardHeight=124,gap=10,start=808-cards.Count*(cardHeight+gap);
            if(cards.Count>0&&cards[0].Id=="retry")start=674;
            scrollViewport=new Rect(16,168,358,Mathf.Max(100,start-184));
            float detailHeight=Wrap(model.Body,scrollViewport.width,42).Count*42*1.16f;
            maxScroll=Mathf.Max(0,detailHeight-scrollViewport.height);scrollOffset=Mathf.Clamp(scrollOffset,0,maxScroll);
            ClipText("Phone dialogue detail",model.Body,new Rect(scrollViewport.x,scrollViewport.y-scrollOffset,scrollViewport.width,detailHeight),42,Ink,scrollViewport);
            for(int i=0;i<cards.Count;i++)
            {
                string caption=cards[i].Text.Replace("想借 ","借 ").Replace("填写其他归还金额","其他金额").Replace("说一个其他金额","其他金额").Replace("发送这句话","发送");
                Card(cards[i],new Rect(8,start+i*(cardHeight+gap),374,cardHeight),caption,42);
            }
        }
        void Envelope(string id,Rect r,bool muted)
        {
            Surface(id+" envelope body",r,muted?new Color(.66f,.29f,.15f):new Color(.83f,.18f,.08f),5);
            var a=Surface(id+" envelope flap left",new Rect(r.x+2,r.y+17,r.width*.53f,2),new Color(1,.78f,.44f),0);a.localRotation=Quaternion.Euler(0,0,-24);
            var b=Surface(id+" envelope flap right",new Rect(r.x+r.width*.47f,r.y+17,r.width*.49f,2),new Color(1,.78f,.44f),0);b.localRotation=Quaternion.Euler(0,0,24);
            Surface(id+" envelope seal",new Rect(r.center.x-5,r.y+20,10,10),new Color(1,.80f,.48f),5);
        }
        string ContactSummary(string value,float width,float size)
        {
            // Preview only: keep the original conversation and touch/layout bounds.
            // Match BoundedGlyphLabel's raster size/advances, reserving a small
            // rounding margin. Never shrink text or split a text element.
            value=(value??"").Replace('\r',' ').Replace('\n',' ');const string ellipsis="…";
            font.RequestCharactersInTexture(value+ellipsis,80,FontStyle.Normal);
            float limit=Mathf.Max(0,width-2);
            if(Measure(value,size)<=limit)return value;
            if(Measure(ellipsis,size)>limit)return "";
            string prefix="";var elements=System.Globalization.StringInfo.GetTextElementEnumerator(value);
            while(elements.MoveNext())
            {string next=prefix+elements.GetTextElement();if(Measure(next+ellipsis,size)>limit)break;prefix=next;}
            return prefix+ellipsis;
        }
        float Measure(string value,float size)
        {float width=0;foreach(char c in value)width+=font.GetCharacterInfo(c,out var info,80,FontStyle.Normal)?info.advance*size/80:size;return width;}
        static Rect Clip(Rect a,Rect b)=>Rect.MinMaxRect(Mathf.Max(a.xMin,b.xMin),Mathf.Max(a.yMin,b.yMin),Mathf.Min(a.xMax,b.xMax),Mathf.Min(a.yMax,b.yMax));
        List<string> Wrap(string text,float width,float size)
        {
            font.RequestCharactersInTexture(text,80,FontStyle.Normal);var lines=new List<string>();string line="";float used=0;
            foreach(char c in text){if(c=='\n'){lines.Add(line);line="";used=0;continue;}float advance=font.GetCharacterInfo(c,out var info,80,FontStyle.Normal)?info.advance*size/80:size;if(used+advance>width&&line.Length>0){lines.Add(line);line="";used=0;}line+=c;used+=advance;}lines.Add(line);return lines;
        }
        void ChatText(string name,string value,Rect rect,float size,Color color)=>ClipText(name,value,rect,size,color,chatViewport);
        void ClipText(string name,string value,Rect rect,float size,Color color,Rect viewport)
        {
            float y=rect.y;int index=0;foreach(string line in Wrap(value,rect.width,size))
            {var row=new Rect(rect.x,y,rect.width,size*1.16f);if(row.yMin>=viewport.yMin&&row.yMax<=viewport.yMax)Text(name+" line "+index,line,row,size,color);y+=size*1.16f;index++;}
        }
        bool ScreenLocal(Vector2 pixel,out Vector2 local)
        {
            local=default;if(camera==null)return false;var ray=camera.ScreenPointToRay(pixel);
            if(!Physics.Raycast(ray,out var hit,30,~0,QueryTriggerInteraction.Ignore)||hit.collider!=glass)return false;
            var p=screen.InverseTransformPoint(hit.point);local=new Vector2(p.x+Width*.5f,Height*.5f-p.y);return true;
        }
        public void BeginPointer(Vector2 pixel)
        {gesture=IsFocused;dragging=false;pointerStart=pointerLast=pixel;TryConsumeUi(pixel,out tapped);}
        public void MovePointer(Vector2 pixel)
        {
            if(!gesture)return;if((pixel-pointerStart).sqrMagnitude>144)dragging=true;
            if(dragging&&presenter.Panel!=G3Panel.Phone&&presenter.Panel!=G3Panel.CustomAmount&&presenter.Panel!=G3Panel.PhonePacket&&presenter.Panel!=G3Panel.PhoneRecords&&ScreenLocal(pointerStart,out var start)&&scrollViewport.Contains(start)&&ScreenLocal(pointerLast,out var previous)&&ScreenLocal(pixel,out var now))
            {scrollOffset=Mathf.Clamp(scrollOffset+(presenter.Panel==G3Panel.Contact?now.y-previous.y:previous.y-now.y),0,maxScroll);signature="";Show(presenter,lastModel,camera,lastSafe);}
            pointerLast=pixel;
        }
        public G3Action EndPointer(bool cancelled=false)
        {
            var action=default(G3Action);if(gesture&&!dragging&&!cancelled&&TryConsumeUi(pointerLast,out var release)&&release.Id==tapped.Id)action=tapped;
            gesture=false;dragging=false;tapped=default;return action;
        }
        void Avatar(string who,Rect r)
        {
            bool player=who=="player",mother=who.Contains("mother");Color background=player?new Color(.40f,.59f,.69f):mother?new Color(.64f,.75f,.52f):new Color(.81f,.62f,.60f);
            Surface(who+" avatar",r,background,8);float unit=r.width/46;
            if(mother)
            {
                Surface(who+" flower stem",new Rect(r.x+22*unit,r.y+15*unit,2*unit,22*unit),new Color(.29f,.44f,.22f),0);
                foreach(var p in new[]{new Vector2(15,13),new Vector2(22,10),new Vector2(28,15),new Vector2(25,22),new Vector2(17,21)})Surface(who+" flower petal",new Rect(r.x+p.x*unit,r.y+p.y*unit,9*unit,9*unit),new Color(.96f,.74f,.68f),4.5f*unit);
                Surface(who+" flower center",new Rect(r.x+22*unit,r.y+17*unit,6*unit,6*unit),new Color(1,.90f,.58f),3*unit);
                Surface(who+" terracotta pot",new Rect(r.x+14*unit,r.y+32*unit,20*unit,10*unit),new Color(.73f,.46f,.31f),3*unit);
            }
            else
            {
                Surface(who+" avatar sun",new Rect(r.x+28*unit,r.y+8*unit,11*unit,11*unit),new Color(1,.82f,.52f),5.5f*unit);
                Surface(who+" horizon",new Rect(r.x+3*unit,r.y+31*unit,40*unit,11*unit),player?new Color(.21f,.34f,.43f):new Color(.52f,.39f,.46f),2*unit);
                for(int i=0;i<4;i++)Surface(who+" skyline "+i,new Rect(r.x+(7+i*8)*unit,r.y+(26-i%2*6)*unit,5*unit,(12+i%2*6)*unit),new Color(.31f,.35f,.43f),unit);
            }
        }
        void Card(G3Card card,Rect r,string caption=null,float size=42)=>Button(card.Id,caption??card.Text,card.Action,r,card.Enabled,Color.white,Ink,size);
        void Button(string id,string value,G3Action action,Rect r,bool enabled,Color fill,Color ink,float size=42,float radius=13)
        {Surface(id+" plate",r,enabled?fill:Color.Lerp(fill,Background,.65f),radius);Text(id+" label",value,new Rect(r.x+12,r.y+4,r.width-24,r.height-8),size,enabled?ink:Quiet,TextAnchor.MiddleCenter);hits[id]=new Hit{Rect=r,Action=action,Enabled=enabled};}
        Transform Surface(string name,Rect r,Color color,float radius)
        {var t=G3HudSurface.Create(name,content,glyph,color,color);t.localPosition=new Vector3(r.center.x-Width*.5f,Height*.5f-r.center.y,-.3f);t.localScale=new Vector3(r.width,r.height,1);t.GetComponent<G3HudSurface>().Configure(r.width,r.height,radius,0);foreach(var renderer in t.GetComponentsInChildren<Renderer>())renderer.sortingOrder=drawOrder++;return t;}
        void Text(string name,string value,Rect r,float size,Color color,TextAnchor anchor=TextAnchor.MiddleLeft,bool wordWrap=true)
        {var go=new GameObject(name);go.transform.SetParent(content,false);go.transform.localPosition=new Vector3(r.center.x-Width*.5f,Height*.5f-r.center.y,-.7f);var label=go.AddComponent<BoundedGlyphLabel>();label.Initialize(font,textMaterial,color,anchor);label.SetBox(r.width,r.height,size,wordWrap);label.SetText(value);go.GetComponent<Renderer>().sortingOrder=drawOrder++;labels.Add(label);}
        Vector3 ScreenPoint(float x,float y)=>screen.TransformPoint(new Vector3(x-Width*.5f,Height*.5f-y,-.7f));
        public Rect ButtonRect(string id)
        {
            if(!hits.TryGetValue(id,out var hit)||!IsFocused)throw new KeyNotFoundException(id);var r=hit.Rect;
            var points=new[]{ScreenPoint(r.xMin,r.yMin),ScreenPoint(r.xMax,r.yMin),ScreenPoint(r.xMax,r.yMax),ScreenPoint(r.xMin,r.yMax)}.Select(p=>camera.WorldToScreenPoint(p)).ToArray();
            return Rect.MinMaxRect(points.Min(p=>p.x),points.Min(p=>p.y),points.Max(p=>p.x),points.Max(p=>p.y));
        }
        public bool HasButton(string id)=>IsFocused&&hits.ContainsKey(id);
        public bool TryConsumeUi(Vector2 pixel,out G3Action action)
        {
            action=default;if(!IsFocused||camera==null)return false;
            // Ignore authoring interaction triggers, but respect actual world occluders.
            var ray=camera.ScreenPointToRay(pixel);if(Physics.Raycast(ray,out var hit,30,~0,QueryTriggerInteraction.Ignore)&&hit.collider==glass)
            {var p=screen.InverseTransformPoint(hit.point);var point=new Vector2(p.x+Width*.5f,Height*.5f-p.y);foreach(var pair in hits.Reverse())if(pair.Value.Rect.Contains(point)){action=pair.Value.Enabled?pair.Value.Action:default;break;}}
            return true; // Screen exterior cannot scratch the table or move the player.
        }
        public void RefreshGlyphGeometry(){foreach(var label in labels)label.RebuildIfNeeded();}
        void Clear(){drawOrder=0;wholeMessages.Clear();hits.Clear();labels.Clear();for(int i=content.childCount-1;i>=0;i--){var child=content.GetChild(i).gameObject;child.SetActive(false);Destroy(child);}}
        void OnDestroy(){foreach(var item in owned)if(item!=null)Destroy(item);}
    }
}

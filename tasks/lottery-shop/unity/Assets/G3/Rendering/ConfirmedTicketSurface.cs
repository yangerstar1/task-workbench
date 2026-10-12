using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using Lottery.G3.Core;
using UnityEngine;

namespace Lottery.G3.Rendering
{
    public sealed class ConfirmedTicketSurface : MonoBehaviour
    {
        public const float PaperY=0,TextY=.003f,SilverY=.006f;
        readonly List<UnityEngine.Object> owned=new List<UnityEngine.Object>();
        readonly DisplaySession session=new DisplaySession();
        readonly Dictionary<string,BoundedGlyphLabel> legends=new Dictionary<string,BoundedGlyphLabel>();
        GameObject body; MeshCollider collider; Texture2D[] masks; BoundedGlyphLabel[] cellText;
        float width,depth; Guid token; string activeTicket;
        public TicketLayout Layout {get;private set;}
        public bool IsVisible => body!=null&&body.activeInHierarchy&&session.Visible;
        public long DisplayedRevision => session.Revision;
        public IReadOnlyList<BoundedGlyphLabel> CellLabels => cellText;
        public float PaperWidth => width;
        public void Build(ApprovedArtworkBinding binding,Font font,Shader paper,Shader silver,Shader maskedFont,Shader ordinaryFont,float paperWidth=4.8f)
        {
            if(Layout!=null)throw new InvalidOperationException("Surface is already built");
            if(binding==null||font==null||paper==null||silver==null||maskedFont==null||ordinaryFont==null)throw new ArgumentNullException("Explicit art, font and shaders required");
            binding.RequireVerifiedPair();Layout=binding.GetReviewedLayout();width=paperWidth;depth=paperWidth*Layout.Height/Layout.Width;
            body=new GameObject("Atomic confirmed ticket display");body.transform.SetParent(transform,false);body.SetActive(false);
            var paperMat=Own(new Material(paper));paperMat.SetTexture("_BaseMap",binding.Albedo);
            var paperObject=Quad("Approved printed paper",new PixelRect(0,0,Layout.Width,Layout.Height),PaperY,paperMat);
            collider=paperObject.AddComponent<MeshCollider>();collider.sharedMesh=paperObject.GetComponent<MeshFilter>().sharedMesh;
            masks=new Texture2D[Layout.Cells.Count];cellText=new BoundedGlyphLabel[Layout.Cells.Count];
            for(int i=0;i<Layout.Cells.Count;i++)
            {
                var cell=Layout.Cells[i];int cols=Layout.Cells.Count/2;int ci=cell.CoreIndex;
                int cw=(ci%cols+1)*256/cols-(ci%cols)*256/cols;
                masks[i]=Own(new Texture2D(cw,64,TextureFormat.RGBA32,false,true){name="Confirmed coverage "+cell.Id,filterMode=FilterMode.Point,wrapMode=TextureWrapMode.Clamp});
                WriteMask(i,new byte[cw*64]);
                var silverMat=Own(new Material(silver));silverMat.SetTexture("_RevealTex",masks[i]);Quad("Opaque silver "+cell.Id,cell.Silver,SilverY,silverMat);
                var glyphMat=Own(new Material(maskedFont));glyphMat.SetTexture("_RevealTex",masks[i]);
                var label=Label("Masked result "+cell.Id,cell.Text,glyphMat,font,68);cellText[i]=label;
                float sw=cell.Silver.Width*width/Layout.Width,sh=cell.Silver.Height*depth/Layout.Height;
                var tc=cell.Text.Center(Layout.Width,Layout.Height);var sc=cell.Silver.Center(Layout.Width,Layout.Height);
                label.SetMaskMapping(new Vector4(1/sw,1/sh,.5f+(float)(tc.U-sc.U)*width/sw,.5f+(float)(tc.V-sc.V)*depth/sh));
            }
            var headerMat=Own(new Material(ordinaryFont));
            foreach(var region in Layout.Labels) legends.Add(region.Id,Label("Live "+region.Id,region.Bounds,headerMat,font,region.Id.Contains("strip")?44:68));
        }
        T Own<T>(T value)where T:UnityEngine.Object{owned.Add(value);return value;}
        BoundedGlyphLabel Label(string name,PixelRect rect,Material mat,Font font,float fontPixels)
        {
            var go=new GameObject(name);go.transform.SetParent(body.transform,false);go.transform.localPosition=Point(rect.Center(Layout.Width,Layout.Height),TextY);go.transform.localRotation=Quaternion.Euler(90,0,0);
            var label=go.AddComponent<BoundedGlyphLabel>();label.Initialize(font,mat,new Color(.09f,.15f,.13f));
            label.SetBox(rect.Width*width/Layout.Width,rect.Height*depth/Layout.Height,fontPixels*width/Layout.Width);return label;
        }
        GameObject Quad(string name,PixelRect rect,float y,Material material)
        {
            double u0=(double)rect.X/Layout.Width,u1=(double)(rect.X+rect.Width)/Layout.Width,v0=1-(double)(rect.Y+rect.Height)/Layout.Height,v1=1-(double)rect.Y/Layout.Height;
            var mesh=Own(new Mesh{name=name+" mesh"});mesh.vertices=new[]{Point(new Uv(u0,v0),y),Point(new Uv(u1,v0),y),Point(new Uv(u1,v1),y),Point(new Uv(u0,v1),y)};
            mesh.uv=new[]{Vector2.zero,Vector2.right,Vector2.one,Vector2.up};mesh.triangles=new[]{0,2,1,0,3,2};mesh.RecalculateNormals();mesh.RecalculateBounds();
            var go=new GameObject(name);go.transform.SetParent(body.transform,false);go.AddComponent<MeshFilter>().sharedMesh=mesh;go.AddComponent<MeshRenderer>().sharedMaterial=material;return go;
        }
        Vector3 Point(Uv p,float y)=>new Vector3(((float)p.U-.5f)*width,y,((float)p.V-.5f)*depth);
        public Guid Begin(string ticketId,long revisionFloor)
        {
            Invalidate();activeTicket=ticketId;token=session.Begin(ticketId,revisionFloor);return token;
        }
        public Guid CurrentToken=>token;
        public bool ShowConfirmed(Guid callbackToken,RunState confirmed)
        {
            var t=confirmed?.CurrentTicket;
            if(confirmed==null||confirmed.RecoveryRequired||t==null){Invalidate();return false;}
            if(!isActiveAndEnabled||!session.IsCurrent(callbackToken,t.Id,confirmed.Revision))return false;
            try
            {
                if(t.TicketType!=Layout.Id||t.Scratch==null||t.Scratch.CellCount!=Layout.Cells.Count)throw new InvalidOperationException("Snapshot/layout mismatch");
                var crops=new byte[masks.Length][];var values=new string[masks.Length];
                var signature=new StringBuilder(t.Id).Append('|').Append(confirmed.Revision).Append('|').Append(t.SelectedCell).Append('|').Append(t.Phase);
                for(int i=0;i<masks.Length;i++)
                {
                    int core=Layout.Cells[i].CoreIndex;var r=t.Scratch.GetCellRegion(core);crops[i]=new byte[r.Width*r.Height];
                    bool peek=t.TicketType=="challenge"&&t.PeekedCells[core];
                    for(int y=0;y<r.Height;y++)for(int x=0;x<r.Width;x++)crops[i][y*r.Width+x]=(peek||t.Scratch.IsRevealed(r.X+x,r.Y+y))?(byte)255:(byte)0;
                    if(t.TicketType=="number")values[i]=t.Face.Cells[core].Number.ToString("00")+"\n"+DayRules.Money(t.Face.Cells[core].PrizeMinor);
                    else
                    {
                        // No unopened outcome is put in a text label at all. Selected
                        // results still pass the exact confirmed per-pixel mask fence.
                        bool permitted=peek||t.RevealedCells[core]||t.SelectedCell==core;
                        values[i]=!permitted?"":(t.ChallengeSafe[core]?"安全":"危险")+"\n"+(peek&&!t.RevealedCells[core]?"仅查看":"已承诺");
                    }
                    signature.Append('|').Append(values[i]).Append(':').Append(Convert.ToBase64String(crops[i]));
                }
                string publicNumber=t.TicketType=="number"?t.Face.WinningNumber.ToString("00"):"";signature.Append('|').Append(publicNumber);
                string fingerprint;using(var hash=SHA256.Create())fingerprint=Convert.ToBase64String(hash.ComputeHash(Encoding.UTF8.GetBytes(signature.ToString())));
                body.SetActive(false);
                if(!session.Commit(callbackToken,t.Id,confirmed.Revision,fingerprint))return false;
                for(int i=0;i<masks.Length;i++){WriteMask(i,crops[i]);cellText[i].SetText(values[i]);}
                legends["title_cartouche"].SetText(t.TicketType=="number"?"号码票 · 中奖号 →":"挑战票 · 六安两险");
                if(t.TicketType=="number")
                {legends["winning_number_value_only"].SetText(publicNumber);legends["rule_strip"].SetText("号码相同中奖 · 奖金单位：金币");}
                else legends["rule_status_strip"].SetText(t.SelectedCell>=0?"本格已承诺 · 擦开后再决定":t.Busted?"遇到危险 · 按事前保护结算":"选择一格，或在安全后收手");
                body.SetActive(true);return true;
            }
            catch{Invalidate();throw;}
        }
        public void Show(RunState confirmed)
        {
            var t=confirmed?.CurrentTicket;
            if(t==null||confirmed.RecoveryRequired||t.TicketType!=Layout.Id){Invalidate();return;}
            if(activeTicket!=t.Id||!session.Visible)Begin(t.Id,confirmed.Revision);
            if(confirmed.Revision!=DisplayedRevision||!IsVisible)ShowConfirmed(token,confirmed);
        }
        void WriteMask(int index,byte[] bytes)
        {
            var colors=new Color32[bytes.Length];for(int p=0;p<bytes.Length;p++)colors[p]=new Color32(bytes[p],bytes[p],bytes[p],255);
            masks[index].SetPixels32(colors);masks[index].Apply(false,false);
        }
        public void Invalidate()
        {
            session.Invalidate();token=Guid.Empty;if(body!=null)body.SetActive(false);
            if(cellText!=null)foreach(var label in cellText)if(label!=null)label.SetText("");
        }
        public bool TryPaperUv(Ray ray,out Uv uv)
        {if(IsVisible&&collider!=null&&collider.Raycast(ray,out RaycastHit hit,100)){uv=new Uv(hit.textureCoord.x,hit.textureCoord.y);return true;}uv=default;return false;}
        public Vector3 PaperUvToWorld(Uv uv)=>transform.TransformPoint(Point(uv,PaperY));
        void OnDisable(){Invalidate();}
        void OnDestroy(){foreach(var obj in owned)if(obj!=null)Destroy(obj);}
    }
}

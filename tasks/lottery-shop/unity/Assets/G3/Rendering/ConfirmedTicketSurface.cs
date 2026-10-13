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
        public const float PaperY=0,TextY=.00006f,SilverY=.00012f;
        readonly List<UnityEngine.Object> owned=new List<UnityEngine.Object>();
        readonly DisplaySession session=new DisplaySession();
        readonly Dictionary<string,BoundedGlyphLabel> legends=new Dictionary<string,BoundedGlyphLabel>();
        GameObject body; MeshCollider collider; Texture2D[] masks; BoundedGlyphLabel[] cellText,cellNumbers;
        float width,depth; Guid token; string activeTicket;
        public TicketLayout Layout {get;private set;}
        public bool IsVisible => body!=null&&body.activeInHierarchy&&session.Visible;
        public long DisplayedRevision => session.Revision;
        public IReadOnlyList<BoundedGlyphLabel> CellLabels => cellText;
        public IReadOnlyList<BoundedGlyphLabel> CellNumberLabels=>cellNumbers;
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
            // Thin paper edge and contact shadow share the atomic display body, so
            // neither survives a failed save or leaks an unconfirmed ticket.
            var edge=new GameObject("Fine paper stock edge");edge.transform.SetParent(body.transform,false);
            edge.AddComponent<MeshFilter>().sharedMesh=BuildPaperStockMesh();edge.AddComponent<MeshRenderer>();
            var edgeMat=Own(new Material(Shader.Find("Universal Render Pipeline/Lit")));edgeMat.color=new Color(.78f,.74f,.62f);edgeMat.SetFloat("_Smoothness",.1f);edge.GetComponent<Renderer>().sharedMaterial=edgeMat;
            // Natural edge contact comes from the lit stock mesh. No enlarged black
            // backing box: a 0.4 m sheet must read as paper rather than a rigid board.

            masks=new Texture2D[Layout.Cells.Count];cellText=new BoundedGlyphLabel[Layout.Cells.Count];cellNumbers=new BoundedGlyphLabel[Layout.Id=="challenge"?8:0];
            var publicFont=Own(new Material(ordinaryFont));
            for(int i=0;i<Layout.Cells.Count;i++)
            {
                var cell=Layout.Cells[i];int cols=Layout.Cells.Count/2;int ci=cell.CoreIndex;
                int cw=(ci%cols+1)*256/cols-(ci%cols)*256/cols;
                masks[i]=Own(new Texture2D(cw,64,TextureFormat.RGBA32,false,true){name="Confirmed coverage "+cell.Id,filterMode=FilterMode.Point,wrapMode=TextureWrapMode.Clamp});
                WriteMask(i,new byte[cw*64]);
                var silverMat=Own(new Material(silver));silverMat.SetTexture("_RevealTex",masks[i]);Quad("Opaque silver "+cell.Id,cell.Silver,SilverY,silverMat);
                var glyphMat=Own(new Material(maskedFont));glyphMat.SetTexture("_RevealTex",masks[i]);
                var resultBox=cell.Text;
                if(Layout.Id=="challenge")
                {
                    // Public positional ID only: independent of all hidden outcomes.
                    // Stay inside the reviewed text-safe box, above masked results.
                    var ordinal=Label("Public cell number "+(i+1),new PixelRect(cell.Text.X,cell.Text.Y,cell.Text.Width,64),publicFont,font,60);
                    var pos=ordinal.transform.localPosition;pos.y=SilverY+.00004f;ordinal.transform.localPosition=pos;ordinal.SetText((i+1).ToString());cellNumbers[i]=ordinal;
                    resultBox=new PixelRect(cell.Text.X,cell.Text.Y+68,cell.Text.Width,cell.Text.Height-68);
                }
                var label=Label("Masked result "+cell.Id,resultBox,glyphMat,font,Layout.Id=="number"?76:68);cellText[i]=label;
                float sw=cell.Silver.Width*width/Layout.Width,sh=cell.Silver.Height*depth/Layout.Height;
                var tc=resultBox.Center(Layout.Width,Layout.Height);var sc=cell.Silver.Center(Layout.Width,Layout.Height);
                label.SetMaskMapping(new Vector4(1/sw,1/sh,.5f+(float)(tc.U-sc.U)*width/sw,.5f+(float)(tc.V-sc.V)*depth/sh));
            }
            var headerMat=Own(new Material(ordinaryFont));
            foreach(var region in Layout.Labels) legends.Add(region.Id,Label("Live "+region.Id,region.Bounds,headerMat,font,region.Id.Contains("strip")?44:68));
        }
        Mesh BuildPaperStockMesh()
        {
            // The printed quad is the sole top face. A cube at y=-thickness/2
            // puts its untextured top at PaperY too, making opaque draws compete
            // at equal depth and erase the approved artwork (observed in run08).
            // Four outward sides and an underside preserve real paper thickness
            // and contact while leaving the original UV/collider/layers untouched.
            const float thickness=.00024f;
            float x=width*.5f,z=depth*.5f;
            var a=new Vector3(-x,PaperY,-z);var b=new Vector3(x,PaperY,-z);
            var c=new Vector3(x,PaperY,z);var d=new Vector3(-x,PaperY,z);
            var down=Vector3.down*thickness;
            var vertices=new List<Vector3>();var uvs=new List<Vector2>();var triangles=new List<int>();
            AddStockFace(vertices,uvs,triangles,a,b,b+down,a+down); // -Z
            AddStockFace(vertices,uvs,triangles,b,c,c+down,b+down); // +X
            AddStockFace(vertices,uvs,triangles,c,d,d+down,c+down); // +Z
            AddStockFace(vertices,uvs,triangles,d,a,a+down,d+down); // -X
            AddStockFace(vertices,uvs,triangles,a+down,b+down,c+down,d+down); // -Y
            var mesh=Own(new Mesh{name="Paper stock sides and underside; no top face"});
            mesh.SetVertices(vertices);mesh.SetUVs(0,uvs);mesh.SetTriangles(triangles,0);
            mesh.RecalculateNormals();mesh.RecalculateBounds();return mesh;
        }
        static void AddStockFace(List<Vector3> vertices,List<Vector2> uvs,List<int> triangles,Vector3 a,Vector3 b,Vector3 c,Vector3 d)
        {
            int start=vertices.Count;vertices.AddRange(new[]{a,b,c,d});
            uvs.AddRange(new[]{Vector2.zero,Vector2.right,Vector2.one,Vector2.up});
            triangles.AddRange(new[]{start,start+1,start+2,start,start+2,start+3});
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
            if(!isActiveAndEnabled||confirmed==null||t==null||!session.IsCurrent(callbackToken,t.Id,confirmed.Revision))return false;
            if(confirmed.RecoveryRequired){Invalidate();return false;}
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
                        values[i]=!permitted?"":(t.ChallengeSafe[core]?"安全":"危险")+"\n"+(t.RevealedCells[core]?"已揭晓":peek?"仅查看":"已承诺");
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

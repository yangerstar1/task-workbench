using System;
using System.Collections.Generic;
using UnityEngine;

namespace Lottery.G3.Rendering
{
    // Glyph geometry uses a licensed dynamic font. Bounds are enforced on the CPU;
    // result labels additionally carry UV1 into the exact confirmed silver mask.
    public sealed class BoundedGlyphLabel : MonoBehaviour
    {
        const int RasterSize=80;
        Font font; Material material; Mesh mesh; Color tint;
        string text=""; float em=1,width=1,height=1; TextAnchor anchor; bool dirty=true,wrap;
        Vector4 maskMapping=new Vector4(1,1,0,0);
        public string Text => text;
        public bool Fits { get; private set; }=true;
        public int MissingGlyphCount { get; private set; }
        public Bounds LocalGlyphBounds => mesh==null?new Bounds():mesh.bounds;
        public Vector2 BoxSize => new Vector2(width,height);
        public float EmHeight => em;
        public void Initialize(Font source,Material shared,Color color,TextAnchor alignment=TextAnchor.MiddleCenter)
        {
            font=source??throw new ArgumentNullException(nameof(source)); material=shared??throw new ArgumentNullException(nameof(shared));
            tint=color; anchor=alignment; mesh=new Mesh {name="G3 bounded licensed glyphs"};
            gameObject.AddComponent<MeshFilter>().sharedMesh=mesh; gameObject.AddComponent<MeshRenderer>().sharedMaterial=material;
            Font.textureRebuilt+=AtlasChanged;
        }
        public void SetBox(float w,float h,float fontHeight,bool wordWrap=false)
        {
            if(w<=0||h<=0||fontHeight<=0) throw new ArgumentOutOfRangeException("Text box dimensions must be positive");
            if(width!=w||height!=h||em!=fontHeight||wrap!=wordWrap) {width=w;height=h;em=fontHeight;wrap=wordWrap;dirty=true;}
        }
        // Maps label-local coordinates, measured relative to box center, to mask UV.
        public void SetMaskMapping(Vector4 mapping) {maskMapping=mapping;dirty=true;}
        public void SetText(string value) {value=value??"";if(text!=value){text=value;dirty=true;} RebuildIfNeeded();}
        public void SetColor(Color color) {if(tint!=color){tint=color;dirty=true;}}
        void AtlasChanged(Font rebuilt) {if(rebuilt==font)dirty=true;}
        void LateUpdate(){RebuildIfNeeded();}
        public void RebuildIfNeeded()
        {
            if(!dirty||font==null||mesh==null)return;
            dirty=false; font.RequestCharactersInTexture(text,RasterSize,FontStyle.Normal); MissingGlyphCount=0; Fits=true;
            var lines=new List<List<CharacterInfo>> {new List<CharacterInfo>()}; var advances=new List<float>{0};
            float scale=em/RasterSize;
            foreach(char c in text)
            {
                if(c=='\n'){lines.Add(new List<CharacterInfo>());advances.Add(0);continue;}
                if(!font.GetCharacterInfo(c,out CharacterInfo g,RasterSize,FontStyle.Normal)){MissingGlyphCount++;continue;}
                int line=lines.Count-1; float advance=g.advance*scale;
                if(wrap&&advances[line]+advance>width&&lines[line].Count>0){lines.Add(new List<CharacterInfo>());advances.Add(0);line++;}
                lines[line].Add(g);advances[line]+=advance;
                if(advances[line]>width+.0001f)Fits=false;
            }
            float lineHeight=em*1.16f,totalHeight=em+(lines.Count-1)*lineHeight;
            if(totalHeight>height+.0001f)Fits=false;
            int column=(int)anchor%3,row=(int)anchor/3;
            float baseline=row==0?height*.5f-em*.82f:row==1?totalHeight*.5f-em*.82f:-height*.5f+totalHeight-em*.82f;
            var verts=new List<Vector3>();var uv=new List<Vector2>();var uv1=new List<Vector2>();var colors=new List<Color>();var tris=new List<int>();
            for(int line=0;line<lines.Count;line++)
            {
                float x=column==0?-width*.5f:column==1?-advances[line]*.5f:width*.5f-advances[line];float y=baseline-line*lineHeight;
                foreach(var g in lines[line])
                {
                    float x0=x+g.minX*scale,x1=x+g.maxX*scale,y0=y+g.minY*scale,y1=y+g.maxY*scale;
                    float a=Mathf.Max(x0,-width*.5f),b=Mathf.Min(x1,width*.5f),c=Mathf.Max(y0,-height*.5f),d=Mathf.Min(y1,height*.5f);
                    if(a<b&&c<d&&x1>x0&&y1>y0)
                    {
                        int n=verts.Count;
                        Add(a,c);Add(b,c);Add(b,d);Add(a,d);
                        tris.AddRange(new[]{n,n+2,n+1,n,n+3,n+2});
                        void Add(float px,float py)
                        {
                            float tx=(px-x0)/(x1-x0),ty=(py-y0)/(y1-y0);
                            verts.Add(new Vector3(px,py,0));
                            uv.Add(Vector2.Lerp(Vector2.Lerp(g.uvBottomLeft,g.uvBottomRight,tx),Vector2.Lerp(g.uvTopLeft,g.uvTopRight,tx),ty));
                            uv1.Add(new Vector2(px*maskMapping.x+maskMapping.z,py*maskMapping.y+maskMapping.w));colors.Add(tint);
                        }
                    }
                    x+=g.advance*scale;
                }
            }
            mesh.Clear();mesh.SetVertices(verts);mesh.SetUVs(0,uv);mesh.SetUVs(1,uv1);mesh.SetColors(colors);mesh.SetTriangles(tris,0);mesh.RecalculateBounds();
            material.mainTexture=font.material.mainTexture;
        }
        void OnDestroy(){Font.textureRebuilt-=AtlasChanged;if(mesh!=null)Destroy(mesh);}
    }
}

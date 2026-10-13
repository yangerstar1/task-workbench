using System.Collections.Generic;
using UnityEngine;

namespace Lottery.G3.Interaction
{
    // C: dark compact glass, soft neutral keylines, mint only for actionable/selected UI.
    public static class G3HudTheme
    {
        public static readonly Color Ink=new Color(.055f,.065f,.061f,.90f);
        public static readonly Color InkLift=new Color(.075f,.125f,.105f,.94f);
        public static readonly Color Paper=new Color(.90f,.93f,.91f,1);
        public static readonly Color Card=new Color(.97f,.98f,.97f,1);
        public static readonly Color Copper=new Color(.98f,.48f,.19f,1);
        public static readonly Color Rule=new Color(.43f,.47f,.44f,.55f);
        public static readonly Color QuietInk=new Color(.67f,.73f,.69f,1);
        public static readonly Color DisabledFace=new Color(.14f,.16f,.15f,.90f);
        public static readonly Color DisabledInk=new Color(.58f,.62f,.59f,1);
        public static readonly Color DarkDisabled=DisabledFace;
        public static readonly Color DarkDisabledInk=DisabledInk;
        public static readonly Color Action=new Color(.025f,.245f,.185f,.96f);
        public static readonly Color Mint=new Color(.36f,.85f,.69f,1);
    }

    [DisallowMultipleComponent]
    public sealed class G3HudSurface : MonoBehaviour
    {
        Mesh faceMesh,edgeMesh;Material faceMaterial,edgeMaterial;Renderer edgeRenderer;Color fillTint,edgeTint;
        float lastWidth=-1,lastHeight=-1,lastRadius=-1,lastStroke=-1;
        public static Transform Create(string name,Transform parent,Shader glyphShader,Color fill,Color edge)
        {
            var root=new GameObject(name);root.transform.SetParent(parent,false);
            var surface=root.AddComponent<G3HudSurface>();surface.Build(glyphShader,fill,edge);return root.transform;
        }
        void Build(Shader shader,Color fill,Color edge)
        {
            // The existing, explicitly referenced URP glyph shader provides alpha blend
            // and vertex RGBA. These private materials sample white, never the font atlas.
            faceMesh=new Mesh{name="G3 rounded transparent HUD face"};edgeMesh=new Mesh{name="G3 true outline ring"};
            faceMaterial=new Material(shader){mainTexture=Texture2D.whiteTexture};edgeMaterial=new Material(shader){mainTexture=Texture2D.whiteTexture};
            gameObject.AddComponent<MeshFilter>().sharedMesh=faceMesh;gameObject.AddComponent<MeshRenderer>().sharedMaterial=faceMaterial;
            var outline=new GameObject("Neutral fine keyline");outline.transform.SetParent(transform,false);outline.transform.localPosition=new Vector3(0,0,.0001f);
            outline.AddComponent<MeshFilter>().sharedMesh=edgeMesh;edgeRenderer=outline.AddComponent<MeshRenderer>();edgeRenderer.sharedMaterial=edgeMaterial;
            fillTint=fill;edgeTint=edge;Configure(100,60,8,1);
        }
        // Keep the outline in its face's transparent draw group rather than behind it.
        public void SetSortingOrder(int order)
        {GetComponent<Renderer>().sortingOrder=order;if(edgeRenderer!=null)edgeRenderer.sortingOrder=order;}
        public void Tint(Color fill,Color edge)
        {if(fillTint==fill&&edgeTint==edge)return;fillTint=fill;edgeTint=edge;Paint();}
        public void Configure(float width,float height,float radius=8,float stroke=1)
        {
            if(width==lastWidth&&height==lastHeight&&radius==lastRadius&&stroke==lastStroke)return;
            lastWidth=width;lastHeight=height;lastRadius=radius;lastStroke=stroke;
            stroke=Mathf.Min(stroke,Mathf.Min(width,height)*.45f);
            var outer=Contour(width,height,0,radius);var inner=Contour(width,height,stroke,Mathf.Max(0,radius-stroke));
            var face=new List<Vector3>{Vector3.zero};face.AddRange(inner);var triangles=new List<int>();
            for(int i=1;i<face.Count;i++)triangles.AddRange(new[]{0,i==face.Count-1?1:i+1,i});
            Assign(faceMesh,face,triangles);
            var ring=new List<Vector3>();var edgeTriangles=new List<int>();ring.AddRange(outer);ring.AddRange(inner);
            for(int i=0;i<outer.Count;i++){int next=(i+1)%outer.Count,n=outer.Count;edgeTriangles.AddRange(new[]{i,next,n+i,next,n+next,n+i});}
            Assign(edgeMesh,ring,edgeTriangles);edgeRenderer.enabled=stroke>0;Paint();
        }
        static List<Vector3> Contour(float w,float h,float inset,float radius)
        {
            float left=-.5f+inset/w,right=.5f-inset/w,bottom=-.5f+inset/h,top=.5f-inset/h;
            float rx=Mathf.Min(radius/w,(right-left)*.5f),ry=Mathf.Min(radius/h,(top-bottom)*.5f);var v=new List<Vector3>();
            for(int corner=0;corner<4;corner++)
            {float cx=corner==0||corner==3?right-rx:left+rx,cy=corner<2?top-ry:bottom+ry;
                for(int step=0;step<=8;step++){float angle=(corner*90+step*11.25f)*Mathf.Deg2Rad;v.Add(new Vector3(cx+Mathf.Cos(angle)*rx,cy+Mathf.Sin(angle)*ry,0));}}
            return v;
        }
        static void Assign(Mesh mesh,List<Vector3> vertices,List<int> triangles)
        {mesh.Clear();mesh.SetVertices(vertices);mesh.SetTriangles(triangles,0);var uv=new List<Vector2>();foreach(var p in vertices)uv.Add(Vector2.one*.5f);mesh.SetUVs(0,uv);mesh.RecalculateBounds();}
        void Paint()
        {
            if(faceMesh==null)return;var colors=new List<Color>();
            foreach(var p in faceMesh.vertices){float lift=(p.y+.5f)*.022f;colors.Add(new Color(Mathf.Clamp01(fillTint.r+lift),Mathf.Clamp01(fillTint.g+lift),Mathf.Clamp01(fillTint.b+lift),fillTint.a));}
            faceMesh.SetColors(colors);colors.Clear();for(int i=0;i<edgeMesh.vertexCount;i++)colors.Add(edgeTint);edgeMesh.SetColors(colors);
        }
        void OnDestroy(){if(faceMesh!=null)Destroy(faceMesh);if(edgeMesh!=null)Destroy(edgeMesh);if(faceMaterial!=null)Destroy(faceMaterial);if(edgeMaterial!=null)Destroy(edgeMaterial);}
    }
}

using System.Collections.Generic;
using UnityEngine;

namespace Lottery.G3.Interaction
{
    public enum G3HudSymbol { None,Seat,Shop,Inventory,Phone,More,ChevronUp,ChevronDown,ChevronLeft,ChevronRight,TurnLeft,TurnRight,Check,Lock,CoinBox,Lamp,Stamp,Clip,Ticket,Person,Wallet,Bill,Coins,FastForward }
    [DisallowMultipleComponent]
    public sealed class G3HudIcon : MonoBehaviour
    {
        Mesh mesh;Material material;G3HudSymbol symbol=(G3HudSymbol)(-1);readonly List<Vector3> vertices=new List<Vector3>();readonly List<int> triangles=new List<int>();
        public static G3HudIcon Create(Transform parent,Shader shader)
        {
            var go=new GameObject("Original geometric navigation symbol");go.transform.SetParent(parent,false);var icon=go.AddComponent<G3HudIcon>();
            icon.mesh=new Mesh{name="G3 original stroked UI symbol"};icon.material=new Material(shader);go.AddComponent<MeshFilter>().sharedMesh=icon.mesh;go.AddComponent<MeshRenderer>().sharedMaterial=icon.material;return icon;
        }
        public void Show(G3HudSymbol value,Color tint)
        {
            material.color=tint;gameObject.SetActive(value!=G3HudSymbol.None);if(symbol==value)return;symbol=value;vertices.Clear();triangles.Clear();
            switch(value)
            {
                case G3HudSymbol.Seat:Line(-.32f,-.08f,.32f,-.08f);Line(-.25f,-.08f,-.25f,-.40f);Line(.25f,-.08f,.25f,-.40f);Line(-.29f,.38f,-.29f,-.08f);Line(-.29f,.38f,.24f,.38f);break;
                case G3HudSymbol.Shop:Box(-.39f,-.38f,.39f,.17f);Line(-.45f,.18f,.45f,.18f);Line(-.45f,.18f,-.32f,.42f);Line(.45f,.18f,.32f,.42f);Line(-.32f,.42f,.32f,.42f);Line(0,-.38f,0,.15f);break;
                case G3HudSymbol.Inventory:Box(-.40f,-.37f,.40f,.37f);Line(-.4f,0,.4f,0);Line(-.09f,.20f,.09f,.20f);Line(-.09f,-.17f,.09f,-.17f);break;
                case G3HudSymbol.Phone:Box(-.25f,-.43f,.25f,.43f);Line(-.08f,.30f,.08f,.30f);Line(-.06f,-.30f,.06f,-.30f);break;
                case G3HudSymbol.More:Dot(-.30f,0);Dot(0,0);Dot(.30f,0);break;
                case G3HudSymbol.ChevronUp:Line(-.32f,-.12f,0,.22f);Line(0,.22f,.32f,-.12f);break;
                case G3HudSymbol.ChevronDown:Line(-.32f,.12f,0,-.22f);Line(0,-.22f,.32f,.12f);break;
                case G3HudSymbol.ChevronLeft:Line(.12f,.32f,-.22f,0);Line(-.22f,0,.12f,-.32f);break;
                case G3HudSymbol.ChevronRight:Line(-.12f,.32f,.22f,0);Line(.22f,0,-.12f,-.32f);break;
                case G3HudSymbol.TurnLeft:Line(.32f,-.28f,.32f,.18f);Line(.32f,.18f,-.29f,.18f);Line(-.29f,.18f,-.08f,.39f);Line(-.29f,.18f,-.08f,-.03f);break;
                case G3HudSymbol.TurnRight:Line(-.32f,-.28f,-.32f,.18f);Line(-.32f,.18f,.29f,.18f);Line(.29f,.18f,.08f,.39f);Line(.29f,.18f,.08f,-.03f);break;
                case G3HudSymbol.Check:Line(-.32f,0,-.10f,-.23f);Line(-.10f,-.23f,.34f,.30f);break;
                case G3HudSymbol.CoinBox:Box(-.40f,-.32f,.40f,.20f);Line(-.40f,.20f,-.24f,.37f);Line(.40f,.20f,.24f,.37f);Line(-.24f,.37f,.24f,.37f);Line(-.12f,.28f,.12f,.28f);Line(-.24f,-.32f,-.24f,-.42f);Line(.24f,-.32f,.24f,-.42f);Circle(0,-.05f,.12f);break;
                case G3HudSymbol.Lamp:Line(-.35f,-.37f,.35f,-.37f);Line(-.23f,-.30f,.23f,-.30f);Line(.18f,-.30f,-.08f,.08f);Circle(-.13f,.23f,.22f);Circle(-.13f,.23f,.12f);break;
                case G3HudSymbol.Stamp:Box(-.37f,-.40f,.37f,-.18f);Line(-.20f,-.18f,-.08f,.07f);Line(.20f,-.18f,.08f,.07f);Circle(0,.24f,.19f);Line(-.27f,-.30f,.27f,-.30f);break;
                case G3HudSymbol.Clip:Box(-.27f,-.42f,.27f,.32f);Line(-.12f,.20f,-.12f,.44f);Line(-.12f,.44f,.12f,.44f);Line(.12f,.44f,.12f,.02f);Line(.12f,.02f,-.04f,.02f);Line(-.04f,.02f,-.04f,.23f);break;
                case G3HudSymbol.Ticket:Box(-.42f,-.28f,.42f,.28f);Line(-.12f,-.26f,-.12f,.26f);Line(.03f,.12f,.28f,.12f);Line(.03f,-.07f,.23f,-.07f);break;
                case G3HudSymbol.Person:Circle(0,.18f,.19f);Line(-.37f,-.38f,-.25f,-.14f);Line(-.25f,-.14f,0,-.07f);Line(0,-.07f,.25f,-.14f);Line(.25f,-.14f,.37f,-.38f);Line(-.37f,-.38f,.37f,-.38f);break;
                case G3HudSymbol.Wallet:Box(-.42f,-.28f,.42f,.28f);Box(.11f,-.12f,.42f,.10f);Dot(.24f,-.01f);Line(-.38f,.29f,-.30f,.41f);Line(-.30f,.41f,.27f,.41f);break;
                case G3HudSymbol.Bill:Box(-.31f,-.41f,.31f,.41f);Line(-.17f,.22f,.17f,.22f);Line(-.17f,.04f,.17f,.04f);Line(-.17f,-.14f,.05f,-.14f);break;
                case G3HudSymbol.Coins:Circle(0,.25f,.24f);Line(-.24f,.20f,-.24f,-.28f);Line(.24f,.20f,.24f,-.28f);Line(-.24f,-.04f,0,-.13f);Line(0,-.13f,.24f,-.04f);Line(-.24f,-.26f,0,-.35f);Line(0,-.35f,.24f,-.26f);break;
                case G3HudSymbol.FastForward:Triangle(new Vector2(-.42f,-.30f),new Vector2(-.42f,.30f),new Vector2(.03f,0));Triangle(new Vector2(-.02f,-.30f),new Vector2(-.02f,.30f),new Vector2(.43f,0));break;
                case G3HudSymbol.Lock:Box(-.27f,-.37f,.27f,.07f);Line(-.17f,.07f,-.17f,.31f);Line(-.17f,.31f,.17f,.31f);Line(.17f,.31f,.17f,.07f);break;
            }
            mesh.Clear();mesh.SetVertices(vertices);mesh.SetTriangles(triangles,0);mesh.RecalculateBounds();
        }
        void Triangle(Vector2 a,Vector2 b,Vector2 c){int i=vertices.Count;vertices.Add(a);vertices.Add(b);vertices.Add(c);triangles.AddRange(new[]{i,i+1,i+2});}
        void Circle(float x,float y,float radius)
        {for(int i=0;i<20;i++){float a=i*Mathf.PI*.1f,b=(i+1)*Mathf.PI*.1f;Line(x+Mathf.Cos(a)*radius,y+Mathf.Sin(a)*radius,x+Mathf.Cos(b)*radius,y+Mathf.Sin(b)*radius,.055f);}}
        void Box(float x0,float y0,float x1,float y1){Line(x0,y0,x1,y0);Line(x1,y0,x1,y1);Line(x1,y1,x0,y1);Line(x0,y1,x0,y0);}
        void Dot(float x,float y){Line(x-.025f,y,x+.025f,y,.105f);}
        void Line(float x0,float y0,float x1,float y1,float thickness=.07f)
        {
            var a=new Vector2(x0,y0);var b=new Vector2(x1,y1);var d=(b-a).normalized;var n=new Vector2(-d.y,d.x)*thickness*.5f;int i=vertices.Count;
            vertices.Add(a-n);vertices.Add(b-n);vertices.Add(b+n);vertices.Add(a+n);triangles.AddRange(new[]{i,i+2,i+1,i,i+3,i+2});
        }
        void OnDestroy(){if(mesh!=null)Destroy(mesh);if(material!=null)Destroy(material);}
    }
}

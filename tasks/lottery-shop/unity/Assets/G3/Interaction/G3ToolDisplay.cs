using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering.Universal;
namespace Lottery.G3.Interaction
{
    // Three small physical still-life objects. Authority stays in ConfigurationSnapshot.
    public sealed class G3ToolDisplay : MonoBehaviour
    {
        readonly List<Object> owned=new List<Object>();string shown;GameObject model;Shader shader;
        public void Initialize(Shader lit){shader=lit;}
        public Bounds WorldBounds
        {get{if(model==null)return new Bounds(transform.position,Vector3.zero);var renderers=model.GetComponentsInChildren<Renderer>();if(renderers.Length==0)return new Bounds(transform.position,Vector3.zero);var b=renderers[0].bounds;for(int i=1;i<renderers.Length;i++)b.Encapsulate(renderers[i].bounds);return b;}}
        Material Mat(string name,Color color,float metallic=0,float smooth=.35f)
        {var m=new Material(shader){name=name};m.color=color;m.SetFloat("_Metallic",metallic);m.SetFloat("_Smoothness",smooth);owned.Add(m);return m;}
        GameObject Shape(string name,PrimitiveType type,Vector3 p,Vector3 size,Material m)
        {var g=GameObject.CreatePrimitive(type);g.name=name;g.transform.SetParent(model.transform,false);g.transform.localPosition=p;g.transform.localScale=size;g.GetComponent<Renderer>().sharedMaterial=m;Destroy(g.GetComponent<Collider>());return g;}
        public void Show(string id)
        {
            if(shown==id)return;shown=id;if(model!=null){model.SetActive(false);Destroy(model);}foreach(var m in owned)if(m!=null)Destroy(m);owned.Clear();
            if(string.IsNullOrEmpty(id))return;var authored=Resources.Load<GameObject>("G3/Shop/Tool_"+id+"_Runtime");if(authored!=null){model=Instantiate(authored,transform);model.name="Snapshot-bound authored "+id;model.transform.localScale*=id=="inspection_lamp" ? .53f : .55f;ApplySelectedFinish(id);BuildInspectionLight(id);return;}if(id=="small_prize_box"||id=="inspection_lamp"||id=="large_prize_stamp")throw new System.InvalidOperationException("Normalized authored tool prefab missing: "+id);model=new GameObject("Snapshot-bound "+id);model.transform.SetParent(transform,false);model.transform.localScale=Vector3.one*.45f;
            var brass=Mat("Brushed brass",new Color(.65f,.45f,.18f),.78f,.52f);var wood=Mat("Dark walnut",new Color(.23f,.105f,.055f),0,.22f);
            var ceramic=Mat("Warm cream enamel",new Color(.84f,.80f,.67f),.12f,.42f);var jade=Mat("Green enamel",new Color(.045f,.19f,.14f),.20f,.4f);
            if(id=="small_prize_box")
            {
                Shape("Wooden prize case",PrimitiveType.Cube,new Vector3(0,.057f,0),new Vector3(.23f,.105f,.15f),wood);
                Shape("Brass rim lid",PrimitiveType.Cube,new Vector3(0,.115f,0),new Vector3(.24f,.018f,.16f),brass);
                Shape("Enamel inlay",PrimitiveType.Cube,new Vector3(0,.126f,0),new Vector3(.19f,.006f,.11f),jade);
                Shape("Case latch",PrimitiveType.Cube,new Vector3(0,.08f,.08f),new Vector3(.042f,.055f,.009f),brass);
                for(int i=0;i<3;i++)Shape("Stacked token "+i,PrimitiveType.Cylinder,new Vector3(.055f,.138f+i*.01f,.012f),new Vector3(.058f,.006f,.058f),brass);
            }
            else if(id=="inspection_lamp")
            {
                Shape("Lamp weighted foot",PrimitiveType.Cylinder,new Vector3(0,.025f,0),new Vector3(.19f,.025f,.14f),jade);
                var stem=Shape("Articulated brass neck",PrimitiveType.Cylinder,new Vector3(-.035f,.15f,-.02f),new Vector3(.018f,.13f,.018f),brass);stem.transform.localRotation=Quaternion.Euler(0,0,12);
                var shade=Shape("Inspection enamel shade",PrimitiveType.Cylinder,new Vector3(.025f,.278f,.008f),new Vector3(.19f,.06f,.15f),jade);shade.transform.localRotation=Quaternion.Euler(0,0,-22);
                Shape("Frosted lamp lens",PrimitiveType.Cylinder,new Vector3(.025f,.22f,.008f),new Vector3(.15f,.004f,.11f),ceramic);
            }
            else if(id=="ticket_clip")
            {
                Shape("Receipt tray",PrimitiveType.Cube,new Vector3(0,.013f,0),new Vector3(.23f,.025f,.16f),wood);
                for(int i=0;i<4;i++)Shape("Paper ticket stub",PrimitiveType.Cube,new Vector3(.004f*i,.03f+.005f*i,0),new Vector3(.18f,.004f,.13f),ceramic);
                Shape("Brass binding clip",PrimitiveType.Cube,new Vector3(0,.067f,-.07f),new Vector3(.065f,.064f,.035f),brass);
            }
            else if(id=="loss_mat")
            {Shape("Folded green cushion",PrimitiveType.Cube,new Vector3(0,.025f,0),new Vector3(.24f,.05f,.16f),jade);Shape("Woven cream band",PrimitiveType.Cube,new Vector3(.06f,.054f,0),new Vector3(.025f,.006f,.16f),ceramic);}
            else
            {
                Shape("Stamp resting base",PrimitiveType.Cube,new Vector3(0,.026f,0),new Vector3(.18f,.05f,.13f),wood);
                Shape("Stamp engraved brass foot",PrimitiveType.Cube,new Vector3(0,.067f,0),new Vector3(.14f,.028f,.1f),brass);
                Shape("Stamp turned handle",PrimitiveType.Cylinder,new Vector3(0,.14f,0),new Vector3(.058f,.06f,.058f),wood);
                Shape("Stamp rounded grip",PrimitiveType.Sphere,new Vector3(0,.205f,0),new Vector3(.11f,.08f,.10f),id=="large_prize_stamp"?jade:ceramic);
                Shape("Handle brass collar",PrimitiveType.Cylinder,new Vector3(0,.095f,0),new Vector3(.075f,.01f,.075f),brass);
            }
        }
        void BuildInspectionLight(string id)
        {
            if(id!="inspection_lamp")return;
            var view=GetComponentInParent<G3SceneView>();
            if(view==null||view.Environment==null)return;
            // The importer combines meshes by material; Warm_Light contains only
            // the inspected LED ring in this tool. Use its world-space bounds.
            // This light is presentation only; it never reads or changes game rules.
            Renderer emitter=null;
            foreach(var renderer in model.GetComponentsInChildren<Renderer>())
                if(renderer.sharedMaterial!=null&&renderer.sharedMaterial.name=="Warm_Light"){emitter=renderer;break;}
            if(emitter==null)throw new System.InvalidOperationException("Inspection lamp emitter mesh missing");
            var target=view.Environment.TicketPosition;
            var direction=(target-emitter.bounds.center).normalized;
            var go=new GameObject("Inspection lamp local paper light");go.transform.SetParent(model.transform,false);
            // Clear the lens/bezel before tracing toward the paper, in world metres.
            go.transform.position=emitter.bounds.center+direction*.018f;go.transform.LookAt(target);
            var light=go.AddComponent<Light>();light.type=LightType.Spot;
            light.color=new Color(1f,.94f,.82f);light.intensity=.12f;light.range=.85f;
            // Keep the source at the LED ring and feather its beam onto the paper.
            // The tray lip is ~43 degrees off-axis in the authored left-hand slot;
            // a 35-degree half-cone rejects it without dimming the on-axis ticket.
            // The small core also rolls off the nearer paper instead of applying
            // full intensity across the steep inverse-square near-field gradient.
            light.spotAngle=70f;light.innerSpotAngle=20f;
            // A small local source with no extra shadow atlas slot. The ceiling
            // reading source already supplies the tabletop's soft cast shadows.
            light.shadows=LightShadows.None;light.renderMode=LightRenderMode.ForcePixel;
            light.GetUniversalAdditionalLightData().usePipelineSettings=false;
        }
        void ApplySelectedFinish(string id)
        {
            if(id!="small_prize_box")return;
            // The selected C reference uses a walnut case with brass fittings.
            // Keep the authored lid/latch geometry and item/slot identity intact.
            var walnut=Resources.Load<Material>("G3/Shop/Materials/Warm_Oak");
            if(walnut==null)throw new System.InvalidOperationException("Authored wooden case material missing");
            foreach(var renderer in model.GetComponentsInChildren<Renderer>())
            {
                var materials=renderer.sharedMaterials;bool changed=false;
                for(int i=0;i<materials.Length;i++)if(materials[i]!=null&&materials[i].name=="Oxblood_Enamel"){materials[i]=walnut;changed=true;}
                if(changed)renderer.sharedMaterials=materials;
            }
        }
        void OnDestroy(){foreach(var m in owned)if(m!=null)Destroy(m);}
    }
}

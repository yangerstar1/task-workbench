using System;
using System.Collections.Generic;
using System.Linq;
using Lottery.G3.Core;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Lottery.G3.Interaction
{
    // Presentation only. JSON contains authoring-space anchors, never game state.
    public sealed class G3ShopEnvironment : MonoBehaviour
    {
        [Serializable] public sealed class Anchor { public string name; public float[] position; public float[] rotation; }
        [Serializable] public sealed class CollisionBox { public string name,target; public float[] position,size; }
        [Serializable] public sealed class LayoutData { public Anchor[] anchors; public CollisionBox[] colliders; }
        readonly List<Light> practicals=new List<Light>();readonly HashSet<Material> instantiatedMaterials=new HashSet<Material>();
        Light daylight; LayoutData layout; bool? night; GameObject art;
        UniversalRenderPipelineAsset priorPipeline,runtimePipeline;
        public Vector3 TicketPosition=>AnchorPosition("ticket",new Vector3(2.05f,.797f,-.10f));
        public Vector3 TableCameraPosition=>AnchorPosition("table_camera",TicketPosition+new Vector3(0,1.21f,.59f));
        public Vector3 TableLookAt=>AnchorPosition("table_look_at",TicketPosition);
        public Vector3 EntryPosition=>AnchorPosition("entry",new Vector3(0,0,2.1f));
        public float EntryYaw=>AnchorRotation("entry",new Vector3(8,180,0)).y;
        public Vector3 StandPosition=>AnchorPosition("table_stand",new Vector3(1.15f,0,1.12f));
        public float StandYaw=>AnchorRotation("table_stand",new Vector3(8,210,0)).y;
        public Vector3 ShelfViewPosition=>AnchorPosition("shelf_view",new Vector3(-.95f,0,-.2f));
        public float ShelfViewYaw=>AnchorRotation("shelf_view",new Vector3(8,270,0)).y;
        public Vector3 ShelfTargetPosition=>AnchorPosition("shelf_target",new Vector3(-2.5f,1.2f,-.6f));
        public bool HasImportedArt=>art!=null;
        public int ImportedRendererCount=>art==null?0:art.GetComponentsInChildren<Renderer>().Length;
        public Vector3 AnchorPosition(string name,Vector3 fallback)
        {var a=layout?.anchors?.FirstOrDefault(x=>x.name==name);return a?.position!=null&&a.position.Length==3?V(a.position):fallback;}
        Vector3 AnchorRotation(string name,Vector3 fallback)
        {var a=layout?.anchors?.FirstOrDefault(x=>x.name==name);return a?.rotation!=null&&a.rotation.Length==3?V(a.rotation):fallback;}
        static Vector3 V(float[] p)=>new Vector3(p[0],p[1],p[2]);
        public void Build(bool configureQuality=true)
        {
            var source=Resources.Load<GameObject>("G3/Shop/LotteryShop_Runtime")??Resources.Load<GameObject>("G3/Shop/LotteryShop_Interior");
            var manifest=Resources.Load<TextAsset>("G3/Shop/anchors");
            if(source==null||manifest==null)throw new InvalidOperationException("G3 visual candidate requires imported LotteryShop_Interior.fbx and anchors.json; no whitebox fallback is permitted.");
            layout=JsonUtility.FromJson<LayoutData>(manifest.text);
            if(layout==null||layout.colliders==null||layout.colliders.Length<5)throw new InvalidOperationException("Missing bounded shop collision manifest");
            art=Instantiate(source,transform);art.name="Original authored lottery shop";
            foreach(var r in art.GetComponentsInChildren<Renderer>()){r.shadowCastingMode=r.sharedMaterials.Any(m=>m.renderQueue>=(int)RenderQueue.Transparent)?ShadowCastingMode.Off:ShadowCastingMode.On;r.receiveShadows=true;}
            foreach(var box in layout.colliders)
            {
                var go=new GameObject(box.target=="shop"?"Tool shelf":box.name);go.transform.SetParent(transform,false);go.transform.localPosition=V(box.position);
                var collider=go.AddComponent<BoxCollider>();collider.size=V(box.size);
                if(box.target=="shop"){go.transform.localPosition-=Vector3.up*.5f;collider.center=Vector3.up*.5f;collider.size+=Vector3.up*.16f;}
                if(box.target=="none"||string.IsNullOrEmpty(box.target))continue;
                var target=go.AddComponent<G3WorldTarget>();target.IsTable=box.target=="table";
                switch(box.target){case "shop":target.Panel=G3Panel.Shop;break;case "tickets":target.Panel=G3Panel.Tickets;break;case "inventory":target.Panel=G3Panel.Inventory;break;case "drawer":target.Panel=G3Panel.Drawer;break;case "phone":target.Panel=G3Panel.Phone;break;}
            }
            // Independent camera-only quality state. Does not mutate source pipeline assets.
            priorPipeline=QualitySettings.renderPipeline as UniversalRenderPipelineAsset;
            var sourcePipeline=Resources.Load<UniversalRenderPipelineAsset>("G3/Shop/G3VisualPipeline")??priorPipeline??GraphicsSettings.defaultRenderPipeline as UniversalRenderPipelineAsset;
            if(configureQuality&&sourcePipeline!=null){runtimePipeline=Instantiate(sourcePipeline);runtimePipeline.name="G3 visual candidate runtime lighting";runtimePipeline.shadowDistance=12;runtimePipeline.msaaSampleCount=4;QualitySettings.renderPipeline=runtimePipeline;}
            var sun=new GameObject("Soft window daylight");sun.transform.SetParent(transform,false);sun.transform.rotation=Quaternion.Euler(47,128,0);
            daylight=sun.AddComponent<Light>();daylight.type=LightType.Directional;daylight.color=new Color(1f,.93f,.80f);daylight.intensity=1.35f;daylight.shadows=LightShadows.Soft;daylight.shadowStrength=.65f;daylight.shadowBias=.025f;daylight.shadowNormalBias=.2f;
            Practical("Warm counter pendant",AnchorPosition("light_counter",new Vector3(-.5f,2.35f,-1.35f)),new Color(1,.78f,.52f),1.8f,4.2f);
            Practical("Table reading pendant",AnchorPosition("light_table",new Vector3(2.0f,2.3f,-.2f)),new Color(1,.88f,.69f),1.4f,3.0f);
            Practical("Shelf ambient fill",AnchorPosition("light_shelf",new Vector3(-2.2f,2.2f,-.4f)),new Color(.85f,.9f,1),.6f,3);
            SetNight(false);Physics.SyncTransforms();
        }
        void Practical(string name,Vector3 p,Color color,float strength,float range)
        {var go=new GameObject(name);go.transform.SetParent(transform,false);go.transform.localPosition=p;var l=go.AddComponent<Light>();l.type=LightType.Point;l.color=color;l.intensity=strength;l.range=range;l.shadows=LightShadows.None;practicals.Add(l);}
        public void SetNight(bool value)
        {
            if(night==value)return;night=value;daylight.intensity=value? .23f:1.35f;daylight.color=value?new Color(.44f,.58f,.88f):new Color(1,.93f,.8f);
            RenderSettings.ambientMode=AmbientMode.Trilight;RenderSettings.ambientSkyColor=value?new Color(.23f,.28f,.40f):new Color(.65f,.72f,.80f);
            RenderSettings.ambientEquatorColor=value?new Color(.33f,.28f,.23f):new Color(.52f,.49f,.42f);RenderSettings.ambientGroundColor=new Color(.22f,.19f,.15f);
            for(int i=0;i<practicals.Count;i++)practicals[i].intensity=(i==0?1.8f:i==1?1.4f:.6f)*(value?1.1f:1);
            if(art!=null)foreach(var renderer in art.GetComponentsInChildren<Renderer>())foreach(var material in renderer.materials)
                {instantiatedMaterials.Add(material);if((material.name.StartsWith("Window")||material.name.StartsWith("StreetBlur"))&&material.HasProperty("_BaseColor"))material.SetColor("_BaseColor",value?new Color(.06f,.12f,.24f):new Color(.53f,.72f,.82f));}
        }
        public void Sync(RunState state)=>SetNight(state.Phase==DayPhase.NIGHT_BILL||state.Phase==DayPhase.DAY_COMPLETE||state.Phase==DayPhase.RUN_FAILED);
        void OnDestroy(){foreach(var material in instantiatedMaterials)if(material!=null)Destroy(material);if(runtimePipeline!=null){if(QualitySettings.renderPipeline==runtimePipeline)QualitySettings.renderPipeline=priorPipeline;Destroy(runtimePipeline);}}
    }
}

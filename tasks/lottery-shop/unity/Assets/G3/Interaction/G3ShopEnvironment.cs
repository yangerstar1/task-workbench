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
        [Serializable] public sealed class LayoutData { public Anchor[] anchors; public CollisionBox[] colliders;public float ticketWidth=.4f;public bool requiresUnityXReflection; }
        readonly List<Light> practicals=new List<Light>();readonly HashSet<Material> instantiatedMaterials=new HashSet<Material>();readonly Dictionary<Material,Color> authoredWindowColors=new Dictionary<Material,Color>();
        Light daylight; LayoutData layout; bool? night; GameObject art;
        ReflectionProbe roomReflection;bool refreshReflection,capturedLighting;
        AmbientMode previousAmbientMode;Color previousSky,previousEquator,previousGround,previousAmbient;
        SphericalHarmonicsL2 previousAmbientProbe;Light previousSun;float previousReflectionIntensity;
        const int ReflectionGeometryLayer=10;
        // Run08 clipped walnut/printed stock under the additive direct sources.
        // Keep authored texture factors and ambient bounce; reduce source energy
        // in this Gamma/LDR room instead of baking a compensating dark tint.
        const float DaylightStrength=.8f;
        static readonly float[] PracticalStrengths={1.15f,1.25f,.55f,.06f};
        UniversalRenderPipelineAsset priorPipeline,runtimePipeline;
        public float TicketWidth=>layout!=null&&layout.ticketWidth>0?layout.ticketWidth:.4f;
        public Vector3 TicketPosition=>AnchorPosition("ticket",new Vector3(-2.025f,.81825f,.50f));
        public Vector3 TableCameraPosition=>AnchorPosition("table_camera",TicketPosition+new Vector3(0,.70f,.31f));
        public Vector3 TableLookAt=>AnchorPosition("table_look_at",TicketPosition);
        public Vector3 EntryPosition=>AnchorPosition("entry",new Vector3(-.3f,0,1.69f));
        public float EntryYaw=>AnchorRotation("entry",new Vector3(8,180,0)).y;
        public Vector3 StandPosition=>AnchorPosition("table_stand",new Vector3(-.7f,0,.78f));
        public float StandYaw=>AnchorRotation("table_stand",new Vector3(8,230,0)).y;
        public Vector3 ShelfViewPosition=>AnchorPosition("shelf_view",new Vector3(-.045f,0,-.45f));
        public float ShelfViewYaw=>AnchorRotation("shelf_view",new Vector3(8,180,0)).y;
        public Vector3 ShelfTargetPosition=>AnchorPosition("shelf_target",new Vector3(-.045f,1.04f,-1.765f));
        public bool HasImportedArt=>art!=null;
        public int RenderedShopRendererCount=>ImportedRendererCount;
        public int RenderedShopMaterialCount=>art==null?0:art.GetComponentsInChildren<Renderer>().SelectMany(r=>r.sharedMaterials).Where(m=>m!=null).Distinct().Count();
        public int ImportedRendererCount=>art==null?0:art.GetComponentsInChildren<Renderer>().Length;
        public Vector3 AnchorPosition(string name,Vector3 fallback)
        {var a=layout?.anchors?.FirstOrDefault(x=>x.name==name);return a?.position!=null&&a.position.Length==3?V(a.position):fallback;}
        public Vector3 AnchorEulerAngles(string name,Vector3 fallback)=>AnchorRotation(name,fallback);
        Vector3 AnchorRotation(string name,Vector3 fallback)
        {var a=layout?.anchors?.FirstOrDefault(x=>x.name==name);return a?.rotation!=null&&a.rotation.Length==3?V(a.rotation):fallback;}
        static Vector3 V(float[] p)=>new Vector3(p[0],p[1],p[2]);
        public void Build(bool configureQuality=true)
        {
            var source=Resources.Load<GameObject>("G3/Shop/LotteryShop_Runtime");
            var manifest=Resources.Load<TextAsset>("G3/Shop/anchors");
            if(source==null||manifest==null)throw new InvalidOperationException("G3 visual candidate requires imported LotteryShop_Interior.fbx and anchors.json; no whitebox fallback is permitted.");
            layout=JsonUtility.FromJson<LayoutData>(manifest.text);
            if(layout==null||layout.colliders==null||layout.colliders.Length<5)throw new InvalidOperationException("Missing bounded shop collision manifest");
            previousAmbientMode=RenderSettings.ambientMode;previousSky=RenderSettings.ambientSkyColor;
            previousEquator=RenderSettings.ambientEquatorColor;previousGround=RenderSettings.ambientGroundColor;
            previousAmbient=RenderSettings.ambientLight;previousAmbientProbe=RenderSettings.ambientProbe;
            previousSun=RenderSettings.sun;previousReflectionIntensity=RenderSettings.reflectionIntensity;capturedLighting=true;
            art=Instantiate(source,transform);art.name="Original authored lottery shop";
            foreach(var child in art.GetComponentsInChildren<Transform>())child.gameObject.layer=ReflectionGeometryLayer;
            foreach(var r in art.GetComponentsInChildren<Renderer>())
            {r.shadowCastingMode=r.sharedMaterials.Any(m=>m.renderQueue>=(int)RenderQueue.Transparent)?ShadowCastingMode.Off:ShadowCastingMode.On;r.receiveShadows=true;r.reflectionProbeUsage=ReflectionProbeUsage.BlendProbes;}
            foreach(var box in layout.colliders)
            {
                // The permanent physical phone owns its nearest-hit body/glass
                // colliders. A broad legacy proxy would block screen raycasts.
                if(box.target=="phone")continue;
                var go=new GameObject(box.name);go.transform.SetParent(transform,false);go.transform.localPosition=V(box.position);
                var collider=go.AddComponent<BoxCollider>();collider.size=V(box.size);
                // The shop hit box now belongs to the authored tool-sample tray, not the whole till.
                if(box.target=="none"||string.IsNullOrEmpty(box.target))continue;
                var target=go.AddComponent<G3WorldTarget>();target.IsTable=box.target=="table";
                switch(box.target){case "shop":target.Panel=G3Panel.Shop;break;case "tickets":target.Panel=G3Panel.Tickets;break;case "inventory":target.Panel=G3Panel.Inventory;break;case "drawer":target.Panel=G3Panel.Drawer;break;case "phone":target.Panel=G3Panel.Phone;break;}
            }
            // Independent camera-only quality state. Does not mutate source pipeline assets.
            priorPipeline=QualitySettings.renderPipeline as UniversalRenderPipelineAsset;
            var sourcePipeline=Resources.Load<UniversalRenderPipelineAsset>("G3/Shop/G3VisualPipeline")??priorPipeline??GraphicsSettings.defaultRenderPipeline as UniversalRenderPipelineAsset;
            if(configureQuality&&sourcePipeline!=null){runtimePipeline=Instantiate(sourcePipeline);runtimePipeline.name="G3 visual candidate runtime lighting";runtimePipeline.shadowDistance=12;runtimePipeline.msaaSampleCount=4;QualitySettings.renderPipeline=runtimePipeline;}
            var sun=new GameObject("Soft window daylight");sun.transform.SetParent(transform,false);sun.transform.rotation=Quaternion.Euler(47,232,0);
            daylight=sun.AddComponent<Light>();daylight.type=LightType.Directional;daylight.color=new Color(1f,.94f,.84f);
            daylight.intensity=DaylightStrength;daylight.shadows=LightShadows.Soft;daylight.shadowStrength=.55f;
            daylight.shadowBias=.015f;daylight.shadowNormalBias=.06f;
            daylight.GetUniversalAdditionalLightData().usePipelineSettings=false;RenderSettings.sun=daylight;
            // Real ceiling/pendant sources supply local shape and contact shadows.
            // Explicit ambient SH below supplies the bounce that an unbaked room lacks.
            Practical("Warm counter pendant",AnchorPosition("light_counter",new Vector3(1.12f,2.30f,-.9f)),new Color(1,.89f,.72f),PracticalStrengths[0],4.8f,new Vector3(.4f,.9f,-1.7f),true);
            Practical("Table reading pendant",AnchorPosition("light_table",new Vector3(-1.71f,2.30f,-.24f)),new Color(1,.95f,.86f),PracticalStrengths[1],4.2f,TicketPosition,true);
            Practical("Shelf ambient fill",AnchorPosition("light_shelf",new Vector3(2.2f,2.2f,-.4f)),new Color(.83f,.91f,1),PracticalStrengths[2],4,new Vector3(2.1f,1.1f,-.4f),false);
            Practical("Counter board wash",new Vector3(.45f,2.04f,-2.287f),new Color(1,.93f,.81f),PracticalStrengths[3],2f,new Vector3(.45f,1.6f,-2.5f),false);
            var probe=new GameObject("Shop material reflection");probe.transform.SetParent(transform,false);probe.transform.localPosition=new Vector3(-.4f,1.35f,-.2f);
            roomReflection=probe.AddComponent<ReflectionProbe>();roomReflection.mode=ReflectionProbeMode.Realtime;
            roomReflection.refreshMode=ReflectionProbeRefreshMode.ViaScripting;roomReflection.timeSlicingMode=ReflectionProbeTimeSlicingMode.NoTimeSlicing;
            roomReflection.resolution=128;roomReflection.size=new Vector3(6.4f,3.1f,5.6f);roomReflection.center=new Vector3(.4f,0,.2f);
            roomReflection.boxProjection=true;roomReflection.nearClipPlane=.08f;roomReflection.farClipPlane=12;roomReflection.intensity=.85f;
            // Only authored room geometry enters reflections, never camera-attached HUD.
            roomReflection.cullingMask=1<<ReflectionGeometryLayer;roomReflection.clearFlags=ReflectionProbeClearFlags.SolidColor;
            SetNight(false);Physics.SyncTransforms();
        }
        void Practical(string name,Vector3 p,Color color,float strength,float range,Vector3 target,bool shadow)
        {
            var go=new GameObject(name);go.transform.SetParent(transform,false);go.transform.localPosition=p;go.transform.LookAt(target);
            var light=go.AddComponent<Light>();light.type=LightType.Spot;light.spotAngle=115;light.innerSpotAngle=70;
            light.color=color;light.intensity=strength;light.range=range;light.shadows=shadow?LightShadows.Soft:LightShadows.None;
            light.shadowStrength=.6f;light.shadowBias=.008f;light.shadowNormalBias=.025f;
            light.GetUniversalAdditionalLightData().usePipelineSettings=false;practicals.Add(light);
        }
        void LateUpdate()
        {
            if(!refreshReflection||roomReflection==null)return;
            refreshReflection=false;roomReflection.RenderProbe();
        }
        public void SetNight(bool value)
        {
            if(night==value)return;night=value;
            daylight.intensity=value ? .16f : DaylightStrength;daylight.color=value?new Color(.49f,.62f,.91f):new Color(1,.94f,.84f);
            RenderSettings.ambientMode=AmbientMode.Trilight;
            RenderSettings.ambientSkyColor=value?new Color(.30f,.34f,.43f):new Color(.68f,.74f,.80f);
            RenderSettings.ambientEquatorColor=value?new Color(.35f,.31f,.27f):new Color(.58f,.57f,.51f);
            RenderSettings.ambientGroundColor=value?new Color(.20f,.18f,.17f):new Color(.34f,.31f,.26f);
            // Setting only Trilight colours does not establish a new runtime scene's
            // ambient probe. Set its actual SH coefficients synchronously as well.
            var bounce=new SphericalHarmonicsL2();bounce.AddAmbientLight(value?new Color(.20f,.21f,.24f):new Color(.42f,.46f,.43f));
            bounce.AddDirectionalLight(Vector3.up,value?new Color(.16f,.13f,.10f):new Color(.20f,.22f,.25f),.7f);
            RenderSettings.ambientProbe=bounce;RenderSettings.reflectionIntensity=value ? .7f : 1;
            for(int i=0;i<practicals.Count;i++)practicals[i].intensity=PracticalStrengths[i]*(value?1.04f:1);
            roomReflection.backgroundColor=value?new Color(.08f,.10f,.15f):new Color(.40f,.45f,.49f);refreshReflection=true;
            if(art!=null)foreach(var renderer in art.GetComponentsInChildren<Renderer>())foreach(var material in renderer.materials)
                {instantiatedMaterials.Add(material);if((material.name.StartsWith("Window")||material.name.StartsWith("StreetBlur"))&&material.HasProperty("_BaseColor")){if(!authoredWindowColors.ContainsKey(material))authoredWindowColors[material]=material.GetColor("_BaseColor");material.SetColor("_BaseColor",authoredWindowColors[material]*(value?new Color(.06f,.12f,.24f):Color.white));}}
        }
        public void Sync(RunState state)=>SetNight(state.Phase==DayPhase.NIGHT_BILL||state.Phase==DayPhase.DAY_COMPLETE||state.Phase==DayPhase.RUN_FAILED);
        void OnDestroy()
        {
            foreach(var material in instantiatedMaterials)if(material!=null)Destroy(material);
            if(runtimePipeline!=null){if(QualitySettings.renderPipeline==runtimePipeline)QualitySettings.renderPipeline=priorPipeline;Destroy(runtimePipeline);}
            // A disabled menu can outlive the newer gameplay environment. It must
            // never restore its old snapshot over another environment's lighting.
            if(capturedLighting&&daylight!=null&&RenderSettings.sun==daylight)
            {RenderSettings.ambientMode=previousAmbientMode;RenderSettings.ambientSkyColor=previousSky;RenderSettings.ambientEquatorColor=previousEquator;RenderSettings.ambientGroundColor=previousGround;RenderSettings.ambientLight=previousAmbient;RenderSettings.ambientProbe=previousAmbientProbe;RenderSettings.sun=previousSun;RenderSettings.reflectionIntensity=previousReflectionIntensity;}
        }
    }
}

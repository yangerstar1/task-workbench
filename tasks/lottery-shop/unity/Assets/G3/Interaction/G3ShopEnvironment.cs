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
        Material exteriorMaterial;Texture2D exteriorDay,exteriorNight;Mesh exteriorNearMesh,tableContactMesh,furnitureContactMesh;
        ReflectionProbe roomReflection;bool capturedLighting,bakingReflection;
        Cubemap dayReflection,nightReflection;
        public const string ReflectionRecipe="G3_SHOP_STATIC_REFLECTION_V2";
        public const int ReflectionFaceSize=128,ReflectionMipCount=8;
        [Serializable] public sealed class ReflectionReceipt
        {
            public int schemaVersion,captureRenderers,captureTriangles;public string status,recipe,sourceDigest,sourceCommit,runId,runAttempt,unityVersion,colorSpace,runtimeDependencyHash,pipelineDependencyHash;
            public ReflectionTexture day,night;
        }
        [Serializable] public sealed class ReflectionTexture
        {
            public string file,sha256,metaSha256,metaGuid,format,shape;public long bytes,metaBytes;
            public int sourceWidth,sourceHeight,faceSize,mipCount,pixelSampleCount;public float maxChannelRange;public bool linear,specular;
        }
        AmbientMode previousAmbientMode;Color previousSky,previousEquator,previousGround,previousAmbient;
        SphericalHarmonicsL2 previousAmbientProbe;Light previousSun;float previousReflectionIntensity;
        // User layer 30 is reserved for this isolated offline bake; 31 belongs to Editor previews.
        public const int ReflectionBakeLayer=30;
        const int ReflectionGeometryLayer=10;
        // Run08 clipped walnut/printed stock under the additive direct sources.
        // Keep authored texture factors and ambient bounce; reduce source energy
        // in this Gamma/LDR room instead of baking a compensating dark tint.
        const float DaylightStrength=.6f;
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
        public int RenderedShopRendererCount=>GetComponentsInChildren<Renderer>().Length;
        public int RenderedShopMaterialCount=>art==null?0:GetComponentsInChildren<Renderer>().SelectMany(r=>r.sharedMaterials).Where(m=>m!=null).Distinct().Count();
        public int ImportedRendererCount=>art==null?0:art.GetComponentsInChildren<Renderer>().Length;
        public Vector3 AnchorPosition(string name,Vector3 fallback)
        {var a=layout?.anchors?.FirstOrDefault(x=>x.name==name);return a?.position!=null&&a.position.Length==3?V(a.position):fallback;}
        public Vector3 AnchorEulerAngles(string name,Vector3 fallback)=>AnchorRotation(name,fallback);
        Vector3 AnchorRotation(string name,Vector3 fallback)
        {var a=layout?.anchors?.FirstOrDefault(x=>x.name==name);return a?.rotation!=null&&a.rotation.Length==3?V(a.rotation):fallback;}
        static Vector3 V(float[] p)=>new Vector3(p[0],p[1],p[2]);
        public void Build(bool configureQuality=true)=>BuildInternal(configureQuality,false);
#if UNITY_EDITOR
        // Only the offline Editor baker can construct this first-build path.
        // Runtime never substitutes a blank probe or starts an expensive capture.
        public ReflectionProbe BuildForReflectionBake()
        {
            if(Application.isPlaying)throw new InvalidOperationException("Reflection baking is Editor-only");
            BuildInternal(true,true);return roomReflection;
        }
#endif
        void BuildInternal(bool configureQuality,bool forReflectionBake)
        {
            bakingReflection=forReflectionBake;
            if(!bakingReflection)LoadBakedReflections();
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
            foreach(var child in art.GetComponentsInChildren<Transform>())child.gameObject.layer=bakingReflection?ReflectionBakeLayer:ReflectionGeometryLayer;
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
                // Interaction volumes are selection targets, not solid room geometry.
                // Phone glass rays ignore these triggers but still hit real obstacles.
                collider.isTrigger=true;
                var target=go.AddComponent<G3WorldTarget>();target.IsTable=box.target=="table";
                switch(box.target){case "shop":target.Panel=G3Panel.Shop;break;case "tickets":target.Panel=G3Panel.Tickets;break;case "inventory":target.Panel=G3Panel.Inventory;break;case "drawer":target.Panel=G3Panel.Drawer;break;case "phone":target.Panel=G3Panel.Phone;break;}
            }
            // Independent camera-only quality state. Does not mutate source pipeline assets.
            priorPipeline=QualitySettings.renderPipeline as UniversalRenderPipelineAsset;
            var sourcePipeline=Resources.Load<UniversalRenderPipelineAsset>("G3/Shop/G3VisualPipeline")??priorPipeline??GraphicsSettings.defaultRenderPipeline as UniversalRenderPipelineAsset;
            if(configureQuality&&sourcePipeline!=null){runtimePipeline=Instantiate(sourcePipeline);runtimePipeline.name="G3 visual candidate runtime lighting";runtimePipeline.shadowDistance=12;runtimePipeline.msaaSampleCount=4;QualitySettings.renderPipeline=runtimePipeline;}
            var sun=new GameObject("Soft window daylight");sun.transform.SetParent(transform,false);sun.transform.rotation=Quaternion.Euler(25,190,0);
            daylight=sun.AddComponent<Light>();daylight.type=LightType.Directional;daylight.color=new Color(1f,.94f,.84f);
            daylight.intensity=DaylightStrength;daylight.shadows=LightShadows.Soft;daylight.shadowStrength=.55f;
            daylight.shadowBias=.015f;daylight.shadowNormalBias=.06f;
            daylight.GetUniversalAdditionalLightData().usePipelineSettings=false;RenderSettings.sun=daylight;
            // Real ceiling/pendant sources supply local shape and contact shadows.
            // Trilight colours below supply the effective ambient bounce.
            Practical("Warm counter pendant",AnchorPosition("light_counter",new Vector3(1.12f,2.30f,-.9f)),new Color(1,.89f,.72f),PracticalStrengths[0],4.8f,new Vector3(.4f,.9f,-1.7f),true);
            Practical("Table reading pendant",AnchorPosition("light_table",new Vector3(-1.71f,2.30f,-.24f)),new Color(1,.95f,.86f),PracticalStrengths[1],4.2f,TicketPosition,true);
            Practical("Shelf ambient fill",AnchorPosition("light_shelf",new Vector3(2.2f,2.2f,-.4f)),new Color(.83f,.91f,1),PracticalStrengths[2],4,new Vector3(2.1f,1.1f,-.4f),false);
            Practical("Counter board wash",new Vector3(.45f,2.04f,-2.287f),new Color(1,.93f,.81f),PracticalStrengths[3],2f,new Vector3(.45f,1.6f,-2.5f),false);
            var probe=new GameObject("Shop material reflection");probe.transform.SetParent(transform,false);probe.transform.localPosition=new Vector3(-.4f,1.35f,-.2f);
            roomReflection=probe.AddComponent<ReflectionProbe>();roomReflection.mode=bakingReflection?ReflectionProbeMode.Baked:ReflectionProbeMode.Custom;
            roomReflection.hdr=true;
            roomReflection.refreshMode=ReflectionProbeRefreshMode.ViaScripting;roomReflection.timeSlicingMode=ReflectionProbeTimeSlicingMode.NoTimeSlicing;
            roomReflection.resolution=ReflectionFaceSize;roomReflection.size=new Vector3(6.4f,3.1f,5.6f);roomReflection.center=new Vector3(.4f,0,.2f);
            roomReflection.boxProjection=true;roomReflection.shadowDistance=12;roomReflection.nearClipPlane=.08f;roomReflection.farClipPlane=12;roomReflection.intensity=.85f;
            // Only authored room geometry enters reflections, never camera-attached HUD.
            roomReflection.cullingMask=1<<(bakingReflection?ReflectionBakeLayer:ReflectionGeometryLayer);roomReflection.clearFlags=ReflectionProbeClearFlags.SolidColor;
            BuildExteriorDepth();BuildTableContactShades();BuildFurnitureContactShades();SetNight(false);Physics.SyncTransforms();
        }
        void BuildTableContactShades()
        {
            var shader=Resources.Load<Shader>("G3/Shop/ContactShade");
            if(shader==null)throw new InvalidOperationException("Missing local contact presentation shader");
            var vertices=new List<Vector3>();var uv=new List<Vector2>();var indices=new List<int>();
            // Existing authored pads: top=.840, thickness=.022, felt top=.818.
            // The 6 mm outside rim is translucent, never a raised opaque backing.
            for(int i=1;i<=3;i++)
            {
                var p=AnchorPosition("tool_"+i,TicketPosition);p.y-=.02196f;int n=vertices.Count;const float h=.066f;
                vertices.AddRange(new[]{p+new Vector3(-h,0,-h),p+new Vector3(h,0,-h),p+new Vector3(h,0,h),p+new Vector3(-h,0,h)});
                uv.AddRange(new[]{Vector2.zero,Vector2.right,Vector2.one,Vector2.up});indices.AddRange(new[]{n,n+2,n+1,n,n+3,n+2});
            }
            tableContactMesh=new Mesh{name="Three authored pad contact footprints"};tableContactMesh.SetVertices(vertices);tableContactMesh.SetUVs(0,uv);tableContactMesh.SetTriangles(indices,0);tableContactMesh.RecalculateBounds();tableContactMesh.RecalculateNormals();
            var material=new Material(shader){name="Local pad contact shade"};material.SetColor("_Color",new Color(.025f,.04f,.03f,.28f));material.SetVector("_Inner",new Vector4(.12f/.132f,.12f/.132f,0,0));instantiatedMaterials.Add(material);
            var go=new GameObject("Subtle contact beneath authored tool pads");go.transform.SetParent(transform,false);go.layer=bakingReflection?ReflectionBakeLayer:ReflectionGeometryLayer;
            go.AddComponent<MeshFilter>().sharedMesh=tableContactMesh;var renderer=go.AddComponent<MeshRenderer>();renderer.sharedMaterial=material;
            renderer.shadowCastingMode=ShadowCastingMode.Off;renderer.receiveShadows=false;
        }
        void BuildFurnitureContactShades()
        {
            // The visible terrazzo is above the y=0 collision substrate. Read its
            // imported mesh bounds, in environment space, rather than the collider.
            // Fixed FBX 8c37ca30: all 90 Warm_Terrazzo meshes are floor tiles;
            // their measured top is .02250005 m. No extra floor renderer is made.
            var floor=art.GetComponentsInChildren<MeshFilter>().FirstOrDefault(f=>f.name=="Warm_Terrazzo"&&f.sharedMesh!=null);
            if(floor==null){Debug.LogWarning("Furniture contact skipped: imported terrazzo mesh missing");return;}
            var bounds=floor.sharedMesh.bounds;var matrix=transform.worldToLocalMatrix*floor.transform.localToWorldMatrix;
            float top=float.NegativeInfinity;
            for(int i=0;i<8;i++)
            {
                var corner=bounds.center+Vector3.Scale(bounds.extents,new Vector3((i&1)==0?-1:1,(i&2)==0?-1:1,(i&4)==0?-1:1));
                top=Mathf.Max(top,matrix.MultiplyPoint3x4(corner).y);
            }
            // A changed material grouping must be reviewed, never shade a guessed plane.
            if(float.IsNaN(top)||float.IsInfinity(top)||Mathf.Abs(top-.0225f)>.001f)
            {Debug.LogWarning("Furniture contact skipped: imported terrazzo height changed");return;}
            float y=top+.0015f;
            var shader=Resources.Load<Shader>("G3/Shop/ContactShade");
            if(shader==null)throw new InvalidOperationException("Missing local contact presentation shader");
            var vertices=new List<Vector3>();var uv=new List<Vector2>();var indices=new List<int>();
            // XZ footprints are measured at the actual tile top in the fixed FBX,
            // not the full-height decorative bounding boxes or interaction proxies.
            // Hollow rims leave no second dark slab under a cabinet; each corner
            // belongs to just one surface. Rim reaches 4.5 cm outside the footprint.
            AddFurnitureContactRim(vertices,uv,indices,new Vector3(.7f,y,-1.86f),new Vector2(2.5996f,.6796f));
            // Showcase rounded corners need >=3.515 mm inset at this height;
            // 5 mm hides the full-alpha inner edge with 1.485 mm clearance.
            AddFurnitureContactRim(vertices,uv,indices,new Vector3(2.13f,y,-.32f),new Vector2(.98f,2.05f),.005f);
            AddFurnitureContactRim(vertices,uv,indices,new Vector3(-2.19f,y,-2.25f),new Vector2(1.20202f,.56202f));
            // Four authored Desk_Tapered_Leg sections are .080127 m square here.
            // .134 m quads with _Inner=.6 place the fade at that section: ~2.7 cm rim.
            foreach(float x in new[]{-1.2338815f,-2.8161185f})foreach(float z in new[]{.55f,-.69f})
            {
                var p=new Vector3(x,y,z);int n=vertices.Count;const float h=.067f;
                vertices.AddRange(new[]{p+new Vector3(-h,0,-h),p+new Vector3(h,0,-h),p+new Vector3(h,0,h),p+new Vector3(-h,0,h)});
                uv.AddRange(new[]{Vector2.zero,Vector2.right,Vector2.one,Vector2.up});indices.AddRange(new[]{n,n+2,n+1,n,n+3,n+2});
            }
            furnitureContactMesh=new Mesh{name="Three cabinet rims and four leg contacts"};
            furnitureContactMesh.SetVertices(vertices);furnitureContactMesh.SetUVs(0,uv);furnitureContactMesh.SetTriangles(indices,0);
            furnitureContactMesh.RecalculateBounds();furnitureContactMesh.RecalculateNormals();
            // Separate owned material keeps the existing table-pad material/shader
            // settings intact. Low alpha complements existing real light shadows.
            var material=new Material(shader){name="Subtle furniture floor contact"};
            material.SetColor("_Color",new Color(.035f,.04f,.032f,.14f));material.SetVector("_Inner",new Vector4(.6f,.6f,0,0));instantiatedMaterials.Add(material);
            var go=new GameObject("Subtle contact beneath authored furniture");go.transform.SetParent(transform,false);go.layer=bakingReflection?ReflectionBakeLayer:ReflectionGeometryLayer;
            go.AddComponent<MeshFilter>().sharedMesh=furnitureContactMesh;var renderer=go.AddComponent<MeshRenderer>();renderer.sharedMaterial=material;
            renderer.shadowCastingMode=ShadowCastingMode.Off;renderer.receiveShadows=false;
            renderer.lightProbeUsage=LightProbeUsage.Off;renderer.reflectionProbeUsage=ReflectionProbeUsage.Off;
        }
        static void AddFurnitureContactRim(List<Vector3> vertices,List<Vector2> uv,List<int> indices,Vector3 center,Vector2 footprint,float innerInset=.002f)
        {
            int n=vertices.Count;var outer=footprint*.5f+Vector2.one*.045f;var inner=footprint*.5f-Vector2.one*innerInset;
            // Outer then inner loop; inner UV .2/.8 corresponds to _Inner=.6.
            // Four disjoint trapezoids share edges, so their alpha never stacks.
            foreach(var half in new[]{outer,inner})
                vertices.AddRange(new[]{center+new Vector3(-half.x,0,-half.y),center+new Vector3(half.x,0,-half.y),center+new Vector3(half.x,0,half.y),center+new Vector3(-half.x,0,half.y)});
            uv.AddRange(new[]{Vector2.zero,Vector2.right,Vector2.one,Vector2.up,new Vector2(.2f,.2f),new Vector2(.8f,.2f),new Vector2(.8f,.8f),new Vector2(.2f,.8f)});
            for(int i=0;i<4;i++){int j=(i+1)%4;indices.AddRange(new[]{n+i,n+4+j,n+j,n+i,n+4+i,n+4+j});}
        }
        // V19 presentation-only depth; no colliders, interaction targets or Update loop.
        void BuildExteriorDepth()
        {
            exteriorDay=Resources.Load<Texture2D>("G3/Shop/Exterior/Street-day");
            exteriorNight=Resources.Load<Texture2D>("G3/Shop/Exterior/Street-night");
            var shader=Resources.Load<Shader>("G3/Shop/Exterior/ExteriorBackdrop");
            if(exteriorDay==null||exteriorNight==null||shader==null)throw new InvalidOperationException("Missing v19 exterior day/night assets");
            int replacements=0;
            foreach(var renderer in art.GetComponentsInChildren<Renderer>())
            {
                var materials=renderer.sharedMaterials;bool changed=false;
                for(int i=0;i<materials.Length;i++)if(materials[i].name.StartsWith("StreetBlur",StringComparison.Ordinal))
                {
                    if(exteriorMaterial==null){exteriorMaterial=new Material(shader){name="V19 exterior day-night"};instantiatedMaterials.Add(exteriorMaterial);}
                    materials[i]=exteriorMaterial;changed=true;replacements++;
                }
                if(changed){renderer.sharedMaterials=materials;renderer.shadowCastingMode=ShadowCastingMode.Off;renderer.receiveShadows=false;}
            }
            if(replacements!=1)throw new InvalidOperationException("Expected one existing exterior backdrop; found "+replacements);
            var vertices=new List<Vector3>();var triangles=new List<int>();
            // Outside the existing glass at Z2.61, before the backdrop at Z3.8.
            AddExteriorBox(vertices,triangles,new Vector3(0,-.045f,3.25f),new Vector3(9.1f,.09f,1.26f));
            AddExteriorBox(vertices,triangles,new Vector3(-.405f,.021f,2.76f),new Vector3(1.13f,.042f,.13f));
            // Short storefront returns/awning occlude the finite card at grazing angles.
            AddExteriorBox(vertices,triangles,new Vector3(-3.75f,1.4f,3.175f),new Vector3(.14f,2.8f,1.953f),-50.194f);
            AddExteriorBox(vertices,triangles,new Vector3(3.75f,1.4f,3.175f),new Vector3(.14f,2.8f,1.953f),50.194f);
            AddExteriorBox(vertices,triangles,new Vector3(0,2.83f,3.25f),new Vector3(9.1f,.14f,1.26f));
            exteriorNearMesh=new Mesh{name="V19 static exterior sidewalk and threshold"};
            exteriorNearMesh.SetVertices(vertices);exteriorNearMesh.SetTriangles(triangles,0);exteriorNearMesh.RecalculateNormals();exteriorNearMesh.RecalculateBounds();
            var go=new GameObject("Exterior near-field sidewalk and threshold");go.transform.SetParent(transform,false);go.layer=bakingReflection?ReflectionBakeLayer:ReflectionGeometryLayer;
            go.AddComponent<MeshFilter>().sharedMesh=exteriorNearMesh;var r=go.AddComponent<MeshRenderer>();
            var stone=new Material(Shader.Find("Universal Render Pipeline/Lit")){name="V19 warm pavement"};stone.SetColor("_BaseColor",new Color(.39f,.36f,.30f));stone.SetFloat("_Smoothness",.13f);instantiatedMaterials.Add(stone);
            r.sharedMaterial=stone;r.shadowCastingMode=ShadowCastingMode.Off;r.receiveShadows=true;
        }
        static void AddExteriorBox(List<Vector3> vertices,List<int> triangles,Vector3 center,Vector3 size,float yaw=0)
        {
            // Separate vertices per face preserve stone's hard edges: 24 verts/12 triangles per box.
            Vector3[] p={new Vector3(-1,-1,-1),new Vector3(1,-1,-1),new Vector3(1,1,-1),new Vector3(-1,1,-1),new Vector3(-1,-1,1),new Vector3(1,-1,1),new Vector3(1,1,1),new Vector3(-1,1,1)};
            int[] faces={0,3,2,1,4,5,6,7,0,4,7,3,1,2,6,5,0,1,5,4,3,7,6,2};
            for(int face=0;face<6;face++){int n=vertices.Count;for(int j=0;j<4;j++)vertices.Add(center+Quaternion.Euler(0,yaw,0)*Vector3.Scale(p[faces[face*4+j]],size*.5f));triangles.AddRange(new[]{n,n+1,n+2,n,n+2,n+3});}
        }
        void Practical(string name,Vector3 p,Color color,float strength,float range,Vector3 target,bool shadow)
        {
            var go=new GameObject(name);go.transform.SetParent(transform,false);go.transform.localPosition=p;go.transform.LookAt(target);
            var light=go.AddComponent<Light>();light.type=LightType.Spot;light.spotAngle=115;light.innerSpotAngle=70;
            light.color=color;light.intensity=strength;light.range=range;light.shadows=shadow?LightShadows.Soft:LightShadows.None;
            light.shadowStrength=.6f;light.shadowBias=.008f;light.shadowNormalBias=.025f;
            var additional=light.GetUniversalAdditionalLightData();additional.usePipelineSettings=false;
            // Bound only the newly shadowed counter lamp's mobile filtering cost.
            // This is a production tradeoff candidate, not a long-frame root-cause claim.
            if(name=="Warm counter pendant"&&shadow)additional.softShadowQuality=SoftShadowQuality.Low;
            practicals.Add(light);
        }
        void LoadBakedReflections()
        {
            const string root="G3/Shop/Reflections/";
            var text=Resources.Load<TextAsset>(root+"reflection-receipt");
            if(text==null||System.Text.Encoding.UTF8.GetByteCount(text.text)>16384)throw new InvalidOperationException("Missing or oversized authored shop reflection receipt; run the Editor bake");
            var receipt=JsonUtility.FromJson<ReflectionReceipt>(text.text);
            if(receipt==null||receipt.schemaVersion!=1||receipt.status!="COMPLETE_BAKED_STATIC_REFLECTIONS"||receipt.recipe!=ReflectionRecipe||receipt.colorSpace!=QualitySettings.activeColorSpace.ToString()||!IsDigest(receipt.sourceDigest))throw new InvalidOperationException("Invalid authored shop reflection recipe");
            dayReflection=Resources.Load<Cubemap>(root+"Day");nightReflection=Resources.Load<Cubemap>(root+"Night");
            RequireReflection(dayReflection,receipt.day,"Day.exr");RequireReflection(nightReflection,receipt.night,"Night.exr");
        }
        public static void RequireReflection(Cubemap cube,ReflectionTexture info,string filename)
        {
            if(cube==null||info==null||info.file!=filename||info.faceSize!=ReflectionFaceSize||info.mipCount!=ReflectionMipCount||info.format!="RGBAHalf"||info.shape!="Cube"||!info.linear||!info.specular||!IsDigest(info.sha256)||!IsDigest(info.metaSha256)||info.bytes<=0||info.bytes>8388608||info.metaBytes<=0||info.metaBytes>16384||info.pixelSampleCount!=98304||float.IsNaN(info.maxChannelRange)||float.IsInfinity(info.maxChannelRange)||info.maxChannelRange<=.01f||info.maxChannelRange>65504)
                throw new InvalidOperationException("Missing or invalid authored shop reflection "+filename);
            if(cube.width!=ReflectionFaceSize||cube.height!=ReflectionFaceSize||cube.mipmapCount!=ReflectionMipCount||cube.dimension!=TextureDimension.Cube||cube.format!=TextureFormat.RGBAHalf)
                throw new InvalidOperationException("Shop reflection dimensions, mips or HDR format differ from recipe");
        }
        static bool IsDigest(string value)=>value!=null&&value.Length==64&&value.All(c=>(c>='0'&&c<='9')||(c>='a'&&c<='f'));
        public void SetNight(bool value)
        {
            if(night==value)return;night=value;
            // Raise only the day sun: the real front opening now reaches the walkway floor.
            // Preserve azimuth, source energy, shadow strength, and the night recipe.
            daylight.transform.rotation=value?Quaternion.Euler(25,190,0):Quaternion.Euler(25,185,0);
            daylight.shadowStrength=value?.55f:.65f;
            daylight.intensity=value ? .16f : DaylightStrength;daylight.color=value?new Color(.49f,.62f,.91f):new Color(1,.94f,.84f);
            RenderSettings.ambientMode=AmbientMode.Trilight;
            RenderSettings.ambientSkyColor=value?new Color(.30f,.34f,.43f):new Color(.612f,.666f,.72f);
            RenderSettings.ambientEquatorColor=value?new Color(.35f,.31f,.27f):new Color(.522f,.513f,.459f);
            RenderSettings.ambientGroundColor=value?new Color(.20f,.18f,.17f):new Color(.306f,.279f,.234f);
            // Trilight derives the effective ambient probe from the three colours above.
            // Run37's manual SH-only reduction produced no visible frame improvement.
            // Retain the manual assignment unchanged; tune Trilight through its colours.
            var bounce=new SphericalHarmonicsL2();bounce.AddAmbientLight(value?new Color(.20f,.21f,.24f):new Color(.252f,.276f,.258f));
            bounce.AddDirectionalLight(Vector3.up,value?new Color(.16f,.13f,.10f):new Color(.20f,.22f,.25f),.7f);
            RenderSettings.ambientProbe=bounce;RenderSettings.reflectionIntensity=value ? .7f : 1;
            // The reading pendant is the baseline, independent of purchased tools.
            // Night previously reduced it to 1.30 while the daylight was also removed.
            for(int i=0;i<practicals.Count;i++)practicals[i].intensity=i==1?1.6f:PracticalStrengths[i]*(value?1.04f:1);
            roomReflection.backgroundColor=value?new Color(.08f,.10f,.15f):new Color(.40f,.45f,.49f);
            if(!bakingReflection)roomReflection.customBakedTexture=value?nightReflection:dayReflection;
            if(exteriorMaterial!=null){exteriorMaterial.SetTexture("_BaseMap",value?exteriorNight:exteriorDay);exteriorMaterial.SetFloat("_Exposure",value?.72f:1f);}
            SetWindowColors(value);
        }
        void SetWindowColors(bool value)
        {
            if(art==null)return;
            foreach(var renderer in art.GetComponentsInChildren<Renderer>())
            {
                // Reading sharedMaterials does not implicitly instantiate assets
                // while the same environment is built by the offline Editor baker.
                // Only slots whose colour actually changes get an owned copy.
                var materials=renderer.sharedMaterials;bool changed=false;
                for(int i=0;i<materials.Length;i++)
                {
                    var material=materials[i];
                    if(material==null||material==exteriorMaterial||
                        !(material.name.StartsWith("Window")||material.name.StartsWith("StreetBlur"))||
                        !material.HasProperty("_BaseColor"))continue;
                    if(!authoredWindowColors.TryGetValue(material,out var authored))
                    {
                        authored=material.GetColor("_BaseColor");
                        material=new Material(material){name=material.name+" (Instance)"};
                        instantiatedMaterials.Add(material);authoredWindowColors.Add(material,authored);
                        materials[i]=material;changed=true;
                    }
                    material.SetColor("_BaseColor",authored*(value?new Color(.06f,.12f,.24f):Color.white));
                }
                // Reassign the array only after a slot was replaced. Repeated
                // day/night transitions keep the same copies and authored colours.
                if(changed)renderer.sharedMaterials=materials;
            }
        }
        public void Sync(RunState state)=>SetNight(state.Phase==DayPhase.NIGHT_BILL||state.Phase==DayPhase.DAY_COMPLETE||state.Phase==DayPhase.RUN_FAILED);
        static void ReleaseOwned(UnityEngine.Object value)
        {
#if UNITY_EDITOR
            if(!Application.isPlaying){DestroyImmediate(value);return;}
#endif
            Destroy(value);
        }
        void OnDestroy()
        {
            foreach(var material in instantiatedMaterials)if(material!=null)ReleaseOwned(material);
            if(exteriorNearMesh!=null)ReleaseOwned(exteriorNearMesh);
            if(tableContactMesh!=null)ReleaseOwned(tableContactMesh);
            if(furnitureContactMesh!=null)ReleaseOwned(furnitureContactMesh);
            if(runtimePipeline!=null){if(QualitySettings.renderPipeline==runtimePipeline)QualitySettings.renderPipeline=priorPipeline;ReleaseOwned(runtimePipeline);}
            // A disabled menu can outlive the newer gameplay environment. It must
            // never restore its old snapshot over another environment's lighting.
            if(capturedLighting&&daylight!=null&&RenderSettings.sun==daylight)
            {RenderSettings.ambientMode=previousAmbientMode;RenderSettings.ambientSkyColor=previousSky;RenderSettings.ambientEquatorColor=previousEquator;RenderSettings.ambientGroundColor=previousGround;RenderSettings.ambientLight=previousAmbient;RenderSettings.ambientProbe=previousAmbientProbe;RenderSettings.sun=previousSun;RenderSettings.reflectionIntensity=previousReflectionIntensity;}
        }
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using Unity.Collections;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    public static partial class JourneySceneAuthoring
    {
        // New producer only. These are scene-local additions, never edits to the retained RV/source assets.
        internal const string PolishSource = "Assets/DesertRV/Art/EnvironmentV4";
        internal const string PolishGenerated = Folder + "/EnvironmentV4";
        static readonly Dictionary<string, Material> polishMaterials = new Dictionary<string, Material>();
        static readonly string[] polishMaterialNames = { "Sand", "TrackSand", "Sheet", "Asphalt", "Concrete", "Plaster", "Oxide", "Steel", "Ivory", "Ochre", "Rubber", "Oil", "Lamp", "Factory" };

        // ENVIRONMENT_V4_CONTRACT_BEGIN
        static string[] PolishExpectedMeshNames(int region)
        {
            switch(region)
            {
                case 1: return new[]{"CanopyBase-Concrete","CanopyUpper-Ivory","CanopyUpper-Lamp","CanopyUpper-Oxide","CanopyUpper-Steel","Forecourt-Concrete","ForecourtDrain-Steel","ForecourtDust-Sand","ForecourtWear-Oil","Ground-Sand","GroundWear-Oil","PullOff-TrackSand","PumpDetails-Ochre","PumpDetails-Steel","ReliefEast-Sand","ReliefWest-Sand","Road-Asphalt","Shoulder-Sand","StationBack-Concrete","StationBack-Ivory","StationBack-Oxide","StationBack-Steel","StationFascia-Oxide","StationFuel-Concrete","StationFuel-Ivory","StationFuel-Oxide","StationFuel-Steel","StationRoof-Ivory","StationRoof-Rubber","StationRoof-Steel","StationRoofBase-Concrete","StationServiceBase-Concrete","StationWallLeft-Plaster","StationWallRear-Plaster","StationWallRight-Plaster"};
                case 2: return new[]{"Container0-Sheet","Container1-Sheet","Container2-Sheet","Ground-Sand","GroundWear-Oil","PullOff-TrackSand","ReliefEast-Sand","ReliefWest-Sand","Road-Asphalt","ScrapStacks-Oxide","ScrapStacks-Steel","Shoulder-Sand","YardGroundEast-Concrete","YardGroundWest-Concrete","YardPipeStore-Oxide","YardPipeStore-Steel","YardRearEast-Concrete","YardRearEast-Ivory","YardRearEast-Steel","YardRearWest-Concrete","YardRearWest-Oxide","YardRearWest-Steel","YardWorkshop-Lamp","YardWorkshop-Sheet","YardWorkshop-Steel"};
                case 3: return new[]{"BeaconGroundEast-Concrete","BeaconGroundWest-Concrete","Ground-Sand","GroundWear-Oil","PullOff-TrackSand","RelayBatteries-Ivory","RelayBatteries-Steel","RelayCanopy-Lamp","RelayCanopy-Sheet","RelayCanopy-Steel","RelayHouse-Concrete","RelayHouse-Ivory","RelayHouse-Steel","ReliefEast-Sand","ReliefWest-Sand","Road-Asphalt","Shoulder-Sand","TowerFixtures-Lamp","TowerFixtures-Steel","TowerLadder-Ivory","TowerLadder-Steel","TowerUpper-Ivory","TowerUpper-Steel"};
                default: throw new ArgumentOutOfRangeException(nameof(region));
            }
        }
        // ENVIRONMENT_V4_CONTRACT_END
        static void AuthorEnvironmentPolish(Scene source, RegionBinding region, JourneyMotor motor)
        {
            Directory.CreateDirectory(PolishGenerated); AssetDatabase.Refresh(); polishMaterials.Clear();
            // Finite material inventory, shared by all regions. No per-object material instantiation.
            foreach (string name in polishMaterialNames) PolishMaterial(name);
            var p = new PolishAuthor(region);
            RefineGround(p, region);
            if (region.region == 1) RefineStation(p, source, region);
            else if (region.region == 2) RefineScrapyard(p, region);
            else RefineBeacon(p, region);
            p.Save();
            WritePolishReceipt(region);
        }

        static Material PolishMaterial(string kind)
        {
            if (polishMaterials.TryGetValue(kind, out var cached) && cached) return cached;
            if (!polishMaterialNames.Contains(kind)) throw new InvalidOperationException("Unregistered EnvironmentV4 material: " + kind);
            string path = PolishGenerated + "/Surface-" + kind + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!m)
            {
                var shader = Shader.Find("Universal Render Pipeline/Lit");
                if (!shader || !shader.isSupported) throw new InvalidOperationException("EnvironmentV4 requires supported URP Lit.");
                m = new Material(shader) { name = "EnvironmentV4 " + kind, enableInstancing = true };
                string tile = null; Color tint = Color.white; float smooth = .19f, metal = 0, normal = .35f;
                switch (kind)
                {
                    case "Sand": tile = "sand_03"; tint = new Color(1.75f, 1.52f, 1.16f); normal = .19f; break;
                    case "TrackSand": tile = "aerial_sand"; tint = new Color(1.18f, 1.08f, .91f); normal = .27f; break;
                    case "Sheet": tile = "corrugated_iron_03"; tint = new Color(.90f, .88f, .80f); normal = .22f; break;
                    case "Asphalt": tile = "asphalt_02"; tint = new Color(.76f, .77f, .76f); normal = .3f; break;
                    case "Concrete": tile = "concrete_floor_worn_001"; tint = new Color(1.42f, 1.36f, 1.20f); normal = .3f; break;
                    case "Plaster": tile = "painted_plaster_wall"; tint = new Color(1.06f, .97f, .78f); normal = .22f; break;
                    case "Oxide": tile = "rusty_metal_02"; tint = new Color(.65f, .30f, .18f); normal = .32f; break;
                    case "Steel": tint = new Color(.22f, .275f, .28f); smooth = .32f; metal = .55f; break;
                    case "Ivory": tile = "rusty_metal_02"; tint = new Color(.78f, .75f, .65f); normal = .19f; break;
                    case "Ochre": tile = "rusty_metal_02"; tint = new Color(.91f, .57f, .16f); normal = .19f; break;
                    case "Rubber": tint = new Color(.07f, .082f, .08f); smooth = .12f; break;
                    case "Oil": tint = new Color(.20f, .17f, .115f); smooth = .12f; break;
                    case "Lamp": tint = new Color(1, .72f, .37f); smooth = .36f; break;
                    case "Factory": tint = new Color(.75f, .70f, .60f); smooth = .21f; metal = .25f; break;
                }
                m.SetColor("_BaseColor", tint); m.SetFloat("_Smoothness", smooth); m.SetFloat("_Metallic", metal);
                if (tile != null)
                {
                    m.SetTexture("_BaseMap", RequiredPolishTexture(tile + "_diff_1k.jpg"));
                    m.SetTexture("_BumpMap", RequiredPolishTexture(tile + "_nor_gl_1k.jpg"));
                    m.SetTexture("_MetallicGlossMap", RequiredPolishTexture(tile + "_metallic_smoothness_1k.png"));
                    m.SetFloat("_BumpScale", normal); m.SetFloat("_Smoothness", .70f);
                    m.EnableKeyword("_NORMALMAP"); m.EnableKeyword("_METALLICSPECGLOSSMAP");
                }
                if (kind == "Factory") m.SetTexture("_BaseMap", RequiredPolishTexture("Factory/colormap.png"));
                if (kind == "Lamp") { m.EnableKeyword("_EMISSION"); m.SetColor("_EmissionColor", new Color(2.8f, 1.6f, .55f)); }
                AssetDatabase.CreateAsset(m, path);
            }
            polishMaterials[kind] = m; return m;
        }
        static Texture2D RequiredPolishTexture(string name)
        {
            var t = AssetDatabase.LoadAssetAtPath<Texture2D>(PolishSource + "/" + name);
            if (!t) throw new InvalidOperationException("Verified EnvironmentV4 texture missing: " + name);
            return t;
        }
        static float TextureMetres(string material) => material == "TrackSand" ? 15 : material == "Sand" || material == "Plaster" || material == "Sheet" ? 2 : material == "Asphalt" || material == "Concrete" ? 3 : 1;

        static void RefineGround(PolishAuthor p, RegionBinding b)
        {
            // Replace only generated surface renderers. Keep the existing 230 x 310 m ground collider and road collider.
            var ground = b.transform.Find("Route foundation").GetComponent<Renderer>(); ground.enabled = false;
            foreach (var r in b.GetComponentsInChildren<Renderer>(true))
            {
                string n = r.name;
                if (n == "Road surface" || n == "Far road continuation" || n == "Road behind arrival" || n.StartsWith("Road shoulder patch ") || n.StartsWith("Roadside sand lobe ")) r.enabled = false;
            }
            // Geometric edges vary; the playable road core stays completely clear and flat.
            p.Quad("Ground", "Sand", new Vector3(-1200, -.039f, -1115), new Vector3(-1200, -.039f, 1285), new Vector3(1200, -.039f, 1285), new Vector3(1200, -.039f, -1115));
            for (int n = 0; n < 88; n++)
            {
                float z0 = -600 + n * 14, z1 = z0 + 14;
                float l0 = -4.03f - .10f * Mathf.Sin(n * 1.77f), l1 = -4.03f - .10f * Mathf.Sin((n + 1) * 1.77f);
                float r0 = 4.03f + .10f * Mathf.Cos(n * 1.37f), r1 = 4.03f + .10f * Mathf.Cos((n + 1) * 1.37f);
                p.Quad("Road", "Asphalt", new Vector3(l0,.038f,z0),new Vector3(l1,.038f,z1),new Vector3(r1,.038f,z1),new Vector3(r0,.038f,z0));
            }
            // Shallow sand ingress in broken ribbons, not repeated oval blobs. No raised driving obstacles.
            foreach (float side in new[] { -1f, 1f })
                for (int i = 0; i < 26; i++)
                {
                    float z = -14 + i * 3.6f;
                    float x = side * (4.05f + .05f * Mathf.Sin(i * 2.1f));
                    float ingress = .09f + (i % 5) * .035f;
                    var a = new Vector3(x, .043f, z); var c = new Vector3(x + side * (.48f + i % 3 * .10f), .008f, z + 3.5f);
                    var inner = new Vector3(x - side * ingress, .045f, z + 1.5f); var outer = new Vector3(c.x, .008f, z);
                    if (side > 0) p.Quad("Shoulder", "Sand", a, inner, c, outer);
                    else p.Quad("Shoulder", "Sand", outer, c, inner, a);
                }
            // Low ground relief provides a layered horizon; every berm starts outside x +/- 25 m.
            // Collision is the authored triangle surface, not a cube approximation or decoration blocker.
            foreach (float side in new[] { -1f, 1f })
            {
                string group = side < 0 ? "ReliefWest" : "ReliefEast";
                for (int i = 0; i < 4; i++)
                    p.Berm(group, "Sand", new Vector3(side * (39 + i % 2 * 7), -.047f, 10 + i * 32), new Vector2(13 + i * 2, 25), 1.15f + i % 3 * .48f, i + b.region * 7, true);
                for (int i = 0; i < 3; i++)
                    p.Berm(group, "Sand", new Vector3(side * (83 + i * 6), -.05f, 54 + i * 65), new Vector2(28, 47), 5.5f + i * 2.1f, i + 33, true);
            }
            // Aerial capture contains tire marks; confine it to realistic pull-off strips, never the empty desert.
            foreach(float side in new[]{-1f,1f})
                p.FlatPatch("PullOff","TrackSand",new Vector3(side*7.5f,.001f,17),new Vector2(2.0f,7.0f),31+(int)side);
            // Small worn repair patches break the single-road texture scale without narrowing travel.
            for (int i = 0; i < 5; i++)
            {
                float z = 13 + i * 10;
                p.FlatPatch("GroundWear", "Oil", new Vector3(i % 2 == 0 ? -2.1f : 1.8f, .048f, z), new Vector2(.42f, 1.2f), 11 + i);
            }
        }

        static void RefineStation(PolishAuthor p, Scene source, RegionBinding b)
        {
            var geom = SourceGeometry(source);
            Bounds apron = geom.Single(t => t.name == "GEO-station_apron").GetComponent<Renderer>().bounds;
            Bounds roof = geom.Single(t => t.name == "GEO-roof_slab").GetComponent<Renderer>().bounds;
            Bounds canopy = geom.Single(t => t.name == "GEO-pump_canopy").GetComponent<Renderer>().bounds;
            // Assignment affects scene instances only. Source FBX/materials and every retained RV renderer remain untouched.
            foreach (var t in geom)
            {
                var r = t.GetComponent<Renderer>(); if (!r) continue; string n = t.name;
                if (n == "GEO-station_apron") { r.enabled = false; continue; }
                if (n == "GEO-garage_left_wall") p.SourceMesh("StationWallLeft", "Plaster", r);
                if (n == "GEO-garage_right_wall") p.SourceMesh("StationWallRight", "Plaster", r);
                if (n == "GEO-garage_rear_wall") p.SourceMesh("StationWallRear", "Plaster", r);
                if (n.StartsWith("GEO-roof_weathered_patch")) r.enabled = false;
                if (n == "GEO-roof_slab") p.SourceMesh("StationRoofBase", "Concrete", r);
                if (n == "GEO-pump_canopy") p.SourceMesh("CanopyBase", "Concrete", r);
                if (n.Contains("fascia")) p.SourceMesh("StationFascia", "Oxide", r);
            }
            // Slabs have metre-scale UVs, filled expansion joints and a chipped perimeter.
            for (float x = apron.min.x; x < apron.max.x - .01f; x += 2.75f)
                for (float z = apron.min.z; z < apron.max.z - .01f; z += 2.75f)
                {
                    float sx = Mathf.Min(2.75f, apron.max.x - x), sz = Mathf.Min(2.75f, apron.max.z - z);
                    p.Box("Forecourt", "Concrete", new Vector3(x + sx*.5f, .006f, z + sz*.5f), new Vector3(sx-.022f,.09f,sz-.022f));
                }
            // Forecourt-to-sand transition stays below the 18 cm clearance threshold.
            for (int i = 0; i < 9; i++)
            {
                float z = apron.min.z + .9f + i * (apron.size.z - 1.8f) / 8;
                p.FlatPatch("ForecourtDust", "Sand", new Vector3(apron.max.x - .32f, .056f, z), new Vector2(.5f, .45f + i % 3 * .25f), i+41);
            }
            for (int i = 0; i < 2; i++)
            {
                var pump = geom.Single(t => t.name == (i == 0 ? "GEO-pump_island" : "GEO-pump_island.001")).GetComponent<Renderer>().bounds;
                p.FlatPatch("ForecourtWear", "Oil", new Vector3(pump.center.x + 1.2f,.058f,pump.center.z), new Vector2(.58f,1.1f), 73+i);
                // Discrete pump island guards are grouped beside the existing island, never the road.
                for (int k = -1; k <= 1; k += 2)
                {
                    Vector3 at = new Vector3(pump.center.x, .08f, pump.center.z + k * (pump.extents.z + .32f));
                    p.Cylinder("PumpDetails", "Ochre", at, at+Vector3.up*.70f, .065f, 10);
                    p.Cylinder("PumpDetails", "Steel", at+Vector3.up*.46f, at+Vector3.up*.58f, .067f, 10);
                }
            }
            // Tapered parapet cap, a rooftop cooling plant and pipe runs read in the actual driving camera.
            Vector3 cooler = new Vector3(roof.center.x, roof.max.y+.43f, roof.center.z + roof.size.z*.23f);
            p.BevelBox("StationRoof", "Ivory", cooler, new Vector3(2.2f,.86f,1.6f), .075f);
            p.Box("StationRoof", "Steel", cooler+new Vector3(0,-.28f,0), new Vector3(2.28f,.16f,1.67f));
            for (int j=0;j<9;j++) p.Box("StationRoof", "Steel", cooler+new Vector3(1.105f,-.17f+j*.046f,0),new Vector3(.025f,.018f,1.31f));
            for (int j=0;j<2;j++)
            {
                Vector3 fan=cooler+new Vector3(-.5f+j, .45f, 0);
                p.Cylinder("StationRoof","Steel",fan,fan+Vector3.up*.065f,.40f,24);
                p.Cylinder("StationRoof","Rubber",fan+Vector3.up*.067f,fan+Vector3.up*.076f,.325f,24);
                for(int k=0;k<6;k++)p.Beam("StationRoof","Ivory",fan+Vector3.up*.084f,fan+Quaternion.Euler(0,k*60,0)*Vector3.right*.32f+Vector3.up*.084f,.025f,.025f);
            }
            Vector3 pipeA = cooler + new Vector3(-1.12f,-.21f,0), pipeB = new Vector3(roof.min.x+.6f,cooler.y-.21f,roof.center.z);
            p.Cylinder("StationRoof","Steel",pipeA,pipeB,.07f,12);
            p.Cylinder("StationRoof","Steel",pipeB,new Vector3(pipeB.x,.22f,pipeB.z),.07f,12);
            // A readable framed fascia and physically supported canopy lights, with enough underside structure at eye level.
            float front = canopy.max.x + .025f;
            p.Box("CanopyUpper","Oxide",new Vector3(front,canopy.max.y+.15f,canopy.center.z),new Vector3(.14f,.47f,canopy.size.z+.15f));
            p.Box("CanopyUpper","Ivory",new Vector3(front+.075f,canopy.max.y+.15f,canopy.center.z),new Vector3(.015f,.19f,canopy.size.z-.55f));
            for(int j=0;j<4;j++)
            {
                float z=canopy.min.z+.35f+j*(canopy.size.z-.7f)/3;
                p.Box("CanopyUpper","Steel",new Vector3(canopy.center.x,canopy.min.y-.08f,z),new Vector3(canopy.size.x-.1f,.14f,.09f));
            }
            foreach(float dz in new[]{-1.25f,1.25f})
            {
                Vector3 at=new Vector3(canopy.center.x,canopy.min.y-.14f,canopy.center.z+dz);
                p.BevelBox("CanopyUpper","Steel",at,new Vector3(1.05f,.12f,.28f),.02f);
                p.Box("CanopyUpper","Lamp",at+Vector3.down*.07f,new Vector3(.87f,.025f,.18f));
                PolishSpot(b.transform,"Station shielded canopy light",at+Vector3.down*.08f,1.0f,7,85);
            }
            // Drain and rear service approach are anchored to the real building, not guessed world coordinates.
            float drainX=Mathf.Min(apron.max.x-.5f, -5.1f);
            for(int j=0;j<24;j++)p.Box("ForecourtDrain","Steel",new Vector3(drainX,.059f,apron.min.z+.4f+j*.21f),new Vector3(.45f,.012f,.045f));
            Vector3 service=new Vector3(roof.min.x-2.15f,0,roof.center.z);
            p.Box("StationServiceBase","Concrete",service+new Vector3(0,.04f,0),new Vector3(3.2f,.16f,5.2f));
            PlaceFactory(b,"pipe-large-valve",service+new Vector3(-.5f,.14f,-1.2f),new Vector3(1.4f,1.4f,1.4f),Quaternion.Euler(0,90,0));
            PlaceFactory(b,"machine-bed",service+new Vector3(.15f,.14f,1.2f),new Vector3(1.7f,1.35f,1.5f),Quaternion.identity);
            // Visible from both normal driving and dismount: a paired roadside fuel installation.
            // The closest tank stays 8.65 m from the road centre, well clear of the 8.6 m corridor.
            for(int i=0;i<2;i++)
            {
                float x=9.55f+i*2.2f;Vector3 from=new Vector3(x,1.05f,7),to=new Vector3(x,1.05f,11.5f);
                p.Cylinder("StationFuel","Ivory",from,to,.82f,24);
                foreach(float z in new[]{7.6f,10.8f})
                {
                    p.Cylinder("StationFuel","Steel",new Vector3(x,1.05f,z-.055f),new Vector3(x,1.05f,z+.055f),.835f,24);
                    p.Box("StationFuel","Concrete",new Vector3(x,.22f,z),new Vector3(1.35f,.44f,.40f));
                }
                p.Cylinder("StationFuel","Oxide",new Vector3(x,1.82f,8.1f),new Vector3(x,2.14f,8.1f),.105f,12);
                p.Cylinder("StationFuel","Steel",new Vector3(x,.56f,6.9f),new Vector3(x,.56f,6.2f),.06f,12);
            }
            p.EnableCollision("StationFuel","Ivory","Concrete");
            // Back-of-site shade structure: broad form with open approach and a stepped, non-box silhouette.
            Vector3 shade = new Vector3(roof.min.x-3.5f,0,roof.max.z+3.8f);
            p.Shed("StationBack",shade,new Vector3(6,3.2f,4.5f),"Oxide");
            for(int i=0;i<4;i++)
            {
                Vector3 at=shade+new Vector3(-1.9f+i*1.15f,.13f,1.3f);
                p.BevelBox("StationBack","Ivory",at+Vector3.up*(.48f+i%2*.21f),new Vector3(.92f,.95f+i%2*.42f,1.1f),.05f);
                p.Box("StationBack","Steel",at+new Vector3(.47f,.6f,0),new Vector3(.03f,.08f,.74f));
            }
        }

        static void RefineScrapyard(PolishAuthor p, RegionBinding b)
        {
            // Suppress overly bright repeated ribs in the old candidate, retain physical container walls.
            int containerIndex=0;
            foreach(var r in b.GetComponentsInChildren<Renderer>(true))
            {
                if(r.name=="Container corrugation")r.enabled=false;
                if(r.name=="Salvage container body")p.SourceMesh("Container"+(containerIndex++),"Sheet",r);
                if(r.name=="Service corrugated roof")r.enabled=false;
                if(r.name=="Workshop dismantling table")r.enabled=false;
            }
            // Distinct left sorting court and right powered workshop: a broad worn hardstand establishes context.
            p.Box("YardGroundWest","Concrete",new Vector3(-12,.015f,32),new Vector3(14,.09f,42));
            p.Box("YardGroundEast","Concrete",new Vector3(13,.015f,30),new Vector3(15,.09f,39));
            for(int row=0;row<3;row++)
                for(int i=0;i<6;i++)
                {
                    Vector3 at=new Vector3(-16+row*.45f,.2f+row*.48f,15+i*1.9f);
                    p.Beam("ScrapStacks","Oxide",at,at+new Vector3(1.8f,.17f+i%2*.12f,1.1f),.30f,.23f);
                    p.Beam("ScrapStacks","Steel",at+new Vector3(.15f,.24f,.3f),at+new Vector3(1.3f,.35f,1.4f),.14f,.18f);
                }
            // A serrated corrugated roof is generated as one mesh per material, not dozens of cube renderers.
            p.CorrugatedPanel("YardWorkshop","Sheet",new Vector3(11,3.58f,28),new Vector3(8.6f,.10f,8.6f),.16f);
            foreach(float x in new[]{7.3f,14.7f})p.Beam("YardWorkshop","Steel",new Vector3(x,3.35f,24),new Vector3(x,3.35f,32),.14f,.17f);
            // Existing power and coil approach corridors at z=23 and z=30 remain untouched.
            PlaceFactory(b,"machine-bed",new Vector3(12,.10f,26.2f),new Vector3(2.3f,1.5f,1.8f),Quaternion.Euler(0,180,0));
            PlaceFactory(b,"pipe-large-valve",new Vector3(15,.10f,29.5f),new Vector3(1.8f,1.8f,1.8f),Quaternion.Euler(0,90,0));
            PlaceFactory(b,"hopper-square",new Vector3(-15,.10f,37),new Vector3(3.1f,3.9f,3.1f),Quaternion.identity);
            PlaceFactory(b,"crane-magnet",new Vector3(-11,3.2f,38),new Vector3(1.2f,1.3f,1.2f),Quaternion.identity);
            PlaceFactory(b,"catwalk-stairs",new Vector3(18,.1f,41),new Vector3(2.5f,2.6f,3.6f),Quaternion.Euler(0,180,0));
            PlaceFactory(b,"catwalk-straight",new Vector3(17.3f,2.6f,38),new Vector3(1.6f,1.1f,4.0f),Quaternion.identity);
            for(int i=0;i<3;i++)
            {
                Vector3 at=new Vector3(16,.1f,14+i*1.45f);
                p.Cylinder("YardPipeStore","Steel",at,at+Vector3.right*3.2f,.22f,14);
                p.Cylinder("YardPipeStore","Oxide",at+Vector3.up*.47f,at+Vector3.right*3.2f+Vector3.up*.47f,.19f,14);
            }
            // Open sheds close the back of the yard, making a navigable space rather than isolated props.
            p.Shed("YardRearWest",new Vector3(-12,0,49),new Vector3(9,4.0f,6),"Oxide");
            p.Shed("YardRearEast",new Vector3(14,0,49),new Vector3(9,3.5f,5),"Ivory");
            p.Box("YardWorkshop","Steel",new Vector3(11,3.2f,26),new Vector3(1.35f,.13f,.3f));
            p.Box("YardWorkshop","Lamp",new Vector3(11,3.12f,26),new Vector3(1.15f,.035f,.2f));
            PolishSpot(b.transform,"Yard overhead task luminaire",new Vector3(11,3.08f,26),2.1f,11,100);
        }

        static void RefineBeacon(PolishAuthor p, RegionBinding b)
        {
            // Cream concrete, blue steel and warm task pools provide a distinct night compound identity.
            foreach(var r in b.GetComponentsInChildren<Renderer>(true))
            {
                if(r.name=="Relay shelter rear wall")r.gameObject.SetActive(false);
                if(r.name=="Service corrugated roof")r.enabled=false;
            }
            p.Box("BeaconGroundWest","Concrete",new Vector3(-11,.012f,33),new Vector3(9,.09f,12));
            p.Box("BeaconGroundEast","Concrete",new Vector3(12,.012f,29),new Vector3(14,.09f,17));
            // A windscreen perimeter and two shallow equipment alcoves; front/road and interaction paths are open.
            p.Shed("RelayHouse",new Vector3(14,0,36),new Vector3(8.5f,3.7f,5),"Ivory");
            p.CorrugatedPanel("RelayCanopy","Sheet",new Vector3(12,3.73f,31),new Vector3(7.5f,.1f,8.5f),.17f);
            for(int i=0;i<3;i++)
            {
                float z=26+i*2.65f;
                p.BevelBox("RelayBatteries","Ivory",new Vector3(17,1.0f,z),new Vector3(1.6f,2,1.85f),.07f);
                p.Box("RelayBatteries","Steel",new Vector3(16.18f,1.0f,z),new Vector3(.035f,1.65f,1.5f));
                for(int j=0;j<6;j++)p.Box("RelayBatteries","Ivory",new Vector3(16.15f,.5f+j*.13f,z),new Vector3(.02f,.027f,1.22f));
            }
            PlaceFactory(b,"machine-bed",new Vector3(11.5f,.10f,36.5f),new Vector3(2.7f,1.65f,1.9f),Quaternion.identity);
            PlaceFactory(b,"pipe-large-bend",new Vector3(18,.12f,32),new Vector3(1.25f,1.5f,1.25f),Quaternion.Euler(0,90,0));
            // Tower service platform, ladder and enclosed lantern frame read from the driver's approach.
            for(int level=0;level<2;level++)
            {
                float y=4.1f+level*4.2f;
                p.Box("TowerUpper","Steel",new Vector3(-11,y,33),new Vector3(2.6f,.12f,2.6f));
                foreach(float dx in new[]{-1.27f,1.27f})
                {
                    p.Cylinder("TowerUpper","Ivory",new Vector3(-11+dx,y,31.73f),new Vector3(-11+dx,y+.95f,31.73f),.035f,8);
                    p.Cylinder("TowerUpper","Ivory",new Vector3(-11+dx,y+.95f,31.73f),new Vector3(-11+dx,y+.95f,34.27f),.027f,8);
                }
            }
            foreach(float dx in new[]{-.27f,.27f})p.Cylinder("TowerLadder","Steel",new Vector3(-9.05f+dx,.15f,32.6f),new Vector3(-9.05f+dx,8.4f,32.6f),.038f,10);
            for(int i=0;i<27;i++)p.Cylinder("TowerLadder","Ivory",new Vector3(-9.32f,.3f+i*.30f,32.6f),new Vector3(-8.78f,.3f+i*.30f,32.6f),.025f,8);
            for(int i=0;i<4;i++)
            {
                float a=i*Mathf.PI*.5f;
                Vector3 q=new Vector3(-11+Mathf.Cos(a)*1.2f,10.35f,33+Mathf.Sin(a)*1.2f);
                p.Cylinder("TowerUpper","Steel",q,q+Vector3.up*1.0f,.07f,10);
            }
            // Hero lighting is attached to actual visible housings; no global darkness concealing geometry.
            foreach(Vector3 at in new[]{new Vector3(11,3.2f,29),new Vector3(-11,3.6f,31.8f)})
            {
                string group=at.x<0?"TowerFixtures":"RelayCanopy";
                p.BevelBox(group,"Steel",at,new Vector3(.6f,.17f,.34f),.025f);
                p.Box(group,"Lamp",at+Vector3.down*.10f,new Vector3(.45f,.035f,.25f));
                PolishSpot(b.transform,"Beacon shielded service flood",at+Vector3.down*.13f,3.0f,12,103);
            }
        }

        static void PolishSpot(Transform parent,string name,Vector3 at,float intensity,float range,float angle)
        {
            var light=new GameObject(name).AddComponent<Light>();light.transform.SetParent(parent,false);light.transform.position=at;
            light.transform.rotation=Quaternion.Euler(90,0,0);light.type=LightType.Spot;light.color=new Color(1,.78f,.48f);
            light.intensity=intensity;light.range=range;light.spotAngle=angle;light.innerSpotAngle=angle*.55f;light.shadows=LightShadows.None;
        }
        static void PlaceFactory(RegionBinding b,string asset,Vector3 at,Vector3 maximum,Quaternion rotation)
        {
            string path=PolishSource+"/Factory/"+asset+".fbx";
            var original=AssetDatabase.LoadAssetAtPath<GameObject>(path);if(!original)throw new InvalidOperationException("Verified CC0 model missing: "+path);
            var holder=new GameObject("EnvironmentV4 Kenney "+asset).transform;holder.SetParent(b.transform,false);
            var instance=(GameObject)PrefabUtility.InstantiatePrefab(original,holder);instance.SetActive(true);
            foreach(var r in instance.GetComponentsInChildren<Renderer>(true))
            {r.sharedMaterials=Enumerable.Repeat(PolishMaterial("Factory"),Mathf.Max(1,r.sharedMaterials.Length)).ToArray();r.lightmapIndex=-1;r.realtimeLightmapIndex=-1;}
            foreach(var collider in instance.GetComponentsInChildren<Collider>(true))Object.DestroyImmediate(collider);
            PlaceGeometry(holder,Vector3.zero);holder.rotation=rotation;FitGeometry(holder,at,maximum);
            // Only large explorable structures receive mesh collision; small valves/pipe decoration stays non-blocking.
            if(asset=="machine-bed"||asset=="hopper-square"||asset=="catwalk-stairs"||asset=="catwalk-straight")
                foreach(var mesh in instance.GetComponentsInChildren<MeshFilter>(true)) if(mesh.sharedMesh)mesh.gameObject.AddComponent<MeshCollider>().sharedMesh=mesh.sharedMesh;
        }

        [Serializable] sealed class PolishReceipt { public int region,meshCount,rendererCount,triangles,importedModelRenderers,importedModelTriangles,addedLights;public string status="authored-not-visually-accepted"; public string[] generatedFiles; }
        static void WritePolishReceipt(RegionBinding b)
        {
            var own=b.GetComponentsInChildren<MeshFilter>(true).Where(m=>AssetDatabase.GetAssetPath(m.sharedMesh).StartsWith(PolishGenerated+"/",StringComparison.Ordinal)).ToArray();
            int triangles=own.Sum(m=>(int)m.sharedMesh.GetIndexCount(0)/3);
            var imported=b.GetComponentsInChildren<MeshFilter>(true).Where(m=>AssetDatabase.GetAssetPath(m.sharedMesh).StartsWith(PolishSource+"/Factory/",StringComparison.Ordinal)).ToArray();
            int importedTriangles=imported.Sum(m=>Enumerable.Range(0,m.sharedMesh.subMeshCount).Sum(i=>(int)m.sharedMesh.GetIndexCount(i)/3));
            if(imported.Length>20||importedTriangles>18000)throw new InvalidOperationException("EnvironmentV4 imported model budget exceeded.");
            int lights=b.GetComponentsInChildren<Light>(true).Count(l=>l.name.Contains("shielded")||l.name=="Yard overhead task luminaire");
            if(own.Length>80||triangles>90000||lights>3)throw new InvalidOperationException("EnvironmentV4 incremental mobile art budget exceeded.");
            Directory.CreateDirectory("JourneyEvidence/environment-v4");
            string[] files=Directory.GetFiles(PolishGenerated,"*",SearchOption.TopDirectoryOnly).Where(f=>!f.EndsWith(".meta",StringComparison.Ordinal)).OrderBy(f=>f,StringComparer.Ordinal).ToArray();
            File.WriteAllText("JourneyEvidence/environment-v4/region-"+b.region+"-authoring.json",JsonUtility.ToJson(new PolishReceipt{region=b.region,meshCount=own.Length,rendererCount=own.Length+imported.Length,triangles=triangles,importedModelRenderers=imported.Length,importedModelTriangles=importedTriangles,addedLights=lights,generatedFiles=files},true));
        }

        // A small deterministic static mesh writer. Every spatial group is a distinct culling batch.
        // Metre-projected UVs are generated per face; tile size never depends on an object's local scale.
        sealed class PolishAuthor
        {
            readonly RegionBinding region;
            readonly SortedDictionary<string,PolishMesh> meshes=new SortedDictionary<string,PolishMesh>(StringComparer.Ordinal);
            public PolishAuthor(RegionBinding b){region=b;}
            PolishMesh Get(string group,string mat,bool collide=false)
            {
                string key=group+"-"+mat;
                if(!meshes.TryGetValue(key,out var mesh)){mesh=new PolishMesh(mat);meshes.Add(key,mesh);}
                mesh.collide|=collide;return mesh;
            }
            public void SourceMesh(string group,string material,Renderer renderer)
            {
                var filter=renderer.GetComponent<MeshFilter>();if(!filter||!filter.sharedMesh)throw new InvalidOperationException("Source wall has no retained mesh.");
                Matrix4x4 matrix=filter.transform.localToWorldMatrix;bool reverse=matrix.determinant<0;
                using(var data=MeshUtility.AcquireReadOnlyMeshData(filter.sharedMesh))
                using(var vertices=new NativeArray<Vector3>(data[0].vertexCount,Allocator.Temp))
                {
                    data[0].GetVertices(vertices);
                    for(int sub=0;sub<data[0].subMeshCount;sub++)
                    {
                        var desc=data[0].GetSubMesh(sub);if(desc.topology!=MeshTopology.Triangles)throw new InvalidOperationException("Retained station mesh is not triangles.");
                        using(var indices=new NativeArray<int>(desc.indexCount,Allocator.Temp))
                        {
                            data[0].GetIndices(indices,sub,true);
                            for(int i=0;i<indices.Length;i+=3)
                            {
                                Vector3 a=matrix.MultiplyPoint3x4(vertices[indices[i]]),b=matrix.MultiplyPoint3x4(vertices[indices[i+1]]),c=matrix.MultiplyPoint3x4(vertices[indices[i+2]]);
                                if(reverse)Get(group,material).Tri(a,c,b);else Get(group,material).Tri(a,b,c);
                            }
                        }
                    }
                }
                renderer.enabled=false; // original scene collider retained; only this candidate's renderer is hidden.
            }
            public void EnableCollision(string group,params string[] materials){foreach(string mat in materials)Get(group,mat).collide=true;}
            public void Quad(string group,string mat,Vector3 a,Vector3 b,Vector3 c,Vector3 d)=>Get(group,mat).Quad(a,b,c,d);
            public void Box(string group,string mat,Vector3 center,Vector3 size)
            {
                var m=Get(group,mat);Vector3 h=size*.5f;
                Vector3 a=center+new Vector3(-h.x,-h.y,-h.z),b=center+new Vector3(-h.x,-h.y,h.z),c=center+new Vector3(h.x,-h.y,h.z),d=center+new Vector3(h.x,-h.y,-h.z);
                Vector3 e=a+Vector3.up*size.y,f=b+Vector3.up*size.y,g=c+Vector3.up*size.y,k=d+Vector3.up*size.y;
                m.Quad(e,f,g,k);m.Quad(a,d,c,b);m.Quad(a,b,f,e);m.Quad(d,k,g,c);m.Quad(a,e,k,d);m.Quad(b,c,g,f);
            }
            public void BevelBox(string group,string mat,Vector3 at,Vector3 size,float bevel)
            {
                // Chamfered vertical corner silhouette plus inset top ring. 26 triangles, not a rounded high-poly cube.
                var m=Get(group,mat);float x=size.x*.5f,z=size.z*.5f,h=size.y*.5f;
                bevel=Mathf.Min(bevel,Mathf.Min(x,z)*.4f);
                Vector3[] ring={new Vector3(-x+bevel,0,-z),new Vector3(-x,0,-z+bevel),new Vector3(-x,0,z-bevel),new Vector3(-x+bevel,0,z),new Vector3(x-bevel,0,z),new Vector3(x,0,z-bevel),new Vector3(x,0,-z+bevel),new Vector3(x-bevel,0,-z)};
                for(int i=0;i<8;i++)
                {
                    int j=(i+1)%8;Vector3 a=at+ring[i]+Vector3.down*h,b=at+ring[j]+Vector3.down*h,c=b+Vector3.up*(size.y-bevel),d=a+Vector3.up*(size.y-bevel);
                    m.Quad(a,b,c,d);Vector3 e=at+ring[i]*.96f+Vector3.up*h,f=at+ring[j]*.96f+Vector3.up*h;
                    m.Quad(d,c,f,e);m.Tri(at+Vector3.up*h,e,f);
                }
            }
            public void Beam(string group,string mat,Vector3 from,Vector3 to,float width,float depth)
            {
                Vector3 forward=(to-from).normalized,right=Vector3.Cross(forward,Mathf.Abs(Vector3.Dot(forward,Vector3.up))>.95f?Vector3.forward:Vector3.up).normalized*width*.5f;
                Vector3 up=Vector3.Cross(right.normalized,forward).normalized*depth*.5f;var m=Get(group,mat);
                Vector3 a=from-right-up,b=from-right+up,c=from+right+up,d=from+right-up,e=to-right-up,f=to-right+up,g=to+right+up,h=to+right-up;
                m.Quad(d,c,b,a);m.Quad(f,g,h,e);m.Quad(b,f,e,a);m.Quad(c,g,f,b);m.Quad(d,h,g,c);m.Quad(a,e,h,d);
            }
            public void Cylinder(string group,string mat,Vector3 from,Vector3 to,float radius,int sides)
            {
                var m=Get(group,mat);Vector3 axis=(to-from).normalized;
                Vector3 x=Vector3.Cross(axis,Mathf.Abs(Vector3.Dot(axis,Vector3.up))>.95f?Vector3.forward:Vector3.up).normalized;
                Vector3 y=Vector3.Cross(axis,x).normalized;
                for(int i=0;i<sides;i++)
                {
                    float a=i*Mathf.PI*2/sides,b=(i+1)*Mathf.PI*2/sides;Vector3 p=(x*Mathf.Cos(a)+y*Mathf.Sin(a))*radius,q=(x*Mathf.Cos(b)+y*Mathf.Sin(b))*radius;
                    m.Quad(from+p,from+q,to+q,to+p);m.Tri(from,from+q,from+p);m.Tri(to,to+p,to+q);
                }
            }
            public void CorrugatedPanel(string group,string mat,Vector3 center,Vector3 size,float pitch)
            {
                var m=Get(group,mat);int count=Mathf.CeilToInt(size.x/pitch);float step=size.x/count;
                for(int i=0;i<count;i++)
                {
                    float x=center.x-size.x*.5f+i*step,nx=x+step,h=center.y+(i%2==0?.025f:-.025f),nh=center.y+(i%2==0?-.025f:.025f);
                    m.Quad(new Vector3(x,h,center.z-size.z*.5f),new Vector3(x,h,center.z+size.z*.5f),new Vector3(nx,nh,center.z+size.z*.5f),new Vector3(nx,nh,center.z-size.z*.5f));
                }
            }
            public void Shed(string group,Vector3 at,Vector3 size,string roofMat)
            {
                foreach(float x in new[]{-size.x*.5f,size.x*.5f})foreach(float z in new[]{-size.z*.5f,size.z*.5f})
                {
                    Box(group,"Steel",at+new Vector3(x,size.y*.5f,z),new Vector3(.17f,size.y,.17f));
                    Box(group,"Concrete",at+new Vector3(x,.13f,z),new Vector3(.46f,.26f,.46f));
                    Beam(group,"Steel",at+new Vector3(x,size.y-.75f,z),at+new Vector3(x-Mathf.Sign(x)*.65f,size.y-.06f,z),.09f,.09f);
                }
                CorrugatedPanel(group,roofMat,at+Vector3.up*size.y,new Vector3(size.x+.45f,.10f,size.z+.45f),.18f);
                Box(group,"Steel",at+new Vector3(0,size.y-.09f,-size.z*.5f),new Vector3(size.x+.2f,.18f,.13f));
                // rear windscreen has an open lower gap, deliberate stepped wall silhouette.
                Box(group,roofMat,at+new Vector3(0,1.32f,size.z*.5f),new Vector3(size.x,2.5f,.09f));
                Get(group,"Steel").collide=true;Get(group,"Concrete").collide=true;Get(group,roofMat).collide=true;
            }
            public void FlatPatch(string group,string mat,Vector3 at,Vector2 radius,int seed)
            {
                var m=Get(group,mat);int sides=11;
                for(int i=0;i<sides;i++)
                {
                    float a=i*Mathf.PI*2/sides,c=(i+1)*Mathf.PI*2/sides;
                    float ra=.77f+.23f*Mathf.Sin(i*2.714f+seed),rc=.77f+.23f*Mathf.Sin((i+1)*2.714f+seed);
                    m.Tri(at,at+new Vector3(Mathf.Cos(c)*radius.x*rc,0,Mathf.Sin(c)*radius.y*rc),at+new Vector3(Mathf.Cos(a)*radius.x*ra,0,Mathf.Sin(a)*radius.y*ra));
                }
            }
            public void Berm(string group,string mat,Vector3 at,Vector2 radius,float height,int seed,bool collide)
            {
                var m=Get(group,mat,collide);m.smoothNormals=true;const int rings=6,sides=28;
                Func<int,int,Vector3> point=(r,i)=>
                {
                    float angle=i*Mathf.PI*2/sides,f=(float)r/rings;
                    float wobble=1+.075f*Mathf.Sin(angle*3+seed)+.045f*Mathf.Cos(angle*5+seed);
                    float h=height*Mathf.Pow(Mathf.Max(0,1-f*f),2)*(1+.10f*Mathf.Sin(angle*2+seed)*f);
                    return at+new Vector3(Mathf.Cos(angle)*radius.x*f*wobble,h,Mathf.Sin(angle)*radius.y*f*wobble);
                };
                for(int r=0;r<rings;r++)for(int i=0;i<sides;i++)m.Quad(point(r,i+1),point(r+1,i+1),point(r+1,i),point(r,i));
            }
            public void Save()
            {
                if(!meshes.Keys.SequenceEqual(PolishExpectedMeshNames(region.region)))
                    throw new InvalidOperationException("EnvironmentV4 generated mesh membership differs from the finite producer contract: "+string.Join(",",meshes.Keys));
                foreach(var item in meshes)
                {
                    string path=PolishGenerated+"/R"+region.region+"-"+item.Key+".asset";
                    if(File.Exists(path))throw new IOException("Refusing to replace generated EnvironmentV4 mesh: "+path);
                    var mesh=item.Value.Build("EnvironmentV4 "+item.Key);AssetDatabase.CreateAsset(mesh,path);
                    var go=new GameObject("EnvironmentV4 "+item.Key);go.transform.SetParent(region.transform,false);
                    go.AddComponent<MeshFilter>().sharedMesh=mesh;var renderer=go.AddComponent<MeshRenderer>();renderer.sharedMaterial=PolishMaterial(item.Value.material);
                    renderer.shadowCastingMode=item.Key.StartsWith("Ground")||item.Key.StartsWith("Road")||item.Key.StartsWith("Forecourt")||item.Key.StartsWith("Shoulder")?ShadowCastingMode.Off:ShadowCastingMode.On;
                    renderer.receiveShadows=true;GameObjectUtility.SetStaticEditorFlags(go,StaticEditorFlags.BatchingStatic);
                    if(item.Value.collide)go.AddComponent<MeshCollider>().sharedMesh=mesh;
                }
                AssetDatabase.SaveAssets();
            }
        }
        sealed class PolishMesh
        {
            public readonly string material;public bool collide,smoothNormals;
            readonly List<Vector3> vertices=new List<Vector3>();readonly List<Vector2> uv=new List<Vector2>();readonly List<int> indices=new List<int>();
            public PolishMesh(string mat){material=mat;}
            public void Tri(Vector3 a,Vector3 b,Vector3 c)
            {
                Vector3 normal=Vector3.Cross(b-a,c-a);if(normal.sqrMagnitude<.00000001f)return;
                int first=vertices.Count;vertices.Add(a);vertices.Add(b);vertices.Add(c);
                foreach(var p in new[]{a,b,c})uv.Add(Project(p,normal.normalized)/TextureMetres(material));
                indices.Add(first);indices.Add(first+1);indices.Add(first+2);
            }
            public void Quad(Vector3 a,Vector3 b,Vector3 c,Vector3 d){Tri(a,b,c);Tri(a,c,d);}
            static Vector2 Project(Vector3 p,Vector3 n)
            {if(Mathf.Abs(n.y)>=Mathf.Abs(n.x)&&Mathf.Abs(n.y)>=Mathf.Abs(n.z))return new Vector2(p.x,p.z);if(Mathf.Abs(n.x)>=Mathf.Abs(n.z))return new Vector2(p.z,p.y);return new Vector2(p.x,p.y);}
            public Mesh Build(string name)
            {
                var mesh=new Mesh{name=name,indexFormat=vertices.Count>65535?IndexFormat.UInt32:IndexFormat.UInt16};
                mesh.SetVertices(vertices);mesh.SetUVs(0,uv);mesh.SetTriangles(indices,0);mesh.RecalculateNormals();
                if(smoothNormals)
                {
                    var normals=mesh.normals;var sums=new Dictionary<Vector3Int,Vector3>();
                    Func<Vector3,Vector3Int> key=v=>new Vector3Int(Mathf.RoundToInt(v.x*10000),Mathf.RoundToInt(v.y*10000),Mathf.RoundToInt(v.z*10000));
                    for(int i=0;i<vertices.Count;i++){var k=key(vertices[i]);if(sums.TryGetValue(k,out var n))sums[k]=n+normals[i];else sums[k]=normals[i];}
                    for(int i=0;i<vertices.Count;i++)normals[i]=sums[key(vertices[i])].normalized;
                    mesh.normals=normals;
                }
                mesh.RecalculateTangents();mesh.RecalculateBounds();return mesh;
            }
        }
    }
}

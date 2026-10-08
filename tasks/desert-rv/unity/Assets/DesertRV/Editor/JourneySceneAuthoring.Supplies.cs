using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace DesertRV.Editor
{
    public static partial class JourneySceneAuthoring
    {
        // Coordinates are tied to the R3 native scene evidence, not an extended route.
        [Serializable] public sealed class SupplyPlacement
        {
            public int region, amount;
            public string id, group, label, risk, landmark;
            public SupplyKind kind;
            public Vector3 at, stand;
            public float yaw;
        }
        public static SupplyPlacement[] SupplyPlacements(int region)
        {
            switch (region)
            {
                case 1: return new[] {
                    Placement(1,"apron-ammo",SupplyKind.Ammo,12,new Vector3(-6.4f,.025f,10.7f),0,"钉弹最多 +12","露天路肩，留意前方兽群","站前露天路肩"),
                    Placement(1,"garage-kit",SupplyKind.RepairKit,1,new Vector3(-12.4f,.025f,-.65f),0,"维修包 +1","车库内，须回车内工作台使用","车库工作台前") };
                case 2: return new[] {
                    Placement(2,"container-ammo",SupplyKind.Ammo,18,new Vector3(-8.3f,.025f,23),-90,"钉弹最多 +18","集装箱东侧，北面敞开","西侧集装箱旁"),
                    Placement(2,"canopy-kit",SupplyKind.RepairKit,1,new Vector3(10,.025f,26.2f),0,"维修包 +1","棚下，侧面没有墙体保护","东侧工作棚内") };
                case 3: return new[] {
                    Placement(3,"tower-ammo",SupplyKind.Ammo,18,new Vector3(-6.7f,.025f,30),0,"钉弹最多 +18","塔前露天，接近来袭方向","灯塔路侧"),
                    Placement(3,"relay-kit",SupplyKind.RepairKit,1,new Vector3(13.5f,.025f,31),0,"维修包 +1","后墙前，留意棚的两侧","继电棚后墙前") };
                default: throw new ArgumentOutOfRangeException(nameof(region));
            }
        }
        static SupplyPlacement Placement(int region,string suffix,SupplyKind kind,int amount,Vector3 at,float yaw,string label,string risk,string landmark)
        {
            return new SupplyPlacement {region=region,id="region-"+region+"/optional/"+suffix,group="region-"+region+"/optional-choice",kind=kind,amount=amount,
                at=at,stand=at+Quaternion.Euler(0,yaw,0)*Vector3.back*1.25f,yaw=yaw,label=label,risk=risk,landmark=landmark};
        }
        static void AuthorOptionalSupplies(Scene source,RegionBinding b,JourneyMotor motor)
        {
            if (b.supplies != null && b.supplies.Length != 0) throw new InvalidOperationException("Refusing to replace existing authored supplies.");
            var font=AssetDatabase.LoadAssetAtPath<Font>("Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf");
            if (!font) throw new InvalidOperationException("Retained CJK font required for readable supply choices.");
            var root=new GameObject("Optional supply choice - region "+b.region);root.transform.SetParent(b.transform,false);
            var view=root.AddComponent<JourneySupplyChoiceVisual>();view.region=b.region;
            var placements=SupplyPlacements(b.region);view.choiceGroup=placements[0].group;
            var supplies=new List<JourneySupplyPoint>();var options=new List<JourneySupplyChoiceVisual.Option>();
            foreach(var p in placements)
            {
                // Copy only the retained self-authored case assembly. It is NOT a commercial-art approval.
                var box=CopySized(source,root.transform,"Optional cache - "+p.id,Vector3.zero,new Vector3(1.12f,.60f,.75f),
                    "GEO-garage_toolbox","GEO-toolbox_lid","GEO-toolbox_handle","GEO-toolbox_clasp");
                foreach(var c in box.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
                Bounds bounds=GeometryBounds(box);
                var surface=box.gameObject.AddComponent<BoxCollider>();
                surface.center=box.InverseTransformPoint(bounds.center);
                surface.size=new Vector3(bounds.size.x/box.lossyScale.x,bounds.size.y/box.lossyScale.y,bounds.size.z/box.lossyScale.z);
                // Pivot the complete normalized geometry under an unscaled root before rotation.
                var visual=new GameObject("Supply visual - "+p.id).transform;visual.SetParent(root.transform,false);
                box.SetParent(visual,true);visual.SetPositionAndRotation(p.at,Quaternion.Euler(0,p.yaw,0));
                var anchor=Point("Supply interaction - "+p.id,visual,visual.TransformPoint(new Vector3(0,bounds.center.y,bounds.min.z-.01f)));
                var badgeColor=p.kind==SupplyKind.Ammo?new Color(.92f,.64f,.24f):new Color(.32f,.77f,.72f);
                // Signs/locks carry no colliders; all interaction belongs to the exact case surface.
                var active=SupplySign(visual,"Available choice",font,p.label+"\n本区二选一 · 可跳过",new Vector3(0,1.18f,0),1.62f,.66f,badgeColor);
                var sealedSign=SupplySign(visual,"Sealed choice",font,"已封存 · 不可领取\n本区补给已经选择",new Vector3(0,1.18f,0),1.62f,.66f,new Color(.61f,.63f,.62f));
                var strap=RenderOnlyBox("Closed cache seal",sealedSign.transform,sealedSign.transform.TransformPoint(new Vector3(0,-.88f,-.36f)),new Vector3(.10f,.56f,.02f),Cream);
                strap.transform.rotation=visual.rotation*Quaternion.Euler(0,0,24);sealedSign.SetActive(false);
                supplies.Add(new JourneySupplyPoint {id=p.id,label=p.label,choiceGroup=p.group,riskHint="本区二选一 · "+p.risk,
                    kind=p.kind,amount=p.amount,point=anchor,surface=surface,visual=visual.gameObject});
                options.Add(new JourneySupplyChoiceVisual.Option{id=p.id,availableSign=active,sealedSign=sealedSign});
            }
            b.supplies=supplies.ToArray();view.options=options.ToArray();
            Vector3 boardAt=b.region==1?new Vector3(-6.4f,1.45f,6.5f):b.region==2?new Vector3(6.3f,1.45f,19.5f):new Vector3(6.3f,1.45f,26.2f);
            string heading="可选补给 · 本区只取一箱\n"+placements[0].label+"："+placements[0].landmark+"\n"+placements[1].label+"："+placements[1].landmark+"\n拿取后另一箱封存 · 可全部跳过";
            view.availableBoard=SupplySign(root.transform,"Optional supply directions",font,heading,boardAt,3.3f,1.35f,Cream);
            view.sealedBoard=SupplySign(root.transform,"Optional supply choice completed",font,"本区补给已选择\n另一箱已封存 · 继续原路线",boardAt,3.3f,1.35f,new Color(.61f,.63f,.62f));
            view.sealedBoard.SetActive(false);
            // No new light source, objective, wait, reward loop, enemy, distance or route modification.
        }
        static GameObject SupplySign(Transform parent,string name,Font font,string text,Vector3 local,float width,float height,Color ink)
        {
            var root=new GameObject(name).transform;root.SetParent(parent,false);root.localPosition=local;
            var backing=RenderOnlyBox(name+" backing",root,root.position+root.forward*.035f,new Vector3(width,height,.045f),new Color(.12f,.16f,.17f));
            backing.transform.rotation=root.rotation;
            var post=RenderOnlyBox(name+" post",root,root.position-root.up*(height*.5f+.3f),new Vector3(.055f,.65f,.055f),Steel);post.transform.rotation=root.rotation;
            var canvasObject=new GameObject("Chinese world label",typeof(RectTransform),typeof(Canvas));canvasObject.transform.SetParent(root,false);
            var canvas=canvasObject.GetComponent<Canvas>();canvas.renderMode=RenderMode.WorldSpace;
            var rect=(RectTransform)canvasObject.transform;rect.sizeDelta=new Vector2(width*300,height*300);rect.localScale=Vector3.one/300;
            rect.localPosition=new Vector3(0,0,-.002f);
            var words=new GameObject("Choice text",typeof(RectTransform),typeof(CanvasRenderer),typeof(Text));words.transform.SetParent(rect,false);
            var label=words.GetComponent<Text>();label.font=font;label.text=text;label.fontSize=42;label.color=ink;label.alignment=TextAnchor.MiddleCenter;
            label.horizontalOverflow=HorizontalWrapMode.Wrap;label.verticalOverflow=VerticalWrapMode.Truncate;label.raycastTarget=false;
            var textRect=(RectTransform)words.transform;textRect.anchorMin=Vector2.zero;textRect.anchorMax=Vector2.one;textRect.offsetMin=new Vector2(12,6);textRect.offsetMax=new Vector2(-12,-6);
            return root.gameObject;
        }
        // During authoring all three candidate environments may be loaded at once.
        // Ignore only OTHER scene instances in this editor check; runtime uses unchanged
        // JourneyRaycast against its actually loaded current environment and persistent RV.
        static bool SupplyRayClear(RegionBinding b,Vector3 origin,Vector3 point,Collider target)
        {
            Vector3 delta=point-origin;
            var hits=Physics.RaycastAll(origin,delta.normalized,delta.magnitude,~0,QueryTriggerInteraction.Ignore)
                .Where(h=>h.collider.gameObject.scene==b.gameObject.scene).OrderBy(h=>h.distance).ToArray();
            return hits.Length==0 || (hits[0].collider==target && Vector3.Distance(hits[0].point,point)<.35f);
        }
        [Serializable] sealed class SupplyReachRecord
        {
            public string id,group;public Vector3 casePosition,stand,interaction;public float reachDistance;public int approachSamples;
            public bool lineOfSight,walkingCapsuleClear,caseClear,optionalOnly=true;
        }
        [Serializable] sealed class SupplyReachReport
        {public string status="NATIVE_STATIC_PLACEMENT_ONLY_NOT_GAMEPLAY_ACCEPTANCE";public int region;public SupplyReachRecord[] supplies;}
        static void CheckOptionalSupplyApproaches(RegionBinding b)
        {
            Physics.SyncTransforms();var plan=SupplyPlacements(b.region);
            if(b.supplies==null || b.supplies.Length!=2)throw new InvalidOperationException("Expected exactly two optional supply alternatives.");
            var records=new List<SupplyReachRecord>();
            for(int i=0;i<2;i++)
            {
                var p=plan[i];var s=b.supplies[i];
                if(s.id!=p.id || s.choiceGroup!=p.group || s.amount!=p.amount || s.kind!=p.kind || !s.point || !s.surface || !s.visual || s.surface.isTrigger)
                    throw new InvalidOperationException("Supply binding does not match the placement contract: "+p.id);
                var overlaps=Physics.OverlapBox(s.surface.bounds.center,s.surface.bounds.extents*.97f,Quaternion.identity,~0,QueryTriggerInteraction.Ignore)
                    .Where(c=>c!=s.surface && c.gameObject.scene==b.gameObject.scene && c.bounds.max.y>.08f && !c.GetComponentInParent<BeastActor>()).ToArray();
                if(overlaps.Length>0)throw new InvalidOperationException("Supply case intersects scenery: "+p.id+" by "+string.Join(",",overlaps.Select(c=>c.name)));
                var foot=p.stand;var eye=foot+Vector3.up*1.52f;
                if(Vector3.Distance(eye,s.point.position)>2.2f || !SupplyRayClear(b,eye,s.point.position,s.surface))
                    throw new InvalidOperationException("Supply interaction is out of reach or behind real geometry: "+p.id);
                // Both options are reached by a short horizontal path from the existing road edge.
                // Sample actual scene colliders at a walking capsule; do not silently ignore the RV/world.
                Vector3 start=new Vector3(Mathf.Sign(foot.x)*4f,foot.y,foot.z);int samples=Mathf.CeilToInt(Vector3.Distance(start,foot)/.25f)+1;
                for(int n=0;n<=samples;n++)
                {
                    Vector3 at=Vector3.Lerp(start,foot,n/(float)samples);
                    var blockers=Physics.OverlapCapsule(at+Vector3.up*.36f,at+Vector3.up*1.44f,.28f,~0,QueryTriggerInteraction.Ignore)
                        .Where(c=>c.gameObject.scene==b.gameObject.scene && !c.GetComponentInParent<BeastActor>()).ToArray();
                    if(blockers.Length>0)throw new InvalidOperationException("Supply walking approach blocked: "+p.id+" at "+at+" by "+string.Join(",",blockers.Select(c=>c.name)));
                }
                // Native visibility from the actual nearby approach, not through-world UI.
                var sign=s.visual.transform.Find("Available choice");
                if(!sign || !SupplyRayClear(b,eye,sign.position,null))throw new InvalidOperationException("Supply sign hidden from approach: "+p.id);
                records.Add(new SupplyReachRecord{id=p.id,group=p.group,casePosition=p.at,stand=foot,interaction=s.point.position,
                    reachDistance=Vector3.Distance(eye,s.point.position),approachSamples=samples+1,lineOfSight=true,walkingCapsuleClear=true,caseClear=true});
            }
            if(b.supplies[0].choiceGroup!=b.supplies[1].choiceGroup || b.supplies[0].id==b.supplies[1].id)
                throw new InvalidOperationException("Optional supplies are not a mutually exclusive unique pair.");
            Directory.CreateDirectory("JourneyEvidence");File.WriteAllText("JourneyEvidence/supply-placement-region-"+b.region+".json",JsonUtility.ToJson(new SupplyReachReport{region=b.region,supplies=records.ToArray()},true));
        }
    }
}

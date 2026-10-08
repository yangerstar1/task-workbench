using System;
using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class WeakPointPresentationTests
    {
        const BindingFlags All=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance;
        static Type T(string name)=>Type.GetType("DesertRV."+name+", Assembly-CSharp",true);
        static object Get(object o,string n)=>o.GetType().GetProperty(n,All).GetValue(o);
        static void Set(object o,string n,object v)=>o.GetType().GetField(n,All).SetValue(o,v);
        static object Call(object o,string n,params object[] a)=>o.GetType().GetMethod(n,All).Invoke(o,a);
        static Transform Child(string name,Transform parent)
        { var go=new GameObject(name);go.transform.SetParent(parent,false);return go.transform; }
        sealed class Fixture:IDisposable
        {
            public readonly GameObject Root=new GameObject("armored contract fixture"), Host=new GameObject("session fixture");
            public readonly Component Actor,Presenter;
            public readonly object State;
            public readonly MeshRenderer Body,Core;
            public readonly Transform Assembly;
            public readonly Transform[] Plates=new Transform[2];
            public readonly MeshRenderer[] PlateMeshes=new MeshRenderer[2];
            public readonly Material Closed,Open;
            public readonly AnimationClip Clip;
            readonly List<UnityEngine.Object> generated=new List<UnityEngine.Object>();
            readonly string controllerPath="Assets/__WeakPointContract_"+Guid.NewGuid().ToString("N")+".controller";
            public Fixture()
            {
                Root.SetActive(false);Host.SetActive(false);
                var session=Host.AddComponent(T("JourneySession"));State=Activator.CreateInstance(T("SessionState"));
                Call(State,"ConfigureStorm",-100d,1d,1d);Call(State,"Start");session.GetType().GetProperty("State").SetValue(session,State);
                Actor=Root.AddComponent(T("BeastActor"));Set(Actor,"armored",true);Set(Actor,"journey",session);
                var shader=Shader.Find("Universal Render Pipeline/Lit");Assert.That(shader,Is.Not.Null);
                Closed=new Material(shader);Open=new Material(shader);Open.SetColor("_EmissionColor",new Color(2,.7f,.2f));Open.EnableKeyword("_EMISSION");
                generated.Add(Closed);generated.Add(Open);
                var carrier=Child("BodyCarrier",Root.transform);Assembly=Child("WeakPointAssembly",carrier);
                Body=MakeMesh("Bulwark_Body",carrier);Core=MakeMesh("Core_Renderer",Assembly);
                for(int i=0;i<2;i++) { Plates[i]=Child(i==0?"ArmorPlate_L_Pivot":"ArmorPlate_R_Pivot",Assembly);PlateMeshes[i]=MakeMesh("PlateMesh",Plates[i]); }
                var controller=AnimatorController.CreateAnimatorControllerAtPath(controllerPath);Clip=new AnimationClip {name="Recover"};
                AnimationUtility.SetEditorCurve(Clip,EditorCurveBinding.FloatCurve("BodyCarrier",typeof(Transform),"m_LocalPosition.y"),AnimationCurve.Linear(0,0,2,.05f));
                AssetDatabase.AddObjectToAsset(Clip,controller);
                foreach(string name in new[]{"Idle","Walk","Windup","Attack","Recover","Hit","Death"})
                { var state=controller.layers[0].stateMachine.AddState(name);state.motion=Clip;if(name=="Idle")controller.layers[0].stateMachine.defaultState=state; }
                var animator=Root.AddComponent<Animator>();animator.runtimeAnimatorController=controller;Set(Actor,"animator",animator);
                Presenter=Root.AddComponent(T("BeastWeakPointPresentation"));((Behaviour)Presenter).enabled=false;
                Set(Presenter,"actor",Actor);Set(Presenter,"bodyRenderer",Body);Set(Presenter,"weakPointRoot",Assembly);Set(Presenter,"weakPointRenderer",Core);Set(Presenter,"openMaterial",Open);
                Set(Presenter,"armorPlates",Plates);Set(Presenter,"plateRenderers",PlateMeshes);Set(Presenter,"openLocalEulerAngles",new[]{new Vector3(0,0,-140),new Vector3(0,0,140)});
                Root.SetActive(true);
            }
            MeshRenderer MakeMesh(string name,Transform parent)
            {
                var node=Child(name,parent);var mesh=new Mesh {name=name+" independent test mesh"};
                mesh.vertices=new[]{Vector3.zero,Vector3.right*.1f,Vector3.up*.1f};mesh.triangles=new[]{0,1,2};mesh.RecalculateBounds();generated.Add(mesh);
                node.gameObject.AddComponent<MeshFilter>().sharedMesh=mesh;var renderer=node.gameObject.AddComponent<MeshRenderer>();renderer.sharedMaterial=Closed;return renderer;
            }
            public void OpenWindow()
            {
                int generation=(int)Get(State,"Generation");var combat=Activator.CreateInstance(T("BeastCombatState"),State,1,generation);
                int charge=(int)Call(combat,"TryBeginCharge",1,generation);Assert.That(charge,Is.GreaterThan(0));
                Assert.That(Call(combat,"TryBeginRecovery",1,generation,charge,2d),Is.True);
                Set(Actor,"combat",combat);Set(Actor,"combatRegion",1);Set(Actor,"combatGeneration",generation);
                Actor.GetType().GetProperty("Phase").SetValue(Actor,Enum.Parse(T("BeastPhase"),"Recover"));
            }
            public void Enable()
            {
                ((Behaviour)Presenter).enabled=true;
                if(!(bool)Presenter.GetType().GetField("owns",All).GetValue(Presenter)) Call(Presenter,"OnEnable");
            }
            public void Disable()
            {
                ((Behaviour)Presenter).enabled=false;
                if((bool)Presenter.GetType().GetField("owns",All).GetValue(Presenter)) Call(Presenter,"OnDisable");
            }
            public List<string> Gate()
            {
                var errors=new List<string>();
                var gate=Type.GetType("DesertRV.Editor.WeakPointContractChecks, Assembly-CSharp-Editor",true);
                gate.GetMethod("Validate").Invoke(null,new object[]{Presenter,"fixture",errors});return errors;
            }
            public void Dispose()
            {
                Disable();UnityEngine.Object.DestroyImmediate(Root);UnityEngine.Object.DestroyImmediate(Host);
                AssetDatabase.DeleteAsset(controllerPath);foreach(var obj in generated) if(obj) UnityEngine.Object.DestroyImmediate(obj);
            }
        }
        [Test] public void Binding_RejectsLegacyPlateWholeBodyAndSharedGeometry()
        {
            using(var f=new Fixture())
            {
                object[] reason={null};Assert.That(Call(f.Presenter,"ValidateBindings",reason),Is.True);
                Set(f.Presenter,"armorPlate",f.Plates[0]);Set(f.Presenter,"armorPlates",new[]{f.Plates[0]});
                Assert.That(Call(f.Presenter,"ValidateBindings",reason),Is.False);Set(f.Presenter,"armorPlates",f.Plates);
                Set(f.Presenter,"weakPointRenderer",f.Body);Assert.That(Call(f.Presenter,"ValidateBindings",reason),Is.False);Set(f.Presenter,"weakPointRenderer",f.Core);
                var filter=f.Core.GetComponent<MeshFilter>();var mesh=filter.sharedMesh;filter.sharedMesh=f.Body.GetComponent<MeshFilter>().sharedMesh;
                Assert.That(Call(f.Presenter,"ValidateBindings",reason),Is.False);filter.sharedMesh=mesh;
                Assert.That(f.Core.sharedMaterial,Is.SameAs(f.Closed));Assert.That(f.Body.sharedMaterial,Is.SameAs(f.Closed));
            }
        }
        [Test] public void Lifecycle_OnlyCoreAndBothPlatesFollowRealWindowAcrossPauseDisableDeathRestart()
        {
            using(var f=new Fixture())
            {
                var closed=new[]{Quaternion.Euler(4,0,0),Quaternion.Euler(-4,0,0)};
                for(int i=0;i<2;i++) f.Plates[i].localRotation=closed[i];
                Color bodyEmission=f.Body.sharedMaterial.GetColor("_EmissionColor");f.OpenWindow();f.Enable();
                Assert.That(f.Core.sharedMaterial,Is.SameAs(f.Open));Assert.That(f.Body.sharedMaterial,Is.SameAs(f.Closed));
                for(int i=0;i<2;i++) Assert.That(Quaternion.Angle(closed[i],f.Plates[i].localRotation),Is.GreaterThan(100));
                Call(f.State,"Pause");var combat=f.Actor.GetType().GetField("combat",All).GetValue(f.Actor);Call(combat,"Tick",20d);
                Call(f.Presenter,"LateUpdate");Assert.That(f.Core.sharedMaterial,Is.SameAs(f.Open));
                f.Disable();Assert.That(f.Core.sharedMaterial,Is.SameAs(f.Closed));
                for(int i=0;i<2;i++) Assert.That(Quaternion.Angle(closed[i],f.Plates[i].localRotation),Is.LessThan(.01f));
                f.Enable();Assert.That(f.Core.sharedMaterial,Is.SameAs(f.Open));
                for(int i=0;i<2;i++) Assert.That(Quaternion.Angle(closed[i],f.Plates[i].localRotation),Is.GreaterThan(100));
                Call(f.State,"Resume");Call(combat,"Tick",2d);Call(f.Presenter,"LateUpdate");Assert.That(f.Core.sharedMaterial,Is.SameAs(f.Closed));
                f.OpenWindow();Call(f.Presenter,"LateUpdate");f.Actor.GetType().GetProperty("Phase").SetValue(f.Actor,Enum.Parse(T("BeastPhase"),"Dead"));
                Call(f.Presenter,"LateUpdate");Assert.That(f.Core.sharedMaterial,Is.SameAs(f.Closed));
                f.OpenWindow();Call(f.Presenter,"LateUpdate");Call(f.State,"DamagePlayer",100);Call(f.Presenter,"LateUpdate");Assert.That(f.Core.sharedMaterial,Is.SameAs(f.Closed));
                Call(f.State,"RestartJourney");Call(f.Presenter,"LateUpdate");Assert.That(f.Core.sharedMaterial,Is.SameAs(f.Closed));
                for(int i=0;i<2;i++) Assert.That(Quaternion.Angle(closed[i],f.Plates[i].localRotation),Is.LessThan(.01f));
                Assert.That(f.Body.sharedMaterial.GetColor("_EmissionColor"),Is.EqualTo(bodyEmission));
                foreach(var plate in f.PlateMeshes) Assert.That(plate.sharedMaterial,Is.SameAs(f.Closed));
            }
        }
        [Test] public void Gate_RejectsConstantAssemblyCurvesMaterialKeysAndBodyEmissionLeak()
        {
            using(var f=new Fixture())
            {
                Assert.That(f.Gate(),Is.Empty);
                var binding=EditorCurveBinding.FloatCurve("BodyCarrier/WeakPointAssembly/ArmorPlate_L_Pivot",typeof(Transform),"m_LocalRotation.w");
                AnimationUtility.SetEditorCurve(f.Clip,binding,AnimationCurve.Constant(0,2,1));
                Assert.That(f.Gate().Exists(x=>x.Contains("Animator curve")),Is.True);AnimationUtility.SetEditorCurve(f.Clip,binding,null);
                var materialBinding=EditorCurveBinding.PPtrCurve("BodyCarrier/WeakPointAssembly/Core_Renderer",typeof(MeshRenderer),"m_Materials.Array.data[0]");
                AnimationUtility.SetObjectReferenceCurve(f.Clip,materialBinding,new[]{new ObjectReferenceKeyframe {time=0,value=f.Open}});
                Assert.That(f.Gate().Exists(x=>x.Contains("Animator object curve")),Is.True);AnimationUtility.SetObjectReferenceCurve(f.Clip,materialBinding,null);
                f.Body.sharedMaterial=f.Open;Assert.That(f.Gate().Exists(x=>x.Contains("outside the dedicated core")),Is.True);f.Body.sharedMaterial=f.Closed;
                Assert.That(f.Gate(),Is.Empty);
            }
        }
    }
}

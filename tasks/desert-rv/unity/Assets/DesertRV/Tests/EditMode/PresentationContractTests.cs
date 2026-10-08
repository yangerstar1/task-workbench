using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    // Reflection follows the existing test assembly boundary; all runtime tests still require Unity Actions.
    public sealed class PresentationContractTests
    {
        const BindingFlags All = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Get(object o, string name) => o.GetType().GetProperty(name, All).GetValue(o);
        static void Set(object o, string name, object value) => o.GetType().GetField(name, All).SetValue(o, value);
        static object Call(object o, string name, params object[] args) => o.GetType().GetMethod(name, All).Invoke(o, args);
        static Component Add(GameObject go, string type) => go.AddComponent(T(type));
        [Test] public void Cursor_ConsumesOnceAndRejectsOldEpoch()
        {
            var cursor = Activator.CreateInstance(T("PresentationEventCursor"));
            Assert.That(Call(cursor,"Consume",1,1,1), Is.True);
            Assert.That(Call(cursor,"Consume",1,1,1), Is.False);
            Assert.That(Call(cursor,"Consume",1,1,0), Is.False);
            Assert.That(Call(cursor,"Consume",2,1,2), Is.False);
            Assert.That(Call(cursor,"Consume",2,2,1), Is.True);
        }
        [Test] public void Ownership_DuplicateRejectedAndReleasedOwnerCanRebind()
        {
            var go = new GameObject("ownership fixture");
            var other = new GameObject("duplicate fixture");
            try
            {
                var type = T("PresentationOwnership");
                var acquire = type.GetMethod("Acquire",BindingFlags.Static|BindingFlags.NonPublic);
                var release = type.GetMethod("Release",BindingFlags.Static|BindingFlags.NonPublic);
                Assert.That(acquire.Invoke(null,new object[]{go.transform,go.transform,"test"}),Is.True);
                Assert.That(acquire.Invoke(null,new object[]{go.transform,other.transform,"test"}),Is.False);
                release.Invoke(null,new object[]{go.transform,go.transform,"test"});
                Assert.That(acquire.Invoke(null,new object[]{go.transform,other.transform,"test"}),Is.True);
                release.Invoke(null,new object[]{go.transform,other.transform,"test"});
            }
            finally { UnityEngine.Object.DestroyImmediate(go); UnityEngine.Object.DestroyImmediate(other); }
        }
        sealed class Fixture : IDisposable
        {
            public readonly GameObject Root = new GameObject("presentation fixture");
            public readonly Component Session, Actions, Actor;
            public readonly object State;
            public Fixture()
            {
                Root.SetActive(false);
                Session=Add(Root,"JourneySession"); State=Activator.CreateInstance(T("SessionState"));
                Call(State,"ConfigureStorm",-100d,1d,1d); Call(State,"Start");
                Session.GetType().GetProperty("State").SetValue(Session,State);
                Actions=Add(Root,"JourneyActions"); Set(Actions,"journey",Session);
                var region=Add(Root,"RegionBinding");
                Set(region,"region",1); Actions.GetType().GetProperty("Region").SetValue(Actions,region);
                Actions.GetType().GetProperty("PresentationGeneration").SetValue(Actions,1);
                Actor=Add(Root,"BeastActor"); Set(Actor,"journey",Session); Set(Actor,"armored",true);
                Actor.GetType().GetProperty("Health").SetValue(Actor,160);
            }
            public void Dispose() { UnityEngine.Object.DestroyImmediate(Root); }
        }
        [Test] public void WeakPoint_RealWindowPauseDeathAndGenerationFence()
        {
            using (var f = new Fixture())
            {
                var combat=Activator.CreateInstance(T("BeastCombatState"),f.State,1,1);
                int charge=(int)Call(combat,"TryBeginCharge",1,1);
                Call(combat,"TryBeginRecovery",1,1,charge,2d);
                Set(f.Actor,"combat",combat); Set(f.Actor,"combatRegion",1); Set(f.Actor,"combatGeneration",1);
                f.Actor.GetType().GetProperty("Phase").SetValue(f.Actor,Enum.Parse(T("BeastPhase"),"Recover"));
                Assert.That(Get(f.Actor,"WeakPointExposed"),Is.True);
                Call(f.State,"Pause"); Call(combat,"Tick",20d);
                Assert.That(Get(f.Actor,"WeakPointExposed"),Is.True);
                Call(f.State,"Resume"); Call(combat,"Tick",2d);
                Assert.That(Get(f.Actor,"WeakPointExposed"),Is.False);
                Set(combat,"<WeakPointRemaining>k__BackingField",1d);
                f.Actor.GetType().GetProperty("Phase").SetValue(f.Actor,Enum.Parse(T("BeastPhase"),"Dead"));
                Assert.That(Get(f.Actor,"WeakPointExposed"),Is.False);
                f.Actor.GetType().GetProperty("Phase").SetValue(f.Actor,Enum.Parse(T("BeastPhase"),"Recover"));
                Set(f.Actor,"combatGeneration",0);
                Assert.That(Get(f.Actor,"WeakPointExposed"),Is.False);
            }
        }
        [Test] public void Arc_OnlyEventEndpointsOnceAndNeverMutatesCombat()
        {
            using (var f = new Fixture())
            {
                var presenter=Add(f.Root,"ArcPresentation"); Set(presenter,"actions",f.Actions); Set(presenter,"owns",true);
                var line=f.Root.AddComponent<LineRenderer>();
                var fx=new GameObject("impact"); fx.transform.SetParent(f.Root.transform); var particles=fx.AddComponent<ParticleSystem>();
                var audio=f.Root.AddComponent<AudioSource>();
                Set(presenter,"beams",new[]{line}); Set(presenter,"impacts",new[]{particles});
                Set(presenter,"remaining",new float[1]); Set(presenter,"audioSource",audio); Set(presenter,"soundPulse",7);
                var cursor=presenter.GetType().GetField("hits",All).GetValue(presenter); Call(cursor,"Reset",0);
                Vector3 origin=new Vector3(1,2,3), endpoint=new Vector3(4,5,6);
                var ev=Activator.CreateInstance(T("ArcPresentationEvent"),0,1,7,f.Actor,origin,endpoint);
                var health=Get(f.Actor,"Health"); var ammo=Get(f.State,"LoadedAmmo");
                Call(presenter,"OnHit",ev); Assert.That(line.GetPosition(0),Is.EqualTo(origin)); Assert.That(line.GetPosition(1),Is.EqualTo(endpoint));
                Call(presenter,"OnHit",ev); // A second slot request would error; duplicate is ignored.
                Assert.That(Get(f.Actor,"Health"),Is.EqualTo(health)); Assert.That(Get(f.State,"LoadedAmmo"),Is.EqualTo(ammo));
                Call(presenter,"ResetVisuals"); Assert.That(line.enabled,Is.False);
                Set(presenter,"owns",false);
            }
        }
        [Test] public void Arc_PauseDoesNotAdvanceLifetimeAndResetClears()
        {
            using (var f = new Fixture())
            {
                var presenter=Add(f.Root,"ArcPresentation"); Set(presenter,"actions",f.Actions); Set(presenter,"owns",true); Set(presenter,"generation",1);
                var line=f.Root.AddComponent<LineRenderer>(); var particles=f.Root.AddComponent<ParticleSystem>();
                Set(presenter,"beams",new[]{line}); Set(presenter,"impacts",new[]{particles}); Set(presenter,"audioSource",f.Root.AddComponent<AudioSource>());
                var remaining=new[]{.16f}; Set(presenter,"remaining",remaining);
                Call(f.State,"Pause"); Call(presenter,"LateUpdate"); Assert.That(remaining[0],Is.EqualTo(.16f));
                Call(f.State,"Resume"); Call(presenter,"LateUpdate"); Assert.That(remaining[0],Is.LessThanOrEqualTo(.16f));
                Call(presenter,"ResetVisuals"); Assert.That(remaining[0],Is.Zero); Assert.That(line.enabled,Is.False);
                Set(presenter,"owns",false);
            }
        }
        [Test] public void Disable_UnsubscribesEveryWeaponNotification()
        {
            using (var f = new Fixture())
            {
                var presenter=Add(f.Root,"WeaponPresentation"); Set(presenter,"subscribed",f.Actions);
                foreach(var pair in new[]{new[]{"ShotPresented","OnShot"},new[]{"ReloadPresented","OnReload"},new[]{"PresentationReset","ResetVisuals"}})
                {
                    var e=f.Actions.GetType().GetEvent(pair[0]);
                    var d=Delegate.CreateDelegate(e.EventHandlerType,presenter,presenter.GetType().GetMethod(pair[1],All)); e.AddEventHandler(f.Actions,d);
                }
                Call(presenter,"OnDisable");
                foreach(var name in new[]{"ShotPresented","ReloadPresented","PresentationReset"})
                    Assert.That(f.Actions.GetType().GetField(name,All).GetValue(f.Actions),Is.Null);
            }
        }
        [Test] public void ReloadPlan_All78PartialCombinationsMatchRealCommit()
        {
            var added=T("ReloadPresentationPlan").GetMethod("Added",BindingFlags.Public|BindingFlags.Static);
            int combinations=0;
            for(int before=0;before<12;before++) for(int reserve=1;reserve<=12-before;reserve++)
            using(var f=new Fixture())
            {
                for(int shot=before;shot<12;shot++) Assert.That(Call(f.State,"TryFire"),Is.True);
                f.State.GetType().GetProperty("ReserveAmmo").SetValue(f.State,reserve);
                int planned=(int)added.Invoke(null,new object[]{before,reserve});
                Assert.That(planned,Is.EqualTo(reserve));
                Assert.That(Get(f.State,"LoadedAmmo"),Is.EqualTo(before)); // Planning cannot spend or refill.
                Call(f.State,"Pause"); Call(f.State,"Reload"); Assert.That(Get(f.State,"LoadedAmmo"),Is.EqualTo(before));
                Call(f.State,"Resume"); Call(f.State,"Reload");
                Assert.That(Get(f.State,"LoadedAmmo"),Is.EqualTo(before+planned));
                Assert.That(Get(f.State,"ReserveAmmo"),Is.Zero); combinations++;
            }
            Assert.That(combinations,Is.EqualTo(78));
            Assert.That(added.Invoke(null,new object[]{11,96}),Is.EqualTo(1));
            Assert.That(added.Invoke(null,new object[]{12,96}),Is.Zero);
            Assert.That(added.Invoke(null,new object[]{4,0}),Is.Zero);
        }
        [Test] public void Pause_PreservesCooldownReloadAndEpochWhileCancellationSpendsNothing()
        {
            using(var f=new Fixture())
            {
                Set(f.Actions,"effects",f.Root.AddComponent<AudioSource>());
                Set(f.Actions,"wind",f.Root.AddComponent<AudioSource>());
                Set(f.Actions,"reloadAudio",f.Root.AddComponent<AudioSource>());
                var tracer=f.Root.AddComponent<LineRenderer>(); Set(f.Actions,"tracer",tracer);
                Set(f.Actions,"fireClock",.17f); Set(f.Actions,"reloadRemaining",.85f); Set(f.Actions,"tracerRemaining",.06f);
                f.Actions.GetType().GetProperty("ReloadLoadedBefore").SetValue(f.Actions,5);
                f.Actions.GetType().GetProperty("ReloadPlannedAdded").SetValue(f.Actions,7);
                object ammo=Get(f.State,"LoadedAmmo"),reserve=Get(f.State,"ReserveAmmo"),epoch=Get(f.Actions,"PresentationEpoch");
                Call(f.Actions,"SetPaused",true); Call(f.Actions,"SetPaused",true);
                Assert.That(Get(f.Actions,"FireRemaining"),Is.EqualTo(.17f)); Assert.That(Get(f.Actions,"ReloadRemaining"),Is.EqualTo(.85f));
                Assert.That(Get(f.Actions,"PresentationEpoch"),Is.EqualTo(epoch)); Assert.That(tracer.enabled,Is.False);
                Call(f.Actions,"CancelReloadPresentation");
                Assert.That(Get(f.Actions,"ReloadRemaining"),Is.Zero); Assert.That(Get(f.Actions,"ReloadPlannedAdded"),Is.Zero);
                Assert.That(Get(f.State,"LoadedAmmo"),Is.EqualTo(ammo)); Assert.That(Get(f.State,"ReserveAmmo"),Is.EqualTo(reserve));
            }
        }
        [Test] public void PartialReload_ProjectsExactCountsAndSameHandStripDisplacement()
        {
            using(var f=new Fixture())
            {
                var presenter=Add(f.Root,"WeaponPresentation"); Set(presenter,"actions",f.Actions);
                var incoming=new GameObject("unkeyed incoming carrier").transform; incoming.SetParent(f.Root.transform);
                var hand=new GameObject("unkeyed left carrier").transform; hand.SetParent(f.Root.transform);
                Set(presenter,"incomingOffset",incoming); Set(presenter,"leftReloadOffset",hand); Set(presenter,"nailPitch",new Vector3(.01f,0,0));
                var old=new Renderer[12]; var fresh=new Renderer[12];
                for(int i=0;i<12;i++)
                {
                    var a=new GameObject("old fixture "+i); a.transform.SetParent(f.Root.transform); old[i]=a.AddComponent<MeshRenderer>();
                    var b=new GameObject("fresh fixture "+i); b.transform.SetParent(incoming); fresh[i]=b.AddComponent<MeshRenderer>();
                }
                Set(presenter,"loadedNails",old); Set(presenter,"incomingNails",fresh);
                f.Actions.GetType().GetProperty("ReloadLoadedBefore").SetValue(f.Actions,3);
                f.Actions.GetType().GetProperty("ReloadPlannedAdded").SetValue(f.Actions,5);
                for(int i=0;i<9;i++) Call(f.State,"TryFire");
                Set(f.Actions,"reloadRemaining",.9f); Call(presenter,"ApplyAmmunition",true);
                for(int i=0;i<12;i++) { Assert.That(old[i].enabled,Is.EqualTo(i<3)); Assert.That(fresh[i].enabled,Is.EqualTo(i<5)); }
                Assert.That(incoming.localPosition.x,Is.EqualTo(.03f).Within(.00001f)); Assert.That(hand.localPosition,Is.EqualTo(incoming.localPosition));
                Call(f.State,"Pause"); Call(presenter,"ApplyAmmunition",true);
                for(int i=0;i<12;i++) { Assert.That(old[i].enabled,Is.EqualTo(i<3)); Assert.That(fresh[i].enabled,Is.EqualTo(i<5)); }
                Call(f.State,"Resume"); Call(f.Actions,"CancelReloadPresentation"); Call(presenter,"ApplyAmmunition",true);
                foreach(var nail in fresh) Assert.That(nail.enabled,Is.False);
                Assert.That(incoming.localPosition,Is.EqualTo(Vector3.zero)); Assert.That(hand.localPosition,Is.EqualTo(Vector3.zero));
                // Fixture's authoritative ammo was never changed by projection or cancellation.
                Assert.That(Get(f.State,"LoadedAmmo"),Is.EqualTo(3));
                for(int i=0;i<12;i++) Assert.That(old[i].enabled,Is.EqualTo(i<3));
                f.State.GetType().GetProperty("Generation").SetValue(f.State,2);
                Call(presenter,"ApplyAmmunition",true);
                foreach(var nail in old) Assert.That(nail.enabled,Is.False);
                foreach(var nail in fresh) Assert.That(nail.enabled,Is.False);
                Assert.That(Get(f.State,"LoadedAmmo"),Is.EqualTo(3));
            }
        }
        [Test] public void PausedReload_DisableEnableRestoresFrozenAnimatorPoseAndCounts()
        {
            string path="Assets/__PresentationLifecycle_"+Guid.NewGuid().ToString("N")+".controller";
            var cameraObject=new GameObject("lifecycle camera fixture");
            try
            {
                var controller=UnityEditor.Animations.AnimatorController.CreateAnimatorControllerAtPath(path);
                var states=controller.layers[0].stateMachine;
                foreach(string name in new[]{"Idle","Fire","Reload"})
                {
                    var clip=new AnimationClip { name=name };
                    float duration=name=="Reload"?1.65f:name=="Fire"?.22f:2f;
                    var binding=UnityEditor.EditorCurveBinding.FloatCurve("LeftCarrier/LeftHand",typeof(Transform),"m_LocalPosition.y");
                    UnityEditor.AnimationUtility.SetEditorCurve(clip,binding,AnimationCurve.Linear(0,0,duration,name=="Reload"?duration:0));
                    UnityEditor.AssetDatabase.AddObjectToAsset(clip,controller);
                    var state=states.AddState(name); state.motion=clip;
                    if(name=="Idle") states.defaultState=state;
                }
                using(var f=new Fixture())
                {
                    var camera=cameraObject.AddComponent<Camera>();
                    var rig=new GameObject("viewmodel fixture"); rig.SetActive(false); rig.transform.SetParent(camera.transform);
                    var animator=rig.AddComponent<Animator>(); animator.runtimeAnimatorController=controller; animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
                    var leftCarrier=new GameObject("LeftCarrier").transform; leftCarrier.SetParent(rig.transform);
                    var left=new GameObject("LeftHand").transform; left.SetParent(leftCarrier);
                    var right=new GameObject("RightHand").transform; right.SetParent(rig.transform);
                    var incoming=new GameObject("IncomingCarrier").transform; incoming.SetParent(rig.transform);
                    var muzzle=new GameObject("Muzzle").transform; muzzle.SetParent(rig.transform);
                    var flash=new GameObject("Flash"); flash.transform.SetParent(muzzle); var particles=flash.AddComponent<ParticleSystem>();
                    var mesh=new GameObject("weapon mesh fixture"); mesh.transform.SetParent(rig.transform); var renderer=mesh.AddComponent<MeshRenderer>();
                    var loaded=new Renderer[12]; var fresh=new Renderer[12];
                    for(int i=0;i<12;i++)
                    {
                        var a=new GameObject("loaded "+i); a.transform.SetParent(rig.transform); loaded[i]=a.AddComponent<MeshRenderer>();
                        var b=new GameObject("incoming "+i); b.transform.SetParent(incoming); fresh[i]=b.AddComponent<MeshRenderer>();
                    }
                    var motor=Add(f.Root,"JourneyMotor"); Set(motor,"view",camera); Set(f.Actions,"motor",motor); Set(f.Actions,"shotMuzzle",muzzle);
                    var presenter=Add(rig,"WeaponPresentation"); Set(presenter,"actions",f.Actions); Set(presenter,"animator",animator);
                    Set(presenter,"weaponRenderer",renderer); Set(presenter,"leftHand",left); Set(presenter,"rightHand",right); Set(presenter,"muzzle",muzzle); Set(presenter,"muzzleFlash",particles);
                    Set(presenter,"loadedNails",loaded); Set(presenter,"incomingNails",fresh); Set(presenter,"incomingOffset",incoming); Set(presenter,"leftReloadOffset",leftCarrier); Set(presenter,"nailPitch",new Vector3(.01f,0,0));
                    for(int i=0;i<9;i++) Call(f.State,"TryFire");
                    Call(f.State,"SetControl",Enum.Parse(T("ControlMode"),"OnFoot"));
                    f.Actions.GetType().GetProperty("ReloadLoadedBefore").SetValue(f.Actions,3); f.Actions.GetType().GetProperty("ReloadPlannedAdded").SetValue(f.Actions,5);
                    Set(f.Actions,"reloadRemaining",.825f); Set(f.Actions,"fireClock",.17f); Call(f.State,"Pause");
                    rig.SetActive(true); animator.Rebind();
                    // EditMode may not deliver non-ExecuteAlways lifecycle callbacks; execute the real callbacks if needed.
                    if(presenter.GetType().GetField("subscribed",All).GetValue(presenter)==null) Call(presenter,"OnEnable");
                    Call(presenter,"LateUpdate");
                    Assert.That(animator.GetCurrentAnimatorStateInfo(0).IsName("Base Layer.Reload"),Is.True);
                    Assert.That(left.localPosition.y,Is.EqualTo(.825f).Within(.015f));
                    ((Behaviour)presenter).enabled=false;
                    if(presenter.GetType().GetField("subscribed",All).GetValue(presenter)!=null) Call(presenter,"OnDisable");
                    foreach(var nail in fresh) Assert.That(nail.enabled,Is.False);
                    ((Behaviour)presenter).enabled=true;
                    if(presenter.GetType().GetField("subscribed",All).GetValue(presenter)==null) Call(presenter,"OnEnable");
                    Call(presenter,"LateUpdate");
                    Assert.That(animator.GetCurrentAnimatorStateInfo(0).IsName("Base Layer.Reload"),Is.True);
                    Assert.That(left.localPosition.y,Is.EqualTo(.825f).Within(.015f));
                    for(int i=0;i<12;i++) { Assert.That(loaded[i].enabled,Is.EqualTo(i<3)); Assert.That(fresh[i].enabled,Is.EqualTo(i<5)); }
                    Assert.That(Get(f.Actions,"ReloadRemaining"),Is.EqualTo(.825f)); Assert.That(Get(f.Actions,"FireRemaining"),Is.EqualTo(.17f));
                    Assert.That(Get(f.State,"LoadedAmmo"),Is.EqualTo(3)); Assert.That(Get(f.State,"ReserveAmmo"),Is.EqualTo(96));
                    Assert.That(f.Actions.GetType().GetField("ReloadPresented",All).GetValue(f.Actions) is Delegate d ? d.GetInvocationList().Length : 0,Is.EqualTo(1));
                    Call(presenter,"OnDisable");
                    UnityEngine.Object.DestroyImmediate(rig);
                }
            }
            finally { UnityEngine.Object.DestroyImmediate(cameraObject); UnityEditor.AssetDatabase.DeleteAsset(path); }
        }
        [Test] public void MissingAssets_FailClosedWithoutCreatingChildren()
        {
            using(var f=new Fixture())
            foreach(var name in new[]{"WeaponPresentation","ArcPresentation","BeastWeakPointPresentation"})
            {
                var presenter=Add(f.Root,name); int count=f.Root.transform.childCount; object[] args={null};
                Assert.That(Call(presenter,"ValidateBindings",args),Is.False); Assert.That(args[0],Is.Not.Null);
                Assert.That(f.Root.transform.childCount,Is.EqualTo(count));
            }
        }
    }
}

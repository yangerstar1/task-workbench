using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
namespace DesertRV.Tests
{
    public sealed class JourneyRamGateVisualTests
    {
        sealed class Fixture : IDisposable
        {
            public readonly GameObject root=new GameObject("gate visual fixture");
            public readonly GameObject intact=new GameObject("intact decoration"), damaged=new GameObject("damaged decoration");
            public readonly BoxCollider gate;
            public readonly Behaviour visual;
            public Fixture()
            {
                gate=root.AddComponent<BoxCollider>();
                intact.transform.SetParent(root.transform);damaged.transform.SetParent(root.transform);damaged.SetActive(false);
                visual=(Behaviour)root.AddComponent(Type.GetType("DesertRV.JourneyRamGateVisual, Assembly-CSharp",true));
                Set("gate",gate);Set("intact",intact);Set("damaged",damaged);Refresh();
            }
            public void Set(string name,object value)=>visual.GetType().GetField(name).SetValue(visual,value);
            public void Refresh()=>visual.GetType().GetMethod("RefreshFromGate").Invoke(visual,null);
            // Invoke the same callback code in EditMode without claiming a running PlayMode controller.
            public void Lifecycle(string name)=>visual.GetType().GetMethod(name,BindingFlags.Instance|BindingFlags.NonPublic).Invoke(visual,null);
            public void Dispose()=>UnityEngine.Object.DestroyImmediate(root);
        }
        [Test] public void ColliderStateChangesOnlyDecoration()
        {
            using(var f=new Fixture())
            {
                Assert.That(f.intact.activeSelf,Is.True);Assert.That(f.damaged.activeSelf,Is.False);
                f.gate.enabled=false;f.Refresh();
                Assert.That(f.intact.activeSelf,Is.False);Assert.That(f.damaged.activeSelf,Is.True);
                Assert.That(f.gate.enabled,Is.False);Assert.That(f.root.activeSelf,Is.True);Assert.That(f.visual.enabled,Is.True);
                f.Refresh();Assert.That(f.gate.enabled,Is.False);
            }
        }
        [Test] public void DisableReenableAndResetRereadRealCollider()
        {
            using(var f=new Fixture())
            {
                f.visual.enabled=false;f.Lifecycle("OnDisable");f.gate.enabled=false;f.Refresh();
                Assert.That(f.intact.activeSelf,Is.True);Assert.That(f.root.activeSelf,Is.True);Assert.That(f.gate.enabled,Is.False);
                f.visual.enabled=true;f.Lifecycle("OnEnable");Assert.That(f.damaged.activeSelf,Is.True);
                f.gate.enabled=true;f.visual.enabled=false;f.Lifecycle("OnDisable");f.visual.enabled=true;f.Lifecycle("OnEnable");
                Assert.That(f.intact.activeSelf,Is.True);Assert.That(f.damaged.activeSelf,Is.False);Assert.That(f.gate.enabled,Is.True);
            }
            using(var fresh=new Fixture()) {Assert.That(fresh.intact.activeSelf,Is.True);Assert.That(fresh.damaged.activeSelf,Is.False);}
        }
        [Test] public void MissingColliderCannotPretendGateBroke()
        {
            using(var f=new Fixture())
            {f.Set("gate",null);f.Refresh();Assert.That(f.intact.activeSelf,Is.True);Assert.That(f.damaged.activeSelf,Is.False);Assert.That(f.gate.enabled,Is.True);}
        }
        [Test] public void BusinessParentAndPhysicalChildrenAreRejected()
        {
            using(var f=new Fixture())
            {
                f.Set("intact",f.root);f.gate.enabled=false;f.Refresh();Assert.That(f.root.activeSelf,Is.True);Assert.That(f.damaged.activeSelf,Is.False);
                f.Set("intact",f.intact);f.intact.AddComponent<BoxCollider>();f.Refresh();
                Assert.That(f.intact.activeSelf,Is.True);Assert.That(f.damaged.activeSelf,Is.False);Assert.That(f.gate.enabled,Is.False);
            }
        }
    }
}

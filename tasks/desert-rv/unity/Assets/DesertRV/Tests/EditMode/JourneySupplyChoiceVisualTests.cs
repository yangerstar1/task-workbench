using System;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class JourneySupplyChoiceVisualTests
    {
        sealed class Fixture : IDisposable
        {
            public readonly GameObject root=new GameObject("choice visual fixture");
            public readonly GameObject board,closedBoard,a,b,closedA,closedB;
            public readonly Component view;
            public readonly object state;
            public Fixture()
            {
                view=root.AddComponent(Production.Type("JourneySupplyChoiceVisual"));
                board=Child("directions");closedBoard=Child("completed directions");a=Child("ammo offer");b=Child("kit offer");
                closedA=Child("ammo sealed");closedB=Child("kit sealed");closedBoard.SetActive(false);closedA.SetActive(false);closedB.SetActive(false);
                Set(view,"region",1);Set(view,"choiceGroup","region-1/optional-choice");Set(view,"availableBoard",board);Set(view,"sealedBoard",closedBoard);
                var type=Production.Type("JourneySupplyChoiceVisual+Option");var options=Array.CreateInstance(type,2);
                options.SetValue(Option(type,"a",a,closedA),0);options.SetValue(Option(type,"b",b,closedB),1);Set(view,"options",options);
                state=Production.Session();Production.Call(state,"SetControl",Production.Enum("ControlMode","OnFoot"));Refresh();
            }
            GameObject Child(string name){var child=new GameObject(name);child.transform.SetParent(root.transform,false);return child;}
            static object Option(Type type,string id,GameObject available,GameObject closed)
            {var o=Activator.CreateInstance(type);Set(o,"id",id);Set(o,"availableSign",available);Set(o,"sealedSign",closed);return o;}
            public static void Set(object target,string field,object value)=>target.GetType().GetField(field).SetValue(target,value);
            public void Refresh()=>Production.Call(view,"Refresh",state);
            public bool Take(string id,string kind="Ammo",int amount=12)=> (bool)Production.Call(state,"TryCollectSupply",1,Production.Get<int>(state,"Generation"),id,Production.Enum("SupplyKind",kind),amount,"region-1/optional-choice");
            public void Dispose()=>UnityEngine.Object.DestroyImmediate(root);
        }
        [Test] public void AuthoritativeChoiceSealsOtherOfferAndDoesNotGrantExtraResources()
        {
            using(var f=new Fixture())
            {
                Assert.That(f.Take("a"),Is.True);f.Refresh();f.Refresh();
                Assert.That(f.a.activeSelf,Is.False);Assert.That(f.b.activeSelf,Is.False);Assert.That(f.closedA.activeSelf,Is.False);Assert.That(f.closedB.activeSelf,Is.True);
                Assert.That(f.board.activeSelf,Is.False);Assert.That(f.closedBoard.activeSelf,Is.True);Assert.That(f.Take("b","RepairKit",1),Is.False);
                Assert.That(Production.Get<int>(f.state,"ReserveAmmo"),Is.EqualTo(108));Assert.That(Production.Get<int>(f.state,"RepairKits"),Is.EqualTo(2));
                Assert.That(Production.Get<int>(f.state,"LoadedAmmo"),Is.EqualTo(12));Assert.That(Production.Get<int>(f.state,"PlayerHealth"),Is.EqualTo(100));
                Assert.That(Production.Get<int>(f.state,"VehicleHealth"),Is.EqualTo(300));Assert.That(Production.Get<double>(f.state,"StormElapsedSeconds"),Is.Zero);
            }
        }
        [Test] public void FullCapacityLeavesBothOffersOpen()
        {
            using(var f=new Fixture())
            {
                Production.Yes(f.state,"TryCollectSupply",1,1,"outside-a",Production.Enum("SupplyKind","Ammo"),24,null);
                Production.Yes(f.state,"TryCollectSupply",1,1,"outside-b",Production.Enum("SupplyKind","Ammo"),24,null);
                Assert.That(f.Take("a"),Is.False);f.Refresh();Assert.That(f.a.activeSelf&&f.b.activeSelf&&f.board.activeSelf,Is.True);
                Assert.That(f.closedA.activeSelf||f.closedB.activeSelf||f.closedBoard.activeSelf,Is.False);
            }
        }
        [Test] public void RestartRefreshRestoresOfferLabelsWithoutResettingGameplay()
        {
            using(var f=new Fixture())
            {
                Assert.That(f.Take("b","RepairKit",1),Is.True);f.Refresh();Assert.That(f.closedA.activeSelf,Is.True);
                Production.Call(f.state,"DamageVehicle",300);Production.Yes(f.state,"RestartJourney");f.Refresh();
                Assert.That(f.a.activeSelf&&f.b.activeSelf&&f.board.activeSelf,Is.True);Assert.That(f.closedA.activeSelf||f.closedB.activeSelf||f.closedBoard.activeSelf,Is.False);
                Assert.That(Production.Get<int>(f.state,"RepairKits"),Is.EqualTo(2));Assert.That(Production.Get<int>(f.state,"ReserveAmmo"),Is.EqualTo(96));
            }
        }
        [Test] public void InvalidBusinessRootOrPhysicalDecorationFailsWithoutDisablingAnything()
        {
            using(var f=new Fixture())
            {
                Fixture.Set(f.view,"availableBoard",f.root);Assert.That(f.Take("a"),Is.True);f.Refresh();
                Assert.That(f.root.activeSelf&&f.board.activeSelf&&f.b.activeSelf,Is.True);
                Fixture.Set(f.view,"availableBoard",f.board);var collider=f.b.AddComponent<BoxCollider>();f.Refresh();
                Assert.That(f.b.activeSelf&&f.board.activeSelf&&collider.enabled,Is.True);Assert.That(f.closedBoard.activeSelf,Is.False);
                UnityEngine.Object.DestroyImmediate(collider);
                var business=new GameObject("inactive business child");business.SetActive(false);business.transform.SetParent(f.b.transform,false);
                business.AddComponent(Production.Type("JourneyMotor"));f.Refresh();
                Assert.That(f.b.activeSelf&&f.board.activeSelf,Is.True);Assert.That(f.closedBoard.activeSelf,Is.False);
                Assert.That(business.activeSelf,Is.False,"Presentation must not change the business child either.");
            }
        }
        [Test] public void MissingStateWrongRegionAndDisabledViewDoNotInventAChoice()
        {
            using(var f=new Fixture())
            {
                Production.Call(f.view,"Refresh",new object[]{null});Assert.That(f.board.activeSelf,Is.True);
                Assert.That(f.Take("a"),Is.True);Fixture.Set(f.view,"region",2);f.Refresh();Assert.That(f.board.activeSelf,Is.True);
                Fixture.Set(f.view,"region",1);((Behaviour)f.view).enabled=false;f.Refresh();Assert.That(f.board.activeSelf,Is.True);
                ((Behaviour)f.view).enabled=true;f.Refresh();Assert.That(f.closedBoard.activeSelf,Is.True);
            }
        }
    }
}

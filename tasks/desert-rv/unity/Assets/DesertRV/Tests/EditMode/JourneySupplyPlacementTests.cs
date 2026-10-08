using System;
using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class JourneySupplyPlacementTests
    {
        static Array Plan(int region)
        {
            var author=Type.GetType("DesertRV.Editor.JourneySceneAuthoring, Assembly-CSharp-Editor",true);
            return (Array)author.GetMethod("SupplyPlacements",BindingFlags.Public|BindingFlags.Static).Invoke(null,new object[]{region});
        }
        static T Field<T>(object row,string name)=>(T)row.GetType().GetField(name).GetValue(row);
        [Test] public void EveryRegionHasExactlyOneOptionalAmmoVersusRepairChoice()
        {
            var ids=new HashSet<string>();var groups=new HashSet<string>();
            for(int region=1;region<=3;region++)
            {
                var rows=Plan(region);Assert.That(rows.Length,Is.EqualTo(2));string group=Field<string>(rows.GetValue(0),"group");Assert.That(groups.Add(group),Is.True);
                foreach(var p in rows)
                {
                    Assert.That(Field<int>(p,"region"),Is.EqualTo(region));Assert.That(ids.Add(Field<string>(p,"id")),Is.True);Assert.That(Field<string>(p,"group"),Is.EqualTo(group));
                    Assert.That(Field<string>(p,"label"),Is.Not.Empty);Assert.That(Field<string>(p,"risk"),Is.Not.Empty);Assert.That(Field<string>(p,"landmark"),Is.Not.Empty);
                }
                Assert.That(Field<object>(rows.GetValue(0),"kind").ToString(),Is.EqualTo("Ammo"));
                Assert.That(Field<int>(rows.GetValue(0),"amount"),Is.EqualTo(region==1?12:18));
                Assert.That(Field<object>(rows.GetValue(1),"kind").ToString(),Is.EqualTo("RepairKit"));Assert.That(Field<int>(rows.GetValue(1),"amount"),Is.EqualTo(1));
                Assert.That(Field<string>(rows.GetValue(1),"label"),Does.Contain("维修包"));
            }
        }
        [Test] public void AllCacheAndStandingPointsRemainOutsideDrivingCorridorAndBeforeExit()
        {
            for(int region=1;region<=3;region++)foreach(var p in Plan(region))
            {
                var at=Field<Vector3>(p,"at");var stand=Field<Vector3>(p,"stand");
                Assert.That(Mathf.Abs(at.x),Is.GreaterThan(5.8f));Assert.That(Mathf.Abs(stand.x),Is.GreaterThan(4.3f));
                Assert.That(at.z,Is.InRange(-2f,32f));Assert.That(stand.z,Is.InRange(-3f,32f));Assert.That(Vector3.Distance(at,stand),Is.EqualTo(1.25f).Within(.001f));
                Assert.That(Mathf.Abs(at.x),Is.LessThan(15f));
            }
        }
        [Test] public void PlacementValuesAreFreshAndCannotMutateTheNextAuthoringRun()
        {
            var rows=Plan(2);rows.GetValue(0).GetType().GetField("amount").SetValue(rows.GetValue(0),100);
            Assert.That(Field<int>(Plan(2).GetValue(0),"amount"),Is.EqualTo(18));
        }
    }
}

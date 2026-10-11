using System;
using System.Collections;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class JourneyMobileHudTests
    {
        const BindingFlags Instance=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
        static Type T(string name)=>Type.GetType("DesertRV."+name+", Assembly-CSharp",true);
        static object E(string name,string value)=>Enum.Parse(T(name),value);
        static object Call(object target,string method,params object[] args)=>target.GetType().GetMethod(method,Instance).Invoke(target,args);
        static object Get(object target,string property)=>target.GetType().GetProperty(property,Instance).GetValue(target);
        static void Set(object target,string field,object value)=>target.GetType().GetField(field,Instance).SetValue(target,value);
        static Rect Box(object layout,string field)=>(Rect)layout.GetType().GetField(field).GetValue(layout);
        [TestCase(568f,296f,TestName="LayoutKeepsTargetsSeparatedAndAimClear_SmallPhone")]
        [TestCase(608f,348f,TestName="LayoutKeepsTargetsSeparatedAndAimClear_Compact")]
        [TestCase(736f,348f,TestName="LayoutKeepsTargetsSeparatedAndAimClear_Wide")]
        [TestCase(853.3333f,480f,TestName="LayoutKeepsTargetsSeparatedAndAimClear_Desktop")]
        public void LayoutKeepsTargetsSeparatedAndAimClear(float width,float height)
        {
            var layout=Activator.CreateInstance(T("JourneyHudLayout"),new object[]{new Vector2(width,height),false});
            Assert.That(Get(layout,"WithinSupportedEnvelope"),Is.True);
            var safe=new Rect(0,0,width,height);
            foreach(string mode in new[]{"foot","drive"})
            {
                string[] names=mode=="foot"?new[]{"Move","Interact","Fire","Reload"}:new[]{"Move","Interact","Accelerate","Brake"};
                var targets=new Rect[5];targets[0]=Box(layout,"Pause");
                for(int i=0;i<names.Length;i++)targets[i+1]=(Rect)Call(layout,"Control",E("TouchControl",names[i]));
                for(int i=0;i<targets.Length;i++)
                {
                    Assert.That(targets[i].width,Is.GreaterThanOrEqualTo(48));Assert.That(targets[i].height,Is.GreaterThanOrEqualTo(48));
                    Assert.That(targets[i].xMin,Is.GreaterThanOrEqualTo(safe.xMin));Assert.That(targets[i].yMin,Is.GreaterThanOrEqualTo(safe.yMin));
                    Assert.That(targets[i].xMax,Is.LessThanOrEqualTo(safe.xMax));Assert.That(targets[i].yMax,Is.LessThanOrEqualTo(safe.yMax));
                    for(int j=i+1;j<targets.Length;j++)Assert.That(targets[i].Overlaps(targets[j]),Is.False,mode+" target collision");
                    foreach(string name in new[]{"Notice","Prompt","Progress"})Assert.That(targets[i].Overlaps(Box(layout,name)),Is.False,name+" blocks a target");
                }
            }
            var aim=new Rect(width*.5f-36,height*.5f-36,72,72);
            foreach(string name in new[]{"Status","Objective","Storm","Damage","RearThreat","Notice","Prompt","Progress"})
                Assert.That(Box(layout,name).Overlaps(aim),Is.False,name+" obscures aim");
        }
        [Test] public void AndroidScaleRejectsInvalidMetricsAndTracksRenderPixels()
        {
            var method=T("JourneyHudLayout").GetMethod("AndroidScale");
            float Scale(float density,int render,int display)=>(float)method.Invoke(null,new object[]{density,render,display});
            Assert.That(Scale(3,1920,1920),Is.EqualTo(3));Assert.That(Scale(3,960,1920),Is.EqualTo(1.5f));
            foreach(float invalid in new[]{float.NaN,float.PositiveInfinity,-1,0,.1f,20})Assert.That(Scale(invalid,1920,1920),Is.Zero);
            Assert.That(Scale(3,1920,0),Is.Zero);Assert.That(Scale(3,1920,16001),Is.Zero);Assert.That(Scale(3,300,4000),Is.Zero);
        }
        [Test] public void SemanticLineBreaksRetainCableCostRiskAndNumbers()
        {
            var layout=T("JourneyHudLayout");
            foreach(string value in new[]{"拔除电缆 · 暂停充能，敌人仍攻击","修理房车 · 只修车况，消耗 1 包","钉弹最多 +18 · 二选一，另一箱封存","无法上车 · 先拔除电缆"})
            {
                string formatted=(string)layout.GetMethod("PromptLines").Invoke(null,new object[]{value});
                Assert.That(formatted.Replace("\n"," · "),Is.EqualTo(value));
            }
            string objective=(string)layout.GetMethod("ObjectiveLines").Invoke(null,new object[]{"拔除电缆，驾驶房车驶入安全区"});
            Assert.That(objective,Is.EqualTo("拔除电缆\n驾驶房车驶入安全区"));
        }
        [Test] public void InteractionLabelsUseExistingSelectorAndRemainFourCharacters()
        {
            var root=new GameObject("HUD semantic fixture");root.SetActive(false);
            try
            {
                var session=root.AddComponent(T("JourneySession"));var state=Activator.CreateInstance(T("SessionState"));
                Set(session,"<State>k__BackingField",state);
                foreach(string name in new[]{"JourneyActions","FirstStationJourney"})
                {
                    var actions=root.AddComponent(T(name));Set(actions,"journey",session);
                    for(int selector=0;selector<=7;selector++)
                    {
                        Set(actions,"interaction",selector);string label=(string)Get(actions,"InteractionLabel");
                        Assert.That(label.Length,Is.InRange(1,4));
                        Assert.That(actions.GetType().GetField("interaction",Instance).GetValue(actions),Is.EqualTo(selector));
                    }
                    Set(actions,"interaction",4);Assert.That(Get(actions,"InteractionLabel"),Is.EqualTo("上车"));
                    Set(actions,"interaction",7);Assert.That(Get(actions,"InteractionLabel"),Is.EqualTo("领取补给"));
                }
                Assert.That(Get(state,"Status").ToString(),Is.EqualTo("Menu"));
            }
            finally{UnityEngine.Object.DestroyImmediate(root);}
        }
        [Test] public void PauseRegionConsumesPointerAndClearRegionsResetsIt()
        {
            var root=new GameObject("pause hit arbitration");
            try
            {
                var adapter=root.AddComponent(T("MobileInputAdapter"));Call(adapter,"SetContext",E("TouchContext","OnFoot"));
                Rect safe=Screen.safeArea;var pause=new Rect(safe.center.x-24,safe.center.y-24,48,48);
                Call(adapter,"SetRegion",E("TouchControl","Look"),safe);Call(adapter,"SetUiBlocker",pause);
                Call(adapter,"Begin",17,pause.center);
                var owners=(IDictionary)adapter.GetType().GetField("owners",Instance).GetValue(adapter);
                Assert.That(owners.Count,Is.Zero);
                Call(adapter,"ClearRegions");Call(adapter,"SetRegion",E("TouchControl","Look"),safe);Call(adapter,"Begin",18,pause.center);
                Assert.That(owners.Count,Is.EqualTo(1));Assert.That(owners[18].ToString(),Is.EqualTo("Look"));
            }
            finally{UnityEngine.Object.DestroyImmediate(root);}
        }
        [Test] public void ActionPriorityAndTwoThumbOwnershipSurviveDragging()
        {
            var root=new GameObject("two-thumb arbitration");
            try
            {
                var adapter=root.AddComponent(T("MobileInputAdapter"));Call(adapter,"SetContext",E("TouchContext","OnFoot"));
                Rect safe=Screen.safeArea;
                var move=new Rect(safe.xMin+8,safe.yMin+8,64,64);var fire=new Rect(safe.xMax-80,safe.yMin+8,64,64);
                Call(adapter,"SetRegion",E("TouchControl","Look"),safe);Call(adapter,"SetRegion",E("TouchControl","Move"),move);Call(adapter,"SetRegion",E("TouchControl","Fire"),fire);
                Call(adapter,"Begin",31,move.center);Call(adapter,"Begin",32,fire.center);
                var owners=(IDictionary)adapter.GetType().GetField("owners",Instance).GetValue(adapter);
                Assert.That(owners[31].ToString(),Is.EqualTo("Move"));Assert.That(owners[32].ToString(),Is.EqualTo("Fire"));
                Call(adapter,"Move",31,fire.center,Vector2.right);Assert.That(owners[31].ToString(),Is.EqualTo("Move"));
                Call(adapter,"ReleaseAll");Assert.That(owners.Count,Is.Zero);Assert.That(Get(Get(adapter,"State"),"FireHeld"),Is.False);
            }
            finally{UnityEngine.Object.DestroyImmediate(root);}
        }
        [Test] public void RenderProductionHudAndMeasureEveryVisibleLabel()
        {
            var capture=Type.GetType("DesertRV.Editor.JourneyHudCapture, Assembly-CSharp-Editor",true);
            capture.GetMethod("CaptureAndMeasure").Invoke(null,null);
        }
    }
}

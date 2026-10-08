using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace DesertRV.Tests
{
    public sealed class WeaponArmReachTests
    {
        const BindingFlags All=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance;
        static Type T(string n)=>Type.GetType("DesertRV."+n+", Assembly-CSharp",true);
        static void Set(object o,string n,object v)=>o.GetType().GetField(n,All).SetValue(o,v);
        static object F(object o,string n)=>o.GetType().GetField(n,All).GetValue(o);
        static object P(object o,string n)=>o.GetType().GetProperty(n,All).GetValue(o);
        static object Call(object o,string n,params object[] args)=>o.GetType().GetMethod(n,All).Invoke(o,args);
        static Transform Child(string n,Transform p) {var g=new GameObject(n);g.transform.SetParent(p,false);return g.transform;}
        sealed class Fixture:IDisposable
        {
            public GameObject Root=new GameObject("synthetic arm solver fixture");
            public Component Reach;
            public Transform Rig,Carrier;
            public object[] Bindings=new object[2];
            public Transform[] Upper=new Transform[2],Fore=new Transform[2],Tip=new Transform[2],Target=new Transform[2],Hand=new Transform[2];
            public Vector3[] TargetRest=new Vector3[2];
            Mesh source;
            public Fixture()
            {
                Root.SetActive(false);var animator=Root.AddComponent<Animator>();Rig=Child("measured rig",Root.transform);
                Rig.localRotation=Quaternion.Euler(15,31,-19);Rig.localScale=Vector3.one*.8f;Carrier=Child("LeftReloadOffset",Rig);
                Reach=Root.AddComponent(T("WeaponArmReach"));Set(Reach,"animator",animator);Set(Reach,"rigRoot",Rig);
                source=new Mesh {name="synthetic calibration provenance"};Set(Reach,"calibratedSourceModel",source);Set(Reach,"sourceSha256",new string('a',64));
                Set(Reach,"positionToleranceRig",.0001f);Set(Reach,"numericToleranceRig",.000001f);
                for(int i=0;i<2;i++)
                {
                    float l1=i==0?.37576588f:.40360872f,l2=.33503731f;
                    Upper[i]=Child("upper "+i,Rig);Upper[i].localPosition=new Vector3(i==0?-.2f:.2f,0,0);Upper[i].localRotation=Quaternion.Euler(4,i==0?12:-12,9);
                    Fore[i]=Child("fore "+i,Upper[i]);Fore[i].localPosition=Vector3.right*l1;Fore[i].localRotation=Quaternion.Euler(0,25,0);
                    Tip[i]=Child("tip "+i,Fore[i]);Tip[i].localPosition=Vector3.forward*l2;
                    Hand[i]=Child("hand "+i,i==0?Carrier:Rig);Hand[i].position=Tip[i].position;Target[i]=Child("target "+i,Hand[i]);TargetRest[i]=Hand[i].localPosition;
                    var b=Activator.CreateInstance(T("ArmReachBinding"));Bindings[i]=b;
                    Set(b,"upperArm",Upper[i]);Set(b,"forearm",Fore[i]);Set(b,"wristTip",Tip[i]);Set(b,"wristTarget",Target[i]);Set(b,"calibrated",true);
                    Set(b,"upperLengthRig",l1);Set(b,"foreLengthRig",l2);Set(b,"sourceUpperLength",l1);Set(b,"sourceForeLength",l2);Set(b,"sourceToRigScale",1f);
                    Set(b,"upperAxisLocal",Vector3.right);Set(b,"foreAxisLocal",Vector3.forward);
                    Vector3 s=Rig.InverseTransformPoint(Upper[i].position),e=Rig.InverseTransformPoint(Fore[i].position),w=Rig.InverseTransformPoint(Tip[i].position);
                    Set(b,"poleRigLocal",Vector3.ProjectOnPlane(e-s,(w-s).normalized).normalized);
                    Set(b,"shoulderLocal",Upper[i].localPosition);Set(b,"elbowLocal",Fore[i].localPosition);Set(b,"tipLocal",Tip[i].localPosition);
                    Set(b,"upperScale",Vector3.one);Set(b,"foreScale",Vector3.one);Set(b,"upperBindRotation",Upper[i].localRotation);Set(b,"foreBindRotation",Fore[i].localRotation);Set(b,"neutralPoseEvidence","Synthetic NUnit neutral; not an imported asset");
                    Set(Reach,i==0?"left":"right",b);
                }
            }
            public void Sample(float phase,int before)
            {
                Call(Reach,"RestoreBindPose"); // Models the required pre-Animator reset.
                for(int i=0;i<2;i++)
                {
                    Upper[i].localRotation=(Quaternion)F(Bindings[i],"upperBindRotation")*Quaternion.AngleAxis(Mathf.Sin(phase*6.28f)*3,Vector3.right);
                    Hand[i].localPosition=TargetRest[i]+Vector3.up*(Mathf.Sin(phase*6.28f)*.005f);
                }
                float grip=(float)T("ReloadPresentationPlan").GetMethod("GripWeight").Invoke(null,new object[]{phase});
                Carrier.localPosition=Vector3.up*(before*.001f*grip); // Absolute count offset exactly once.
            }
            public string LastReason;
            public bool Solve()
            {
                object[] args={null};bool ok=(bool)Call(Reach,"TrySolveBoth",args);
                string Metrics(string side)
                {
                    var v=P(Reach,side+"Diagnostics");
                    return side+"="+F(v,"reason")+" gap="+F(v,"wristGap")+" distance="+F(v,"targetDistance")+
                        " upper="+F(v,"upperLength")+"/"+F(v,"expectedUpperLength")+" fore="+F(v,"foreLength")+"/"+F(v,"expectedForeLength")+
                        " shoulder="+F(v,"shoulderDrift")+" target="+F(v,"targetDrift");
                }
                LastReason=(string)args[0]+"; "+Metrics("Left")+"; "+Metrics("Right");return ok;
            }
            public void Dispose() {UnityEngine.Object.DestroyImmediate(Root);UnityEngine.Object.DestroyImmediate(source);}
        }
        [Test] public void Math_RejectsUnreachableZeroDistanceAndUnresolvedPole()
        {
            bool Elbow(Vector3 target,float a,float b,Vector3 pole)
            {object[] args={Vector3.zero,Vector3.right,target,a,b,pole,.000001f,null,null,null};return (bool)T("TwoBoneArmSolver").GetMethod("TryElbow").Invoke(null,args);}
            Assert.That(Elbow(Vector3.right*3,1,1,Vector3.up),Is.False);
            Assert.That(Elbow(Vector3.right*.1f,1,.2f,Vector3.up),Is.False);
            Assert.That(Elbow(Vector3.zero,1,1,Vector3.up),Is.False);
            Assert.That(Elbow(Vector3.right,1,1,Vector3.right),Is.False);
            Assert.That(Elbow(new Vector3(float.NaN,0,0),1,1,Vector3.up),Is.False);
            Assert.That(Elbow(Vector3.right*2,1,1,Vector3.up),Is.True,"Straight reach uses the calibrated pole, not a guessed axis.");
            // Tight seam budgets require real tiny swings, including the near-parallel dot band.
            foreach(float angle in new[]{.0005f,-.0005f,.0001f,3.14109265f})
            {
                var target=new Vector3(Mathf.Cos(angle),Mathf.Sin(angle),0);
                object[] args={Vector3.right,target,Vector3.forward,.000001f,null};
                Assert.That((bool)T("TwoBoneArmSolver").GetMethod("TrySwing").Invoke(null,args),Is.True);
                Assert.That(Vector3.Distance((Quaternion)args[4]*Vector3.right,target),Is.LessThan(.000001f),"radians="+angle);
            }
        }
        [Test] public void Synthetic600ArmSamples_PreserveLengthsShouldersAndHandTargets()
        {
            using(var f=new Fixture())
            {
                int samples=0;
                foreach(int before in new[]{0,3,11}) for(int frame=1;frame<=100;frame++)
                {
                    f.Sample((frame-1)/99f,before);var shoulder=new[]{f.Upper[0].position,f.Upper[1].position};var target=new[]{f.Target[0].position,f.Target[1].position};
                    Assert.That(f.Solve(),Is.True,"Synthetic frame "+frame+" count "+before+" "+f.LastReason);
                    for(int i=0;i<2;i++)
                    {
                        Assert.That(Vector3.Distance(f.Tip[i].position,target[i]),Is.LessThan(.0001f));
                        Assert.That(Vector3.Distance(f.Upper[i].position,shoulder[i]),Is.LessThan(.000001f));
                        Assert.That(Vector3.Distance(f.Target[i].position,target[i]),Is.LessThan(.000001f));
                        Assert.That(f.Fore[i].localPosition,Is.EqualTo(F(f.Bindings[i],"elbowLocal")));Assert.That(f.Upper[i].localScale,Is.EqualTo(Vector3.one));Assert.That(f.Fore[i].localScale,Is.EqualTo(Vector3.one));samples++;
                    }
                }
                Assert.That(samples,Is.EqualTo(600));
            }
        }
        [Test] public void PausedRepeatedSamples_DoNotAccumulateRotationOrCountOffset()
        {
            using(var f=new Fixture()) foreach(int frame in new[]{35,60,68})
            {
                float phase=(frame-1)/99f;f.Sample(phase,11);Assert.That(f.Solve(),Is.True,f.LastReason);
                var up=f.Upper[0].localRotation;var fore=f.Fore[0].localRotation;var carrier=f.Carrier.localPosition;var target=f.Target[0].position;
                for(int repeat=0;repeat<50;repeat++)
                {
                    f.Sample(phase,11);Assert.That(f.Solve(),Is.True,f.LastReason);
                    Assert.That(Quaternion.Angle(up,f.Upper[0].localRotation),Is.LessThan(.02f));Assert.That(Quaternion.Angle(fore,f.Fore[0].localRotation),Is.LessThan(.02f));
                    Assert.That(f.Carrier.localPosition,Is.EqualTo(carrier));Assert.That(Vector3.Distance(f.Target[0].position,target),Is.LessThan(.000001f));
                }
            }
        }
        [Test] public void FailedSecondArm_RollsBackBothWithoutStretchOrTargetClamp()
        {
            using(var f=new Fixture())
            {
                f.Sample(.5f,3);f.Hand[1].localPosition+=Vector3.up*5;var left=f.Upper[0].localRotation;var right=f.Fore[1].localRotation;var target=f.Target[1].position;
                Assert.That(f.Solve(),Is.False);Assert.That(P(f.Reach,"LastSolveAccepted"),Is.False);
                Assert.That(Quaternion.Angle(left,f.Upper[0].localRotation),Is.LessThan(.001f));Assert.That(Quaternion.Angle(right,f.Fore[1].localRotation),Is.LessThan(.001f));Assert.That(f.Target[1].position,Is.EqualTo(target));
            }
        }
        [Test] public void Binding_FailsWithoutCalibrationOrWithScaleAxisJointChanges()
        {
            using(var f=new Fixture())
            {
                bool Valid(){object[] a={null};return (bool)Call(f.Reach,"ValidateBindings",a);}
                Assert.That(Valid(),Is.True);Set(f.Bindings[0],"calibrated",false);Assert.That(Valid(),Is.False);Set(f.Bindings[0],"calibrated",true);
                var axis=F(f.Bindings[0],"upperAxisLocal");Set(f.Bindings[0],"upperAxisLocal",Vector3.zero);Assert.That(Valid(),Is.False);Set(f.Bindings[0],"upperAxisLocal",axis);
                f.Rig.localScale=new Vector3(.8f,1,.8f);Assert.That(Valid(),Is.False);f.Rig.localScale=Vector3.one*.8f;
                f.Fore[0].localPosition+=Vector3.right*.01f;Assert.That(Valid(),Is.False);f.Fore[0].localPosition=(Vector3)F(f.Bindings[0],"elbowLocal");
                foreach(string node in new[]{"upperArm","forearm","wristTip","wristTarget"})
                { var original=F(f.Bindings[1],node);Set(f.Bindings[1],node,F(f.Bindings[0],node));Assert.That(Valid(),Is.False,node+" cannot cross-bind sides");Set(f.Bindings[1],node,original); }
                var target=F(f.Bindings[1],"wristTarget");Set(f.Bindings[1],"wristTarget",f.Tip[0]);Assert.That(Valid(),Is.False);Set(f.Bindings[1],"wristTarget",target);
            }
        }
        [Test] public void RestoreAndDisable_ClearCorrectionsWithoutMovingHandOrTarget()
        {
            using(var f=new Fixture())
            {
                f.Sample(.5f,11);Assert.That(f.Solve(),Is.True,f.LastReason);var target=f.Target[0].position;
                Call(f.Reach,"RestoreBindPose");
                Assert.That(Quaternion.Angle(f.Upper[0].localRotation,(Quaternion)F(f.Bindings[0],"upperBindRotation")),Is.LessThan(.001f));Assert.That(f.Target[0].position,Is.EqualTo(target));
                f.Sample(.5f,11);Assert.That(f.Solve(),Is.True,f.LastReason);Call(f.Reach,"OnDisable");Assert.That(P(f.Reach,"LastSolveAccepted"),Is.False);
                Assert.That(Quaternion.Angle(f.Fore[0].localRotation,(Quaternion)F(f.Bindings[0],"foreBindRotation")),Is.LessThan(.001f));
            }
        }
        [Test] public void FailureReporting_IsDeduplicatedButCountsRejectedSamples()
        {
            var go=new GameObject("failure reporting fixture");go.SetActive(false);
            try
            {
                var presenter=go.AddComponent(T("WeaponPresentation"));
                LogAssert.Expect(LogType.Error,"Arm reach failed (visual rejected): synthetic unreachable");
                Call(presenter,"ReportArmFailure","synthetic unreachable");Call(presenter,"ReportArmFailure","synthetic unreachable");
                Assert.That(P(presenter,"ArmReachRejectedSamples"),Is.EqualTo(2));Assert.That(P(presenter,"ArmReachFailure"),Is.EqualTo("synthetic unreachable"));
            }
            finally {UnityEngine.Object.DestroyImmediate(go);}
        }
    }
}

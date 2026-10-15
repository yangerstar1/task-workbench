using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using IPhase=UnityEngine.InputSystem.TouchPhase;

namespace Lottery.G3.PlayMode.Tests
{
    public sealed partial class G3PlayTests
    {
        const string PhoneCase="Lottery.G3.PlayMode.Tests.G3PlayTests.PhoneReturnFunctionalObservationOnly";
        [Serializable] sealed class PhoneRouteRow
        {
            public int segment,frames; public string outcome;
            public double elapsedMs; public float pathMeters,maxFrameWall,remaining;
            public float[] position;
        }
        [Serializable] sealed class PhoneReceipt
        {
            public int schemaVersion=1; public string scope="PHONE_RETURN_FUNCTIONAL_DIAGNOSTIC_NOT_G3_PASS",testIdentity=PhoneCase;
            public string sourceCommit,reviewedCandidateCommit,runId,runAttempt,renderer="unknown";
            public string status="INCONCLUSIVE",stage="SETUP",timing="NOT_OBSERVED";
            public bool setupComplete,routeComplete,cleanupComplete,deadlineExceeded,phoneOpened,cameraRestored,finalSeated;
            public double elapsedMs; public int mode=-1; public bool phoneFocused;
            public string initialStateHash="UNAVAILABLE",stateHash="UNAVAILABLE",initialTicketHash="UNAVAILABLE",ticketHash="UNAVAILABLE";
            public long initialPaidMinor=-1,paidMinor=-1; public double initialScratch=-1,scratch=-1;
            public float[] position=new float[3],cameraPositionBefore=new float[3],cameraPositionAfter=new float[3],cameraRotationBefore=new float[4],cameraRotationAfter=new float[4];
            public List<PhoneRouteRow> routes=new List<PhoneRouteRow>();
        }
        PhoneReceipt phoneReceipt;
        System.Diagnostics.Stopwatch phoneClock;
        string PhonePath=>Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts/phone-return-probe/phone-return.json"));
        static string PhoneArg(string key){var a=Environment.GetCommandLineArgs();int i=Array.IndexOf(a,key);return i>=0&&i+1<a.Length?a[i+1]:"";}
        static float[] PhoneVector(Vector3 v)=>new[]{v.x,v.y,v.z};
        static float[] PhoneRotation(Quaternion q)=>new[]{q.x,q.y,q.z,q.w};
        static string PhoneHash(string s){using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(Encoding.UTF8.GetBytes(s))).Replace("-","").ToLowerInvariant();}
        void BeginPhoneDiagnostic()
        {
            phoneReceipt=null;phoneClock=null;
            if(TestContext.CurrentContext.Test.FullName!=PhoneCase)return;
            phoneClock=System.Diagnostics.Stopwatch.StartNew();
            Assert.That(PhoneArg("-g3PhoneReturnDiagnostic"),Is.EqualTo("1"));
            Assert.That(PhoneArg("-testFilter"),Is.EqualTo("^"+System.Text.RegularExpressions.Regex.Escape(PhoneCase)+"$"));
            Assert.That(PhoneArg("-assemblyNames"),Is.EqualTo("Lottery.G3.PlayMode.Tests"));
            phoneReceipt=new PhoneReceipt{sourceCommit=PhoneArg("-probeCommit"),reviewedCandidateCommit=PhoneArg("-probeReviewedCommit"),runId=PhoneArg("-probeRunId"),runAttempt=PhoneArg("-probeRunAttempt")};
            // Raw driver/device text is inspected in memory only and never exported.
            string device=SystemInfo.graphicsDeviceName;
            phoneReceipt.renderer=string.IsNullOrEmpty(device)?"unknown":device.IndexOf("llvmpipe",StringComparison.OrdinalIgnoreCase)>=0?"llvmpipe":"other";
            PersistPhoneDiagnostic();
        }
        void CheckPhoneDeadline()
        {
            if(phoneReceipt==null)return;
            if(phoneClock.Elapsed.TotalSeconds>=180)
            {
                phoneReceipt.deadlineExceeded=true;phoneReceipt.status="INCONCLUSIVE";PersistPhoneDiagnostic();
                Assert.Fail("PHONE_RETURN_FIXED_180_SECOND_CASE_DEADLINE");
            }
        }
        void PersistPhoneDiagnostic()
        {
            if(phoneReceipt==null)return;
            phoneReceipt.elapsedMs=phoneClock.Elapsed.TotalMilliseconds;
            string json=JsonUtility.ToJson(phoneReceipt);Assert.That(Encoding.UTF8.GetByteCount(json),Is.LessThanOrEqualTo(65536));
            Directory.CreateDirectory(Path.GetDirectoryName(PhonePath));
            string temporary=PhonePath+".tmp";
            using(var stream=new FileStream(temporary,FileMode.Create,FileAccess.Write,FileShare.None))
            {var bytes=Encoding.UTF8.GetBytes(json);stream.Write(bytes,0,bytes.Length);stream.Flush(true);}
            if(File.Exists(PhonePath))File.Replace(temporary,PhonePath,null);else File.Move(temporary,PhonePath);
        }
        void PhoneSnapshot(string stage)
        {
            phoneReceipt.stage=stage;
            if(app!=null)
            {
                var state=State;var ticket=state.CurrentTicket;
                phoneReceipt.stateHash=StateCodec.ComputeHash(state);
                phoneReceipt.ticketHash=ticket==null?"UNAVAILABLE":PhoneHash(ticket.Id);
                phoneReceipt.paidMinor=ticket==null?-1:ticket.PriceMinor;
                phoneReceipt.scratch=ticket==null?-1:ticket.Scratch.CellCoverage(3);
                phoneReceipt.position=PhoneVector(P.View.Walk.SavedPosition);
                phoneReceipt.mode=(int)Router.Mode;phoneReceipt.phoneFocused=P.View.Phone.IsFocused;
                phoneReceipt.finalSeated=!P.Walking&&P.Panel==G3Panel.None;
            }
            PersistPhoneDiagnostic();
        }
        // Flatten only ordinary enumerators, so every resumed nested UI/look/walk
        // operation is checked against ONE stopwatch that began before SetUp.
        IEnumerator PhoneBounded(IEnumerator body)
        {
            var stack=new Stack<IEnumerator>();stack.Push(body);
            try
            {
                while(stack.Count>0)
                {
                    CheckPhoneDeadline();var top=stack.Peek();bool more=top.MoveNext();CheckPhoneDeadline();
                    if(!more){(stack.Pop() as IDisposable)?.Dispose();continue;}
                    if(top.Current is IEnumerator child){stack.Push(child);continue;}
                    Assert.That(top.Current,Is.Null,"Only existing frame yields are permitted");yield return null;
                }
            }
            finally{while(stack.Count>0)(stack.Pop() as IDisposable)?.Dispose();}
        }
        void EndPhoneDiagnostic(bool cleanupComplete)
        {
            if(phoneReceipt==null)return;
            phoneReceipt.cleanupComplete=cleanupComplete;phoneReceipt.stage="TEARDOWN";
            phoneReceipt.deadlineExceeded|=phoneClock.Elapsed.TotalSeconds>=180;
            phoneReceipt.status=phoneReceipt.routeComplete&&cleanupComplete&&!phoneReceipt.deadlineExceeded?"FUNCTIONAL_ROUTE_AND_STATE_OBSERVED":"INCONCLUSIVE";
            PersistPhoneDiagnostic();CheckPhoneDeadline();
        }
        // This diagnostic has a distinct identity and is opt-in by exact filter.
        // The original WORLD cases, their 45-second assertions and identities are unchanged.
        [UnityTest,Explicit("Separate bounded functional observation; never canonical WORLD"),Timeout(180000)]
        public IEnumerator PhoneReturnFunctionalObservationOnly()
        {
            Assert.That(phoneReceipt,Is.Not.Null);phoneReceipt.setupComplete=true;PhoneSnapshot("READY");
            yield return PhoneBounded(PhoneReturnBody());
        }
        IEnumerator PhoneReturnBody()
        {
            PrepareWorldInputViewport();
            long beforeCash=State.CashMinor;
            Buy("number");ScratchCell(3,.3f);string hash=StateCodec.ComputeHash(State);
            PhoneSnapshot("TICKET_READY");phoneReceipt.initialStateHash=hash;phoneReceipt.initialTicketHash=phoneReceipt.ticketHash;
            phoneReceipt.initialPaidMinor=phoneReceipt.paidMinor;phoneReceipt.initialScratch=phoneReceipt.scratch;
            Assert.That(beforeCash-State.CashMinor,Is.EqualTo(phoneReceipt.paidMinor));
            Assert.That(phoneReceipt.initialScratch,Is.GreaterThan(0).And.LessThan(1));PersistPhoneDiagnostic();
            yield return TouchUiRelease("stand");
            yield return PhoneWalk(0,new Vector3(.15f,0,.30f));yield return PhoneWalk(1,new Vector3(1.20f,0,-.85f),true);
            var phone=P.View.Phone.ScreenWorldCorners;Vector3 center=phone.Aggregate(Vector3.zero,(a,b)=>a+b)/phone.Length;
            yield return TouchFace(center);Vector3 pos=app.SceneCamera.transform.position;Quaternion rot=app.SceneCamera.transform.rotation;
            phoneReceipt.cameraPositionBefore=PhoneVector(pos);phoneReceipt.cameraRotationBefore=PhoneRotation(rot);PhoneSnapshot("BEFORE_PHONE");
            yield return TouchWorldOpen(center,G3Panel.Phone);Assert.That(P.View.Phone.IsFocused,Is.True);phoneReceipt.phoneOpened=true;PhoneSnapshot("PHONE_OPEN");
            yield return TouchUiRelease("close-phone");
            phoneReceipt.cameraPositionAfter=PhoneVector(app.SceneCamera.transform.position);phoneReceipt.cameraRotationAfter=PhoneRotation(app.SceneCamera.transform.rotation);PhoneSnapshot("PHONE_CLOSED");
            Assert.That(P.View.Phone.IsFocused,Is.False);Assert.That(app.SceneCamera.transform.position,Is.EqualTo(pos));Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(rot));
            phoneReceipt.cameraRestored=true;Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));PersistPhoneDiagnostic();
            yield return PhoneWalk(2,new Vector3(.15f,0,.30f));yield return PhoneWalk(3,new Vector3(-.65f,0,.90f));
            yield return TouchWorldOpen(new Vector3(-1.35f,.85f,.45f),G3Panel.None,true);PhoneSnapshot("FINAL_SEAT");
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));Assert.That(phoneReceipt.ticketHash,Is.EqualTo(phoneReceipt.initialTicketHash));
            Assert.That(phoneReceipt.paidMinor,Is.EqualTo(phoneReceipt.initialPaidMinor));Assert.That(phoneReceipt.scratch,Is.EqualTo(phoneReceipt.initialScratch));
            Assert.That(phoneReceipt.finalSeated,Is.True);Assert.That(phoneReceipt.phoneFocused,Is.False);
            phoneReceipt.routeComplete=true;PhoneSnapshot("ROUTE_COMPLETE");
        }
        IEnumerator PhoneWalk(int segment,Vector3 destination,bool concurrentLook=false)
        {
            yield return WorldNeutral();var origin=P.View.Walk.SavedPosition;float started=Time.realtimeSinceStartup;
            var sample=new WorldWalkObservation{Origin=origin,Previous=origin,Destination=destination,Started=started,PreviousAt=started,MinRemaining=WorldDistance(origin,destination)};
            var row=new PhoneRouteRow{segment=segment,outcome="ABORTED",position=PhoneVector(origin)};phoneReceipt.routes.Add(row);
            Vector2 move=P.View.JoystickRect.center,look=LookOrigin;bool reached=false,movedLook=false;int checkpoints=0;
            Quaternion initialLook=app.SceneCamera.transform.rotation;
            WorldTouches(Finger(901,IPhase.Began,move));if(concurrentLook)WorldTouches(Finger(902,IPhase.Began,look));
            UpdatePhoneRoute(row,sample,destination,"BEGIN");
            try
            {
                while(WorldDistance(P.View.Walk.SavedPosition,destination)>.09f)
                {
                    CheckPhoneDeadline();
                    Vector3 world=destination-P.View.Walk.SavedPosition;world.y=0;
                    Vector3 local=Quaternion.Inverse(Quaternion.Euler(0,app.SceneCamera.transform.eulerAngles.y,0))*world.normalized;
                    sample.LastCommand=new Vector2(local.x,local.z);Vector2 point=move+sample.LastCommand*P.View.JoystickRect.width*.3f;
                    yield return null;
                    if(concurrentLook&&!movedLook)
                    {
                        look+=Vector2.right*12*P.View.TouchPixelsPerDp;
                        WorldTouches(Finger(901,IPhase.Moved,point),Finger(902,IPhase.Moved,look));
                        Assert.That(Router.MoveTouchId,Is.EqualTo(901));Assert.That(Router.LookTouchId,Is.EqualTo(902));Assert.That(Quaternion.Angle(initialLook,app.SceneCamera.transform.rotation),Is.GreaterThan(1));movedLook=true;
                    }
                    else WorldTouches(Finger(901,IPhase.Moved,point));
                    sample.Observe(P.View.Walk.SavedPosition);
                    // Observe 45s overrun without ending normal movement. This is never a timing pass.
                    if(Time.realtimeSinceStartup-started>=45)phoneReceipt.timing="TIMING_FAIL";
                    if(checkpoints<8&&Time.realtimeSinceStartup-started>=(checkpoints+1)*5){checkpoints++;UpdatePhoneRoute(row,sample,destination,"MOVING");}
                }
                CheckPhoneDeadline();reached=true;
            }
            finally
            {
                UpdatePhoneRoute(row,sample,destination,reached?"REACHED":"ABORTED");
                WorldTouches(Finger(901,IPhase.Ended,move));if(concurrentLook)WorldTouches(Finger(902,IPhase.Ended,look));
            }
            yield return WorldNeutral();Assert.That(Vector3.Distance(P.View.Walk.SavedPosition,origin),Is.GreaterThan(.05f));
        }
        void UpdatePhoneRoute(PhoneRouteRow row,WorldWalkObservation sample,Vector3 target,string outcome)
        {
            row.outcome=outcome;row.elapsedMs=(Time.realtimeSinceStartup-sample.Started)*1000d;row.frames=sample.Frames;
            row.pathMeters=sample.PathMeters;row.maxFrameWall=Mathf.Max(sample.MaxFrameWall,Time.realtimeSinceStartup-sample.PreviousAt);row.remaining=WorldDistance(P.View.Walk.SavedPosition,target);row.position=PhoneVector(P.View.Walk.SavedPosition);
            if(row.elapsedMs>=45000)phoneReceipt.timing="TIMING_FAIL";
            else if(phoneReceipt.timing=="NOT_OBSERVED")phoneReceipt.timing="NO_OVERRUN_OBSERVED";
            PhoneSnapshot("WALK");
        }
    }
}

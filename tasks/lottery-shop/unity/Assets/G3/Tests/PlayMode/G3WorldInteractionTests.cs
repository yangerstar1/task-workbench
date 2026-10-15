using System.Collections;
using System.Linq;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
using Lottery.G3.Rendering;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.TestTools;
using IPhase=UnityEngine.InputSystem.TouchPhase;

namespace Lottery.G3.PlayMode.Tests
{
    public sealed partial class G3PlayTests
    {
        // WORLD_INPUT_V2. Only DeclareWorldSpawn sets a pose, before a route starts.
        // Every subsequent displacement/look/activation is a real simulated touch event.
        void PrepareWorldInputViewport()
        {
            BindPresentationTarget(640,360);
            Assert.That(P.View.PresentationWidth,Is.EqualTo(640));Assert.That(P.View.PresentationHeight,Is.EqualTo(360));
            Assert.That(app.SceneCamera.aspect,Is.EqualTo(16f/9f).Within(.00001f));
            Assert.That(P.View.HasMeasuredAndroidDensity,Is.False,"This Editor fixture uses the declared fallback, not measured Android dp");
            Assert.That(P.View.TouchPixelsPerDp,Is.EqualTo(1));
            TestContext.Out.WriteLine("WORLD_INPUT_V2 640x360 SIMULATED_EDITOR_FALLBACK_DP NOT_ANDROID NOT_ORIGINAL_RESOLUTION_VISUAL_EVIDENCE");
        }
        void DeclareWorldSpawn(Vector3 position,float yaw)
        {
            Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            P.Execute(new G3Action(G3ActionKind.Stand));
            P.View.Walk.SetPose(position,yaw);Physics.SyncTransforms();
        }
        IEnumerator WorldNeutral()
        {yield return null;PumpInput();Router.PollInput();Assert.That(Router.AwaitingRelease,Is.False);}
        void WorldTouches(params TouchState[] states)
        {foreach(var state in states)UnityEngine.InputSystem.InputSystem.QueueStateEvent(touch,state);PumpInput();Router.PollInput();}
        static TouchState Finger(int id,IPhase phase,Vector2 point)=>new TouchState{touchId=id,phase=phase,position=point,pressure=phase==IPhase.Ended||phase==IPhase.Canceled?0:1};
        Vector2 LookOrigin=>new Vector2(P.View.PresentationSafeArea.xMin+P.View.PresentationSafeArea.width*.73f,P.View.PresentationSafeArea.center.y);
        IEnumerator TouchFace(Vector3 target)
        {
            yield return WorldNeutral();
            for(int i=0;i<24;i++)
            {
                Vector3 d=target-app.SceneCamera.transform.position;
                float desiredYaw=Mathf.Atan2(d.x,d.z)*Mathf.Rad2Deg,desiredPitch=-Mathf.Atan2(d.y,new Vector2(d.x,d.z).magnitude)*Mathf.Rad2Deg;
                float yaw=Mathf.DeltaAngle(app.SceneCamera.transform.eulerAngles.y,desiredYaw),pitch=Mathf.DeltaAngle(app.SceneCamera.transform.eulerAngles.x,desiredPitch);
                if(Mathf.Abs(yaw)<3&&Mathf.Abs(pitch)<3)yield break;
                Vector2 start=LookOrigin,delta=new Vector2(Mathf.Clamp(yaw,-25,25)/.26f,-Mathf.Clamp(pitch,-15,15)/.20f)*P.View.TouchPixelsPerDp;
                Vector2 end=start+delta;Assert.That(P.View.IsSafePointer(end),Is.True);
                WorldTouches(Finger(902,IPhase.Began,start));yield return null;
                WorldTouches(Finger(902,IPhase.Moved,end));yield return null;
                WorldTouches(Finger(902,IPhase.Ended,end));yield return WorldNeutral();
            }
            Assert.Fail("Real LOOK touch did not face the declared world target");
        }
        // Source-owned fixed labels and numeric samples only, at most 10 output rows
        // per segment (begin, eight checkpoints, finish). No frame-by-frame log flood.
        static string WorldNumber(float value)=>value.ToString("F4",System.Globalization.CultureInfo.InvariantCulture);
        static string WorldVector(Vector3 value)=>"("+WorldNumber(value.x)+","+WorldNumber(value.y)+","+WorldNumber(value.z)+")";
        static float WorldDistance(Vector3 a,Vector3 b)=>new Vector2(a.x-b.x,a.z-b.z).magnitude;
        // Failure-only numeric attribution; does not change the route or frame budget.
        // Snapshot order: glyph count/ticks/max, atlas notifications, input count/ticks/max, overflow.
        struct WorldCostSnapshot
        {
            public long GlyphCount,GlyphTicks,GlyphMax,Atlas,InputCount,InputTicks,InputMax,Overflow;
            public static WorldCostSnapshot Read()
            {
                var glyph=BoundedGlyphLabel.CostObservation();var input=G3InputRouter.CostObservation();
                return new WorldCostSnapshot{GlyphCount=glyph[0],GlyphTicks=glyph[1],GlyphMax=glyph[2],Atlas=glyph[3],
                    InputCount=input[0],InputTicks=input[1],InputMax=input[2],Overflow=System.Math.Max(glyph[4],input[6])};
            }
            static string Numbers(params long[] values)=>string.Join(",",values.Select(x=>x.ToString(System.Globalization.CultureInfo.InvariantCulture)));
            public string FixedValues()=>Numbers(GlyphCount,GlyphTicks,GlyphMax,Atlas,InputCount,InputTicks,InputMax,Overflow);
            // Maxima are cumulative, not additive; their pre/post values are retained separately.
            public string Delta(WorldCostSnapshot before)=>Numbers(GlyphCount-before.GlyphCount,GlyphTicks-before.GlyphTicks,
                Atlas-before.Atlas,InputCount-before.InputCount,InputTicks-before.InputTicks);
        }
        sealed class WorldWorkloadObservation
        {
            readonly WorldCostSnapshot baseline;WorldCostSnapshot previous,beforeWorst,afterWorst;float longest;int worstFrame;
            public WorldWorkloadObservation()
            {
                BoundedGlyphLabel.BeginCostObservation();G3InputRouter.BeginCostObservation();
                baseline=previous=beforeWorst=afterWorst=WorldCostSnapshot.Read();
            }
            public void Observe(float interval,int frame)
            {
                // Existing getters allocate only two tiny arrays; live snapshots stay constant-size.
                var current=WorldCostSnapshot.Read();
                if(interval>longest){longest=interval;worstFrame=frame;beforeWorst=previous;afterWorst=current;}
                previous=current;
            }
            public string FailureSummary()=>" WORLD_WORKLOAD_V1 tickFrequency="+System.Diagnostics.Stopwatch.Frequency.ToString(System.Globalization.CultureInfo.InvariantCulture)+
                " worstFrame="+worstFrame.ToString(System.Globalization.CultureInfo.InvariantCulture)+" base=("+baseline.FixedValues()+
                ") pre=("+beforeWorst.FixedValues()+") post=("+afterWorst.FixedValues()+") delta=("+afterWorst.Delta(beforeWorst)+")";
            public void End(){BoundedGlyphLabel.EndCostObservation();G3InputRouter.EndCostObservation();}
        }
        WorldPhaseObservation activeWorldPhase;
        // Constant-size per-route observation. Wall phases overlap runtime counters;
        // they must not be added together as if they were exclusive CPU categories.
        sealed class WorldPhaseObservation
        {
            const long Limit=1000000000000000L;
            struct Snapshot
            {
                public long PumpCalls,PumpTicks,DiagnosticCalls,DiagnosticTicks,PollCalls,PollTicks,GlyphCalls,GlyphTicks,Atlas;
                public long UpdateCalls,UpdateTicks,ShowCalls,ShowTicks,Gc0,Gc1,Gc2;public bool Overflow;
            }
            Snapshot before,worst;long pumpCalls,pumpTicks,diagnosticCalls,diagnosticTicks,started,resumed,worstWall,worstYield,worstResume;
            int pendingFrame,worstFrame,intervals;bool open,overflow,worstIncomplete;
            long cpuBefore,cpuAfter,worstCpuTicks;bool worstCpuAvailable;
            // Process CPU across the same yield: CPU work versus off-CPU waiting.
            // TimeSpan ticks (10,000,000/s), NOT Stopwatch ticks. No process identity,
            // paths, exception text, profiler stream or child-process data is exported.
            static long ReadProcessCpuTicks()
            {
                try{using(var process=System.Diagnostics.Process.GetCurrentProcess())return process.TotalProcessorTime.Ticks;}
                catch{return -1;}
            }
            // A single fixed native marker, all threads, individual completed samples.
            // No frame aggregation, ring overwrite, GPU timer, stream or marker metadata.
            const int ShaderCapacity=64;
            Unity.Profiling.ProfilerRecorder shaderRecorder;
            bool shaderReady;
            struct ShaderSample {public bool Available,Saturated;public long Ns,Calls;}
            ShaderSample currentShader,worstShader;
            void InitializeShaderObservation()
            {
                try
                {
                    shaderRecorder=new Unity.Profiling.ProfilerRecorder("Shader.CreateGPUProgram",ShaderCapacity,Unity.Profiling.ProfilerRecorderOptions.None);
                    shaderReady=shaderRecorder.Valid&&shaderRecorder.UnitType==Unity.Profiling.ProfilerMarkerDataUnit.TimeNanoseconds;
                }
                catch{shaderReady=false;}
            }
            void BeforeShaderYield()
            {
                currentShader=default;
                if(!shaderReady)return;
                try{shaderRecorder.Reset();shaderRecorder.Start();shaderReady=shaderRecorder.IsRunning;}
                catch{shaderReady=false;}
            }
            void AfterShaderYield()
            {
                if(!shaderReady)return;
                try
                {
                    shaderRecorder.Stop();
                    if(!shaderRecorder.Valid||shaderRecorder.UnitType!=Unity.Profiling.ProfilerMarkerDataUnit.TimeNanoseconds)return;
                    int count=shaderRecorder.Count;
                    if(count<0||count>ShaderCapacity)return;
                    var sample=new ShaderSample{Available=true,Saturated=count==ShaderCapacity||shaderRecorder.WrappedAround};
                    for(int i=0;i<count;i++)
                    {
                        var value=shaderRecorder.GetSample(i);
                        // None collects individual marker invocations, not frame aggregates.
                        // Unexpected sample shape is UNKNOWN, never a negative finding.
                        if(value.Value<0||value.Count!=1)return;
                        if(value.Value>Limit||sample.Ns>Limit-value.Value){sample.Ns=Limit;sample.Saturated=true;}
                        else sample.Ns+=value.Value;
                        sample.Calls++;
                    }
                    currentShader=sample;
                }
                catch{shaderReady=false;currentShader=default;}
            }
            void EndShaderObservation()
            {
                try{shaderRecorder.Dispose();}catch{shaderReady=false;}
            }
            readonly int gcMax=System.Math.Min(2,System.GC.MaxGeneration);
            public WorldPhaseObservation(){G3SceneView.BeginPhaseCostObservation();InitializeShaderObservation();}
            void Add(ref long target,long value)
            {if(value<0||value>Limit||target>Limit-value){target=Limit;overflow=true;}else target+=value;}
            long Bound(long value){if(value<0||value>Limit){overflow=true;return System.Math.Max(0,System.Math.Min(Limit,value));}return value;}
            public void ObservePump(long ticks){Add(ref pumpCalls,1);Add(ref pumpTicks,ticks);}
            public void ObserveDiagnostic(long ticks){Add(ref diagnosticCalls,1);Add(ref diagnosticTicks,ticks);}
            Snapshot Read()
            {
                var glyph=BoundedGlyphLabel.CostObservation();var input=G3InputRouter.CostObservation();var scene=G3SceneView.ReadPhaseCostObservation();
                return new Snapshot{PumpCalls=pumpCalls,PumpTicks=pumpTicks,DiagnosticCalls=diagnosticCalls,DiagnosticTicks=diagnosticTicks,PollCalls=input[0],PollTicks=input[1],GlyphCalls=glyph[0],GlyphTicks=glyph[1],Atlas=glyph[3],
                    UpdateCalls=scene.UpdateCalls,UpdateTicks=scene.UpdateTicks,ShowCalls=scene.ShowCalls,ShowTicks=scene.ShowTicks,
                    Gc0=System.GC.CollectionCount(0),Gc1=gcMax>=1?System.GC.CollectionCount(1):0,Gc2=gcMax>=2?System.GC.CollectionCount(2):0,
                    Overflow=overflow||glyph[4]!=0||input[6]!=0||scene.Overflow};
            }
            public void BeforeYield(int frame)
            {before=Read();pendingFrame=frame;resumed=0;cpuAfter=-1;cpuBefore=ReadProcessCpuTicks();BeforeShaderYield();started=System.Diagnostics.Stopwatch.GetTimestamp();open=true;}
            public void AfterYield(){if(open){resumed=System.Diagnostics.Stopwatch.GetTimestamp();AfterShaderYield();cpuAfter=ReadProcessCpuTicks();}}
            public void EndFrame(bool incomplete=false)
            {
                if(!open)return;long ended=System.Diagnostics.Stopwatch.GetTimestamp();open=false;var after=Read();
                long wall=Bound(ended-started);intervals++;
                if(worstFrame!=0&&wall<=worstWall)return;
                worstFrame=pendingFrame;worstWall=wall;worstIncomplete=incomplete||resumed==0;
                worstCpuAvailable=resumed!=0&&cpuBefore>=0&&cpuAfter>=cpuBefore&&cpuAfter-cpuBefore<=Limit;
                worstCpuTicks=worstCpuAvailable?cpuAfter-cpuBefore:0;
                worstShader=worstIncomplete?default:currentShader;
                worstYield=Bound((resumed==0?ended:resumed)-started);worstResume=resumed==0?0:Bound(ended-resumed);
                worst=new Snapshot{PumpCalls=Bound(after.PumpCalls-before.PumpCalls),PumpTicks=Bound(after.PumpTicks-before.PumpTicks),
                    DiagnosticCalls=Bound(after.DiagnosticCalls-before.DiagnosticCalls),DiagnosticTicks=Bound(after.DiagnosticTicks-before.DiagnosticTicks),
                    PollCalls=Bound(after.PollCalls-before.PollCalls),PollTicks=Bound(after.PollTicks-before.PollTicks),
                    GlyphCalls=Bound(after.GlyphCalls-before.GlyphCalls),GlyphTicks=Bound(after.GlyphTicks-before.GlyphTicks),Atlas=Bound(after.Atlas-before.Atlas),
                    UpdateCalls=Bound(after.UpdateCalls-before.UpdateCalls),UpdateTicks=Bound(after.UpdateTicks-before.UpdateTicks),
                    ShowCalls=Bound(after.ShowCalls-before.ShowCalls),ShowTicks=Bound(after.ShowTicks-before.ShowTicks),
                    Gc0=Bound(after.Gc0-before.Gc0),Gc1=Bound(after.Gc1-before.Gc1),Gc2=Bound(after.Gc2-before.Gc2),Overflow=before.Overflow||after.Overflow};
            }
            static string N(long value)=>value.ToString(System.Globalization.CultureInfo.InvariantCulture);
            public string Summary(string segment)=>"WORLD_PHASE_V1 segment="+segment+" frequency="+N(System.Diagnostics.Stopwatch.Frequency)+
                " intervals="+N(intervals)+" frame="+N(worstFrame)+" wallTicks="+N(worstWall)+" yieldTicks="+N(worstYield)+" resumeTicks="+N(worstResume)+
                " pumpCalls="+N(worst.PumpCalls)+" pumpTicks="+N(worst.PumpTicks)+
                " diagnosticCalls="+N(worst.DiagnosticCalls)+" diagnosticTicks="+N(worst.DiagnosticTicks)+" pollCalls="+N(worst.PollCalls)+" pollTicks="+N(worst.PollTicks)+
                " glyphCalls="+N(worst.GlyphCalls)+" glyphTicks="+N(worst.GlyphTicks)+" atlasNotifications="+N(worst.Atlas)+
                " updateCalls="+N(worst.UpdateCalls)+" updateTicks="+N(worst.UpdateTicks)+" showCalls="+N(worst.ShowCalls)+" showTicks="+N(worst.ShowTicks)+
                " gcMax="+N(gcMax)+" gc0="+N(worst.Gc0)+" gc1="+N(worst.Gc1)+" gc2="+N(worst.Gc2)+
                " incomplete="+(worstIncomplete?"1":"0")+" overflow="+(overflow||worst.Overflow?"1":"0")+" cpuAvailable="+(worstCpuAvailable?"1":"0")+" processCpuTicks="+N(worstCpuTicks)+
                " shaderAvailable="+(worstShader.Available?"1":"0")+" shaderNs="+N(worstShader.Ns)+" shaderCalls="+N(worstShader.Calls)+" shaderSaturated="+(worstShader.Saturated?"1":"0");
            public void End(){try{EndShaderObservation();}finally{G3SceneView.EndPhaseCostObservation();}}
        }
        sealed class WorldWalkObservation
        {
            public string Segment;public Vector3 Origin,Destination,Previous;
            public float Started,PreviousAt,LastStep,PathMeters,MaxFrameWall,MaxFrameDelta,MinRemaining;
            public int Frames,StationaryFrames;public Vector2 LastCommand;public WorldWorkloadObservation Workload;
            public void Observe(Vector3 body)
            {
                float now=Time.realtimeSinceStartup;
                LastStep=WorldDistance(body,Previous);PathMeters+=LastStep;
                MaxFrameWall=Mathf.Max(MaxFrameWall,now-PreviousAt);MaxFrameDelta=Mathf.Max(MaxFrameDelta,Time.unscaledDeltaTime);
                MinRemaining=Mathf.Min(MinRemaining,WorldDistance(body,Destination));
                Frames++;if(LastStep<.0001f)StationaryFrames++;Workload?.Observe(now-PreviousAt,Frames);
                Previous=body;PreviousAt=now;
            }
        }
        string WorldWalkDiagnostic(WorldWalkObservation sample,string phase)
        {
            var body=P.View.Walk.SavedPosition;
            return "WORLD_ROUTE_V1 segment="+sample.Segment+" phase="+phase+" elapsed="+WorldNumber(Time.realtimeSinceStartup-sample.Started)+
                " limit=45 frames="+sample.Frames+" stationaryFrames="+sample.StationaryFrames+" body="+WorldVector(body)+
                " origin="+WorldVector(sample.Origin)+" destination="+WorldVector(sample.Destination)+" remaining="+WorldNumber(WorldDistance(body,sample.Destination))+
                " minRemaining="+WorldNumber(sample.MinRemaining)+" lastStep="+WorldNumber(sample.LastStep)+" pathMeters="+WorldNumber(sample.PathMeters)+
                " maxFrameWall="+WorldNumber(sample.MaxFrameWall)+" maxUnscaledDelta="+WorldNumber(sample.MaxFrameDelta)+
                " command="+WorldVector(new Vector3(sample.LastCommand.x,0,sample.LastCommand.y))+" camera="+WorldVector(app.SceneCamera.transform.position)+
                " cameraEuler="+WorldVector(app.SceneCamera.transform.eulerAngles)+" moveId="+Router.MoveTouchId+" lookId="+Router.LookTouchId+
                " mode="+(int)Router.Mode+" focused="+Router.IsFocused+" awaitingRelease="+Router.AwaitingRelease+" cameraWrite="+P.View.Walk.CameraWriteEnabled;
        }
        void WriteWorldDiagnostic(string sample)
        {
            long started=activeWorldPhase!=null?System.Diagnostics.Stopwatch.GetTimestamp():0;
            try{G3WorldProgress.Record(sample);TestContext.Out.WriteLine(sample);}
            finally{activeWorldPhase?.ObserveDiagnostic(System.Diagnostics.Stopwatch.GetTimestamp()-started);}
        }
        void AssertWorldRouteBudget(WorldWalkObservation sample,string phase)
        {
            float elapsed=Time.realtimeSinceStartup-sample.Started;
            // Build the detailed string only on failure, not on every movement frame.
            if(!(elapsed<45))Assert.That(elapsed,Is.LessThan(45),"Real joystick route stalled; never teleport or extend the native budget. "+WorldWalkDiagnostic(sample,phase)+(sample.Workload?.FailureSummary()??""));
        }
        IEnumerator TouchWalkTo(string segment,Vector3 destination,bool proveConcurrentLook=false)
        {
            yield return WorldNeutral();Vector3 origin=P.View.Walk.SavedPosition;float started=Time.realtimeSinceStartup;
            var sample=new WorldWalkObservation{Segment=segment,Origin=origin,Previous=origin,Destination=destination,Started=started,PreviousAt=started,MinRemaining=WorldDistance(origin,destination)};
            WriteWorldDiagnostic(WorldWalkDiagnostic(sample,"BEGIN"));int checkpoints=0;bool reached=false;
            Vector2 move=P.View.JoystickRect.center,look=LookOrigin;
            WorldTouches(Finger(901,IPhase.Began,move));
            if(proveConcurrentLook)WorldTouches(Finger(902,IPhase.Began,look));
            bool movedLook=false;Quaternion initialLook=app.SceneCamera.transform.rotation;
            try
            {
                if(G3WorldProgress.PhaseTimingEnabled)
                {sample.Workload=new WorldWorkloadObservation();activeWorldPhase=new WorldPhaseObservation();}
                while(WorldDistance(P.View.Walk.SavedPosition,destination)>.09f)
                {
                    AssertWorldRouteBudget(sample,"STALL");
                    Vector3 world=destination-P.View.Walk.SavedPosition;world.y=0;
                    Vector3 local=Quaternion.Inverse(Quaternion.Euler(0,app.SceneCamera.transform.eulerAngles.y,0))*world.normalized;
                    sample.LastCommand=new Vector2(local.x,local.z);
                    Vector2 point=move+sample.LastCommand*P.View.JoystickRect.width*.3f;
                    activeWorldPhase?.BeforeYield(sample.Frames+1);
                    yield return null;
                    activeWorldPhase?.AfterYield();
                    if(proveConcurrentLook&&!movedLook)
                    {
                        look+=Vector2.right*12*P.View.TouchPixelsPerDp;
                        WorldTouches(Finger(901,IPhase.Moved,point),Finger(902,IPhase.Moved,look));
                        Assert.That(Router.MoveTouchId,Is.EqualTo(901));Assert.That(Router.LookTouchId,Is.EqualTo(902));Assert.That(Quaternion.Angle(initialLook,app.SceneCamera.transform.rotation),Is.GreaterThan(1));movedLook=true;
                    }
                    else WorldTouches(Finger(901,IPhase.Moved,point));
                    sample.Observe(P.View.Walk.SavedPosition);
                    if(checkpoints<8&&Time.realtimeSinceStartup-started>=(checkpoints+1)*5)
                    {checkpoints++;WriteWorldDiagnostic(WorldWalkDiagnostic(sample,"SAMPLE"));}
                    activeWorldPhase?.EndFrame();
                }
                // Arrival on a slow frame does not silently bypass the same 45 s bound.
                AssertWorldRouteBudget(sample,"ARRIVAL");
                reached=true;
            }
            finally
            {
                var phases=activeWorldPhase;activeWorldPhase=null;
                try{phases?.EndFrame(true);}
                finally{phases?.End();sample.Workload?.End();}
                WriteWorldDiagnostic(WorldWalkDiagnostic(sample,reached?"REACHED":"ABORTED"));
                if(phases!=null)WriteWorldDiagnostic(phases.Summary(segment));
            }
            WorldTouches(Finger(901,IPhase.Ended,move));if(proveConcurrentLook)WorldTouches(Finger(902,IPhase.Ended,look));
            yield return WorldNeutral();Assert.That(Vector3.Distance(P.View.Walk.SavedPosition,origin),Is.GreaterThan(.05f));
        }
        IEnumerator TouchUiRelease(string id)
        {
            yield return WorldNeutral();Assert.That(P.View.HasButton(id),Is.True);
            var point=P.View.ButtonRect(id).center;WorldTouches(Finger(909,IPhase.Began,point));
            WorldTouches(Finger(909,IPhase.Ended,point));yield return WorldNeutral();
        }
        IEnumerator TouchWorldOpen(Vector3 target,G3Panel panel,bool table=false)
        {
            yield return TouchFace(target);Physics.SyncTransforms();var pixel=P.View.WorldToPresentationPoint(target);
            Assert.That(P.View.IsSafePointer(pixel),Is.True);var physical=P.View.WorldTarget(pixel);var diagnostic=WorldRayDiagnostic(target,pixel);WriteWorldDiagnostic(diagnostic);Assert.That(physical,Is.Not.Null,"Nearest unobstructed collider must be a reachable physical target. "+diagnostic);
            Assert.That(physical.IsTable,Is.EqualTo(table));if(!table)Assert.That(physical.Panel,Is.EqualTo(panel));
            var before=P.Panel;WorldTouches(Finger(903,IPhase.Began,pixel));Assert.That(P.Panel,Is.EqualTo(before),"Press is not activation");
            WorldTouches(Finger(903,IPhase.Ended,pixel));Assert.That(P.Panel,Is.EqualTo(panel));
            if(table)Assert.That(P.Walking,Is.False);yield return WorldNeutral();
        }
        // Fixed source-owned numeric observations only; not a replacement for the assertion.
        string WorldRayDiagnostic(Vector3 target,Vector2 pixel)
        {
            var ray=app.SceneCamera.ViewportPointToRay(new Vector3(pixel.x/P.View.PresentationWidth,pixel.y/P.View.PresentationHeight,0));
            bool hitAny=Physics.Raycast(ray,out RaycastHit hit,5,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Collide);
            var physical=hitAny?hit.collider.GetComponentInParent<G3WorldTarget>():null;
            string kind=!hitAny?"NONE":hit.collider is CharacterController?"CHARACTER_CONTROLLER":physical!=null?"WORLD_TARGET":"UNTARGETED_COLLIDER";
            var body=P.View.Walk.SavedPosition;
            float reach=hitAny?new Vector2(hit.point.x-body.x,hit.point.z-body.z).magnitude:-1;
            var foreign=Physics.RaycastAll(ray,5,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Collide)
                .Where(x=>!P.View.Walk.OwnsBodyCollider(x.collider)).OrderBy(x=>x.distance).ThenBy(x=>x.collider.GetComponentInParent<G3WorldTarget>()!=null?1:0).ToArray();
            var selected=foreign.Length>0?foreign[0]:default;
            return "WORLD_RAY_V2 kind="+kind+" trigger="+(hitAny&&hit.collider.isTrigger)+" ownBody="+(hitAny&&P.View.Walk.OwnsBodyCollider(hit.collider))+
                " environment="+(hitAny&&hit.collider.transform.IsChildOf(P.View.Environment.transform))+" hitDistance="+WorldNumber(hitAny?hit.distance:-1)+
                " horizontalReach="+WorldNumber(reach)+" body="+WorldVector(body)+" camera="+WorldVector(app.SceneCamera.transform.position)+
                " target="+WorldVector(target)+" pixel="+WorldVector(new Vector3(pixel.x,pixel.y,0))+" rayOrigin="+WorldVector(ray.origin)+" rayDirection="+WorldVector(ray.direction)+
                " foreignHits="+foreign.Length+" foreignDistance="+WorldNumber(foreign.Length>0?selected.distance:-1)+
                " foreignController="+(foreign.Length>0&&selected.collider is CharacterController)+" foreignTarget="+(foreign.Length>0&&selected.collider.GetComponentInParent<G3WorldTarget>()!=null)+
                " foreignNearestTies="+(foreign.Length>0?foreign.Count(x=>x.distance==selected.distance):0);
        }
        [UnityTest,Timeout(180000)]
        public IEnumerator WorldInputEntryToTicketRackAndTableUsesConcurrentMoveLookAndRelease()
        {
            PrepareWorldInputViewport();
            DeclareWorldSpawn(P.View.Environment.EntryPosition,P.View.Environment.EntryYaw);
            yield return TouchWalkTo("ENTRY_TO_TICKET_RACK",new Vector3(.65f,0,.25f),true);
            yield return TouchWorldOpen(new Vector3(1.64f,.91f,-.32f),G3Panel.Tickets);
            Click("buy-number");Confirm();Assert.That(State.CurrentTicket.TicketType,Is.EqualTo("number"));string hash=StateCodec.ComputeHash(State);Close();
            yield return TouchWalkTo("TICKET_RACK_TO_TABLE",new Vector3(-.65f,0,.90f));
            yield return TouchWorldOpen(new Vector3(-1.35f,.85f,.45f),G3Panel.None,true);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));ScratchCell(3,.3f);Assert.That(State.CurrentTicket.Scratch.CellCoverage(3),Is.GreaterThan(0));
        }
        [UnityTest,Timeout(180000)]
        public IEnumerator WorldInputTableToPhysicalPhoneAndBackPreservesTicketAndCamera()
        {
            PrepareWorldInputViewport();
            // Explicit local transaction setup precedes the real spatial route.
            Buy("number");ScratchCell(3,.3f);string hash=StateCodec.ComputeHash(State);
            yield return TouchUiRelease("stand");
            yield return TouchWalkTo("TABLE_TO_PHONE_AISLE",new Vector3(.15f,0,.30f));yield return TouchWalkTo("AISLE_TO_PHONE",new Vector3(1.20f,0,-.85f),true);
            var phone=P.View.Phone.ScreenWorldCorners;Vector3 phoneCenter=phone.Aggregate(Vector3.zero,(a,b)=>a+b)/phone.Length;
            yield return TouchFace(phoneCenter);Vector3 pos=app.SceneCamera.transform.position;Quaternion rot=app.SceneCamera.transform.rotation;
            yield return TouchWorldOpen(phoneCenter,G3Panel.Phone);Assert.That(P.View.Phone.IsFocused,Is.True);
            yield return TouchUiRelease("close-phone");Assert.That(P.View.Phone.IsFocused,Is.False);Assert.That(app.SceneCamera.transform.position,Is.EqualTo(pos));Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(rot));
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            yield return TouchWalkTo("PHONE_TO_RETURN_AISLE",new Vector3(.15f,0,.30f));yield return TouchWalkTo("RETURN_AISLE_TO_TABLE",new Vector3(-.65f,0,.90f));
            yield return TouchWorldOpen(new Vector3(-1.35f,.85f,.45f),G3Panel.None,true);Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
        }
        [UnityTest,Timeout(180000)]
        public IEnumerator WorldInputStorageToolShelfDrawerAndPointerOwnershipArePhysical()
        {
            PrepareWorldInputViewport();
            // Declared local projection reference only, before the spatial route begins.
            SetupLocalPanel(G3Panel.Shop);string localStock=P.BuildPanel().Body;Close();
            string hash=StateCodec.ComputeHash(State);DeclareWorldSpawn(P.View.Environment.EntryPosition,P.View.Environment.EntryYaw);
            yield return TouchWalkTo("ENTRY_TO_INVENTORY",new Vector3(1.35f,0,1.40f),true);
            yield return TouchWorldOpen(new Vector3(2.345f,.75f,2.02f),G3Panel.Inventory);Close();
            yield return TouchWalkTo("INVENTORY_TO_SHELF_AISLE",new Vector3(.25f,0,.8f));yield return TouchWalkTo("AISLE_TO_TOOL_SHELF",new Vector3(-.08f,0,-1.20f));
            yield return TouchWorldOpen(P.View.Environment.ShelfTargetPosition,G3Panel.Shop);
            Assert.That(P.BuildPanel().Cards.Any(x=>x.Id.StartsWith("stock-")),Is.True);string physicalStock=P.BuildPanel().Body;Close();
            // Compare the public service projection without changing navigation state.
            Assert.That(State.Stock.Count,Is.GreaterThan(0));Assert.That(physicalStock,Is.EqualTo(localStock),"Physical entry and declared local projection show the identical stock");
            yield return TouchWalkTo("TOOL_SHELF_TO_DRAWER",new Vector3(-.24f,0,-.08f));
            yield return TouchWorldOpen(new Vector3(-1.17f,.65f,0),G3Panel.Drawer);Close();
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash));
            yield return WorldPointerRejectionChecks(new Vector3(-1.17f,.65f,0));
        }
        void AssertWorldPickExcludesOnlyOwnedBody(Vector2 pixel)
        {
            var walk=P.View.Walk;var own=walk.GetComponent<CharacterController>();
            Assert.That(own,Is.Not.Null);Assert.That(walk.OwnsBodyCollider(own),Is.True);Assert.That(walk.OwnsBodyCollider(null),Is.False);
            Assert.That(own.enabled,Is.True);int originalLayer=own.gameObject.layer;Vector3 originalCenter=own.center;
            var ray=app.SceneCamera.ViewportPointToRay(new Vector3(pixel.x/P.View.PresentationWidth,pixel.y/P.View.PresentationHeight,0));
            var expected=P.View.WorldTarget(pixel);Assert.That(expected,Is.Not.Null);
            var temporary=new System.Collections.Generic.List<GameObject>();
            try
            {
                // Deliberate collider-only regression fixture, after the real route.
                // Keep the player's transform/reach/camera fixed. Force its exact
                // controller onto the ray and prove it remains enabled yet ignored.
                own.center=walk.transform.InverseTransformPoint(ray.GetPoint(.4f));Physics.SyncTransforms();
                Assert.That(Physics.Raycast(ray,out var ownedHit,5,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Collide),Is.True);
                Assert.That(ownedHit.collider,Is.SameAs(own),"Counterexample must actually hit the owned controller first");
                Assert.That(P.View.WorldTarget(pixel),Is.SameAs(expected));Assert.That(own.enabled,Is.True);Assert.That(own.gameObject.layer,Is.EqualTo(originalLayer));
                own.center=originalCenter;Physics.SyncTransforms();
                // Another controller remains opaque, even inside our transform tree.
                var foreign=new GameObject("Declared foreign controller picking fixture");temporary.Add(foreign);foreign.transform.SetParent(walk.transform,true);foreign.transform.position=ray.GetPoint(.5f);
                var other=foreign.AddComponent<CharacterController>();other.radius=.07f;other.height=.2f;other.center=Vector3.zero;
                Physics.SyncTransforms();Assert.That(walk.OwnsBodyCollider(other),Is.False);
                Assert.That(Physics.RaycastAll(ray,5,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Collide).Any(x=>x.collider==other),Is.True,"Foreign controller must intersect the ray");
                Assert.That(P.View.WorldTarget(pixel),Is.Null,"Foreign CharacterController must block a target behind it");
                foreign.SetActive(false);Physics.SyncTransforms();Assert.That(P.View.WorldTarget(pixel),Is.SameAs(expected));
                // An ordinary child collider is not owned merely because of ancestry.
                var child=new GameObject("Declared foreign child box picking fixture");temporary.Add(child);child.transform.SetParent(walk.transform,true);child.transform.position=ray.GetPoint(.5f);child.transform.rotation=Quaternion.LookRotation(ray.direction);
                var childBox=child.AddComponent<BoxCollider>();childBox.size=new Vector3(.2f,.2f,.03f);Physics.SyncTransforms();
                Assert.That(walk.OwnsBodyCollider(childBox),Is.False);Assert.That(P.View.WorldTarget(pixel),Is.Null);
                child.SetActive(false);Physics.SyncTransforms();Assert.That(P.View.WorldTarget(pixel),Is.SameAs(expected));
                // Force more than 16 hits, beyond the non-allocating query capacity.
                // Every extra collider is behind the original nearest target.
                var targetHit=Physics.RaycastAll(ray,5,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Collide)
                    .Where(x=>x.collider.GetComponentInParent<G3WorldTarget>()==expected).OrderBy(x=>x.distance).First();
                Assert.That(targetHit.distance+1.05f,Is.LessThan(5));
                for(int i=0;i<20;i++)
                {
                    var extra=new GameObject("Declared dense picking fixture");temporary.Add(extra);extra.transform.position=ray.GetPoint(targetHit.distance+.1f+i*.04f);extra.transform.rotation=Quaternion.LookRotation(ray.direction);
                    extra.AddComponent<BoxCollider>().size=new Vector3(.08f,.08f,.01f);
                }
                Physics.SyncTransforms();Assert.That(Physics.RaycastAll(ray,5,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Collide).Length,Is.GreaterThan(16));
                Assert.That(P.View.WorldTarget(pixel),Is.SameAs(expected),"Saturated hit buffers must not lose the nearest target");
                child.SetActive(true);Physics.SyncTransforms();Assert.That(P.View.WorldTarget(pixel),Is.Null,"Saturated hit buffers must not lose a nearer opaque blocker");
                // Equal-nearest distinct targets are ambiguous, independent of the
                // order returned by PhysX. Fail closed instead of selecting either.
                child.AddComponent<G3WorldTarget>().Panel=G3Panel.Inventory;
                var twin=new GameObject("Declared tied picking fixture");temporary.Add(twin);twin.transform.position=child.transform.position;twin.transform.rotation=child.transform.rotation;
                var twinBox=twin.AddComponent<BoxCollider>();twinBox.size=childBox.size;twin.AddComponent<G3WorldTarget>().Panel=G3Panel.Shop;
                Physics.SyncTransforms();var tied=Physics.RaycastAll(ray,5,Physics.DefaultRaycastLayers,QueryTriggerInteraction.Collide).Where(x=>x.collider==childBox||x.collider==twinBox).ToArray();
                Assert.That(tied.Length,Is.EqualTo(2));Assert.That(tied[0].distance,Is.EqualTo(tied[1].distance));
                Assert.That(P.View.WorldTarget(pixel),Is.Null,"Equal-nearest distinct targets must fail closed");
                Assert.That(P.View.WorldTarget(new Vector2(float.NaN,pixel.y)),Is.Null);Assert.That(P.View.WorldTarget(new Vector2(pixel.x,float.PositiveInfinity)),Is.Null);
            }
            finally
            {
                own.center=originalCenter;
                foreach(var item in temporary){item.SetActive(false);Object.Destroy(item);}Physics.SyncTransforms();
            }
            Assert.That(own.enabled,Is.True);Assert.That(own.gameObject.layer,Is.EqualTo(originalLayer));Assert.That(P.View.WorldTarget(pixel),Is.SameAs(expected));
        }
        IEnumerator WorldPointerRejectionChecks(Vector3 target)
        {
            yield return TouchFace(target);var pixel=P.View.WorldToPresentationPoint(target);Assert.That(P.View.WorldTarget(pixel),Is.Not.Null);
            AssertWorldPickExcludesOnlyOwnedBody(pixel);
            WorldTouches(Finger(903,IPhase.Began,pixel));WorldTouches(Finger(903,IPhase.Canceled,pixel));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));yield return WorldNeutral();
            WorldTouches(Finger(903,IPhase.Began,pixel));WorldTouches(Finger(903,IPhase.Ended,pixel+Vector2.right*9*P.View.TouchPixelsPerDp));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));yield return WorldNeutral();
            WorldTouches(Finger(903,IPhase.Began,pixel));WorldTouches(Finger(903,IPhase.Ended,new Vector2(-1,pixel.y)));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));yield return WorldNeutral();
            Assert.That(P.View.WorldTarget(new Vector2(-1,pixel.y)),Is.Null);Assert.That(P.View.WorldTarget(new Vector2(P.View.PresentationWidth,pixel.y)),Is.Null);
            // Two occupied movement roles cannot allow a third finger to open a world panel.
            var move=P.View.JoystickRect.center;var look=LookOrigin;
            WorldTouches(Finger(901,IPhase.Began,move),Finger(902,IPhase.Began,look));
            WorldTouches(Finger(904,IPhase.Began,pixel));WorldTouches(Finger(904,IPhase.Ended,pixel));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            WorldTouches(Finger(901,IPhase.Canceled,move),Finger(902,IPhase.Canceled,look));yield return WorldNeutral();
            // Settings is the one allowed third-finger safety action while MOVE + LOOK own their IDs.
            var safety=P.View.ButtonRect("open-settings").center;var stablePosition=P.View.Walk.SavedPosition;var stableRotation=app.SceneCamera.transform.rotation;
            string stableState=StateCodec.ComputeHash(State);
            WorldTouches(Finger(901,IPhase.Began,move),Finger(902,IPhase.Began,look));
            Assert.That(Router.MoveTouchId,Is.EqualTo(901));Assert.That(Router.LookTouchId,Is.EqualTo(902));
            WorldTouches(Finger(907,IPhase.Began,safety));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            WorldTouches(Finger(907,IPhase.Ended,safety));Assert.That(P.Panel,Is.EqualTo(G3Panel.Settings));
            WorldTouches(Finger(901,IPhase.Ended,move),Finger(902,IPhase.Ended,look));yield return WorldNeutral();
            Assert.That(Router.MoveTouchId,Is.EqualTo(-1));Assert.That(Router.LookTouchId,Is.EqualTo(-1));
            Assert.That(P.View.Walk.SavedPosition,Is.EqualTo(stablePosition));Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(stableRotation));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(stableState));
            Close();yield return WorldNeutral();yield return null;Router.PollInput();Assert.That(P.View.Walk.SavedPosition,Is.EqualTo(stablePosition));
            // Generic non-continuous UI executes only at same-control release.
            var settings=P.View.ButtonRect("open-settings").center;
            WorldTouches(Finger(906,IPhase.Began,settings));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            WorldTouches(Finger(906,IPhase.Ended,settings+Vector2.down*20*P.View.TouchPixelsPerDp));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));yield return WorldNeutral();
            WorldTouches(Finger(906,IPhase.Began,settings));P.Refresh();
            WorldTouches(Finger(906,IPhase.Ended,settings));Assert.That(P.Panel,Is.EqualTo(G3Panel.None),"A refreshed layout invalidates the pending control");yield return WorldNeutral();
            WorldTouches(Finger(906,IPhase.Began,settings));WorldTouches(Finger(906,IPhase.Ended,settings));Assert.That(P.Panel,Is.EqualTo(G3Panel.Settings));
            string unchanged=StateCodec.ComputeHash(State);WorldTouches(Finger(906,IPhase.Ended,settings));Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(unchanged));Close();yield return WorldNeutral();
            // An actual solid collider nearer than the target must block the production ray.
            var blocker=new GameObject("Declared temporary occlusion test wall");
            try
            {
                blocker.transform.position=(app.SceneCamera.transform.position+target)*.5f;blocker.transform.rotation=Quaternion.LookRotation(target-app.SceneCamera.transform.position);
                blocker.AddComponent<BoxCollider>().size=new Vector3(.7f,.7f,.05f);Physics.SyncTransforms();Assert.That(P.View.WorldTarget(pixel),Is.Null);
                WorldTouches(Finger(905,IPhase.Began,pixel));WorldTouches(Finger(905,IPhase.Ended,pixel));Assert.That(P.Panel,Is.EqualTo(G3Panel.None));
            }
            finally{Object.Destroy(blocker);}yield return WorldNeutral();
        }
    }
}


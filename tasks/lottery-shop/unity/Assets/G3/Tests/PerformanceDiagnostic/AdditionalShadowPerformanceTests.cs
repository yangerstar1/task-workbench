using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Lottery.G3.Core;
using Lottery.G3.Interaction;
using Lottery.G3.Persistence;
using NUnit.Framework;
using Unity.Profiling;
using Unity.Profiling.LowLevel;
using Unity.Profiling.LowLevel.Unsafe;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;
using Stopwatch = System.Diagnostics.Stopwatch;

namespace Lottery.G3.PerformanceDiagnostic.Tests
{
    // Independent controlled rendering diagnosis. Never a production quality tier,
    // capture replacement, device benchmark, or evidence that shadows may be removed.
    public sealed class AdditionalShadowPerformanceTests : IPrebuildSetup
    {
        const string Scope="PERFORMANCE_DIAGNOSTIC_NOT_G3_PASS";
        const string Identity="Lottery.G3.PerformanceDiagnostic.Tests.AdditionalShadowPerformanceTests.AdditionalShadowCostAbaKeepsSceneAndRestoresLights";
        const int WarmupFrames=2,SampleFrames=6,ReceiptBytes=131072;
        static readonly string[] Phases={"A1","B","A2"};
        static readonly string[] LegacyRoots={"Probe Camera","Probe Key Light","Render capability sample","Probe Overlay","G3 One Day Whitebox"};
        static readonly MetricSpec[] Specs={
            new MetricSpec("mainThread","Main Thread",true),new MetricSpec("renderThread","Render Thread",true),
            new MetricSpec("drawCalls","Draw Calls Count",false),new MetricSpec("batches","Batches Count",false),
            new MetricSpec("setPass","SetPass Calls Count",false),new MetricSpec("triangles","Triangles Count",false),
            new MetricSpec("vertices","Vertices Count",false),
            new MetricSpec("mainShadowCpu","Draw Main Light Shadowmap",true),
            new MetricSpec("additionalShadowCpu","Draw Additional Lights Shadowmap",true),
            new MetricSpec("presentWaitCpu","Gfx.WaitForPresentOnGfxThread",true)};
        readonly Dictionary<GameObject,bool> hidden=new Dictionary<GameObject,bool>();
        readonly List<MetricReader> readers=new List<MetricReader>();
        readonly List<PhaseReceipt> phases=new List<PhaseReceipt>();
        Scene prior,scene;RenderPipelineAsset priorDefault,priorQuality;
        G3SliceBootstrap app;FileStateStore store;RenderTexture target;
        LightSnapshot[] lights;RendererSnapshot[] geometry;
        Stopwatch total;Receipt receipt;string output,stateHash,storeDirectory;
        Vector3 cameraPosition;Quaternion cameraRotation;float cameraFov;
        RenderPipelineAsset measuringPipeline;bool writeFailed,cleanupFailed,capturedGlobals,observingCamera;int cameraRenderCount;

        // Reuse the reviewed additive preparation and strict live scene/root guard.
        // The test runner filters THIS assembly; it must not run the capture case.
        public void Setup(){PerformancePreparation.Prepare();}

        [UnitySetUp]
        public IEnumerator CreateRealScene()
        {
            total=Stopwatch.StartNew();
            output=Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts/performance-probe/performance-receipt.json"));
            receipt=new Receipt{sourceCommit=Arg("-probeCommit"),runId=Arg("-probeRunId"),runAttempt=Arg("-probeRunAttempt"),reviewedCandidateCommit=Arg("-probeReviewedCommit"),
                unityVersion=Application.unityVersion,graphicsDeviceType=SystemInfo.graphicsDeviceType.ToString(),
                softwareRendererDetected=IsSoftwareRenderer()};WriteReceipt();
            Assert.That(Arg("-g3PerformanceProbe"),Is.EqualTo("1"));
            Assert.That(Application.isPlaying,Is.True);Assert.That(Application.unityVersion,Is.EqualTo("6000.3.19f1"));
            Assert.That(SystemInfo.graphicsDeviceType,Is.Not.EqualTo(GraphicsDeviceType.Null));
            prior=SceneManager.GetActiveScene();priorDefault=GraphicsSettings.defaultRenderPipeline;priorQuality=QualitySettings.renderPipeline;capturedGlobals=true;
            foreach(var owner in Object.FindObjectsByType<G3SliceBootstrap>(FindObjectsSortMode.None))Hide(owner.gameObject);
            for(int i=0;i<SceneManager.sceneCount;i++)
            {var s=SceneManager.GetSceneAt(i);if(s.isLoaded)foreach(var root in s.GetRootGameObjects())if(LegacyRoots.Contains(root.name))Hide(root);}
            scene=SceneManager.CreateScene("G3 independent rendering performance diagnosis");SceneManager.SetActiveScene(scene);
            storeDirectory=Path.Combine(Path.GetTempPath(),"lottery-g3-performance-"+Guid.NewGuid().ToString("N"));
            store=new FileStateStore(storeDirectory,RunFactory.CreateDiagnostic("g3-day-qafixture-001"));
            app=new GameObject("Performance probe real G3 app").AddComponent<G3SliceBootstrap>();
            app.Initialize(new DayGameService(store),null,store);app.Presenter.Router.PollAutomatically=false;
            target=new RenderTexture(1280,720,24,RenderTextureFormat.ARGB32){name="Independent performance fixed native camera target"};
            target.Create();app.SceneCamera.targetTexture=target;
            app.Presenter.Execute(new G3Action(G3ActionKind.Stand));
            app.Presenter.View.Walk.SetPose(app.Presenter.View.Environment.EntryPosition,app.Presenter.View.Environment.EntryYaw);
            app.Presenter.View.Layout();Physics.SyncTransforms();
            yield return null;CheckBudget();
            Assert.That(Object.FindObjectsByType<G3SliceBootstrap>(FindObjectsSortMode.None).Count(x=>x.isActiveAndEnabled),Is.EqualTo(1));
            Assert.That(Camera.allCameras.Count(x=>x.enabled&&x.gameObject.activeInHierarchy),Is.EqualTo(1));
            var environment=app.Presenter.View.Environment;
            var candidates=environment.GetComponentsInChildren<Light>().Where(x=>x.type==LightType.Spot&&x.shadows!=LightShadows.None).ToArray();
            Assert.That(candidates.Length,Is.EqualTo(2));
            Assert.That(candidates.Select(x=>x.name).OrderBy(x=>x).ToArray(),Is.EqualTo(new[]{"Table reading pendant","Warm counter pendant"}));
            lights=candidates.Select(x=>new LightSnapshot(x)).ToArray();
            geometry=app.GetComponentsInChildren<Renderer>(true).Select(x=>new RendererSnapshot(x)).ToArray();
            stateHash=StateCodec.ComputeHash(app.Presenter.Snapshot);cameraPosition=app.SceneCamera.transform.position;
            cameraRotation=app.SceneCamera.transform.rotation;cameraFov=app.SceneCamera.fieldOfView;measuringPipeline=QualitySettings.renderPipeline;
            receipt.stateSha256=stateHash;receipt.cameraPosition=cameraPosition;receipt.cameraEuler=app.SceneCamera.transform.eulerAngles;receipt.cameraFov=cameraFov;receipt.sceneRenderers=geometry.Length;
            receipt.shopRenderers=environment.RenderedShopRendererCount;receipt.shopMaterials=environment.RenderedShopMaterialCount;
            receipt.setupElapsedMs=total.ElapsedMilliseconds;receipt.setupComplete=true;receipt.stage="READY";WriteReceipt();
        }
        void Hide(GameObject go){if(go.activeSelf&&!hidden.ContainsKey(go)){hidden.Add(go,true);go.SetActive(false);}}

        [UnityTest,Timeout(180000)]
        public IEnumerator AdditionalShadowCostAbaKeepsSceneAndRestoresLights()
        {
            try
            {
                BeginCameraObservation();
                for(int p=0;p<Phases.Length;p++)
                {
                    CheckBudget();bool disable=p==1;
                    foreach(var snapshot in lights)snapshot.Light.shadows=disable?LightShadows.None:snapshot.Shadows;
                    RequireInvariant(disable);
                    if(p==2)receipt.a2Restored=true;
                    var phase=new PhaseReceipt{phase=Phases[p],shadowedAdditionalLights=disable?0:2};phases.Add(phase);
                    receipt.stage=Phases[p];WriteReceipt();var phaseClock=Stopwatch.StartNew();
                    for(int warm=0;warm<WarmupFrames;warm++)
                    {
                        int beforeRender=cameraRenderCount;yield return null;
                        Assert.That(cameraRenderCount-beforeRender,Is.InRange(1,16),"Warmup must render the actual G3 camera");
                        phase.warmupCompleted++;receipt.measuredAndWarmupFrames++;phase.elapsedMs=phaseClock.ElapsedMilliseconds;CheckBudget(phaseClock);
                    }
                    OpenReaders();
                    try
                    {
                        for(int sample=0;sample<SampleFrames;sample++)
                        {
                            int before=Time.frameCount,beforeRender=cameraRenderCount;var frameClock=Stopwatch.StartNew();
                            yield return null;double frameWall=frameClock.Elapsed.TotalMilliseconds;phase.elapsedMs=phaseClock.ElapsedMilliseconds;CheckBudget(phaseClock);
                            Assert.That(Time.frameCount,Is.GreaterThan(before),"A measurement must contain an actual player frame");
                            int rendered=cameraRenderCount-beforeRender;
                            Assert.That(rendered,Is.InRange(1,16),"A sample must observe the actual G3 camera render callback");
                            phase.samples.Add(new FrameSample{index=sample,frameDelta=Time.frameCount-before,cameraRenderDelta=rendered,
                                wallMs=frameWall,metrics=readers.Select(x=>x.Sample()).ToArray()});
                            receipt.measuredAndWarmupFrames++;
                        }
                    }
                    finally{CloseReaders();}
                    RequireInvariant(disable);phase.elapsedMs=phaseClock.ElapsedMilliseconds;phase.complete=true;WriteReceipt();
                }
                receipt.stateUnchanged=StateCodec.ComputeHash(app.Presenter.Snapshot)==stateHash;
                receipt.renderingUnchanged=true;CheckBudget();receipt.measurementElapsedMs=total.ElapsedMilliseconds;receipt.measurementsComplete=true;
            }
            finally
            {
                // Restore first; a diagnostic-write failure cannot prevent restoration.
                receipt.finallyRestored=TryRestoreLights();receipt.stage="RESTORED";
                EndCameraObservation();CloseReaders();WriteReceipt();
            }
            Assert.That(receipt.finallyRestored,Is.True);Assert.That(receipt.a2Restored,Is.True);
            Assert.That(receipt.stateUnchanged,Is.True);Assert.That(receipt.measuredAndWarmupFrames,Is.EqualTo(24));
            Assert.That(writeFailed,Is.False,"Bounded performance receipt must be written");
            // No assertion about which phase is faster, no device or quality verdict.
        }
        void BeginCameraObservation()
        {if(observingCamera)return;cameraRenderCount=0;RenderPipelineManager.endCameraRendering+=CameraRendered;observingCamera=true;}
        void CameraRendered(ScriptableRenderContext context,Camera camera)
        {if(app!=null&&app.Presenter!=null&&camera==app.SceneCamera)cameraRenderCount++;}
        void EndCameraObservation()
        {if(!observingCamera)return;RenderPipelineManager.endCameraRendering-=CameraRendered;observingCamera=false;}
        void RequireInvariant(bool shadowsOff)
        {
            Assert.That(StateCodec.ComputeHash(app.Presenter.Snapshot),Is.EqualTo(stateHash));
            Assert.That(app.SceneCamera.transform.position,Is.EqualTo(cameraPosition));
            Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(cameraRotation));
            Assert.That(app.SceneCamera.fieldOfView,Is.EqualTo(cameraFov));
            Assert.That(app.SceneCamera.targetTexture,Is.SameAs(target));Assert.That(QualitySettings.renderPipeline,Is.SameAs(measuringPipeline));
            Assert.That(target.width,Is.EqualTo(1280));Assert.That(target.height,Is.EqualTo(720));
            foreach(var light in lights)light.Require(shadowsOff?LightShadows.None:light.Shadows);
            foreach(var renderer in geometry)renderer.Require();
        }
        void CheckBudget(Stopwatch phase=null)
        {Assert.That(total.Elapsed.TotalSeconds,Is.LessThan(180),"Performance diagnosis exceeded 180 seconds");if(phase!=null)Assert.That(phase.Elapsed.TotalSeconds,Is.LessThan(60),"Performance phase exceeded 60 seconds");}
        void OpenReaders()
        {
            CloseReaders();var available=new List<ProfilerRecorderHandle>();ProfilerRecorderHandle.GetAvailable(available);
            foreach(var spec in Specs)readers.Add(new MetricReader(spec,available));
        }
        void CloseReaders(){foreach(var reader in readers){try{reader.Dispose();}catch{cleanupFailed=true;}}readers.Clear();}
        bool TryRestoreLights()
        {
            if(lights==null)return false;bool ok=true;
            foreach(var snapshot in lights)
            {try{if(snapshot.Light==null){ok=false;continue;}snapshot.Light.shadows=snapshot.Shadows;if(snapshot.Light.shadows!=snapshot.Shadows)ok=false;}catch{ok=false;}}
            return ok;
        }
        void WriteReceipt()
        {
            if(receipt==null)return;
            try
            {
                receipt.elapsedMs=total.ElapsedMilliseconds;receipt.phases=phases.ToArray();
                receipt.status=receipt.measurementsComplete&&receipt.finallyRestored&&receipt.teardownRestored&&receipt.cleanupComplete&&!writeFailed&&!cleanupFailed?"COMPLETE_MEASUREMENTS_ONLY":"PARTIAL_MEASUREMENTS_ONLY";
                string json=JsonUtility.ToJson(receipt,true);if(Encoding.UTF8.GetByteCount(json)>ReceiptBytes)throw new InvalidOperationException("Bounded receipt overflow");
                Directory.CreateDirectory(Path.GetDirectoryName(output));File.WriteAllText(output,json);
            }
            catch{writeFailed=true;}
        }
        void Cleanup(Action action){try{action();}catch{cleanupFailed=true;}}
        [UnityTearDown]
        public IEnumerator RestoreScene()
        {
            if(receipt!=null)receipt.teardownRestored=TryRestoreLights();
            EndCameraObservation();CloseReaders();
            Cleanup(()=>{if(app!=null){if(app.Presenter!=null)app.SceneCamera.targetTexture=null;Object.Destroy(app.gameObject);}});
            Cleanup(()=>{if(target!=null){target.Release();Object.Destroy(target);}});
            Cleanup(()=>{if(store!=null)store.Dispose();});store=null;
            Cleanup(()=>{if(storeDirectory!=null&&Directory.Exists(storeDirectory))Directory.Delete(storeDirectory,true);});
            yield return null;
            if(capturedGlobals)
            {
                Cleanup(()=>GraphicsSettings.defaultRenderPipeline=priorDefault);
                Cleanup(()=>QualitySettings.renderPipeline=priorQuality);
                Cleanup(()=>{if(prior.IsValid()&&prior.isLoaded)SceneManager.SetActiveScene(prior);});
            }
            if(scene.IsValid()&&scene.isLoaded)
            {
                AsyncOperation unload=null;Cleanup(()=>unload=SceneManager.UnloadSceneAsync(scene));
                var clock=Stopwatch.StartNew();while(unload!=null&&!unload.isDone&&clock.Elapsed.TotalSeconds<10)yield return null;
                if(unload==null||!unload.isDone)cleanupFailed=true;
            }
            foreach(var pair in hidden)Cleanup(()=>{if(pair.Key!=null)pair.Key.SetActive(pair.Value);else cleanupFailed=true;});hidden.Clear();
            if(capturedGlobals&&SceneManager.GetActiveScene().handle!=prior.handle)cleanupFailed=true;
            if(receipt!=null){receipt.stage="TEARDOWN";receipt.cleanupComplete=!cleanupFailed;WriteReceipt();}
            Assert.That(cleanupFailed,Is.False);Assert.That(writeFailed,Is.False);
            if(receipt!=null&&receipt.setupComplete)Assert.That(receipt.teardownRestored,Is.True);
        }
        static bool IsSoftwareRenderer(){string name=(SystemInfo.graphicsDeviceName??"").ToLowerInvariant();return name.Contains("llvmpipe")||name.Contains("softpipe");}
        static string Arg(string name){var args=Environment.GetCommandLineArgs();for(int i=0;i<args.Length-1;i++)if(args[i]==name)return args[i+1];return "UNAVAILABLE";}

        sealed class LightSnapshot
        {
            public readonly Light Light;public readonly LightShadows Shadows;
            readonly float intensity,range,spotAngle,innerSpotAngle,strength,bias,normalBias;readonly Color color;readonly Vector3 position;readonly Quaternion rotation;
            public LightSnapshot(Light l){Light=l;Shadows=l.shadows;intensity=l.intensity;range=l.range;spotAngle=l.spotAngle;innerSpotAngle=l.innerSpotAngle;strength=l.shadowStrength;bias=l.shadowBias;normalBias=l.shadowNormalBias;color=l.color;position=l.transform.position;rotation=l.transform.rotation;}
            public void Require(LightShadows shadows)
            {Assert.That(Light,Is.Not.Null);Assert.That(Light.shadows,Is.EqualTo(shadows));Assert.That(Light.intensity,Is.EqualTo(intensity));Assert.That(Light.range,Is.EqualTo(range));Assert.That(Light.spotAngle,Is.EqualTo(spotAngle));Assert.That(Light.innerSpotAngle,Is.EqualTo(innerSpotAngle));Assert.That(Light.shadowStrength,Is.EqualTo(strength));Assert.That(Light.shadowBias,Is.EqualTo(bias));Assert.That(Light.shadowNormalBias,Is.EqualTo(normalBias));Assert.That(Light.color,Is.EqualTo(color));Assert.That(Light.transform.position,Is.EqualTo(position));Assert.That(Light.transform.rotation,Is.EqualTo(rotation));}
        }
        sealed class RendererSnapshot
        {
            readonly Renderer renderer;readonly Material[] materials;readonly Mesh mesh;readonly Matrix4x4 matrix;readonly bool enabled,active;
            public RendererSnapshot(Renderer r){renderer=r;materials=r.sharedMaterials;mesh=r.GetComponent<MeshFilter>()?.sharedMesh;matrix=r.localToWorldMatrix;enabled=r.enabled;active=r.gameObject.activeSelf;}
            public void Require(){Assert.That(renderer,Is.Not.Null);Assert.That(renderer.sharedMaterials,Is.EqualTo(materials));Assert.That(renderer.GetComponent<MeshFilter>()?.sharedMesh,Is.SameAs(mesh));Assert.That(renderer.localToWorldMatrix,Is.EqualTo(matrix));Assert.That(renderer.enabled,Is.EqualTo(enabled));Assert.That(renderer.gameObject.activeSelf,Is.EqualTo(active));}
        }
        sealed class MetricSpec
        {public readonly string Code,Name;public readonly bool Time;public MetricSpec(string code,string name,bool time){Code=code;Name=name;Time=time;}}
        sealed class MetricReader : IDisposable
        {
            readonly MetricSpec spec;ProfilerRecorder recorder;string unavailable="NOT_EXPOSED";int previousCount;
            public MetricReader(MetricSpec spec,List<ProfilerRecorderHandle> handles)
            {
                this.spec=spec;
                var matches=handles.Where(h=>ProfilerRecorderHandle.GetDescription(h).Name==spec.Name).ToArray();
                if(matches.Length==0)return;if(matches.Length!=1){unavailable="AMBIGUOUS_MARKER";return;}
                var description=ProfilerRecorderHandle.GetDescription(matches[0]);
                var expected=spec.Time?ProfilerMarkerDataUnit.TimeNanoseconds:ProfilerMarkerDataUnit.Count;
                if(description.UnitType!=expected){unavailable="UNIT_MISMATCH";return;}
                if(description.DataType!=ProfilerMarkerDataType.Int64){unavailable="TYPE_MISMATCH";return;}
                try
                {
                    recorder=new ProfilerRecorder(matches[0],16,ProfilerRecorderOptions.StartImmediately|ProfilerRecorderOptions.SumAllSamplesInFrame);
                    unavailable=recorder.Valid?"NO_NEW_SAMPLE":"INVALID_RECORDER";
                }
                catch(Exception){unavailable="RECORDER_UNAVAILABLE";}
            }
            public MetricSample Sample()
            {
                var result=new MetricSample{code=spec.Code,unit=spec.Time?"NANOSECONDS":"COUNT",reason=unavailable,value=-1,milliseconds=-1};
                if(!recorder.Valid)return result;
                result.isRunning=recorder.IsRunning;result.sampleCount=recorder.Count;
                if(!result.isRunning){result.reason="NOT_RUNNING";return result;}
                if(result.sampleCount<=previousCount){result.reason="NO_NEW_SAMPLE";return result;}
                var sample=recorder.GetSample(result.sampleCount-1);previousCount=result.sampleCount;
                if(sample.Value<0){result.reason="NEGATIVE_VALUE";return result;}
                result.available=true;result.reason="OBSERVED";result.value=sample.Value;result.milliseconds=spec.Time?sample.Value/1000000d:-1;return result;
            }
            public void Dispose(){if(recorder.Valid)recorder.Dispose();}
        }
        [Serializable] sealed class Receipt
        {
            public int schemaVersion=1,width=1280,height=720,warmupFrames=WarmupFrames,sampleFrames=SampleFrames,measuredAndWarmupFrames,shopRenderers,shopMaterials,sceneRenderers;
            public string scope=Scope,testIdentity=Identity,sourceCommit,reviewedCandidateCommit,runId,runAttempt,unityVersion,graphicsDeviceType,status="PARTIAL_MEASUREMENTS_ONLY",stage="SETUP",gpuTiming="NOT_COLLECTED_CPU_COUNTERS_ONLY",visualReview="NOT_EVALUATED",deviceQa="NOT_RUN",stateSha256="UNAVAILABLE",cameraOrigin="FIXTURE_POSITIONED_NORMAL_ENTRY";
            public Vector3 cameraPosition,cameraEuler;public float cameraFov;
            public long elapsedMs,setupElapsedMs,measurementElapsedMs;public bool softwareRendererDetected,setupComplete,a2Restored,finallyRestored,teardownRestored,stateUnchanged,renderingUnchanged,measurementsComplete,cleanupComplete;
            public PhaseReceipt[] phases=new PhaseReceipt[0];
        }
        [Serializable] sealed class PhaseReceipt
        {public string phase;public int shadowedAdditionalLights,warmupCompleted;public long elapsedMs;public bool complete;public List<FrameSample> samples=new List<FrameSample>();}
        [Serializable] sealed class FrameSample
        {public int index,frameDelta,cameraRenderDelta;public double wallMs;public MetricSample[] metrics;}
        [Serializable] sealed class MetricSample
        {public string code,unit,reason;public bool available,isRunning;public int sampleCount;public long value;public double milliseconds;}
    }
}

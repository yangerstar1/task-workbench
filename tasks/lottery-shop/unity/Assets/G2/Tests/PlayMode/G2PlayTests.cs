using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Lottery.G2.Core;
using Lottery.G2.Interaction;
using Lottery.G2.Persistence;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;
using IPhase = UnityEngine.InputSystem.TouchPhase;

namespace Lottery.G2.PlayMode.Tests
{
    // SIMULATED_INPUT_SYSTEM: real device events in the actual scene, not Android touch evidence.
    public sealed class G2PlayTests
    {
        Scene prior,scene;
        readonly List<GameObject> hiddenRoots=new List<GameObject>();
        G2SliceBootstrap app;
        Mouse mouse; Touchscreen touch; Keyboard keyboard;
        InputSettings.UpdateMode oldUpdate;
        RenderPipelineAsset previousPipeline,previousQuality;
        UniversalRenderPipelineAsset pipeline;
        FileStateStore testStore;
        ToggleFault faults;
        sealed class ToggleFault : IStoreFaultInjector
        {
            public bool BeforeWrite,AfterPublish,BlockRecovery;
            public void OnPoint(StoreFaultPoint point)
            {
                if(point==StoreFaultPoint.BeforeWrite && BeforeWrite) { BeforeWrite=false; throw new IOException("Synthetic pre-write failure"); }
                if(point==StoreFaultPoint.AfterPublish && AfterPublish) { AfterPublish=false; throw new IOException("Synthetic post-publish failure"); }
                if(point==StoreFaultPoint.BeforeRecoveryRead && BlockRecovery) throw new IOException("Synthetic unavailable recovery read");
            }
        }
        string directory;
        SlicePresenter P => app.Presenter;
        InputRouter Router => P.Router;
        RunState State => P.Snapshot;
        [UnitySetUp]
        public IEnumerator SetUp()
        {
            prior=SceneManager.GetActiveScene();
            foreach(var root in prior.GetRootGameObjects()) if(root.activeSelf) { hiddenRoots.Add(root); root.SetActive(false); }
            scene=SceneManager.CreateScene("G2 isolated input and camera test"); SceneManager.SetActiveScene(scene);
            previousPipeline=GraphicsSettings.defaultRenderPipeline; previousQuality=QualitySettings.renderPipeline;
            Assert.That(Application.isPlaying,Is.True,"This assembly must run in PlayMode");
#if UNITY_EDITOR
            pipeline=UnityEditor.AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/GeneratedProbe/Pipeline.asset");
#else
            Assert.Fail("This simulated-input CI fixture requires the restored Editor pipeline asset");
#endif
            Assert.That(pipeline,Is.Not.Null);
            GraphicsSettings.defaultRenderPipeline=pipeline; QualitySettings.renderPipeline=pipeline;
            oldUpdate=InputSystem.settings.updateMode; InputSystem.settings.updateMode=InputSettings.UpdateMode.ProcessEventsManually;
            mouse=InputSystem.AddDevice<Mouse>(); touch=InputSystem.AddDevice<Touchscreen>(); keyboard=InputSystem.AddDevice<Keyboard>();
            directory=Path.Combine(Path.GetTempPath(),"lottery-g2-play-"+Guid.NewGuid().ToString("N"));
            faults=new ToggleFault();
            testStore=new FileStateStore(directory,RunState.CreateNew("g2-play-fixed-run","g2-play-fixed-seed"),faults);
            var core=new TicketService(testStore);
            app=new GameObject("Real G2 scene bootstrap").AddComponent<G2SliceBootstrap>(); app.Initialize(core,null,testStore); Router.PollAutomatically=false;
            Physics.SyncTransforms();
            yield return null;
            Assert.That(app.SceneCamera.orthographic,Is.True);
        }
        [UnityTearDown]
        public IEnumerator TearDown()
        {
            if(app!=null) Object.Destroy(app.gameObject);
            testStore?.Dispose();
            if(mouse!=null && mouse.added) InputSystem.RemoveDevice(mouse);
            if(touch!=null && touch.added) InputSystem.RemoveDevice(touch);
            if(keyboard!=null && keyboard.added) InputSystem.RemoveDevice(keyboard);
            InputSystem.settings.updateMode=oldUpdate;
            GraphicsSettings.defaultRenderPipeline=previousPipeline; QualitySettings.renderPipeline=previousQuality;
            if(prior.IsValid()) SceneManager.SetActiveScene(prior);
            if(scene.IsValid()) yield return SceneManager.UnloadSceneAsync(scene);
            foreach(var root in hiddenRoots) if(root!=null) root.SetActive(true); hiddenRoots.Clear();
            if(directory!=null && Directory.Exists(directory)) Directory.Delete(directory,true);
            yield return null;
        }
        Vector2 ScreenUv(float u,float v) => app.SceneCamera.WorldToScreenPoint(P.View.Surface.UvToWorld(new Vector2(u,v)));
        void MouseEvent(Vector2 position,bool down)
        {
            var state=new MouseState { position=position,buttons=(ushort)(down?1:0) };
            InputSystem.QueueStateEvent(mouse,state); InputSystem.Update(); Router.PollInput();
        }
        void Click(SliceAction action)
        {
            var p=P.View.ButtonRect(action).center; MouseEvent(p,true); MouseEvent(p,false);
        }
        void TouchEvent(int id,IPhase phase,Vector2 position)
        {
            InputSystem.QueueStateEvent(touch,new TouchState { touchId=id,phase=phase,position=position,pressure=phase==IPhase.Ended?0:1 });
            InputSystem.Update(); Router.PollInput();
        }
        void Serpentine(float right)
        {
            MouseEvent(ScreenUv(.008f,.012f),true);
            bool toRight=true;
            for(float v=.012f;v<1;v+=.072f)
            {
                MouseEvent(ScreenUv(toRight?right:.008f,Mathf.Min(v,.99f)),true);
                MouseEvent(ScreenUv(toRight?right:.008f,Mathf.Min(v+.072f,.99f)),true); toRight=!toRight;
            }
            MouseEvent(ScreenUv(right,.99f),false);
        }
        int RevealedPixels()
        {
            var mask=State.CurrentTicket.Scratch; int count=0;
            for(int i=0;i<mask.Width*mask.Height;i++) if(mask.IsRevealed(i)) count++;
            return count;
        }
        [UnityTest]
        public IEnumerator BuyHalfScratchPanelReturnRevealAndClaimCommitsOneTicket()
        {
            long initial=State.CashMinor; Click(SliceAction.Buy);
            Assert.That(State.CashMinor,Is.EqualTo(initial-1000));
            string id=State.CurrentTicket.Id; long prize=State.CurrentTicket.RawPrizeMinor;
            Serpentine(.47f); Assert.That(RevealedPixels(),Is.InRange(5000,26000));
            Assert.That(State.CurrentTicket.Phase,Is.EqualTo(TicketPhase.ACTIVE));
            string halfHash=StateCodec.ComputeHash(State);
            Click(SliceAction.OpenPanel); Assert.That(Router.Mode,Is.EqualTo(SliceMode.PANEL));
            MouseEvent(ScreenUv(.85f,.3f),true); MouseEvent(ScreenUv(.85f,.3f),false);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(halfHash));
            Click(SliceAction.ClosePanel); Assert.That(State.CurrentTicket.Id,Is.EqualTo(id));
            Serpentine(.992f); Assert.That(State.CurrentTicket.Scratch.IsFullyRevealed,Is.True);
            Assert.That(State.CashMinor,Is.EqualTo(initial-1000),"Revealed prize must not be in the wallet yet");
            Click(SliceAction.Claim); Assert.That(State.CashMinor,Is.EqualTo(initial-1000+prize));
            Assert.That(State.CurrentTicket.Phase,Is.EqualTo(TicketPhase.SETTLED)); Assert.That(State.SettledTicketCount,Is.EqualTo(1));
            string settledHash=StateCodec.ComputeHash(State); long settledCash=State.CashMinor,settledRevision=State.Revision;
            testStore.Dispose();
            using var reopened=new FileStateStore(directory,RunState.CreateNew("ignored","ignored"));
            var recovered=new TicketService(reopened);
            Assert.That(StateCodec.ComputeHash(recovered.Snapshot),Is.EqualTo(settledHash));
            Assert.That(recovered.Claim(id,"duplicate-claim",settledRevision).Code,Is.EqualTo("ALREADY_SETTLED"));
            Assert.That(recovered.Snapshot.CashMinor,Is.EqualTo(settledCash));
            yield return null;
        }
        [UnityTest]
        public IEnumerator UiHitConsumesGestureAndPanelPreservesTicket()
        {
            Click(SliceAction.Buy); string initial=StateCodec.ComputeHash(State);
            MouseEvent(P.View.ButtonRect(SliceAction.Claim).center,true); MouseEvent(ScreenUv(.5f,.5f),true); MouseEvent(ScreenUv(.5f,.5f),false);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(initial),"Disabled claim must eat its whole gesture");
            Click(SliceAction.OpenPanel); Click(SliceAction.ClosePanel); Click(SliceAction.OpenPanel);
            MouseEvent(ScreenUv(.1f,.1f),true); MouseEvent(ScreenUv(.9f,.9f),true); MouseEvent(ScreenUv(.9f,.9f),false);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(initial));
            var cameraPosition=app.SceneCamera.transform.position; var cameraRotation=app.SceneCamera.transform.rotation;
            Click(SliceAction.ClosePanel); Serpentine(.2f);
            Assert.That(app.SceneCamera.transform.position,Is.EqualTo(cameraPosition)); Assert.That(app.SceneCamera.transform.rotation,Is.EqualTo(cameraRotation));
            yield return null;
        }
        [UnityTest]
        public IEnumerator SecondTouchCannotTakeOverAndTouchUsesSameUvProjection()
        {
            Click(SliceAction.Buy);
            TouchEvent(11,IPhase.Began,ScreenUv(.10f,.15f)); TouchEvent(22,IPhase.Began,ScreenUv(.90f,.85f));
            TouchEvent(11,IPhase.Moved,ScreenUv(.25f,.15f)); TouchEvent(11,IPhase.Ended,ScreenUv(.25f,.15f));
            TouchEvent(22,IPhase.Moved,ScreenUv(.75f,.85f)); TouchEvent(22,IPhase.Ended,ScreenUv(.75f,.85f));
            Assert.That(State.CurrentTicket.Scratch.IsRevealed(45,19),Is.True);
            Assert.That(State.CurrentTicket.Scratch.IsRevealed(230,108),Is.False,"Secondary finger must neither scratch nor take over");
            InputSystem.Update(); Router.PollInput();
            TouchEvent(33,IPhase.Began,ScreenUv(.90f,.85f)); TouchEvent(33,IPhase.Canceled,ScreenUv(.90f,.85f));
            Assert.That(State.CurrentTicket.Scratch.IsRevealed(230,108),Is.True);
            Assert.That(Router.CapturedPointerId,Is.EqualTo(-1));
            yield return null;
        }
        [UnityTest]
        public IEnumerator PointerExitReentryAndFocusCancelDoNotBridge()
        {
            Click(SliceAction.Buy);
            MouseEvent(ScreenUv(.10f,.8f),true); MouseEvent(new Vector2(-100,-100),true); MouseEvent(ScreenUv(.90f,.8f),true); MouseEvent(ScreenUv(.90f,.8f),false);
            Assert.That(State.CurrentTicket.Scratch.IsRevealed(128,102),Is.False,"Out-of-ticket travel cannot bridge a scratch");
            MouseEvent(ScreenUv(.10f,.4f),true); Router.NotifyFocus(false); Router.NotifyFocus(true);
            MouseEvent(ScreenUv(.90f,.4f),true); MouseEvent(ScreenUv(.90f,.4f),false);
            Assert.That(State.CurrentTicket.Scratch.IsRevealed(230,51),Is.False,"Held pointer must lift after focus cancellation");
            MouseEvent(ScreenUv(.90f,.4f),true); MouseEvent(ScreenUv(.90f,.4f),false);
            Assert.That(State.CurrentTicket.Scratch.IsRevealed(230,51),Is.True);
            Assert.That(State.CurrentTicket.Scratch.IsRevealed(128,51),Is.False);
            yield return null;
        }
        [UnityTest]
        public IEnumerator BackCancelsCaptureAndReturnsToCommittedTicket()
        {
            Click(SliceAction.Buy); string id=State.CurrentTicket.Id;
            MouseEvent(ScreenUv(.1f,.3f),true);
            InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.Escape)); InputSystem.Update(); Router.PollInput();
            Assert.That(Router.Mode,Is.EqualTo(SliceMode.PANEL)); Assert.That(Router.CapturedPointerId,Is.EqualTo(-1));
            InputSystem.QueueStateEvent(keyboard,new KeyboardState()); InputSystem.Update(); Router.PollInput(); MouseEvent(ScreenUv(.9f,.3f),false);
            Click(SliceAction.ClosePanel); Assert.That(State.CurrentTicket.Id,Is.EqualTo(id)); Assert.That(State.CurrentTicket.Scratch.IsRevealed(128,38),Is.False);
            Assert.That(P.View.ButtonRect(SliceAction.OpenPanel).xMin,Is.GreaterThanOrEqualTo(Screen.safeArea.xMin));
            Assert.That(P.View.ButtonRect(SliceAction.Buy).yMin,Is.GreaterThanOrEqualTo(Screen.safeArea.yMin));
            yield return null;
        }
        [UnityTest]
        public IEnumerator SaveFailureNeverShowsUncommittedScratch()
        {
            Click(SliceAction.Buy); string hash=StateCodec.ComputeHash(State); faults.BeforeWrite=true;
            MouseEvent(ScreenUv(.15f,.25f),true); MouseEvent(ScreenUv(.35f,.25f),true); MouseEvent(ScreenUv(.35f,.25f),false);
            Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash)); Assert.That(P.IsCommitting,Is.True);
            Assert.That(P.View.Surface.CommittedMaskTexture.GetPixel(45,32).r,Is.EqualTo(0));
            Click(SliceAction.Retry); Assert.That(P.IsCommitting,Is.False);
            Assert.That(State.CurrentTicket.Scratch.IsRevealed(45,32),Is.True);
            Assert.That(P.View.Surface.CommittedMaskTexture.GetPixel(45,32).r,Is.EqualTo(1));
            yield return null;
        }
        [UnityTest]
        public IEnumerator UnknownBuyBlocksInputUntilOriginalCommitIsRecovered()
        {
            long initial=State.CashMinor; faults.AfterPublish=true; faults.BlockRecovery=true; Click(SliceAction.Buy);
            Assert.That(Router.Mode,Is.EqualTo(SliceMode.COMMITTING)); Assert.That(State.CurrentTicket,Is.Null);
            Assert.That(State.CashMinor,Is.EqualTo(initial));
            Click(SliceAction.OpenPanel); Assert.That(P.PanelOpen,Is.False);
            Click(SliceAction.Retry); Assert.That(Router.Mode,Is.EqualTo(SliceMode.COMMITTING));
            faults.BlockRecovery=false; Click(SliceAction.Retry);
            Assert.That(State.TicketsPurchasedToday,Is.EqualTo(1)); Assert.That(State.CashMinor,Is.EqualTo(initial-1000));
            Assert.That(State.Commands.Count(c=>c.Kind=="BUY_TICKET"),Is.EqualTo(1)); Assert.That(P.IsCommitting,Is.False);
            yield return null;
        }
        [Serializable] sealed class FrameReceipt { public string stage,file,sha256,stateSha256; public long bytes; }
        [Serializable] sealed class RenderReceipt
        {
            public int schemaVersion=1,width=1280,height=720,sourceViewportWidth,sourceViewportHeight;
            public string scope="G2_CAMERA_RENDER_NOT_DEVICE_TESTED",sourceCommit,runId,unityVersion,rulesSha256;
            public string captureMethod="URP_STANDARD_REQUEST_READPIXELS",graphicsDeviceType,graphicsDeviceName;
            public string inputEvidence="SIMULATED_INPUT_SYSTEM",deviceQa="NOT_RUN",visualReview="PENDING";
            public FrameReceipt[] frames;
        }
        [UnityTest]
        public IEnumerator ActualUrpFramesShowCommittedMaskAndSettlement()
        {
            Assert.That(SystemInfo.graphicsDeviceType,Is.Not.EqualTo(GraphicsDeviceType.Null),"P3 requires a real graphics device; never promote a null renderer");
            string output=Path.GetFullPath(Path.Combine(Application.dataPath,"../../artifacts/g2-play/captures")); Directory.CreateDirectory(output);
            string receiptPath=Path.Combine(output,"render-receipt.json"); if(File.Exists(receiptPath)) File.Delete(receiptPath);
            var records=new List<FrameReceipt>(); var textures=new List<Texture2D>();
            try
            {
                Click(SliceAction.Buy); yield return null; textures.Add(Capture("initial",output,records));
                Serpentine(.47f); yield return null; textures.Add(Capture("half",output,records));
                Assert.That(State.CurrentTicket.Scratch.IsRevealed(45,32),Is.True); Assert.That(State.CurrentTicket.Scratch.IsRevealed(215,32),Is.False);
                Assert.That(ChangedPixels(textures[0],textures[1],.08f,.38f),Is.GreaterThan(500),"Committed scratch must change local rendered pixels");
                Assert.That(ChangedPixels(textures[0],textures[1],.72f,.94f),Is.LessThan(12),"Untouched scratch region must remain covered");
                Serpentine(.992f); Assert.That(State.CurrentTicket.Scratch.IsFullyRevealed,Is.True); yield return null; textures.Add(Capture("revealed",output,records));
                Assert.That(ChangedPixels(textures[1],textures[2],.72f,.94f),Is.GreaterThan(500));
                long before=State.CashMinor,prize=State.CurrentTicket.RawPrizeMinor; Click(SliceAction.Claim); yield return null; textures.Add(Capture("settled",output,records));
                Assert.That(State.CashMinor,Is.EqualTo(before+prize)); Assert.That(State.SettledTicketCount,Is.EqualTo(1));
                var receipt=new RenderReceipt {sourceCommit=Arg("-probeCommit"),runId=Arg("-probeRunId"),unityVersion=Application.unityVersion,rulesSha256=NumberTicketRules.RulesSha256,
                    sourceViewportWidth=Screen.width,sourceViewportHeight=Screen.height,graphicsDeviceType=SystemInfo.graphicsDeviceType.ToString(),graphicsDeviceName=SystemInfo.graphicsDeviceName.Substring(0,Math.Min(160,SystemInfo.graphicsDeviceName.Length)),frames=records.ToArray()};
                Assert.That(receipt.sourceCommit,Does.Match("^[0-9a-f]{40}$")); Assert.That(receipt.runId,Does.Match("^[1-9][0-9]*$"));
                File.WriteAllText(receiptPath,JsonUtility.ToJson(receipt,true));
            }
            finally { foreach(var texture in textures) Object.Destroy(texture); }
        }
        Texture2D Capture(string stage,string output,List<FrameReceipt> records)
        {
            P.View.RefreshGlyphGeometry();
            var target=new RenderTexture(1280,720,24,RenderTextureFormat.ARGB32) { antiAliasing=1 }; target.Create();
            var request=new RenderPipeline.StandardRequest { destination=target };
            Assert.That(RenderPipeline.SupportsRenderRequest(app.SceneCamera,request),Is.True,"URP must support actual render requests");
            var old=RenderTexture.active; var texture=new Texture2D(1280,720,TextureFormat.RGB24,false);
            try
            {
                RenderPipeline.SubmitRenderRequest(app.SceneCamera,request); RenderTexture.active=target;
                texture.ReadPixels(new Rect(0,0,1280,720),0,0,false); texture.Apply(false,false);
                var sampled=new HashSet<Color32>(); var pixels=texture.GetPixels32();
                for(int i=0;i<pixels.Length;i+=499) sampled.Add(pixels[i]); Assert.That(sampled.Count,Is.GreaterThan(20),"Reject empty or flat placeholder frame");
                byte[] png=texture.EncodeToPNG(); Assert.That(png.Length,Is.InRange(10000,4*1024*1024));
                File.WriteAllBytes(Path.Combine(output,stage+".png"),png);
                records.Add(new FrameReceipt { stage=stage,file=stage+".png",sha256=StateCodec.HashBytes(png),bytes=png.Length,stateSha256=StateCodec.ComputeHash(State) });
                return texture;
            }
            finally { RenderTexture.active=old; target.Release(); Object.Destroy(target); }
        }
        int ChangedPixels(Texture2D before,Texture2D after,float u0,float u1)
        {
            var a=ScreenUv(u0,.14f); var b=ScreenUv(u1,.40f);
            int left=Mathf.RoundToInt(Mathf.Min(a.x,b.x)/Screen.width*1280),right=Mathf.RoundToInt(Mathf.Max(a.x,b.x)/Screen.width*1280);
            int bottom=Mathf.RoundToInt(Mathf.Min(a.y,b.y)/Screen.height*720),top=Mathf.RoundToInt(Mathf.Max(a.y,b.y)/Screen.height*720),changed=0;
            for(int y=bottom;y<top;y++) for(int x=left;x<right;x++) if(((Vector4)(before.GetPixel(x,y)-after.GetPixel(x,y))).sqrMagnitude>.02f) changed++;
            return changed;
        }
        static string Arg(string name) { var args=Environment.GetCommandLineArgs(); int i=Array.IndexOf(args,name); return i>=0 && i+1<args.Length?args[i+1]:""; }
    }
}

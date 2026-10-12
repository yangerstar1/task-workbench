using System;
using System.IO;
using Lottery.G2.Core;
using Lottery.G2.Persistence;
using Lottery.G2.Ads;
using UnityEngine;

namespace Lottery.G2.Interaction
{
    public sealed class G2SliceBootstrap : MonoBehaviour
    {
        public Font chineseFont;
        public Shader scratchShader,fontShader,flatShader,surfaceShader;
        FileStateStore ownedStore;
        public SlicePresenter Presenter { get; private set; }
        public Camera SceneCamera => Presenter.View.SceneCamera;
        public void Initialize(TicketService service=null,string storeDirectory=null,IStateStore sharedStore=null)
        {
            if(Presenter!=null) throw new InvalidOperationException("G2 bootstrap already initialized");
            if(chineseFont==null) chineseFont=Resources.Load<Font>("ProbeChinese");
            if(scratchShader==null) scratchShader=Shader.Find("Lottery/G2/Scratch");
            if(fontShader==null) fontShader=Shader.Find("Lottery/G2/Font");
            if(flatShader==null) flatShader=Shader.Find("Lottery/G2/Flat");
            if(surfaceShader==null) surfaceShader=Shader.Find("Universal Render Pipeline/Lit");
            if(service==null)
            {
                string directory=storeDirectory??Path.Combine(Application.persistentDataPath,"G2Slice");
                ownedStore=new FileStateStore(directory,RunState.CreateNew(Guid.NewGuid().ToString("N"),Guid.NewGuid().ToString("N")));
                sharedStore=ownedStore; service=new TicketService(sharedStore);
            }
            var view=gameObject.AddComponent<G2SceneView>(); view.Initialize(chineseFont,flatShader,fontShader,scratchShader,surfaceShader);
            var fake=sharedStore==null?null:new FakeRewardedAdService(sharedStore);
            var ads=sharedStore==null?null:new AdPurchaseService(sharedStore,fake);
            Presenter=gameObject.AddComponent<SlicePresenter>(); Presenter.Initialize(service,view,ads,fake);
            var router=gameObject.AddComponent<InputRouter>(); router.Initialize(Presenter,view); Presenter.Router=router;
        }
        void OnDestroy() { ownedStore?.Dispose(); }
        void Start() { if(Presenter==null) Initialize(); }
    }
}

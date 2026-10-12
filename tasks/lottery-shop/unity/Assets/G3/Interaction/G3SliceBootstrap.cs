using System;
using System.IO;
using Lottery.G3.Core;
using Lottery.G3.Persistence;
using Lottery.G3.Rendering;
using UnityEngine;

namespace Lottery.G3.Interaction
{
    public sealed class G3SliceBootstrap : MonoBehaviour
    {
        public Font chineseFont;
        public Shader paperShader,silverShader,maskedFontShader,fontShader,flatShader,surfaceShader;
        public ApprovedArtworkBinding numberArtwork,challengeArtwork;
        FileStateStore ownedStore;
        public G3Presenter Presenter {get;private set;}
        public Camera SceneCamera=>Presenter.View.SceneCamera;
        public void Initialize(DayGameService service=null,string storeDirectory=null,IStateStore sharedStore=null)
        {
            if(Presenter!=null)throw new InvalidOperationException("G3 bootstrap initialized twice");
            if(chineseFont==null)chineseFont=Resources.Load<Font>("ProbeChinese");
            if(paperShader==null)paperShader=Shader.Find("Lottery/G3/TicketPaper");if(silverShader==null)silverShader=Shader.Find("Lottery/G3/LocalSilver");if(maskedFontShader==null)maskedFontShader=Shader.Find("Lottery/G3/MaskedFont");
            if(fontShader==null)fontShader=Shader.Find("Lottery/G2/Font");if(flatShader==null)flatShader=Shader.Find("Lottery/G2/Flat");if(surfaceShader==null)surfaceShader=Shader.Find("Universal Render Pipeline/Lit");
            if(numberArtwork==null)numberArtwork=Resources.Load<ApprovedArtworkBinding>("G3/number");if(challengeArtwork==null)challengeArtwork=Resources.Load<ApprovedArtworkBinding>("G3/challenge");
            if(service==null){ownedStore=new FileStateStore(storeDirectory??Path.Combine(Application.persistentDataPath,"g3-day-v1"),RunFactory.Create(Guid.NewGuid().ToString("N"),Guid.NewGuid().ToString("N")));sharedStore=ownedStore;service=new DayGameService(ownedStore);}
            var view=gameObject.AddComponent<G3SceneView>();view.Initialize(chineseFont,flatShader,fontShader,surfaceShader,paperShader,silverShader,maskedFontShader,numberArtwork,challengeArtwork);
            Presenter=gameObject.AddComponent<G3Presenter>();var router=gameObject.AddComponent<G3InputRouter>();Presenter.Router=router;router.Initialize(Presenter,view);Presenter.Initialize(service,view);
            Application.targetFrameRate=60;
        }
        void Start(){if(Presenter==null)Initialize();}
        void OnDestroy(){ownedStore?.Dispose();}
    }
}

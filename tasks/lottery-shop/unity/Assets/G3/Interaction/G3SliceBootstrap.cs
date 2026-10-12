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
        FileStateStore ownedStore;G3StartScreen startScreen;
        public G3StartScreen StartScreen=>startScreen;
        public static string DefaultStoreDirectory=>Path.Combine(Application.persistentDataPath,"g3-day-v2");
        static string ExistingOrNewDirectory=>HasStoredData(DefaultStoreDirectory)?DefaultStoreDirectory:HasStoredData(Path.Combine(Application.persistentDataPath,"g3-day-v1"))?Path.Combine(Application.persistentDataPath,"g3-day-v1"):DefaultStoreDirectory;
        public G3Presenter Presenter {get;private set;}
        public Camera SceneCamera=>Presenter.View.SceneCamera;
        public void Initialize(DayGameService service=null,string storeDirectory=null,IStateStore sharedStore=null)
        {
            if(Presenter!=null)throw new InvalidOperationException("G3 bootstrap initialized twice");
            if(chineseFont==null)chineseFont=Resources.Load<Font>("ProbeChinese");
            if(paperShader==null)paperShader=Shader.Find("Lottery/G3/TicketPaper");if(silverShader==null)silverShader=Shader.Find("Lottery/G3/LocalSilver");if(maskedFontShader==null)maskedFontShader=Shader.Find("Lottery/G3/MaskedFont");
            if(fontShader==null)fontShader=Shader.Find("Lottery/G2/Font");if(flatShader==null)flatShader=Shader.Find("Lottery/G2/Flat");if(surfaceShader==null)surfaceShader=Shader.Find("Universal Render Pipeline/Lit");
            if(numberArtwork==null)numberArtwork=Resources.Load<ApprovedArtworkBinding>("G3/number");if(challengeArtwork==null)challengeArtwork=Resources.Load<ApprovedArtworkBinding>("G3/challenge");
            if(service==null){ownedStore=new FileStateStore(storeDirectory??ExistingOrNewDirectory,RunFactory.Create(Guid.NewGuid().ToString("N"),Guid.NewGuid().ToString("N")));sharedStore=ownedStore;service=new DayGameService(ownedStore);}
            var view=gameObject.AddComponent<G3SceneView>();view.Initialize(chineseFont,flatShader,fontShader,surfaceShader,paperShader,silverShader,maskedFontShader,numberArtwork,challengeArtwork);
            Presenter=gameObject.AddComponent<G3Presenter>();var router=gameObject.AddComponent<G3InputRouter>();Presenter.Router=router;router.Initialize(Presenter,view);Presenter.Initialize(service,view);
            Application.targetFrameRate=60;
        }
        public static bool HasStoredData(string directory)=>Directory.Exists(directory)&&Directory.GetFiles(directory).Length>0;
        public bool TryStartNew(bool diagnostic,string storeDirectory=null)
        {
            string directory=storeDirectory??ExistingOrNewDirectory;
            if(Presenter!=null||HasStoredData(directory)||(diagnostic&&!FixtureAccess.Enabled))return false;
            var initial=diagnostic?RunFactory.CreateDiagnostic("g3-day-qafixture-001"):RunFactory.Create(Guid.NewGuid().ToString("N"),Guid.NewGuid().ToString("N"));
            ownedStore=new FileStateStore(directory,initial);
            if(!ownedStore.CanMutate){ownedStore.Dispose();ownedStore=null;return false;}
            Initialize(new DayGameService(ownedStore),directory,ownedStore);Presenter.Router.CancelGesture();return true;
        }
        public void ShowStartMenu(string storeDirectory=null)
        {
            if(Presenter!=null||startScreen!=null)throw new InvalidOperationException("G3 entry already selected");
            string directory=storeDirectory??ExistingOrNewDirectory;
            if(HasStoredData(directory)){Initialize(null,directory);return;}
            var menu=new GameObject("G3 explicit new-run choice");menu.transform.SetParent(transform,false);startScreen=menu.AddComponent<G3StartScreen>();
            startScreen.Initialize(chineseFont!=null?chineseFont:Resources.Load<Font>("ProbeChinese"),flatShader!=null?flatShader:Shader.Find("Lottery/G2/Flat"),fontShader!=null?fontShader:Shader.Find("Lottery/G2/Font"),FixtureAccess.Enabled,qa=>TryStartNew(qa,directory));
        }
        void Start(){if(Presenter==null&&startScreen==null)ShowStartMenu();}
        void OnDestroy(){ownedStore?.Dispose();}
    }
}

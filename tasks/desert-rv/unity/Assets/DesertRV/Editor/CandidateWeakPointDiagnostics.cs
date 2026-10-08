using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEngine;
using UnityEngine.SceneManagement;
namespace DesertRV.Editor
{
    public static class CandidateWeakPointDiagnostics
    {
        const BindingFlags Instance=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
        [Serializable] sealed class Sample
        {
            public string state,view,coreMaterial,imageLabel;public float fieldOfView=60,distance=3;public bool weakPointExposed,bodyUnchanged;
            public Quaternion[] localPlateRotations;public Vector3 cameraPosition;
        }
        [Serializable] sealed class Report
        {
            public string status="failed-editor-fixture",scope="explicit-Editor-fixture-real-presenter-not-full-gameplay";
            public bool calibratedForScene=false,visualAccepted=false;
            public string limitation="Fixture assigns actor combat references/phase using reflection, then uses real BeastCombatState window and actor.WeakPointExposed. Not a world encounter, collision test or end-to-end playthrough. Whole body is vulnerable during Recover; no directional damage rule.";
            public List<Sample> samples=new List<Sample>();
        }
        public static void Capture(GameObject subject,Camera camera,Action<string> capture)
        {
            var actor=subject.GetComponent<BeastActor>();var presenter=subject.GetComponent<BeastWeakPointPresentation>();
            if(!actor || !actor.armored || !presenter)throw new InvalidOperationException("Actual armored prefab presenter required.");
            if(!presenter.ValidateBindings(out var reason))throw new InvalidOperationException(reason);
            var report=new Report();var host=new GameObject("Explicit editor weakpoint fixture session");
            SceneManager.MoveGameObjectToScene(host,subject.scene);host.SetActive(false);
            bool presenterStarted=false;
            var originalJourney=actor.journey;var body=presenter.bodyRenderer;
            var bodyMaterials=(Material[])body.sharedMaterials.Clone();var emissions=bodyMaterials.Select(m=>m.HasProperty("_EmissionColor")?m.GetColor("_EmissionColor"):Color.black).ToArray();
            var closedMaterial=presenter.weakPointRenderer.sharedMaterials[0];var closed=presenter.armorPlates.Select(p=>p.localRotation).ToArray();
            try
            {
                var session=host.AddComponent<JourneySession>();var state=new DesertRV.SessionState();state.ConfigureStorm(-100d,1d,1d);state.Start();
                typeof(JourneySession).GetProperty("State",Instance).SetValue(session,state);
                actor.journey=session;actor.enabled=false;
                var combat=new BeastCombatState(state,1,state.Generation);
                Set(actor,"combat",combat);Set(actor,"combatRegion",1);Set(actor,"combatGeneration",state.Generation);
                typeof(BeastActor).GetProperty("Phase",Instance).SetValue(actor,BeastPhase.Recover);
                actor.animator.Play("Base Layer.Recover",0,0);actor.animator.Update(0);
                presenterStarted=true;presenter.enabled=true;
                if(!(bool)typeof(BeastWeakPointPresentation).GetField("owns",Instance).GetValue(presenter))Call(presenter,"OnEnable");
                Snapshot("closed-before",false);
                int charge=combat.TryBeginCharge(1,state.Generation);
                if(charge<=0 || !combat.TryBeginRecovery(1,state.Generation,charge,2d))throw new InvalidOperationException("Real fixture recovery window failed.");
                Call(presenter,"LateUpdate");Snapshot("open",true);
                combat.Tick(2d);Call(presenter,"LateUpdate");Snapshot("closed-after",false);
                report.status="editor-fixture-captured-unreviewed";
                void Snapshot(string label,bool expected)
                {
                    if(actor.WeakPointExposed!=expected)throw new InvalidOperationException("Real actor window mismatch: "+label);
                    var actualCore=presenter.weakPointRenderer.sharedMaterials[0];
                    if(actualCore!=(expected?presenter.openMaterial:closedMaterial))throw new InvalidOperationException("Core slot 0 material mismatch.");
                    if(!body.sharedMaterials.SequenceEqual(bodyMaterials))throw new InvalidOperationException("Body material references changed.");
                    for(int i=0;i<bodyMaterials.Length;i++)if(bodyMaterials[i].HasProperty("_EmissionColor") && bodyMaterials[i].GetColor("_EmissionColor")!=emissions[i])throw new InvalidOperationException("Body emission changed.");
                    for(int i=0;i<2;i++)
                    {
                        var required=closed[i]*(expected?Quaternion.Euler(presenter.openLocalEulerAngles[i]):Quaternion.identity);
                        if(Quaternion.Angle(required,presenter.armorPlates[i].localRotation)>.01f)throw new InvalidOperationException("Plate local rotation mismatch.");
                    }
                    // Measured model faces +Z; views are descriptive geometry views, never hit eligibility.
                    var directions=new[]{subject.transform.forward,subject.transform.right,-subject.transform.forward};var names=new[]{"front","side","rear"};
                    for(int v=0;v<3;v++)
                    {
                        camera.transform.position=subject.transform.position+directions[v]*3+Vector3.up*1.65f;
                        camera.transform.LookAt(presenter.weakPointRenderer.bounds.center);camera.fieldOfView=60;
                        capture("weakpoint-"+label+"-"+names[v]);
                        report.samples.Add(new Sample{state=label,view=names[v],imageLabel="weakpoint-"+label+"-"+names[v],fieldOfView=camera.fieldOfView,distance=3,weakPointExposed=actor.WeakPointExposed,bodyUnchanged=true,coreMaterial=UnityEditor.AssetDatabase.GetAssetPath(actualCore),localPlateRotations=presenter.armorPlates.Select(p=>p.localRotation).ToArray(),cameraPosition=camera.transform.position});
                    }
                }
            }
            finally
            {
                try {File.WriteAllText("JourneyEvidence/CandidateArt/weakpoint-fixture-report.json",JsonUtility.ToJson(report,true));}
                finally
                {
                    try {if(presenterStarted)Call(presenter,"OnDisable");presenter.enabled=false;actor.journey=originalJourney;}
                    finally {UnityEngine.Object.DestroyImmediate(host);}
                }
            }
        }
        static void Set(object target,string name,object value)=>target.GetType().GetField(name,Instance).SetValue(target,value);
        static void Call(object target,string name)=>target.GetType().GetMethod(name,Instance).Invoke(target,null);
    }
}

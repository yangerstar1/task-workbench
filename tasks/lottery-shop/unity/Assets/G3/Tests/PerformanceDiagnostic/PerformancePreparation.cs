using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Lottery.G3.PerformanceDiagnostic.Tests
{
    // No lifecycle-probe assembly exception and no destructive NewScene fallback.
    // Reuses the existing production preparation entry with the same live-object
    // preservation guard as the independently reviewed visual capture hook.
    static class PerformancePreparation
    {
        public static void Prepare()
        {
#if UNITY_EDITOR
            var args=Environment.GetCommandLineArgs();
            string Read(string key){for(int i=0;i<args.Length-1;i++)if(args[i]==key)return args[i+1];return "";}
            if(Read("-g3PerformanceProbe")!="1"||Read("-assemblyNames")!="Lottery.G3.PerformanceDiagnostic.Tests")
                throw new InvalidOperationException("Dedicated performance invocation required");
            var type=AppDomain.CurrentDomain.GetAssemblies().Select(a=>a.GetType("Lottery.G3.Editor.G3Build",false)).FirstOrDefault(t=>t!=null);
            if(type==null)throw new InvalidOperationException("G3Build missing");
            var method=type.GetMethod("PrepareForVisualTestsObserved",System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Static);
            if(method==null)throw new InvalidOperationException("Guarded G3 preparation missing");
            var preserved=new PrebuildSceneGuard();var failures=new List<Exception>();
            try{method.Invoke(null,new object[]{new Action<int,bool,bool,bool,bool,bool>((stage,valid,loaded,active,attempted,returned)=>{})});}
            catch(Exception failure){failures.Add(failure);}
            finally{try{preserved.RequireUnchanged();}catch(Exception failure){failures.Add(failure);}}
            if(failures.Count>1)throw new AggregateException("Performance prebuild and preservation failed",failures);
            if(failures.Count==1)System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(failures[0]).Throw();
#endif
        }
#if UNITY_EDITOR
        enum GuardFailure
        {
            NoOriginalScene, InvalidOriginalActiveScene, SceneCountChanged,
            ActiveSceneChanged, SceneIdentityChanged, SceneLoadedStateChanged,
            ScenePathChanged, SceneDirtyStateChanged, RootCountChanged,
            RootIdentityChanged, RootActiveStateChanged, BuildSceneSelectionChanged
        }
        sealed class PrebuildGuardException : InvalidOperationException
        {
            public readonly GuardFailure Code;
            public PrebuildGuardException(GuardFailure code) : base("Prebuild scene preservation guard: " + code) { Code = code; }
        }
        sealed class PrebuildSceneGuard
        {
            readonly Scene[] scenes;
            readonly bool[] loadedScenes, dirtyScenes;
            readonly string[] scenePaths;
            readonly GameObject[][] roots;
            readonly bool[][] activeRoots;
            readonly Scene active;
            readonly UnityEditor.EditorBuildSettingsScene[] buildScenes;
            public PrebuildSceneGuard()
            {
                active = SceneManager.GetActiveScene();
                scenes = Enumerable.Range(0, SceneManager.sceneCount).Select(SceneManager.GetSceneAt).ToArray();
                scenePaths = scenes.Select(s => s.path).ToArray();
                loadedScenes = scenes.Select(s => s.isLoaded).ToArray();
                dirtyScenes = scenes.Select(s => s.isDirty).ToArray();
                roots = scenes.Select(s => s.isLoaded ? s.GetRootGameObjects() : new GameObject[0]).ToArray();
                activeRoots = roots.Select(rs => rs.Select(r => r.activeSelf).ToArray()).ToArray();
                buildScenes = UnityEditor.EditorBuildSettings.scenes;
                if(scenes.Length == 0) throw new PrebuildGuardException(GuardFailure.NoOriginalScene);
                if(!active.IsValid() || !active.isLoaded) throw new PrebuildGuardException(GuardFailure.InvalidOriginalActiveScene);
            }
            public void RequireUnchanged()
            {
                if(SceneManager.sceneCount != scenes.Length) throw new PrebuildGuardException(GuardFailure.SceneCountChanged);
                if(SceneManager.GetActiveScene().handle != active.handle) throw new PrebuildGuardException(GuardFailure.ActiveSceneChanged);
                for(int i = 0; i < scenes.Length; i++)
                {
                    var current = SceneManager.GetSceneAt(i);
                    if(!scenes[i].IsValid() || current.handle != scenes[i].handle)
                        throw new PrebuildGuardException(GuardFailure.SceneIdentityChanged);
                    if(current.isLoaded != loadedScenes[i]) throw new PrebuildGuardException(GuardFailure.SceneLoadedStateChanged);
                    if(current.path != scenePaths[i])
                        throw new PrebuildGuardException(GuardFailure.ScenePathChanged);
                    if(current.isDirty != dirtyScenes[i])
                        throw new PrebuildGuardException(GuardFailure.SceneDirtyStateChanged);
                    var currentRoots = current.isLoaded ? current.GetRootGameObjects() : new GameObject[0];
                    if(currentRoots.Length != roots[i].Length)
                        throw new PrebuildGuardException(GuardFailure.RootCountChanged);
                    for(int r = 0; r < roots[i].Length; r++)
                    {
                        if(roots[i][r] == null || !currentRoots.Contains(roots[i][r]))
                            throw new PrebuildGuardException(GuardFailure.RootIdentityChanged);
                        if(roots[i][r].activeSelf != activeRoots[i][r]) throw new PrebuildGuardException(GuardFailure.RootActiveStateChanged);
                    }
                }
                var currentBuildScenes = UnityEditor.EditorBuildSettings.scenes;
                if(currentBuildScenes.Length != buildScenes.Length ||
                    currentBuildScenes.Where((s, i) => s.path != buildScenes[i].path || s.enabled != buildScenes[i].enabled).Any())
                    throw new PrebuildGuardException(GuardFailure.BuildSceneSelectionChanged);
            }
        }
#endif
    }
}

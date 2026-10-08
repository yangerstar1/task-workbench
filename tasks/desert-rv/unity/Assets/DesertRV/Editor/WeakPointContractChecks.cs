using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace DesertRV.Editor
{
    public static class WeakPointContractChecks
    {
        // Pure preflight. No animation sampling, generation, mutation or approval writes.
        public static void Validate(BeastWeakPointPresentation presenter,string label,List<string> errors)
        {
            if(!presenter) { errors.Add(label+": weakpoint presenter missing."); return; }
            if(!presenter.ValidateBindings(out var reason)) { errors.Add(label+": "+reason); return; }
            var actor=presenter.actor;
            if(!actor.animator || !actor.animator.runtimeAnimatorController)
            { errors.Add(label+": actor Animator/controller required to verify unkeyed plate assembly."); return; }
            if(!presenter.weakPointRoot.IsChildOf(actor.animator.transform))
            { errors.Add(label+": weakpoint assembly must lie in the inspected actor Animator hierarchy."); return; }
            string rootPath=AnimationUtility.CalculateTransformPath(presenter.weakPointRoot,actor.animator.transform);
            if(string.IsNullOrEmpty(rootPath)) { errors.Add(label+": assembly cannot be the Animator root."); return; }
            bool Owns(string path) => path==rootPath || path.StartsWith(rootPath+"/",StringComparison.Ordinal);
            foreach(var clip in actor.animator.runtimeAnimatorController.animationClips.Distinct())
            {
                if(!clip) continue;
                // Includes constant baked keys, render flags and object-reference material curves.
                foreach(var binding in AnimationUtility.GetCurveBindings(clip))
                    if(Owns(binding.path)) errors.Add(label+": Animator curve drives runtime-owned weakpoint assembly: "+clip.name+" / "+binding.path+" / "+binding.propertyName);
                foreach(var binding in AnimationUtility.GetObjectReferenceCurveBindings(clip))
                    if(Owns(binding.path)) errors.Add(label+": Animator object curve drives runtime-owned weakpoint assembly: "+clip.name+" / "+binding.path);
            }
            var core=presenter.weakPointRenderer;
            foreach(var renderer in actor.GetComponentsInChildren<Renderer>(true))
                if(renderer!=core && renderer.sharedMaterials.Contains(presenter.openMaterial))
                    errors.Add(label+": open-core material is already bound outside the dedicated core renderer.");
            if(!presenter.openMaterial.HasProperty("_EmissionColor") || presenter.openMaterial.GetColor("_EmissionColor").maxColorComponent<=0)
                errors.Add(label+": open-core material requires an authored visible emission color on the dedicated core.");
            if(!presenter.openMaterial.IsKeywordEnabled("_EMISSION"))
                errors.Add(label+": open-core emission keyword must be enabled on the authored material.");
        }
    }
}

using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
namespace DesertRV {
// Approximate the warm fixtures' indirect light inside the moving cabin.
// Exterior SH still changes with the parking location; no world-space shadows are baked into the RV.
[ExecuteAlways]
public sealed class CabinLighting:MonoBehaviour {
    public Color fixtureBounce=new Color(.20f,.13f,.072f,1);
    readonly List<Renderer> interior=new List<Renderer>();
    MaterialPropertyBlock block;
    readonly SphericalHarmonicsL2[] sample=new SphericalHarmonicsL2[1];
    Vector3 lastPosition;float nextRefresh;
    void OnEnable(){Collect();Refresh();}
    public void Collect(){
        interior.Clear();
        foreach(var r in GetComponentsInChildren<Renderer>()){
            if(!r.enabled)continue;
            string n=r.name;
            if(n=="Finished cabin surfaces"||n.Contains("cabin_finished")||n.Contains("ceiling")||n.Contains("cabinet")||n.Contains("workbench")||n.Contains("repair_bench")||n.Contains("supply_")||n.Contains("interior_")||n.Contains("floor_board")||n.Contains("service_panel")||n.Contains("work_notes")||n.StartsWith("GEO-refine_cabin"))interior.Add(r);
        }
    }
    void Update(){if(Time.realtimeSinceStartup>=nextRefresh||(transform.position-lastPosition).sqrMagnitude>.25f)Refresh();}
    public void Refresh(){
        if(block==null)block=new MaterialPropertyBlock();
        if(interior.Count==0)Collect();
        foreach(var r in interior){
            if(!r)continue;
            LightProbes.GetInterpolatedProbe(r.bounds.center,r,out sample[0]);sample[0].AddAmbientLight(fixtureBounce.linear);
            r.lightProbeUsage=LightProbeUsage.CustomProvided;r.GetPropertyBlock(block);block.CopySHCoefficientArraysFrom(sample);r.SetPropertyBlock(block);
        }
        lastPosition=transform.position;nextRefresh=Time.realtimeSinceStartup+.5f;
    }
}}

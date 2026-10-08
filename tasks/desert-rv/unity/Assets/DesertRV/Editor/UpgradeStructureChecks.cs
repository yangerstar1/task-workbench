using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace DesertRV.Editor {
public static class UpgradeStructureChecks {
    static void Require(bool ok,string why){if(!ok)throw new Exception(why);}
    static Transform Find(GameObject root,string name)=>root.GetComponentsInChildren<Transform>(true).Single(t=>t.name==name);
    public static void Run(){
        const string path="Assets/DesertRV/Art/rv-upgrade-structure.fbx";
        AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport);
        var importer=(ModelImporter)AssetImporter.GetAtPath(path);
        importer.materialImportMode=ModelImporterMaterialImportMode.ImportStandard;
        importer.importCameras=false;importer.importLights=false;importer.importAnimation=false;
        importer.globalScale=1;importer.SaveAndReimport();
        var baseline=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/DesertRV/Art/rv-body-study.fbx"));
        var prepared=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(path));
        try {
            var oldRenderers=baseline.GetComponentsInChildren<MeshRenderer>();
            var renderers=prepared.GetComponentsInChildren<MeshRenderer>().ToDictionary(r=>r.name);
            float maxBoundsDelta=0;
            foreach(var old in oldRenderers){
                Require(renderers.ContainsKey(old.name),"Accepted mesh was removed: "+old.name);
                var current=renderers[old.name];
                maxBoundsDelta=Mathf.Max(maxBoundsDelta,(current.bounds.center-old.bounds.center).magnitude,(current.bounds.size-old.bounds.size).magnitude);
            }
            Require(maxBoundsDelta<.001f,"FBX reparent changed accepted geometry: "+maxBoundsDelta);
            var ram=Find(prepared,"MOUNT_front_ram");
            var roof=Find(prepared,"MOUNT_roof_equipment");
            var cargo=Find(prepared,"MODULE_roof_cargo");
            Require(cargo.parent==roof && cargo.GetComponentsInChildren<MeshRenderer>().Length==3,"Roof cargo not independently replaceable");
            cargo.gameObject.SetActive(false);
            Require(renderers["GEO-roof_skylight_frame"].gameObject.activeInHierarchy && renderers["GEO-solar_panel"].gameObject.activeInHierarchy,"Removing cargo removed skylight or solar");
            cargo.gameObject.SetActive(true);
            var spinAxis=(Find(prepared,"RIG-wheel_right_front").position-Find(prepared,"RIG-wheel_left_front").position).normalized;
            float maxWheelCentreDrift=0;
            foreach(var side in new[]{"left","right"})foreach(var end in new[]{"front","rear"}){
                var wheel=Find(prepared,"RIG-wheel_"+side+"_"+end);
                Require(wheel.childCount==64,"Incomplete wheel group: "+wheel.name);
                var tyre=wheel.GetComponentsInChildren<MeshRenderer>().Single(r=>r.name.StartsWith("GEO-road_tyre"));
                var centre=tyre.bounds.center;
                Require(Vector3.Distance(centre,wheel.position)<.001f,"Imported wheel pivot left its axle");
                var rotation=wheel.rotation;
                wheel.Rotate(spinAxis,60,Space.World);
                maxWheelCentreDrift=Mathf.Max(maxWheelCentreDrift,Vector3.Distance(centre,tyre.bounds.center));
                wheel.rotation=rotation;
            }
            Require(maxWheelCentreDrift<.001f,"Wheels orbit instead of spin");
            foreach(var side in new[]{"left","right"}){
                var bracket=renderers["GEO-front_mount_bracket_"+side].bounds;
                Require(bracket.Intersects(renderers["GEO-chassis"].bounds)&&bracket.Intersects(renderers["GEO-front_bumper"].bounds),"Mount bracket does not connect chassis and bumper");
            }
            Require(ram.IsChildOf(prepared.transform)&&roof.IsChildOf(prepared.transform),"Mounts detached from vehicle");
            var report=$"UPGRADE_STRUCTURE_UNITY_PASSED\nacceptedMeshes={oldRenderers.Length}\nmaxBoundsDeltaMetres={maxBoundsDelta:R}\nmaxWheelCentreDriftMetres={maxWheelCentreDrift:R}\nroofCargoRemovable=true\nfrontBracketsConnected=true\nramMountWorld={ram.position}\nroofMountWorld={roof.position}\nstatus=structure verified only; module art, equipped clearances, gameplay and Web route not accepted\n";
            File.WriteAllText(Path.GetFullPath(Path.Combine(Application.dataPath,"../../upgrade-unity-report.txt")),report);
            Debug.Log(report);
        } finally {UnityEngine.Object.DestroyImmediate(baseline);UnityEngine.Object.DestroyImmediate(prepared);}
    }
}
}

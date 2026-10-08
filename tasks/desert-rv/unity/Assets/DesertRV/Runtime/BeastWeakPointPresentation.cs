using UnityEngine;

namespace DesertRV
{
    [DisallowMultipleComponent]
    public sealed class BeastWeakPointPresentation : MonoBehaviour
    {
        public BeastActor actor;
        public Renderer bodyRenderer;
        public Transform weakPointRoot;
        // Dedicated core mesh, never the whole skinned body or an emissive light proxy.
        public Renderer weakPointRenderer;
        public int materialSlot;
        public Material openMaterial;
        public Transform[] armorPlates = new Transform[2];
        public MeshRenderer[] plateRenderers = new MeshRenderer[2];
        public Vector3[] openLocalEulerAngles = { new Vector3(0,0,-140), new Vector3(0,0,140) };
        // Serialized legacy references are retained for migration diagnostics, never production fallback.
        [HideInInspector] public Transform armorPlate;
        [HideInInspector] public Vector3 openLocalEuler = new Vector3(-28,0,0);
        BeastActor boundActor;
        Renderer boundCore;
        Transform[] boundPlates;
        Vector3[] boundOpenEuler;
        Material boundOpenMaterial;
        Material[] original;
        Quaternion[] closedRotations;
        bool owns, open;

        public bool ValidateBindings(out string reason)
        {
            reason = null;
            var coreMesh = MeshOf(weakPointRenderer); var bodyMesh = MeshOf(bodyRenderer);
            if (!actor || !actor.armored || !bodyRenderer || !bodyMesh || bodyMesh.vertexCount < 3 || !weakPointRoot || weakPointRoot == actor.transform ||
                !weakPointRoot.IsChildOf(actor.transform) || !bodyRenderer.transform.IsChildOf(actor.transform) ||
                bodyRenderer.transform.IsChildOf(weakPointRoot))
                reason = "Weakpoint needs an armored body and a separate owned weakpoint assembly.";
            else if (!(weakPointRenderer is MeshRenderer) || weakPointRenderer == bodyRenderer || !weakPointRenderer.enabled || !coreMesh ||
                coreMesh.vertexCount < 3 || coreMesh.subMeshCount != 1 || materialSlot != 0 ||
                !weakPointRenderer.transform.IsChildOf(weakPointRoot) || weakPointRenderer.transform == weakPointRoot ||
                weakPointRenderer.sharedMaterials.Length != 1 || !weakPointRenderer.sharedMaterials[0] ||
                !openMaterial || openMaterial == weakPointRenderer.sharedMaterials[0] || coreMesh == MeshOf(bodyRenderer))
                reason = "Weakpoint requires a distinct core-only rigid mesh with one material slot (0).";
            else if (armorPlates == null || armorPlates.Length != 2 || plateRenderers == null || plateRenderers.Length != 2 ||
                openLocalEulerAngles == null || openLocalEulerAngles.Length != 2)
                reason = "Weakpoint requires exactly two authored plates and two opening rotations; legacy single plate cannot pass.";
            else
            {
                for (int i = 0; i < 2; i++)
                {
                    var plate = armorPlates[i]; var renderer = plateRenderers[i]; var mesh = MeshOf(renderer);
                    if (!plate || plate == weakPointRoot || !plate.IsChildOf(weakPointRoot) || !renderer ||
                        !renderer.transform.IsChildOf(plate) || !renderer.enabled || renderer.sharedMaterials.Length==0 || System.Array.Exists(renderer.sharedMaterials,m=>!m) || renderer == weakPointRenderer || renderer == bodyRenderer ||
                        !mesh || mesh.vertexCount < 3 || mesh == coreMesh || mesh == MeshOf(bodyRenderer) ||
                        weakPointRenderer.transform.IsChildOf(plate) || !Finite(openLocalEulerAngles[i]) ||
                        Quaternion.Angle(Quaternion.identity,Quaternion.Euler(openLocalEulerAngles[i])) < 1)
                        reason = "Each plate needs independent rigid geometry, a dedicated pivot and a finite nonzero opening rotation.";
                }
                if (armorPlates[0] && armorPlates[1] && (armorPlates[0].IsChildOf(armorPlates[1]) || armorPlates[1].IsChildOf(armorPlates[0])))
                    reason = "Plate pivots must be distinct sibling branches, not shared or nested.";
                if (plateRenderers[0] && plateRenderers[0] == plateRenderers[1]) reason = "Both plates cannot reference the same renderer.";
            }
            return reason == null;
        }
        public static Mesh MeshOf(Renderer renderer)
        {
            if (!renderer) return null;
            if (renderer is SkinnedMeshRenderer skin) return skin.sharedMesh;
            var filter=renderer.GetComponent<MeshFilter>(); return filter ? filter.sharedMesh : null;
        }
        static bool Finite(Vector3 v) => !float.IsNaN(v.x) && !float.IsNaN(v.y) && !float.IsNaN(v.z) &&
            !float.IsInfinity(v.x) && !float.IsInfinity(v.y) && !float.IsInfinity(v.z);
        void OnEnable()
        {
            if (!ValidateBindings(out var reason)) { Debug.LogError(reason,this); enabled=false; return; }
            if (!PresentationOwnership.Acquire(actor,this,"weakpoint")) { Debug.LogError("Duplicate weakpoint presenter.",this); enabled=false; return; }
            owns=true; boundActor=actor; boundCore=weakPointRenderer; boundOpenMaterial=openMaterial;
            boundPlates=(Transform[])armorPlates.Clone(); boundOpenEuler=(Vector3[])openLocalEulerAngles.Clone();
            original=boundCore.sharedMaterials; closedRotations=new Quaternion[2];
            for(int i=0;i<2;i++) closedRotations[i]=boundPlates[i].localRotation;
            // Re-enable during paused recovery restores the same authoritative frozen state immediately.
            Apply(boundActor.WeakPointExposed);
        }
        void OnDisable()
        {
            if(!owns) return;
            Apply(false); PresentationOwnership.Release(boundActor,this,"weakpoint");
            owns=false; boundActor=null; boundCore=null; boundPlates=null;
        }
        void Apply(bool exposed)
        {
            open=exposed;
            if(boundCore && original!=null)
            {
                var materials=(Material[])original.Clone();
                if(exposed) materials[0]=boundOpenMaterial;
                boundCore.sharedMaterials=materials;
            }
            ApplyPlates();
        }
        void ApplyPlates()
        {
            if(boundPlates==null) return;
            for(int i=0;i<2;i++) if(boundPlates[i])
                boundPlates[i].localRotation=closedRotations[i]*(open?Quaternion.Euler(boundOpenEuler[i]):Quaternion.identity);
        }
        void LateUpdate()
        {
            if(!owns) return;
            bool exposed=boundActor && boundActor.WeakPointExposed;
            if(exposed!=open) Apply(exposed);
            else ApplyPlates();
        }
    }
}

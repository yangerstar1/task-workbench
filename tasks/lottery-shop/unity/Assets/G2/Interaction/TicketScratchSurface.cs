using Lottery.G2.Core;
using UnityEngine;

namespace Lottery.G2.Interaction
{
    public sealed class TicketScratchSurface : MonoBehaviour
    {
        Texture2D maskTexture;
        Color32[] pixels;
        Mesh mesh;
        MeshCollider hitCollider;
        public Texture2D CommittedMaskTexture => maskTexture;
        public const float Width = 4.2f, Depth = 2.55f;
        public void Initialize(Material material)
        {
            mesh = new Mesh { name = "G2 ticket scratch UV plane" };
            mesh.vertices = new[] { new Vector3(-Width/2,0,-Depth/2), new Vector3(Width/2,0,-Depth/2), new Vector3(Width/2,0,Depth/2), new Vector3(-Width/2,0,Depth/2) };
            mesh.uv = new[] { Vector2.zero, Vector2.right, Vector2.one, Vector2.up };
            mesh.triangles = new[] { 0,2,1,0,3,2 }; mesh.RecalculateNormals(); mesh.RecalculateBounds();
            gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
            gameObject.AddComponent<MeshRenderer>().sharedMaterial = material;
            hitCollider = gameObject.AddComponent<MeshCollider>(); hitCollider.sharedMesh = mesh;
            maskTexture = new Texture2D(256,128,TextureFormat.RGBA32,false,true) { name = "G2 committed scratch bits", filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp };
            pixels = new Color32[256*128]; material.SetTexture("_Mask",maskTexture);
        }
        public void ShowCommitted(ScratchMask mask)
        {
            if (mask.Width != 256 || mask.Height != 128) throw new System.InvalidOperationException("Unsupported scratch geometry version");
            for (int i = 0; i < pixels.Length; i++) { byte v = mask.IsRevealed(i) ? (byte)255 : (byte)0; pixels[i] = new Color32(v,v,v,255); }
            maskTexture.SetPixels32(pixels); maskTexture.Apply(false,false);
        }
        public bool TryViewportUv(Camera camera, Vector2 viewport, out Vector2 uv)
        {
            if (hitCollider.Raycast(camera.ViewportPointToRay(viewport), out RaycastHit hit, 100f)) { uv=hit.textureCoord; return true; }
            uv=default; return false;
        }
        public Vector3 UvToWorld(Vector2 uv) => transform.TransformPoint(new Vector3((uv.x-.5f)*Width,0,(uv.y-.5f)*Depth));
        void OnDestroy() { if(maskTexture!=null) Destroy(maskTexture); if(mesh!=null) Destroy(mesh); }
    }
}

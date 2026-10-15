using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace Lottery.G3.Interaction
{
    // Screen-space occlusion belongs to the live view, never the six offline
    // reflection faces. All Game cameras, including RenderRequests, use URP's
    // same pass. No capture flags, pose tests, or per-frame resource creation.
    public sealed class G3ContactOcclusionFeature : ScreenSpaceAmbientOcclusion
    {
        public override void AddRenderPasses(ScriptableRenderer renderer, ref RenderingData renderingData)
        {
            if (renderingData.cameraData.cameraType == CameraType.Reflection) return;
            base.AddRenderPasses(renderer, ref renderingData);
        }
    }
}

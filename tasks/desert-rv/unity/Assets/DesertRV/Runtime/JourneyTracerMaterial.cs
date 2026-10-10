using UnityEngine;

namespace DesertRV
{
    // The saved scene references this asset, so its shader is a player build dependency.
    // Runtime callers share it read-only; no per-instance Material is created.
    public static class JourneyTracerMaterial
    {
        public const string AssetPath = "Assets/DesertRV/Art/Materials/JourneyNailTrajectory.mat";
        public const string ShaderName = "Universal Render Pipeline/Unlit";
        public const string UnavailableWarning = "JOURNEY_TRACER_UNAVAILABLE: Assign JourneyNailTrajectory with the URP Unlit shader in the authored scene. Nail trajectory disabled; combat remains available.";

        public static bool IsValid(Material material)
            => material && material.shader && material.shader.name == ShaderName;

        public static Material Validate(Material material, Object context)
        {
            if (IsValid(material)) return material;
            Debug.LogWarning(UnavailableWarning, context);
            return null;
        }
    }
}

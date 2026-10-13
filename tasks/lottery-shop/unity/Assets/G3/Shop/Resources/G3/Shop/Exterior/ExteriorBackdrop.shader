Shader "Lottery/G3/ExteriorBackdrop"
{
    Properties { _BaseMap ("Authored day/night street", 2D) = "white" {} _Exposure ("Controlled display exposure", Range(0,1)) = 1 }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Tags { "LightMode"="UniversalForward" }
            Cull Off ZWrite On ZTest LEqual
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct Attributes { float4 positionOS:POSITION; float2 uv:TEXCOORD0; };
            struct Varyings { float4 positionCS:SV_POSITION; float2 uv:TEXCOORD0; };
            CBUFFER_START(UnityPerMaterial) float _Exposure; CBUFFER_END
            TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
            Varyings vert(Attributes i) { Varyings o; o.positionCS=TransformObjectToHClip(i.positionOS.xyz);o.uv=i.uv;return o; }
            half4 frag(Varyings i):SV_Target { return half4(SAMPLE_TEXTURE2D(_BaseMap,sampler_BaseMap,i.uv).rgb*_Exposure,1); }
            ENDHLSL
        }
    }
}

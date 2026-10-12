Shader "Lottery/G3/LocalSilver"
{
    Properties { _RevealTex ("Confirmed cell pixels; black stays covered", 2D) = "black" {} _Color ("Opaque silver", Color) = (0.59,0.63,0.64,1) }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Opaque" "Queue"="AlphaTest" }
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
            TEXTURE2D(_RevealTex); SAMPLER(sampler_RevealTex);
            CBUFFER_START(UnityPerMaterial) float4 _Color; CBUFFER_END
            Varyings vert(Attributes i) { Varyings o; o.positionCS=TransformObjectToHClip(i.positionOS.xyz); o.uv=i.uv; return o; }
            half4 frag(Varyings i):SV_Target
            {
                clip(0.5-SAMPLE_TEXTURE2D(_RevealTex,sampler_RevealTex,i.uv).r);
                return half4(_Color.rgb,1);
            }
            ENDHLSL
        }
    }
}

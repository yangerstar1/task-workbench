Shader "Lottery/G3/MaskedFont"
{
    Properties { _MainTex ("Licensed font atlas",2D)="white" {} _RevealTex ("Confirmed local mask",2D)="black" {} }
    SubShader
    {
        Tags {"RenderPipeline"="UniversalPipeline" "RenderType"="Transparent" "Queue"="Transparent"}
        Pass
        {
            Tags {"LightMode"="UniversalForward"}
            Cull Off ZWrite Off ZTest LEqual Blend SrcAlpha OneMinusSrcAlpha
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct A {float4 p:POSITION;float2 uv:TEXCOORD0;float2 mask:TEXCOORD1;half4 c:COLOR;};
            struct V {float4 p:SV_POSITION;float2 uv:TEXCOORD0;float2 mask:TEXCOORD1;half4 c:COLOR;};
            TEXTURE2D(_MainTex);SAMPLER(sampler_MainTex);TEXTURE2D(_RevealTex);SAMPLER(sampler_RevealTex);
            V vert(A i){V o;o.p=TransformObjectToHClip(i.p.xyz);o.uv=i.uv;o.mask=i.mask;o.c=i.c;return o;}
            half4 frag(V i):SV_Target
            {
                // Independent mask fence prevents glyph leakage even if the silver
                // material is culled or reordered by a lower quality rendering path.
                clip(i.mask.x);clip(i.mask.y);clip(1-i.mask.x);clip(1-i.mask.y);
                clip(SAMPLE_TEXTURE2D(_RevealTex,sampler_RevealTex,i.mask).r-.5);
                return half4(i.c.rgb,i.c.a*SAMPLE_TEXTURE2D(_MainTex,sampler_MainTex,i.uv).a);
            }
            ENDHLSL
        }
    }
}

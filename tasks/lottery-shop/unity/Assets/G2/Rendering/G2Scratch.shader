Shader "Lottery/G2/Scratch"
{
    Properties { _Mask ("Committed revealed pixels", 2D) = "black" {} _Color ("Silver", Color) = (0.57,0.65,0.65,1) }
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
            TEXTURE2D(_Mask); SAMPLER(sampler_Mask);
            CBUFFER_START(UnityPerMaterial) float4 _Color; CBUFFER_END
            Varyings vert(Attributes i) { Varyings o; o.positionCS=TransformObjectToHClip(i.positionOS.xyz); o.uv=i.uv; return o; }
            half4 frag(Varyings i):SV_Target
            {
                clip(0.5-SAMPLE_TEXTURE2D(_Mask,sampler_Mask,i.uv).r);
                float2 cell=frac(i.uv*float2(3,2));
                half border=step(.025,cell.x)*step(.025,cell.y)*step(cell.x,.975)*step(cell.y,.975);
                half grain=.94+.06*sin(i.uv.x*650)*sin(i.uv.y*420);
                return half4(_Color.rgb*grain*lerp(.62,1,border),1);
            }
            ENDHLSL
        }
    }
}

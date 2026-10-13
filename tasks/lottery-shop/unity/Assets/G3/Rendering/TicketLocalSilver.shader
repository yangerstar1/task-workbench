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
                // Opaque, object-UV anchored brushed foil: mask authority unchanged.
                // Derivative attenuation suppresses subpixel grain in distant views.
                float2 grainUV=i.uv*float2(850,530);
                float2 cell=floor(grainUV);
                float grain=frac(52.9829189*frac(dot(cell,float2(.06711056,.00583715))))-.5;
                float keep=1-saturate(max(fwidth(grainUV.x),fwidth(grainUV.y))-.5);
                float broad=saturate(1-abs(i.uv.x+i.uv.y*.20-.58)*2.6);
                broad=broad*broad;
                return half4(saturate(_Color.rgb*(.90+.13*broad)+grain*.035*keep+.025*broad),1);
            }
            ENDHLSL
        }
    }
}

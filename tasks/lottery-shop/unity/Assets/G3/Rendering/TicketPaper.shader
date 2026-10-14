Shader "Lottery/G3/TicketPaper"
{
    Properties { _BaseMap ("Approved full-paper albedo", 2D) = "white" {} }
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
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes { float4 positionOS:POSITION; float3 normalOS:NORMAL; float2 uv:TEXCOORD0; };
            struct Varyings { float4 positionCS:SV_POSITION; float2 uv:TEXCOORD0; float3 positionWS:TEXCOORD1; half3 normalWS:TEXCOORD2; float4 shadowCoord:TEXCOORD3; };
            TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
            Varyings vert(Attributes i)
            {Varyings o;VertexPositionInputs p=GetVertexPositionInputs(i.positionOS.xyz);o.positionCS=p.positionCS;o.positionWS=p.positionWS;o.normalWS=TransformObjectToWorldNormal(i.normalOS);o.shadowCoord=GetShadowCoord(p);o.uv=i.uv;return o;}
            half4 frag(Varyings i):SV_Target
            {
                half3 n=normalize(i.normalWS);Light light=GetMainLight(i.shadowCoord);
                half3 illumination=SampleSH(n)*.68h+light.color*(saturate(dot(n,light.direction))*light.distanceAttenuation*light.shadowAttenuation*.68h);
                #if defined(_ADDITIONAL_LIGHTS)
                uint count=GetAdditionalLightsCount();for(uint index=0;index<count;index++){Light a=GetAdditionalLight(index,i.positionWS,half4(1,1,1,1));illumination+=a.color*(saturate(dot(n,a.direction))*a.distanceAttenuation*a.shadowAttenuation*.42h);}
                #endif
                // Soft lower bound protects runtime number legibility, without turning
                // the approved source texture into an emissive billboard.
                return half4(SAMPLE_TEXTURE2D(_BaseMap,sampler_BaseMap,i.uv).rgb*clamp(illumination,.52h,1.12h),1);
            }
            ENDHLSL
        }
    }
}

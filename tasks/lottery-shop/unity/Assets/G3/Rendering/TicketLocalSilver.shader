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
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BOX_PROJECTION
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes { float4 positionOS:POSITION; float3 normalOS:NORMAL; float2 uv:TEXCOORD0; };
            struct Varyings { float4 positionCS:SV_POSITION; float2 uv:TEXCOORD0; float3 positionWS:TEXCOORD1; half3 normalWS:TEXCOORD2; float4 shadowCoord:TEXCOORD3; };
            TEXTURE2D(_RevealTex); SAMPLER(sampler_RevealTex);
            CBUFFER_START(UnityPerMaterial) float4 _Color; CBUFFER_END
            Varyings vert(Attributes i)
            { Varyings o;VertexPositionInputs p=GetVertexPositionInputs(i.positionOS.xyz);o.positionCS=p.positionCS;o.positionWS=p.positionWS;o.normalWS=TransformObjectToWorldNormal(i.normalOS);o.shadowCoord=GetShadowCoord(p);o.uv=i.uv;return o; }
            float Grain(float2 p) { return frac(52.9829189*frac(dot(floor(p),float2(.06711056,.00583715)))); }
            half4 frag(Varyings i):SV_Target
            {
                half reveal=SAMPLE_TEXTURE2D(_RevealTex,sampler_RevealTex,i.uv).r;
                half cutEdge=saturate(abs(ddx(reveal))+abs(ddy(reveal)));
                clip(0.5-reveal); // Exact same confirmed mask threshold; texture/UV authority is unchanged.
                // Metre-anchored flakes vary across cells instead of repeating one
                // large UV highlight. Their amplitude fades when below a pixel.
                float2 grainUV=i.positionWS.xz*1100;
                float keep=1-saturate(max(fwidth(grainUV.x),fwidth(grainUV.y))-.5);
                half a=Grain(grainUV),b=Grain(grainUV+float2(17,43));
                half3 n=normalize(i.normalWS+half3((a-.5)*.07,0,(b-.5)*.07)*keep);
                half3 view=GetWorldSpaceNormalizeViewDir(i.positionWS);
                Light light=GetMainLight(i.shadowCoord);
                half roughness=.57h+(a-.5h)*.12h*keep;
                half3 reflected=GlossyEnvironmentReflection(reflect(-view,n),i.positionWS,roughness,1.0h,float2(0,0));
                half3 illumination=SampleSH(n)*.62h+light.color*(saturate(dot(n,light.direction))*light.distanceAttenuation*light.shadowAttenuation*.40h);
                half3 halfDir=SafeNormalize(light.direction+view);
                half glint=pow(saturate(dot(n,halfDir)),32)*light.shadowAttenuation;
                half3 result=_Color.rgb*illumination+reflected*.30h+light.color*glint*.10h+(a-.5h)*.045h*keep;
                // A one-pixel dark lip belongs only to still-covered pixels; no
                // decorative holes or noise can reveal an unconfirmed outcome.
                return half4(saturate(result*(1-cutEdge*.12h)),1);
            }
            ENDHLSL
        }
    }
}

Shader "Lottery/G3/LocalSilver"
{
    Properties
    {
        _RevealTex ("Confirmed cell pixels; black stays covered", 2D) = "black" {}
        _Color ("Opaque silver", Color) = (0.59,0.63,0.64,1)
        _FlakeRelief ("Matte foil relief", Range(0,1)) = 0.65
        _ScratchLip ("Confirmed scratch lip", Range(0,1)) = 0.72
    }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Opaque" "Queue"="AlphaTest" }
        Pass
        {
            Tags { "LightMode"="UniversalForward" }
            Cull Off ZWrite On ZTest LEqual
            HLSLPROGRAM
            #pragma target 3.0 // Explicit mip-zero mask reads; existing Android target is GLES3.
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BOX_PROJECTION
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            struct Attributes { float4 positionOS:POSITION; float3 normalOS:NORMAL; float2 uv:TEXCOORD0; };
            struct Varyings { float4 positionCS:SV_POSITION; float2 uv:TEXCOORD0; float3 positionWS:TEXCOORD1; half3 normalWS:TEXCOORD2; float4 shadowCoord:TEXCOORD3; };
            TEXTURE2D(_RevealTex); SAMPLER(sampler_RevealTex);
            CBUFFER_START(UnityPerMaterial)
                float4 _Color;
                float4 _RevealTex_TexelSize;
                half _FlakeRelief;
                half _ScratchLip;
            CBUFFER_END
            Varyings vert(Attributes i)
            { Varyings o;VertexPositionInputs p=GetVertexPositionInputs(i.positionOS.xyz);o.positionCS=p.positionCS;o.positionWS=p.positionWS;o.normalWS=TransformObjectToWorldNormal(i.normalOS);o.shadowCoord=GetShadowCoord(p);o.uv=i.uv;return o; }
            float Grain(float2 p) { return frac(52.9829189*frac(dot(floor(p),float2(.06711056,.00583715)))); }
            float FoilHash(float2 p)
            {
                float2 q=frac(p*float2(.1031,.11369));
                q+=dot(q,q.yx+19.19);
                return frac(q.x*q.y*23.13);
            }
            // Analytic slope of folded value noise: irregular shallow creases,
            // no image texture, repeated stamp, time animation or extra probe tap.
            // Four lattice hashes are shared by height and both derivatives.
            float3 FoilCrease(float2 p)
            {
                float2 cell=floor(p),f=frac(p);
                float2 u=f*f*(3-2*f),du=6*f*(1-f);
                float a=FoilHash(cell),b=FoilHash(cell+float2(1,0));
                float c=FoilHash(cell+float2(0,1)),d=FoilHash(cell+float2(1,1));
                float h=lerp(lerp(a,b,u.x),lerp(c,d,u.x),u.y);
                float2 slope=float2(lerp(b-a,d-c,u.y)*du.x,lerp(c-a,d-b,u.x)*du.y);
                // A softened fold has a fine lip without a subpixel hard seam.
                slope*=clamp((h-.5)*8,-1,1);
                return float3(slope,abs(h-.5)*2);
            }
            half4 frag(Varyings i):SV_Target
            {
                half reveal=SAMPLE_TEXTURE2D(_RevealTex,sampler_RevealTex,i.uv).r;
                half cutEdge=saturate(abs(ddx(reveal))+abs(ddy(reveal)));
                // Derivatives precede discard, including the distance filter used
                // below. Coverage still has ONE authority and ONE exact clip.
                float2 foilUV=float2(dot(i.positionWS.xz,float2(.8,.6)),dot(i.positionWS.xz,float2(-.6,.8)))*460;
                float foilKeep=1-smoothstep(.45,1.25,max(fwidth(foilUV.x),fwidth(foilUV.y)));
                float2 grainUV=i.positionWS.xz*1100;
                float keep=1-saturate(max(fwidth(grainUV.x),fwidth(grainUV.y))-.5);
                clip(0.5-reveal); // Exact same confirmed mask threshold; texture/UV authority is unchanged.
                // Neighbor reads only shade retained silver. They can neither
                // clip covered pixels nor enlarge the revealed result mask.
                float2 texel=abs(_RevealTex_TexelSize.xy);
                half left=step(.5h,SAMPLE_TEXTURE2D_LOD(_RevealTex,sampler_RevealTex,i.uv-float2(texel.x,0),0).r);
                half right=step(.5h,SAMPLE_TEXTURE2D_LOD(_RevealTex,sampler_RevealTex,i.uv+float2(texel.x,0),0).r);
                half down=step(.5h,SAMPLE_TEXTURE2D_LOD(_RevealTex,sampler_RevealTex,i.uv-float2(0,texel.y),0).r);
                half up=step(.5h,SAMPLE_TEXTURE2D_LOD(_RevealTex,sampler_RevealTex,i.uv+float2(0,texel.y),0).r);
                half lip=max(max(left,right),max(down,up));
                half2 lipSlope=half2(left-right,down-up);
                // Metre-anchored flakes vary across cells instead of repeating one
                // large UV highlight. Their amplitude fades when below a pixel.
                half a=Grain(grainUV),b=Grain(grainUV+float2(17,43));
                float3 crease=FoilCrease(foilUV);
                // Convert the rotated metre-space slope back to world X/Z.
                half2 relief=half2(crease.x*.8-crease.y*.6,crease.x*.6+crease.y*.8);
                half reliefAmount=_FlakeRelief*foilKeep;
                half3 n=normalize(i.normalWS+half3((a-.5)*.07,0,(b-.5)*.07)*keep
                    +half3(relief.x,0,relief.y)*(.13h*reliefAmount));
                half3 view=GetWorldSpaceNormalizeViewDir(i.positionWS);
                Light light=GetMainLight(i.shadowCoord);
                // Broad, matte metal response; never a mirror finish. The paper
                // shader remains diffuse and its approved albedo is untouched.
                half roughness=clamp(.62h+(a-.5h)*.10h*keep+(crease.z-.35h)*.09h*reliefAmount,.54h,.76h);
                half3 reflected=GlossyEnvironmentReflection(reflect(-view,n),i.positionWS,roughness,1.0h,float2(0,0));
                half3 illumination=SampleSH(n)*.62h+light.color*(saturate(dot(n,light.direction))*light.distanceAttenuation*light.shadowAttenuation*.40h);
                half3 halfDir=SafeNormalize(light.direction+view);
                half glint=pow(saturate(dot(n,halfDir)),32)*light.shadowAttenuation;
                half grazing=1-saturate(dot(n,view));
                half reflectionWeight=.28h+.10h*grazing*grazing;
                half3 result=_Color.rgb*illumination+reflected*reflectionWeight+light.color*glint*.10h+(a-.5h)*.045h*keep;
                result*=1+(crease.z-.35h)*.075h*reliefAmount;
                #if defined(_ADDITIONAL_LIGHTS)
                // Match the existing silver direct response for local practicals.
                // Both diffuse and glint are occluded; confirmed coverage is untouched.
                uint count=GetAdditionalLightsCount();
                for(uint index=0;index<count;index++)
                {
                    Light additional=GetAdditionalLight(index,i.positionWS,half4(1,1,1,1));
                    half attenuation=additional.distanceAttenuation*additional.shadowAttenuation;
                    half diffuse=saturate(dot(n,additional.direction));
                    half localGlint=pow(saturate(dot(n,SafeNormalize(additional.direction+view))),32);
                    result+=additional.color*attenuation*(_Color.rgb*diffuse*.40h+localGlint*.10h);
                }
                #endif
                // A broken bright bevel and its shallow dark lip sit entirely
                // on retained silver, one confirmed-mask texel wide. Shade in
                // foil space so opposing edges have opposing relief, with no
                // emissive white outline and no new holes or result disclosure.
                half facing=dot(lipSlope,half2(-.6h,.8h));
                half edgeBreak=.86h+(a-.5h)*.28h*keep;
                half edgeShade=_ScratchLip*edgeBreak*(max(facing,0)*.24h-max(-facing,0)*.12h-lip*.06h);
                half baseLip=cutEdge*.12h*(1-_ScratchLip*lip);
                return half4(saturate(result*(1-baseLip+edgeShade)),1);
            }
            ENDHLSL
        }
    }
}

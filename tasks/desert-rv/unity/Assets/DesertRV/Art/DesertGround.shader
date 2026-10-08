Shader "DesertRV/LayeredSand" {
 Properties {
  _BaseMap("Painted sand albedo",2D)="white"{}
  _BaseColor("Sunlit sand",Color)=(0.9,0.59,0.29,1)
  _LowColor("Compacted sand",Color)=(0.58,0.31,0.13,1)
 }
 SubShader {
  Tags {"RenderType"="Opaque" "RenderPipeline"="UniversalPipeline"}
  Pass {
   Name "ForwardLit" Tags {"LightMode"="UniversalForward"}
   HLSLPROGRAM
   #pragma vertex Vert
   #pragma fragment Frag
   #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
   #pragma multi_compile_fragment _ _SHADOWS_SOFT
   #pragma multi_compile _ LIGHTMAP_ON
   #pragma multi_compile _ DIRLIGHTMAP_COMBINED
   #pragma multi_compile _ LIGHTMAP_SHADOW_MIXING
   #pragma multi_compile _ SHADOWS_SHADOWMASK
   #pragma multi_compile_fog
   #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
   #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
   CBUFFER_START(UnityPerMaterial)
    half4 _BaseColor,_LowColor;
   CBUFFER_END
   TEXTURE2D(_BaseMap);SAMPLER(sampler_BaseMap);
   struct A {float4 vertex:POSITION;float3 normal:NORMAL;float2 uv2:TEXCOORD1;};
   struct V {float4 position:SV_POSITION;float3 world:TEXCOORD0;half3 normal:TEXCOORD1;DECLARE_LIGHTMAP_OR_SH(uv2,sh,2);half fog:TEXCOORD3;};
   V Vert(A input){V output=(V)0;VertexPositionInputs p=GetVertexPositionInputs(input.vertex.xyz);output.position=p.positionCS;output.world=p.positionWS;output.normal=TransformObjectToWorldNormal(input.normal);OUTPUT_LIGHTMAP_UV(input.uv2,unity_LightmapST,output.uv2);OUTPUT_SH(output.normal,output.sh);output.fog=ComputeFogFactor(p.positionCS.z);return output;}
   float Hash(float2 p){return frac(sin(dot(p,float2(127.1,311.7)))*43758.5453);}
   float Noise(float2 p){float2 i=floor(p),f=frac(p);f=f*f*(3-2*f);return lerp(lerp(Hash(i),Hash(i+float2(1,0)),f.x),lerp(Hash(i+float2(0,1)),Hash(i+1),f.x),f.y);}
   half4 Frag(V input):SV_Target {
    float2 p=input.world.xz;
    float broad=Noise(p*.48+float2(6.1,2.7));
    float islands=Noise(p*2.3+float2(3,7));
    float bands=smoothstep(.12,.88,broad*.58+islands*.42);
    half3 albedo=SAMPLE_TEXTURE2D(_BaseMap,sampler_BaseMap,p/6).rgb*lerp(.96,1.04,bands);
    // Subtle wind combing is visible only close up; no normal-map corrugation.
    float nearFade=1-smoothstep(4,13,distance(input.world,_WorldSpaceCameraPos));
    albedo*=1+.016*sin(p.x*23+p.y*7+Noise(p*.6)*5)*nearFade;
    InputData data=(InputData)0;data.positionWS=input.world;data.normalWS=normalize(input.normal);data.viewDirectionWS=GetWorldSpaceNormalizeViewDir(input.world);
    data.shadowCoord=TransformWorldToShadowCoord(input.world);data.fogCoord=input.fog;
    data.bakedGI=SAMPLE_GI(input.uv2,input.sh,data.normalWS);data.normalizedScreenSpaceUV=GetNormalizedScreenSpaceUV(input.position);
    data.shadowMask=SAMPLE_SHADOWMASK(input.uv2);
    SurfaceData surface=(SurfaceData)0;surface.albedo=albedo;surface.metallic=0;surface.smoothness=.02;surface.occlusion=1;surface.alpha=1;surface.normalTS=half3(0,0,1);
    half4 color=UniversalFragmentPBR(data,surface);color.rgb=MixFog(color.rgb,data.fogCoord);return color;
   }
   ENDHLSL
  }
  UsePass "Universal Render Pipeline/Lit/ShadowCaster"
  UsePass "Universal Render Pipeline/Lit/DepthOnly"
 }
}

// Self-authored scene-only ground / thin-overlay shader. No screen-space noise.
Shader "DesertRV/EnvironmentSurface" {
 Properties {
  _BaseMap("Metric albedo",2D)="white"{}
  _BaseColor("Tint and opacity",Color)=(1,1,1,1)
  _DetailContrast("Local texture contrast",Range(0,1))=1
  _DetailStart("Detail fade starts (metres)",Float)=24
  _DetailEnd("Detail fade ends (metres)",Float)=80
  [Enum(UnityEngine.Rendering.BlendMode)] _SrcBlend("Source blend",Float)=1
  [Enum(UnityEngine.Rendering.BlendMode)] _DstBlend("Destination blend",Float)=0
  [Toggle] _ZWrite("Write depth",Float)=1
 }
 SubShader {
  Tags {"RenderPipeline"="UniversalPipeline" "RenderType"="Opaque"}
  Pass {
   Name "ForwardLit" Tags {"LightMode"="UniversalForward"}
   Blend [_SrcBlend] [_DstBlend]
   ZWrite [_ZWrite]
   HLSLPROGRAM
   #pragma target 3.0
   #pragma vertex Vert
   #pragma fragment Frag
   #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
   #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
   #pragma multi_compile_fragment _ _SHADOWS_SOFT
   #pragma multi_compile_fog
   #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
   #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
   CBUFFER_START(UnityPerMaterial)
    float4 _BaseMap_ST;
    half4 _BaseColor;
    float _DetailContrast, _DetailStart, _DetailEnd;
   CBUFFER_END
   TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
   struct Attributes {float4 vertex:POSITION;float3 normal:NORMAL;float2 uv:TEXCOORD0;half4 color:COLOR;};
   struct Varyings {float4 position:SV_POSITION;float3 world:TEXCOORD0;half3 normal:TEXCOORD1;float2 uv:TEXCOORD2;half4 color:COLOR;half fog:TEXCOORD3;};
   Varyings Vert(Attributes input) {
    Varyings output=(Varyings)0;
    VertexPositionInputs p=GetVertexPositionInputs(input.vertex.xyz);
    output.position=p.positionCS; output.world=p.positionWS;
    output.normal=TransformObjectToWorldNormal(input.normal);
    output.uv=TRANSFORM_TEX(input.uv,_BaseMap); output.color=input.color;
    output.fog=ComputeFogFactor(p.positionCS.z); return output;
   }
   half4 Frag(Varyings input):SV_Target {
    // Explicitly converge to the texture's final mip: no distant 2 m periodic normal or albedo grid.
    half3 average=SAMPLE_TEXTURE2D_LOD(_BaseMap,sampler_BaseMap,float2(.5,.5),10).rgb;
    half3 fine=SAMPLE_TEXTURE2D(_BaseMap,sampler_BaseMap,input.uv).rgb;
    half detail=_DetailContrast*(1-smoothstep(_DetailStart,_DetailEnd,distance(input.world,_WorldSpaceCameraPos)));
    InputData data=(InputData)0;
    data.positionWS=input.world; data.normalWS=NormalizeNormalPerPixel(input.normal);
    data.viewDirectionWS=GetWorldSpaceNormalizeViewDir(input.world);
    data.shadowCoord=TransformWorldToShadowCoord(input.world); data.fogCoord=input.fog;
    data.bakedGI=SampleSH(data.normalWS); data.vertexLighting=VertexLighting(input.world,data.normalWS);
    data.normalizedScreenSpaceUV=GetNormalizedScreenSpaceUV(input.position); data.shadowMask=half4(1,1,1,1);
    SurfaceData surface=(SurfaceData)0;
    surface.albedo=lerp(average,fine,detail)*_BaseColor.rgb*input.color.rgb;
    surface.metallic=0; surface.smoothness=.025; surface.occlusion=1;
    surface.alpha=saturate(_BaseColor.a*input.color.a); surface.normalTS=half3(0,0,1);
    half4 color=UniversalFragmentPBR(data,surface);
    color.rgb=MixFog(color.rgb,input.fog); color.a=surface.alpha; return color;
   }
   ENDHLSL
  }
 }
}

Shader "Lottery/G3/ContactShade"
{
    Properties { _Color ("Local contact tint and strength", Color) = (.04,.07,.05,.24) _Inner ("Occluder half size relative to footprint", Vector) = (.91,.91,0,0) }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Transparent" "Queue"="Transparent-20" }
        Pass
        {
            Tags { "LightMode"="SRPDefaultUnlit" }
            Blend SrcAlpha OneMinusSrcAlpha
            Cull Off ZWrite Off ZTest LEqual ColorMask RGB
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct Attributes { float4 positionOS:POSITION; float2 uv:TEXCOORD0; };
            struct Varyings { float4 positionCS:SV_POSITION; float2 uv:TEXCOORD0; };
            CBUFFER_START(UnityPerMaterial) half4 _Color; float4 _Inner; CBUFFER_END
            Varyings vert(Attributes i) { Varyings o;o.positionCS=TransformObjectToHClip(i.positionOS.xyz);o.uv=i.uv;return o; }
            half4 frag(Varyings i):SV_Target
            {
                // Each small footprint is physically beneath its existing object.
                // Opaque depth hides the core; only a soft, fully vanishing rim remains.
                float2 distance=abs(i.uv-.5)*2;
                half fade=(1-smoothstep(_Inner.x,1,distance.x))*(1-smoothstep(_Inner.y,1,distance.y));
                return half4(_Color.rgb,_Color.a*fade);
            }
            ENDHLSL
        }
    }
}

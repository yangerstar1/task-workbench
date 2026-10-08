Shader "DesertRV/SoftDesertSky" {
 Properties {
  _Zenith("Zenith",Color)=(0.35,0.50,0.69,1)
  _Horizon("Horizon",Color)=(0.69,0.76,0.82,1)
  _CloudLight("Cloud light",Color)=(0.94,0.95,0.96,1)
  _CloudShade("Cloud shade",Color)=(0.59,0.67,0.75,1)
 }
 SubShader {
  Tags {"Queue"="Background" "RenderType"="Background" "PreviewType"="Skybox" "RenderPipeline"="UniversalPipeline"}
  Cull Off ZWrite Off
  Pass {
   CGPROGRAM
   #pragma vertex vert
   #pragma fragment frag
   #include "UnityCG.cginc"
   struct appdata {float4 vertex:POSITION;};
   struct v2f {float4 pos:SV_POSITION;float3 ray:TEXCOORD0;};
   float4 _Zenith,_Horizon,_CloudLight,_CloudShade;
   v2f vert(appdata v){v2f o;o.pos=UnityObjectToClipPos(v.vertex);o.ray=v.vertex.xyz;return o;}
   float hash(float2 p){return frac(sin(dot(p,float2(127.1,311.7)))*43758.5453);}
   float noise2(float2 p){float2 i=floor(p),f=frac(p);f=f*f*(3-2*f);return lerp(lerp(hash(i),hash(i+float2(1,0)),f.x),lerp(hash(i+float2(0,1)),hash(i+1),f.x),f.y);}
   float fbm(float2 p){float v=0,a=.55;for(int k=0;k<4;k++){v+=a*noise2(p);p=p*2.03+float2(11.7,19.3);a*=.48;}return v;}
   half4 frag(v2f i):SV_Target {
    float3 d=normalize(i.ray);float h=max(0,d.y);
    float3 sky=lerp(_Horizon.rgb,_Zenith.rgb,smoothstep(0,.45,h));
    // Broad cumulus groups with rounded lobes, instead of high-frequency streaks.
    float azimuth=atan2(d.z,d.x);float elevation=asin(d.y);
    float coverage=0;float cloudTone=0;
    for(int bank=0;bank<9;bank++){
     float centre=-3.14159+bank*.69813+.13*sin(bank*2.41);
     float dx=atan2(sin(azimuth-centre),cos(azimuth-centre));
     float baseHeight=.095+.032*sin(bank*1.79);
     float width=.25+.065*sin(bank*2.3+.8);
     float outline=-10;
     for(int lobe=0;lobe<5;lobe++){
      float offset=(lobe-2)*width*.35;
      float lift=.02+(.065+.015*sin(bank*3+lobe))*sin((lobe+1)*.523599);
      float2 p=float2((dx-offset)/(width*.43),(elevation-baseHeight-lift)/(.07+.028*sin(lobe+1)));
      outline=max(outline,1-length(p));
     }
     float mask=smoothstep(-.055,.06,outline)*smoothstep(.015,.065,elevation);
     float tone=smoothstep(baseHeight-.025,baseHeight+.09,elevation);
     if(mask>coverage){coverage=mask;cloudTone=tone;}
    }
    sky=lerp(sky,lerp(_CloudShade.rgb,_CloudLight.rgb,cloudTone),coverage*.89);
    sky=lerp(sky,_Horizon.rgb,1-smoothstep(-.08,.05,d.y));
    return half4(sky,1);
   }
   ENDCG
  }
 }
}

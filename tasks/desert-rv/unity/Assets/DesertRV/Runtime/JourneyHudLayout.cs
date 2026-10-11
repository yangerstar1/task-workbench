using UnityEngine;

namespace DesertRV
{
    // Top-left safe-area coordinates in Android logical dp (desktop uses a 480-unit height).
    // The 568 x 296 supported mobile envelope is checked, never achieved by shrinking type/targets.
    public sealed class JourneyHudLayout
    {
        public readonly Rect Status, Objective, Pause, Storm, Damage, RearThreat, Aim, Notice, Prompt, Progress, Menu;
        public readonly Vector2 Size;
        public bool WithinSupportedEnvelope => Size.x >= 568 && Size.y >= 296;
        public JourneyHudLayout(Vector2 size, bool keyboardOptions)
        {
            Size=size;
            float w=size.x, h=size.y;
            Status=new Rect(12,12,174,80);
            Objective=new Rect(198,12,Mathf.Min(420,Mathf.Max(120,w-270)),50);
            Pause=new Rect(w-60,12,48,48);
            Storm=new Rect(198,66,Mathf.Min(240,Mathf.Max(120,w-210)),24);
            Damage=new Rect(12,98,174,26);
            RearThreat=Storm;
            Aim=new Rect(w*.5f-22,h*.5f-22,44,44);
            // A single feedback lane: transient results replace the prompt, never stack over it.
            Notice=new Rect(124,h-56,Mathf.Max(120,w-304),44);
            Prompt=Notice;
            Progress=new Rect(124,h-6,Mathf.Max(120,w-304),4);
            Menu=new Rect(0,0,Mathf.Min(440,w-24),keyboardOptions ? 342 : 280);
        }
        public Rect Control(TouchControl control)
        {
            float w=Size.x,h=Size.y;
            switch(control)
            {
                case TouchControl.Move: return new Rect(12,h-108,96,96);
                case TouchControl.Fire: return new Rect(w-84,h-84,72,72);
                case TouchControl.Reload: return new Rect(w-72,h-148,60,52);
                case TouchControl.Interact: return new Rect(w-168,h-76,76,64);
                case TouchControl.Accelerate: return new Rect(w-84,h-164,72,72);
                case TouchControl.Brake: return new Rect(w-84,h-84,72,72);
                default: return new Rect(w*.38f,0,w*.62f,h);
            }
        }
        public static float AndroidScale(float density,int renderWidth,int displayWidth)
        {
            if(float.IsNaN(density)||float.IsInfinity(density)||density<.75f||density>6||
                renderWidth<200||renderWidth>16000||displayWidth<200||displayWidth>16000) return 0;
            float ratio=(float)renderWidth/displayWidth;
            if(ratio<.25f||ratio>2) return 0;
            float scale=density*ratio;
            return scale>=.25f&&scale<=8 ? scale : 0;
        }
        public static string PromptLines(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            int separator=value.IndexOf(" · ",System.StringComparison.Ordinal);
            return separator < 0 ? value : value.Substring(0,separator)+"\n"+value.Substring(separator+3);
        }
        public static string ObjectiveLines(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            int separator=value.IndexOf(" · ",System.StringComparison.Ordinal);
            if (separator >= 0) return value.Substring(0,separator)+"\n<size=14>"+value.Substring(separator+3)+"</size>";
            // Keep the cable prerequisite visible in its own line; wording and sequence are unchanged.
            return value.Replace("拔除电缆，", "拔除电缆\n");
        }
    }
}

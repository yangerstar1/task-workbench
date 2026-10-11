using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.EnhancedTouch;
using ETouch = UnityEngine.InputSystem.EnhancedTouch.Touch;
namespace Lottery.Probe
{
    // This is an input/font/render capability probe, not a playable lottery game.
    public sealed class ProbeRuntime : MonoBehaviour
    {
        public Font chineseFont;
        private Vector2 pointer;
        private string phase = "NONE";
        private int touchCount;
        private bool tracking;
        private GUIStyle label;
        private bool showLicense;
        private Vector2 licenseScroll;
        private void OnEnable() { EnhancedTouchSupport.Enable(); }
        private void OnDisable() { EnhancedTouchSupport.Disable(); tracking = false; }
        private void Update()
        {
            touchCount = ETouch.activeTouches.Count;
            tracking = false;
            if (touchCount > 0)
            {
                var touch = ETouch.activeTouches[0];
                pointer = touch.screenPosition;
                phase = touch.phase.ToString();
                tracking = true;
            }
            else if (Mouse.current != null)
            {
                pointer = Mouse.current.position.ReadValue();
                tracking = Mouse.current.leftButton.isPressed;
                phase = tracking ? "MOUSE_HELD" : "MOUSE_IDLE";
            }
        }
        private void OnGUI()
        {
            if (label == null) label = new GUIStyle(GUI.skin.label) { font = chineseFont, fontSize = 24, normal = { textColor = Color.white } };
            var safe = Screen.safeArea;
            var rect = new Rect(safe.x + 20, Screen.height - safe.yMax + 16, safe.width - 40, 190);
            GUI.Box(rect, GUIContent.none);
            GUI.Label(new Rect(rect.x + 12, rect.y + 10, rect.width - 24, 175),
                "技术探针 G0 · 非游戏成品\n中文：刮奖小店 兑奖 借款 消耗品 ￥100\n" +
                $"输入：{phase}  触点：{touchCount}  坐标：{pointer.x:F0},{pointer.y:F0}\n" +
                $"屏幕：{Screen.width}×{Screen.height}  安全区：{safe}\n仅检查显示与输入；不代表真机或手感验收通过。", label);
            if (GUI.Button(new Rect(safe.xMax - 160, Screen.height - safe.y - 58, 140, 40), "Font license")) showLicense = !showLicense;
            if (showLicense)
            {
                var license = Resources.Load<TextAsset>("ProbeFontLicense");
                var area = new Rect(safe.x + 24, Screen.height - safe.yMax + 24, safe.width - 48, safe.height - 95);
                GUI.Box(area, GUIContent.none);
                var text = license != null ? license.text : "License resource missing";
                var style = new GUIStyle(GUI.skin.label) { font = chineseFont, fontSize = 18, wordWrap = true };
                float height = style.CalcHeight(new GUIContent(text), area.width - 36);
                licenseScroll = GUI.BeginScrollView(area, licenseScroll, new Rect(0, 0, area.width - 20, height + 24));
                GUI.Label(new Rect(10, 10, area.width - 36, height), text, style);
                GUI.EndScrollView();
            }
            if (tracking) GUI.Box(new Rect(pointer.x - 12, Screen.height - pointer.y - 12, 24, 24), "+");
        }
    }
}

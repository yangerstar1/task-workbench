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
        private float licenseMaxScroll;
        private Vector2 previousPointer;
        public static Rect LicenseButtonRect(Rect safe, int screenHeight) => new Rect(safe.xMax - 160, screenHeight - safe.y - 58, 140, 40);
        public static bool HitsLicenseButton(Vector2 screenPoint, Rect safe, int screenHeight) => LicenseButtonRect(safe, screenHeight).Contains(new Vector2(screenPoint.x, screenHeight - screenPoint.y));
        private void OnEnable() { EnhancedTouchSupport.Enable(); }
        private void OnDisable() { EnhancedTouchSupport.Disable(); tracking = false; }
        private void Update()
        {
            touchCount = ETouch.activeTouches.Count;
            bool pressed = false;
            float scrollDelta = 0;
            tracking = false;
            if (touchCount > 0)
            {
                var touch = ETouch.activeTouches[0];
                pointer = touch.screenPosition;
                pressed = touch.phase == UnityEngine.InputSystem.TouchPhase.Began;
                if (touch.phase == UnityEngine.InputSystem.TouchPhase.Moved) scrollDelta = pointer.y - previousPointer.y;
                phase = touch.phase.ToString();
                tracking = true;
            }
            else if (Mouse.current != null)
            {
                pointer = Mouse.current.position.ReadValue();
                tracking = Mouse.current.leftButton.isPressed;
                pressed = Mouse.current.leftButton.wasPressedThisFrame;
                scrollDelta = -Mouse.current.scroll.ReadValue().y;
                phase = tracking ? "MOUSE_HELD" : "MOUSE_IDLE";
            }
            var safe = Screen.safeArea;
            if (pressed && HitsLicenseButton(pointer, safe, Screen.height)) showLicense = !showLicense;
            if (showLicense) licenseScroll.y = Mathf.Clamp(licenseScroll.y + scrollDelta, 0, licenseMaxScroll);
            previousPointer = pointer;
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
            // IMGUI is only the diagnostic renderer. New Input System handles all input above.
            GUI.Box(LicenseButtonRect(safe, Screen.height), showLicense ? "Close license" : "Font license", GUI.skin.button);
            if (showLicense)
            {
                var license = Resources.Load<TextAsset>("ProbeFontLicense");
                var area = new Rect(safe.x + 24, Screen.height - safe.yMax + 24, safe.width - 48, safe.height - 95);
                GUI.Box(area, GUIContent.none);
                var text = license != null ? license.text : "License resource missing";
                var style = new GUIStyle(GUI.skin.label) { font = chineseFont, fontSize = 18, wordWrap = true };
                float height = style.CalcHeight(new GUIContent(text), area.width - 36);
                licenseMaxScroll = Mathf.Max(0, height + 24 - area.height);
                licenseScroll = GUI.BeginScrollView(area, licenseScroll, new Rect(0, 0, area.width - 20, height + 24), GUIStyle.none, GUIStyle.none);
                GUI.Label(new Rect(10, 10, area.width - 36, height), text, style);
                GUI.EndScrollView();
            }
            if (tracking) GUI.Box(new Rect(pointer.x - 12, Screen.height - pointer.y - 12, 24, 24), "+");
        }
    }
}

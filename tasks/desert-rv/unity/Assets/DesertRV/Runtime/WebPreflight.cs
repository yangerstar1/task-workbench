using UnityEngine;

namespace DesertRV
{
    // Technical fixture only. This scene is never a game-art acceptance sample.
    public sealed class WebPreflight : MonoBehaviour
    {
        public Transform subject;
        public Camera view;
        bool active;
        float seconds;
        int moves;
        string action = "Waiting for START";

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.Space)) Toggle();
            if (!active) return;
            seconds += Time.deltaTime;
            subject.Rotate(0, 28 * Time.deltaTime, 0);
            float x = Input.GetAxisRaw("Horizontal");
            float y = Input.GetAxisRaw("Vertical");
            if (x != 0 || y != 0)
            {
                view.transform.position += new Vector3(x, 0, y) * (Time.deltaTime * 3);
                moves++;
                action = "Keyboard input received";
            }
        }

        void OnApplicationFocus(bool focused)
        {
            if (!focused) { active = false; action = "Focus lost: paused"; }
        }

        void OnApplicationPause(bool paused)
        {
            if (paused) { active = false; action = "Page hidden: paused"; }
        }

        void Toggle()
        {
            active = !active;
            action = active ? "Running" : "Paused";
        }

        void OnGUI()
        {
            GUI.skin.label.fontSize = 22;
            GUI.skin.button.fontSize = 22;
            GUI.Box(new Rect(18, 18, 690, 195), "");
            GUI.Label(new Rect(35, 28, 660, 34), "UNITY WEB PREFLIGHT / NOT GAME ART");
            GUI.Label(new Rect(35, 67, 660, 34), "URP 17.3 | Lit materials + realtime shadows");
            GUI.Label(new Rect(35, 102, 660, 34), $"{action} | time {seconds:F1}s | inputs {moves}");
            if (GUI.Button(new Rect(35, 151, 180, 44), active ? "PAUSE" : "START / RESUME")) Toggle();
            GUI.Label(new Rect(230, 155, 455, 40), "WASD / arrows: move   SPACE: pause");
        }
    }
}

using UnityEngine;

// Original, disposable CI demonstration. Contains no Desert RV game content.
public sealed class ProofRuntime : MonoBehaviour
{
    public Transform cube;
    private bool rotating = true;

    private void Update()
    {
        if (cube != null && rotating)
            cube.Rotate(0f, 35f * Time.deltaTime, 0f, Space.World);
    }

    private void OnGUI()
    {
        GUI.Label(new Rect(20, 20, Screen.width - 40, 40),
            "Unity CI proof | " + Application.unityVersion);
        if (GUI.Button(new Rect(20, 70, 220, 80), rotating ? "Pause cube" : "Rotate cube"))
            rotating = !rotating;
    }
}


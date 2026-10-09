#if UNITY_EDITOR
namespace DesertRV.Editor
{
    // Unity's documented -executeMethod entry belongs in an Editor folder/assembly.
    // The backend and its post-domain-reload callbacks remain unchanged.
    public static class JourneyRenderedCommandLine
    {
        public static void Run() => JourneyRenderedDiagnosticRunner.Run();
        public static void RunWindowSmoke() => JourneyRenderedDiagnosticRunner.RunWindowSmoke();
    }
}
#endif

using System.Linq;
using UnityEditor;
using UnityEditor.Build;

namespace DesertRV.Editor
{
    // Reuse the same prepared-source lease, four scene callbacks, dependency closure,
    // performance-resource exclusion and exact settings restoration as the Linux candidate.
    public static partial class JourneyCandidateLinuxBuild
    {
        static bool androidCandidate;
        static string CandidatePlatform => androidCandidate ? "android" : "linux";
        static BuildTarget CandidateTarget => androidCandidate ? BuildTarget.Android : BuildTarget.StandaloneLinux64;
        static string CandidateDefine => androidCandidate ? JourneyCandidateLinuxIdentity.AndroidDefine : JourneyCandidateLinuxIdentity.Define;
        static string CandidateExecutable => androidCandidate ? "DesertRV-Journey.apk" : "DesertRV.x86_64";

        public static bool ValidAndroidBuildProfile(BuildTarget target, BuildOptions options, string[] defines) =>
            target == BuildTarget.Android && options == CandidateOptions && defines != null &&
            defines.SequenceEqual(new[] { JourneyCandidateLinuxIdentity.AndroidDefine });

        public static void BuildPreparedAndroidDiagnostic() => BuildPreparedDiagnostic(true);

        sealed class AndroidCandidateSettings
        {
            internal static readonly string[] Fields = { "scriptingBackend.Android", "Android.targetArchitectures",
                "Android.useCustomKeystore", "Android.buildApkPerCpuArchitecture", "Android.splitApplicationBinary",
                "Android.targetSdkVersion", "Android.bundleVersionCode", "buildAppBundle", "exportAsGoogleAndroidProject",
                "applicationIdentifier.Android", "bundleVersion", "productName" };
            readonly AndroidArchitecture architecture = PlayerSettings.Android.targetArchitectures;
            readonly bool keystore = PlayerSettings.Android.useCustomKeystore;
            readonly bool split = PlayerSettings.Android.buildApkPerCpuArchitecture;
            readonly bool expansion = PlayerSettings.Android.splitApplicationBinary;
            readonly bool bundle = EditorUserBuildSettings.buildAppBundle;
            readonly bool export = EditorUserBuildSettings.exportAsGoogleAndroidProject;
            readonly AndroidSdkVersions sdk = PlayerSettings.Android.targetSdkVersion;
            readonly int code = PlayerSettings.Android.bundleVersionCode;
            readonly string identifier = PlayerSettings.GetApplicationIdentifier(NamedBuildTarget.Android);
            readonly string version = PlayerSettings.bundleVersion;

            internal void Apply(string commit)
            {
                PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
                PlayerSettings.Android.useCustomKeystore = false;
                PlayerSettings.Android.buildApkPerCpuArchitecture = false;
                PlayerSettings.Android.splitApplicationBinary = false;
                PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel35;
                PlayerSettings.Android.bundleVersionCode = 1;
                EditorUserBuildSettings.buildAppBundle = false;
                EditorUserBuildSettings.exportAsGoogleAndroidProject = false;
                PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, "com.desertrv.journey.dev");
                PlayerSettings.bundleVersion = "0.1.0-dev." + commit.Substring(0, 12);
            }

            internal void Restore()
            {
                PlayerSettings.Android.targetArchitectures = architecture;
                PlayerSettings.Android.useCustomKeystore = keystore;
                PlayerSettings.Android.buildApkPerCpuArchitecture = split;
                PlayerSettings.Android.splitApplicationBinary = expansion;
                PlayerSettings.Android.targetSdkVersion = sdk;
                PlayerSettings.Android.bundleVersionCode = code;
                EditorUserBuildSettings.buildAppBundle = bundle;
                EditorUserBuildSettings.exportAsGoogleAndroidProject = export;
                PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, identifier);
                PlayerSettings.bundleVersion = version;
            }
        }
    }
}

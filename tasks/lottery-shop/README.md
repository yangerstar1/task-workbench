# Lottery Shop G0 technical probe

Original, limited Unity capability probe for an Android lottery-shop project. This is not the game, a final art target, a gameplay slice, or evidence of Android-device acceptance.

## Scope

- Unity 6000.3.19f1, URP 17.3.0, Input System 1.20.1, Test Framework 1.6.0.
- Editor-generated URP assets, one primitive surface, camera and light.
- Licensed Noto SC font and Chinese diagnostic overlay.
- EnhancedTouch diagnostic readout; mouse input is explicitly labeled.
- Six native EditMode tests and a development ARM64 IL2CPP Android APK.

Passing these tests checks package resolution, persisted references, font character availability and API setup. It does not prove the scene actually rendered correctly, Android input works, the app is enjoyable, or the final game meets its quality goals. Those observations remain NOT_RUN until performed separately.

## Reproduce

The finite GitHub Actions workflow is the supported build route. Its guarded request is tied to this exact repository and isolated branch. Never run disposable-runner cleanup scripts on a workstation.

Before opening `unity`, restore the licensed font with the repository script. The Editor setup entry point is `Lottery.Probe.Editor.ProbeBuild.Prepare`; the build entry point is `Lottery.Probe.Editor.ProbeBuild.BuildAndroid` with exact source commit and run ID arguments.

Generated assets are under `unity/Assets/GeneratedProbe`. They are generated inputs, not preexisting handcrafted source. The workflow preserves their evidence separately along with the actual package resolution. Unity caches and credentials must never be committed or published. Build output is `build/Android/LotteryG0.apk` with a source-bound receipt. The build does not launch or install the APK.

## Assets and access

All diagnostic code is original. The font is separately licensed under SIL OFL 1.1; see the font notices. No competitor assets, private planning documents, account credentials, or private repository material belong in this public task directory.

# Desert RV：TraversalHarness Android 测试包

这个入口编译已保存的 TraversalHarness 场景，用于恢复源码后的规则测试和 Android 构建验证。它不是完整游戏，不代表美术、剧情、音效、触控真机体验或整体验收完成。生成成功也不代表已经在设备运行。

## 触发前

1. 确认公开导出及素材许可审计已经完成，不可变 PUBLIC-EXPORT.json 的历史哈希与 SOURCE-STATE.json 的当前源码清单都通过校验。原私库保持私有。
2. 确认 main 上的源码、测试、构建方法和此 workflow 已一起复核。新增代码能读取 Unity secrets，因此不要把未审核代码放进此可信分支。
3. 使用仓库所有者 yangerstar1 的身份，在 Actions 选择 `Desert RV saved TraversalHarness Android`，只选择 main，手动 Run workflow。其他账户、fork、非 main、自动 push/PR 不执行。
4. 已有的 UNITY_LICENSE、UNITY_EMAIL、UNITY_PASSWORD 使用仓库 Secrets；不放入输入框、Git、截图、文档或上传资产。无需上传个人签名密钥。

## 执行与边界

- 标准 GitHub-hosted ubuntu-24.04，contents: read，固定第三方 Action commit。
- 不使用收费 runner、付费缓存或云构建后端；公开库标准 runner 的费用与额度仍以 GitHub 账户政策为准。
- Unity 6000.3.19f1 先执行 DesertRV.EditModeTests 的 71 项，再在独立 job 执行 DesertRV.PlayModeTests 的 1 项，最后才编译 Android。两个模式分别核对固定 fullname 库存，不能互相计数或把编译当执行；每项都必须原生 Passed，零用例、缺失、重复、跳过、未知结果和失败均阻断 Android job。
- Android job 重新 checkout 同一 GitHub commit，以现有已保存场景构建 ARM64 IL2CPP APK；不下载或复用旧 APK。
- Unity 导入/编译/许可证失败都会使任务失败，不可据此宣称游戏测试通过。
- 运行仅生成 GitHub Actions artifacts，保留 7 天；不创建 Release、不自动发布。公开仓库 artifacts 可被有权限的 GitHub 用户访问，因此内容须在触发前已获准公开。
- 测试证据为原生 NUnit XML 的安全结构投影，保留原 XML SHA256；不上传 XML 内 stdout、环境或堆栈。APK 只在收据、字节哈希和 ZIP/ARM64 结构独立验证通过后上传。
- 不上传许可证、日志目录、Unity Library/Temp、凭据、缓存或签名密钥。GameCI 获得的 Secrets 仅用于激活，禁止开启 shell tracing、dump env 或上传原始日志。

## 复核产物

先确认该 run 的 head SHA 和 attempt，再核对证据中的 commit、runId、runAttempt、exportManifestSha256、sourceStateSha256，以及 APK SHA256/字节数。测试证据必须显示完整固定库存、PASSED；Android 证据必须和同次 EditMode、PlayMode 两份测试 XML 哈希及各自数量一致。

若需要长期下载链接，先由独立复核者下载该次 artifacts，检查实际内容和哈希，再另行决定是否创建明确标注“TraversalHarness 测试包，非完整游戏”的 Release。此 workflow 本身没有 Release 写权限。

## 故障处理

- 缺少/失效 Secret：在 GitHub Secrets 中修复，不把值贴进 issue、聊天或日志。
- 库存变化：同时评审生产规则、对应模式测试、scripts/expected_test_cases.json 和 scripts/expected_playmode_test_cases.json；不得为了绿灯删掉失败用例。
- 构建失败：查看 GitHub job 状态定位，必要时对相关诊断做脱敏；失败时不会上传未验证 APK。
- 真机验证：下载通过独立校验的 APK 后另行安装测试。CI 成功本身不证明 Android 真机交互、性能或完整游戏就绪。


## 当前源码和历史证据

PUBLIC-EXPORT.json 只证明首次 803 文件公开导出，原私有 sourceCommit 不是以后新增源码的出处。SOURCE-STATE.json 独立列出当前全部 Unity 输入、Packages/ProjectSettings、字体恢复输入、CI 脚本与 workflow。清单基线 SHA 为 6dc675517db262c72dcb8c1507239d4bf10acc5d；运行证据绑定实际 GITHUB_SHA。源码清单不含自身哈希或当前 HEAD，避免循环；执行 scripts/update_source_state.py 更新，提交前检查 diff。

除清单明确列出的确定性恢复字体外，任何新出现但未列入清单的 Unity 文件均拒绝，包括新源码、包、资产和根目录编译响应文件。独立 art/ 目录的离线美术候选脚本不属于 Unity 编译输入，放进 unity/ 后必须重新受审计。历史 manifest 不允许通过同时改文件与hash冒充原始来源。

已确认的原生证据只有基线 run 37796490106 attempt 1 的 34 项 EditMode 通过。本次新源码的 71 项 EditMode 和 1 项 PlayMode 均仍待执行；清单、静态审阅与 Python 验证器单测不构成 Unity 测试通过证明。既有基线运行和产物保留独立身份，不被新库存回写。本轮没有三地区成品场景，Android 仍只构建 TraversalHarness。

重跑必须选择 Re-run all jobs；只重跑下游失败 job 会保留旧 attempt 的测试输出，并被新的严格同 commit/run/attempt/sourceState 身份门禁拒绝。两份测试证据不能跨 attempt 拼接到新 APK 收据。

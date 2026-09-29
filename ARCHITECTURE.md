# 游戏会话与版本适配

开发分支基于 `70446ba`。本目录是架构开发工作树，不覆盖已发布的 2.0.7。

## 调用边界

界面和快捷键仍调用原有 `War3Trainer` API。外部入口由 `war3_trainer_session.py` 绑定到唯一 `GameSession`，嵌套操作复用同一锁和配置作用域。

- `war3_services/` 保存 28 个原生协议服务方法，以及按 8 个领域拆出的 390 个上层业务方法。主文件从约 2.29 万行降至约 1.07 万行。
- `war3_external_backend.py` 保留外部对象/资源读取和基本字段写入，单位与物品通过带会话代际的 `UnitRef` / `ItemRef` 校验。不会强迫外部读取进入游戏线程。
- `war3_engine_24268.py` 是兼容门面与原生执行后端，使用 `war3_operations.py` 的固定协议目录。
- `war3_engine_transport.py` 独占加载、钩子派发和换路线判断。回调可能执行或清理未完成时不自动重放。
- `war3_game_session.py` 统一身份、缓存、清理引用和诊断。每次新开进程句柄都核对进程创建时间，防止预检与写入之间的 PID 复用。

`delivered`、`readback_verified`、`effect_verified` 是不同证据。协议解码不会把实际游戏效果标为已验证。外部写入部分成功后会保留不确定状态，禁止重复写入。

## 唯一版本数据

`profiles/3.0.0.24268.json` 提供构建指纹、对象表、选择列表、TLS、Native 注册表、解码参数、内部 RVA、代码校验和机器 ABI 约束。

Python 在会话作用域内取配置。C 默认结构由 `tools/generate_bridge_profile.py` 生成；传输在安装回调前写入同一配置并读回。桥协议标记不符时拒绝旧 DLL。三个桥内对象表解析器已合并为同一个实现。

修改器版本、游戏版本、适配包版本、桥配置协议版本分别记录。Native 名称/签名用于定位，实际参数 ABI 仍由编译的协议和 C 包装器约束，不能单凭签名匹配改调用方式。

### 保留的版本模块边界

拆出的兼容服务内，字段布局、天赋记录、装备内部行为、图标指令和内部技能回调被标为编译适配模块。它们受指纹和能力门控，不能靠修改 JSON 中的构建号冒充新版本支持。

`facade_binding.py` 只绑定随产品编译的现成函数到宿主的类型/API 命名空间，不读取、编译或执行适配包代码。这一过渡层保留已有测试替换点，后续可逐域改成显式依赖注入。

当前以已发布 2.0.9 核对 390 个搬迁方法：385 个方法语法树一致，5 个差异仅涉及共享会话、类型化物品身份、外部后端接入及物品槽超时不再错误重试生命值写入。全部 471 个原有方法的接口签名保留，28 个原生服务参数构造和快捷键定义一致。

原有 API 保留历史分支用于已有诊断/测试调用；有 `GameSession` 的产品对象禁止进入旧 native helper；旧状态开关只是固定的兼容属性，不能改变当前会话后端。未被产品调用的持久钩子传输已移入 `diagnostics/`，历史 Native 索引仅按需导入。后续继续拆分门面时，应先用调用图和域测试证明分支无产品调用，不能直接删除诊断实现。

## 手动导入与诊断

```powershell
python war3_reforged_trainer.py --inspect-game-profile profiles/3.0.0.24268.json
python war3_reforged_trainer.py --import-game-profile C:\Adapters\verified.json
python tools/game_adapter.py diagnose C:\Game\WarcraftIII.exe
python tools/game_adapter.py candidate C:\Game\WarcraftIII.exe --output build/candidate.json
python tools/game_adapter.py manifest --output build/architecture-manifest.json
```

导入位置为 `%LOCALAPPDATA%/War3Trainer/adapters`。仅加载严格 JSON，不联网下载、不执行包内脚本。候选包不能导入或自动成为正式包。定位输出明确区分匹配证据与从基线继承、尚未验证的假设；新构建仍需结构、语义和功能验收。相同指纹存在不同包时拒绝含糊选择。

天赋模块不匹配不影响普通背包动作；公共对象或上下文失败会阻止其依赖操作。原生注册表缺失单独阻止原生执行，不使外部会话读取跟着失败。仍使用门面固定字段布局的入口会明确要求对应编译模块。

## 开发验证

```powershell
python tools/generate_bridge_profile.py --check
./tools/build_engine_bridge.ps1 -Fixture -OutputDirectory build/architecture-fixture
./tools/build_engine_bridge.ps1 -OutputDirectory build/architecture-runtime
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
python tools/benchmark_architecture.py
python tools/audit_game_architecture.py
```

源码运行优先用 `build/architecture-runtime` 中的新桥；冻结包仍读取自身工具目录。历史测试夹具已统一使用当前源码编译的 `build/architecture-fixture`，不再依赖各个历史构建目录的 DLL。

等价性测试保留原参数构造、匹配相同对象和实际字段读回；C 夹具也验证运行时替换对象表 RVA/布局。性能脚本交错比较相同快照下的冷解析、热解析和 24 单位读取，检查中位数及 P95 不劣于基线 10%。这不是游戏实机性能或外机兼容证明。

公开版本不因本分支测试而更新。真实新游戏版本、不同安全策略机器和实际游戏效果需要独立证据。

## 本轮验证结果

- 拆分后的完整回归：2518 passed、29 skipped、120 subtests passed。
- 末尾的超时修复及相关检查：99 passed；换图代际等最后的定向检查：115 passed。数字分别记录，不相加冒充独立测试数。
- 29 个跳过项是缺失历史文本证据的 12 项及已移除旧 helper 源码的 17 项，不代表外机验证。
- 最终相同快照性能：冷对象解析中位数 +5.7%、P95 +9.2%；热解析 +5.9%/+2.8%；24 单位选择 +0.6%/+4.6%。均在该微基准的 10% 阈值内。
- 已发布工作树仍是 `70446ba` 且没有跟踪文件变更。本轮未构建 EXE、未发布、未写入游戏进程。

仍需实际环境验收：完整界面链路的实机性能、新游戏构建语义、问题外机的当前版本运行日志，以及天赋/装备/技能的实际游戏效果。兼容门面的宿主命名空间绑定是保留现有接口的过渡层；后续新增功能应优先使用独立服务和类型化对象引用。

## 2026-09-29：迁入 2.0.8 / 2.0.9 外机修复

实验分支仍以 2.0.7 的 `70446ba` 为架构基线。本次按 `70446ba..873af71` 的完整修复差异迁移，覆盖 2.0.8 与 2.0.9，来源为已发布分支 `codex/war3-207-loader-fix-20260927`。没有迁入该分支的工作树规则、发布构建脚本、版本资源或发布产物。

| 来源 | 已迁移内容 | 所属边界 |
|---|---|---|
| `4cdf133` / 2.0.8 | SEC_IMAGE 导入预检、IAT 初始化与页保护恢复；受异常保护的加载诊断、展开表及模块引用所有权 | 传输模块、C 桥 |
| `3f6936f` / 2.0.8 | 仅在确认 apphelp 安装读异常、业务未执行且清理完成后，改用系统导出的原生钩子安装接口；不硬编码系统调用号、不修改系统兼容性设置 | 传输模块 |
| `873af71` / 2.0.9 | 仅消费自身内部消息，正常转发其他消息；异常时退出回调计数；卸钩后有界等待回调退出，再移除展开表和释放资源；详细生命周期诊断 | C 桥、传输模块 |
| 架构集成 | 将回调送达、退出、清理分开接入统一会话；显式失败不得被旧的成功字段覆盖；旧生命周期 ABI 在打开进程前被拒绝 | `GameSession`、原生执行后端 |

21 个发布版传输辅助函数与 2.0.9 的语法树一致。派发入口保留模块化的 `prepare_operation`、进程身份检查、`GameProfile` 配置注入与读回，C 桥保留配置驱动对象解析。功能服务没有重新引入选路、偏移或私有会话状态；`UnitRef` / `ItemRef` 和快速外部读写后端保持原边界。

用户随后指定实验版为 **2.1.0 测试版**：源码版本 `2.1.0`、发布通道 `beta`、界面显式标注“测试版”，诊断标识为 `2.1.0-beta-modular-private-callback-drain`。Windows 版本资源设置 prerelease 标记；独立的 `tools/build_release_210.py` / `War3ReforgedTrainer-2.1.0-beta.spec` 只用于本实验分支，历史发布构建器不改动。发布说明以 2.0.9 为功能对照，明确主要是代码结构优化、保留既有功能与兼容修复；发布时必须标为预发布，不替代稳定版。版本元数据和说明准备完成不等同于已构建或发布。

新增 `test_modular_callback_integration.py`、发布修复的导入/备用路线/真实 C 回调测试；测试 DLL 统一编译到 `build/architecture-fixture` 与 `build/architecture-runtime`。`tools/verify_bridge_transport_runtime.py` 使用独立隐藏测试窗口，验证真实 Windows 安装、回调与资源清理；其占位业务由 TLS 检查拒绝，不能算作游戏功能验收。

用户于 2026-09-29 反馈已发布 2.0.9 在该问题外机成功。本次未收到该成功运行的新日志，也未在外机运行实验分支；用户反馈、实验分支夹具结果、Windows 传输实测分别记录，不相互替代。

### 本次迁移验证结果

- 139 个测试模块独立运行：2579 passed、29 skipped、120 subtests passed，无失败。29 项仍是历史证据/旧 helper 前置条件缺失；定向 124 项包含在全量统计中，不重复相加。
- 新编译的实验桥已通过 8 种真实 Windows 进程场景：正常加载、已有模块恢复、SEC_IMAGE、原生备用安装、已加载原生安装、无响应超时保护、回调尾部阻塞、首路真实异常后的备用安装。最后一项仅将异常模块归属替换为外机证据，不能当作本机复现了完整 apphelp 环境。
- 改变测试适配包的对象表 RVA，在正常、备用与阻塞尾部三种路径下均完成配置写入/读回，并通过真实传输报告验证 `GameSession` 的送达、退出、清理状态；没有把占位业务标为读回或游戏效果已验证。
- 同快照微基准相对 `70446ba`：冷对象解析中位数 +5.01%、P95 +4.57%；热解析 +4.81%/+5.75%；24 单位读取 +4.27%/+5.04%，满足 10% 阈值。
- 架构依赖审计完成，公开服务仍经会话绑定；发布版桥接代码与实验配置扩展的差异已核对。
- 本轮只编译测试/开发 DLL，没有构建 EXE、发布、修改游戏或改动发布工作树。实验分支游戏实测、外机实测未执行。

传输场景可在已编译开发桥后复核：

```powershell
python tools/verify_bridge_transport_runtime.py build/architecture-runtime/war3_bridge_24268.dll normal
python tools/verify_bridge_transport_runtime.py build/architecture-runtime/war3_bridge_24268.dll native
python tools/verify_bridge_transport_runtime.py build/architecture-runtime/war3_bridge_24268.dll tail_block
python tools/verify_bridge_transport_runtime.py build/architecture-runtime/war3_bridge_24268.dll native_timeout
python tools/verify_bridge_transport_runtime.py build/architecture-fixture/engine-hero-fixture.dll recovery_fault
```

### 2.1.0 测试版最终自检

版本及说明准备完成后重新运行全量测试：**141 个模块，2591 passed、29 skipped、120 subtests passed，无失败**。先前 139 模块及定向运行的结果被本次覆盖，不重复累计。

`test_release209_equivalence.py` 固定对照已发布提交 `873af7140f6af95f826565d8ae0397f840022b32`，检查 471 个方法签名、390 个搬迁方法的已审差异、28 个原生服务及快捷键。`test_beta_release_contract.py` 检查测试版标识、发布清单、动态协议收集及缺少配置/服务/协议/预发布标记时的构建验收拒绝。新增测试版标签的英文翻译遗漏已修复并通过回归。

发布说明为 `RELEASE_NOTES_v2.1.0-beta.md`。当前交付的是已提交的实验分支源码、开发 DLL、构建配置和待发布说明；EXE 构建及发布未执行。授权构建后在本工作树运行 `python tools/build_release_210.py`，产物必须通过 `python tools/build_release_210.py --verify-only` 及 EXE 自检，再按测试版发布。

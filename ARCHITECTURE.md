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

搬迁时逐一比较 390 个方法的语法树，389 个函数体保留，另一个仅修复基线物品槽超时错误地重试生命值写入的问题。

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

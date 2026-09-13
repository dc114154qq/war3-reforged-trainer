# 3.0.0.24268 适配进度（2026-09-13）

## 已实现、尚未交付的 24 单位支持

用户明确新版编队上限为 24，已选中超过 12 个目标。协议 70 将 C 快照数组、技能扩展容量、组移动及旧形状选择枚举入口统一为 `WAR3_SELECTED_MAX_UNITS=24`；Python 同步为 24。超过 24 返回错误，不发布前 24 个当完整结果。旧形状枚举遇到重复对象也拒绝，防止循环不前进。

真实 C 快照分发器通过 24 个单位各 4096 技能的结果传输；组移动覆盖 13/24 个，25 个在移动前拒绝。Python 混合英雄/普通单位测试覆盖 13/24 个候选显示和完整 action 调用，读取一次选择、共用一次批事务，身份逐项绑定。

专项结果：59 passed、52 subtests passed（4.12s），见 ../selection-24-regression.txt。DLL 已重编译，仍使用旧 23745 bootstrap profile；**这不代表 3.0 实机已可运行，不打包此中间版本**。源码协议与打包后的旧 1.0.19 发布包独立。

## 新构建证据和入口问题

- PID 23864 的进程外指定模块 .text 采集存在 4085 页缺口；已标记，不用零填充部分生成任何可调用 profile。磁盘镜像/代码节与旧构建不符。
- 按旧注册字符串 RIP-relative 模式查新磁盘及完整可读片段，未找到四个已知锚点。空结果不等于新版没有 native 注册表。
- PID 24720 的采集未完成且游戏退出。错误报告 08:47:31 与先前 08:44:16 都是游戏主线程同一栈写地址 0x30；报告没有 capture.dll 栈帧。仅能确定崩溃发生，不能据此确定根因或排除采集的影响。后续移除自定义 WM_APP 消息，改用原 helper 相同的 WH_CALLWNDPROC/WM_NULL。
- PID 24284：使用标准消息后，游戏持续响应，但 capture hook 没有返回状态文件。原已发布 helper 的构建校验命令同样超时 status=1（30 秒）；该命令有严格旧构建头校验，未调用游戏 native 函数。研究工具本地 callback 自检正确返回“不匹配构建”1306。
- 游戏与控制器 integrity 均 8192；检查动态代码、扩展点、签名及映像加载策略所得 flags 都为 0。尚未找到权限或这些缓解策略导致的原因。
- 通过独立研究工具核对新线程执行：WaitForSingleObject 返回完成、线程 exit=0，且读取回传结构成功，但 module=0x12345678/error=0xffffffff 两个初始哨兵保持不变。因此 **诊断入口未写回结果，不能解释成 LoadLibrary 真正返回空句柄或 last_error=0**。详见 load-diagnostic.txt。工具已修正，哨兵未变化时不会报告成功；超时不释放仍可能使用的远端参数/代码。

## 下一步

先确认新构建的线程启动/窗口 hook 执行链及进程内实际代码视图，再恢复可验证的 native 注册锚点、context/hash/resolver 和对象布局。不要反复尝试相同超时命令，不通过放宽旧 profile 指纹来制造支持。研究工具读取指定模块或分配诊断参数不属于产品备用读取；成品仍以完整纯 native 链路为目标。

目前没有对 3.0 游戏执行单位、技能、物品或资源写入，也未声称跨电脑通过。当前用户已经提供 24 单位混选测试环境，不需要再次要求其选中 12 个单位。

## 线程入口来源已定位

只读对比发现游戏中的 LdrInitializeThunk 和 BaseThreadInitThunk 前五字节均为跳转，与本机 ntdll/kernel32 原入口不同。沿有限跳转追踪，两者分别到达 war3_loader.dll 内 RVA 0x1351be0 与 0x1da6be0。RtlUserThreadStart 原始入口未改。证据见 execution-entry.json。

war3_loader.dll 的 Authenticode 签名有效，签名主体 Blizzard Entertainment, Inc.；磁盘 SHA256 E32431E26F58D1201BE3F48BAED485114227864D8C6B871EAE8E9528241EC8E9。3.0 主程序显式导入该模块的 ordinal 1，该 DLL 也只导出 ordinal 1，无命名的选择单位接口。旧 23745 崩溃记录中未找到 war3_loader.dll，但旧安装目录已经不可用，不能据此确定首次引入版本。

新增隔离 Unicorn 跟踪：仅按执行路径读取有限的代码/常量页面，在模拟器内运行线程入口，所有写入均在模拟内存；真实游戏中不调用这些函数。跟踪到通过 PEB 混淆的私有跳板调用 NtQueryVirtualMemory，查询对象是传入的新线程入口地址；在 OS 调用前停止。此证据表明其线程入口路径检查内存信息，尚不能推出完整允许规则，更不能宣称没有内部游戏数据入口。

后续以此明确入口继续审计；不要再次重复无效 LoadLibrary/窗口 hook 超时测试。需要区分加载器职责与选中单位数据来源，仍优先寻找能稳定取得完整选择列表的实际 native 调用链。

## 隔离对照与映像诊断入口

在相同已采集的 BaseThreadInitThunk 跳转路径下，隔离模拟 NtQueryVirtualMemory 的返回：MEM_PRIVATE 场景把原入口 0x720000000 改为加载器内 0x7fff132f2960；MEM_IMAGE 场景保留原入口。最终均到原系统入口的 trampoline 前停止，未在真实进程运行这些模拟调用。证据为 thread-gate-trace-private.json 和 thread-gate-trace-image.json；这只证明该路径对这两个内存类型的差异，不证明所有校验规则。

研究工具以 SEC_IMAGE 映射自己的无导入 PE，入口已可执行。首次调用加载函数时 PID 24284 退出；此错误随后在自建 Python 子进程中完全复现。根因为诊断 C 程序传递 `LoadLibraryW`/`GetLastError` 符号地址可能得到本程序的导入跳板，而非系统模块函数地址。已改为 GetProcAddress 明确解析；不能将这次崩溃归咎于游戏保护。普通分配诊断工具也同步修正。

新增 analysis/test_image_probe.py 在临时目录编译真实映像和控制器，仅针对自己创建的子进程：验证成功加载、文件不存在时返回 126、阶段到达 2、线程正常返回、宿主仍存活；两项通过（3.24s）。桥接 PE 无导入、无 DllMain，不使用游戏函数。控制器只释放已结束线程的自有参数和映射，超时会保留仍可能使用的区域。

修正后的真实游戏 PID 23652 诊断：映像映射成功，线程 exit=0，stage=2，module=NULL，loader error=2148073478（0x80090006，NTE_BAD_SIGNATURE）。游戏仍存活并响应，证据见 image-probe-live.txt。错误码官方定义为 Invalid Signature：https://learn.microsoft.com/en-us/windows/win32/com/com-error-codes-4 。此结果证明实际加载调用已执行并返回签名错误；并未证明签名检查所在全部路径，也没有绕过或修改保护代码。

下一步可从已验证执行的无导入映像入口开展严格只读研究，或寻找游戏允许的加载/扩展机制；仍需确认 native 注册和对象布局，不能视为纯 native 功能已经恢复。暂停重复尝试被拒绝的普通 DLL 加载。

## 共享映像读取结果（2026-09-13）

继续使用当前运行的 PID 23652，按句柄元数据定位主模块的共享 Section（不枚举地址空间、不写入游戏）。本地只读映射校验 PE 时间戳、SizeOfImage 和模块头后，完整取得 `.text` 36036822 字节、`.rdata` 12764066 字节；游戏仍响应。旧的进程外 `ReadProcessMemory` 299 缺口因此解释为对共享映像保护页的外部读取限制，而不是不存在代码。证据见 `module-sections.json`、`section-capture.json`。

在完整共享 `.text` 上按旧版本的四个注册字符串锚点仍没有得到注册记录；不能沿用旧 profile。新代码在磁盘和共享映像起始字节也出现不同，说明需要按 3.0 的新执行/解码路径恢复代码视图。

补充核对：此前注册搜索脚本漏加 PE ImageBase，已经修正；修正后运行时 `.rdata` 的四个名称地址已确认，但在当前共享 `.text` 中仍没有直接 RIP-relative 引用。说明注册链不是旧版简单的 `lea name; call dispatcher` 形状，不能把空结果解释成名称不存在。

运行时 `.rdata` 的名称目录已提取为 `native-catalog.json`。它包含 GroupEnumUnitsSelected、GetUnitState、GetHeroStr、UnitAddAbility、BlzGetUnitAbilityByIndex 及附近签名字符串；这证明 3.0 仍保留需要的 JASS/native 目录。当前代码没有保存这些地址的绝对指针，也没有旧版直接引用，推测注册前经过加载器解码或间接表生成。目录本身还不是可调用 handler，不能拿名称地址冒充函数地址。

进一步只读分析了 Windows 异常分发入口：`KiUserExceptionDispatcher` 的第一跳调用游戏/加载器回调，加载器异常路径建立 Fiber 并调用 TLS 取值；这些调用均只在 Unicorn 的模拟内存中推演，未调用真实函数。模拟结果不能证明完整保护算法，当前不修改异常处理链。

## loader 运行时代码（2026-09-13）

按已确认的 loader 模块基址 0x7fff0ea40000 和 PE `.text` 节，读取了完整 33874870 字节运行时代码，0 个缺页；哈希 `9c366fce157819e5b628a56d499fd6af64c356d29d57f9c6c2f56849b24d133b`，见 `loader-runtime.json`。入口 RVA 0x1351be0 和 0x1da6be0 的运行时代码显示状态值混淆、线程 Fiber/TLS 门控和转发调用；没有看到直接的选中单位 API。

这使当前结论更明确：`war3_loader.dll` 是 3.0 的执行/完整性加载层，不应被当作经典版“大象”选择接口。3.0 仍有完整 JASS 名称目录，但 handler 表是在游戏线程/loader 上下文中生成。产品适配必须找到合法稳定的游戏线程 native 入口，再接入 24 单位快照；不通过 loader 门控、不绕过签名检查、不恢复全扫描。

## 运行时 `.data` 表检查

按主模块共享 Section 句柄 0x320 只读取得 `.data`（RVA 0x2e8d000，184204896 字节）；非零字节约 452543。数据中有 14385 个指向 `.rdata` 范围的 64 位内部表引用，说明 3.0 确实维护大量运行时目录/对象表；但五个已知 native 名称的字符串地址没有直接绝对指针，名称经过索引或编码。原始 `section-data.bin` 保留在本机分析目录，不进入 Git。

当前源码的旧 `war3_bootstrap_query` 依赖 2.0.4 的名称哈希、context slot 和固定 resolver profile；证据已证明这些不能直接移植到 3.0。下一步必须从 `.data` 表的已知目录边界和运行时线程调用上下文恢复 3.0 表项，随后才能重建 `PERSISTENT_NATIVE_NAMES` 的 handler 返回。不要把 `.rdata` 名称地址、`.data` 任意指针或旧版固定 RVA 当作 callable handler。

进一步只读取得 loader `.data`（RVA 0x20f0000，1142719 字节，0 缺页，哈希 `5e8b48688f7b42217531d38cdb34c6b692997334697fea6815b81ac0372364d9`）。它包含 loader 自身的大量上下文/对象表，并有 3 个指向游戏主模块的基址引用（0x7fff10bf6c70、0x7fff10bf6c78、0x7fff10bf7c40）。这些是有价值的 loader→game 上下文锚点，但还不是 native handler；仍只读分析，不调用表项。

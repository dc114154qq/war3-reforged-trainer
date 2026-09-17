# Warcraft III Reforged Trainer 2.0.2

适配 Warcraft III `3.0.0.24268`。

## 变更

- 将 3.0 bridge 改为由目标进程正常加载，使用系统 loader 完成重定位、导入、CFG 与异常处理登记。
- 增加目标模块实际路径校验，避免同名旧 bridge 被误用。
- 移除对正常加载模块重复注册 `.pdata` 的路径，降低不同 Windows 配置下的加载失败概率。
- 修正远程线程、Hook 回调和释放阶段的状态记录；超时或释放失败时保留诊断状态，不再假报成功。
- 保留现有 3.0.0.24268 功能链路和日志留痕。

## 已验证

- bridge ABI 校验通过。
- 冻结态运行自检通过，未包含已退役的旧 native helper。
- 两个独立目录、不同 CWD、`RunAsInvoker` 包级可移植性模拟通过。
- 完整回归：`2277 passed, 17 skipped, 120 subtests passed`。

## 说明

以上包级验证不等同于物理第二台电脑的完整性级别、会话和安全策略验证；失败机请保留 `log` 目录中的诊断日志。

# 鼠标落点投影与传送精度

## 2026-10-23 修订依据

已发布基线：修改器 2.1.16，构建 C95543DDB8C1，源码 c0f142161759f3fb7f20a634b0c2c1d400bcb442。

参考作者 Antares 的 World2Screen 2.0，资源页标注支持 Warcraft 3.0，最后更新 2026-09-19：

- https://www.hiveworkshop.com/threads/fast-world2screen-transform-synced-async.354017/
- 原始研究帖：https://www.hiveworkshop.com/threads/making-an-accurate-get-mouse-screen-position.350018/

实际下载 World2Screen.zip，SHA256 `45ee63136c9751750044d9990ed0c4798613e7cbc652ea593c162bec8782c45a`。
其中原始 World2Screen.lua SHA256 `8e910bf330ab70ec394668de306dc05e8e96677cb2be6b0028ecd8918bd53429`。
资源原件、下载记录和失败的初次网络记录保留于 `build/teleport-projection-20261023/`，没有执行地图脚本或启动游戏。

## 旧算法与修订

旧版把 FOV 当普通垂直视角，用全窗口中心作透视投影中心，并以 eye→target 推导朝向。这与参考源码中的魔兽投影存在可复现的差异。

共用 `war3_services/camera_projection.py` 使用参考源码的魔兽 UI 坐标域、偏移中心、FOV 标定，以及 angle of attack / rotation / local pitch / local yaw 计算射线。系数来自作者的经验标定，不是声称逆向得出的引擎投影矩阵。原有限界地形求交、地图边缘和引擎 SetUnitPosition 路线保留。

游戏自带 common.j 明确：字段 7 为 near clip，字段 8/9/10 才是 local pitch/yaw/roll。原 camera 回调只查 0–7，现增加读取 8–10。CameraWork 仍为 256 字节，旧输出偏移保留，原 padding 的 192–203 存新字段；ABI 从 0x2426801B 变为 0x24268079，旧 DLL 会在 ABI 校验被拒绝。七份 profile 不增加地址或版本分支。

参考源码没有滚转支持。全局或局部 roll 非零时明确停止此次传送，避免给出未经确认的偏转落点。空快照、缺少局部字段、无效 FOV 和视口外鼠标也明确报错，取消旧的默认 70° 猜测。

## 验证方法

使用 Lupa 2.8 执行原封不动的作者 Lua，仅用受控函数提供相机参数；以它的 **World2Screen 正向变换**生成点对。再用本修改器的逆向投影恢复已知世界点，避免用本实现反算自己的预期值。

固定点对记录在 `tests/data/mouse_projection_world2screen_v2.json`，覆盖 35/70/100° FOV、多组基础与局部转向、4:3、16:9、21:9、竖向视口和非中心落点。另测多种 DPI、地形坡度、失败后下一次请求、七份配置的真实生产 C 回调和移动原生路径。

## 验证边界

点对照证明本实现与作者的算法一致，不等于已在本机或外机完成画面落点校准。作者标定与当前游戏渲染、地图镜头可能仍有误差；本轮实际画面投影尚未测量。地形多交点、桥梁与水面等渲染表面和单位碰撞可能另有影响。SetUnitPosition 可能把目标挪至可站立处，多单位还可能分开摆放；原请求与最终读回分别保留，不能把引擎调整的落点称为精确光标命中。

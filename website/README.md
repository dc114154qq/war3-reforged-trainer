# Warcraft III 工具发布站

静态版本归档站。首页提供修改器和独立改键软件两个入口。服务器每 10 分钟读取 GitHub Releases，镜像缺失的 `.exe` 文件，并更新版本说明、文件大小与 SHA256。

- `/trainer/`：修改器版本页，使用 `releases.json`。
- `/hotkeys/`：改键软件版本页，使用 `hotkey-releases.json`。
- `hotkeys-*` 标签归入改键软件，其余 Release 标签归入修改器。

## 本地预览

`releases.json` 生成后，在仓库根目录运行：

```powershell
python -m http.server 8765 --directory website
```

然后访问 `http://127.0.0.1:8765`。

## 同步

服务器目录：

- 网站：`/srv/war3-releases`
- 同步脚本：`/opt/war3-releases/sync_github_releases.py`
- 定时任务：`war3-release-sync.timer`

后续发布新版本时，只需在 GitHub 仓库创建 Release 并上传 `.exe`。改键软件使用 `hotkeys-vX.Y.Z` 标签，修改器沿用 `vX.Y.Z`。同步任务会自动把版本加入对应页面。`manual-releases.json` 仅用于尚未发布到 GitHub 的修改器本地版本；相同标签出现在 GitHub 后，以 GitHub Release 为准。

正式域名为 `twomengxi.xyz`。Caddy 会在 DNS 生效后自动申请并续期 HTTPS 证书；服务器 IP 入口保留为 DNS 传播期间的临时访问地址。

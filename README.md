# Pilotus Research

独立静态网站，部署至 https://research.pilotus.studio/ 。展示 brain.pet / DCCC 和 Titan。页面不加载第三方脚本；插画是原创概念示意，非实验数据。Nunito Sans 与 Caveat 字体及许可随站点保存。

## 本地预览

在此目录执行 `python -m http.server 4191 --bind 127.0.0.1`。

## 部署

所有 HTML/CSS、字体和发布归档在本地准备；云端只解压、切换版本和运行静态服务，不构建或编译。

- 云端独立目录：`/home/cheng/docker-projects/research`。
- `releases/<版本>` 保存成品，`current` 符号链接指向线上版本。
- 用户级服务 `pilotus-research.service` 使用系统已有 Caddy，监听 Docker 网桥 `172.18.0.1:8891`，不直接绑定公网。
- Traefik 的 `pilotus-research` HTTPS 路由转发至 `http://172.18.0.1:8891`，使用既有 `myresolver` 签发证书。
- 上传新版本至 releases，检查文件后以 `current.next` → `current` 的原子重命名切换；Caddy 无需重启。
- 回退时将 `current` 原子切回上一个版本。首次接入的路由备份保存在 Traefik 目录中，以 `dynamic.yml.before-research-` 为前缀；恢复挂载配置时保留原文件 inode，避免 Docker 单文件挂载读到旧文件。

## 检查

2026-11-06：Chromium 检查 320、390、768、1024、1440、1920 px 无横向溢出；桌面/手机截图人工检查；字体及资源无 404，主项目链接和键盘跳转入口正常。发布版本 `20261106-210412`；Research 和 Studio 公网 HTTPS 均返回 200，证书校验通过。Forum / Behavior 返回 200，SOP 返回既有 302。

首次接入脚本 `deploy/activate.py` 会验证 Caddy、备份原配置、验证无关路由保持不变，再切换两个站点；它只用于首次开通，会拒绝覆盖已有 Research 路由。以后的静态更新只需上传成品、切换 `current`，无需再次运行该脚本。

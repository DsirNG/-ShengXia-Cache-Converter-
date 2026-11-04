# macOS 版本

提供 Apple Silicon（arm64，M 系列）和 Intel（x86_64）两个独立 DMG，请按芯片下载。将 ShengXia.app 拖入 Applications 后启动。

默认查找网易云容器的 online_play_cache；找不到时点击浏览，选择实际包含 .uc 或 .uc! 的目录。支持原音频还原、MP3、FLAC、缓存品质确认、暂停/继续以及打开输出目录。品质确认依赖同目录 .info 与资源标识、大小匹配；Mac 缓存缺少这些记录时会标为档位未知。

AV3A 使用 mpv-iina-avs 的 macOS FFmpeg 解码，普通编码使用独立 FFmpeg。原音频保留在 originals，兼容播放文件为立体声 FLAC，不保留原始空间效果。无需用户另外安装 Homebrew 或解码器。

当前构建使用本地临时签名（ad-hoc），尚未完成 Apple Developer ID 签名与公证。首次运行可能被 Gatekeeper 阻止；请按 macOS 的“隐私与安全性”提示决定是否允许打开。正式无提示分发需要开发者证书与公证凭据。

## 构建与验证

在相应架构的 macOS 上安装 Python 3.12（含 Tk）、FFmpeg（含 libmp3lame），执行 `python -m pip install -r requirements-build.txt`，再执行 `python build_macos.py`。

GitHub Actions 的 Build macOS DMG 工作流分别构建两个架构，检查 AAC 原音频还原、MP3/FLAC 编码、元数据资源绑定、Tk 初始化、打包后的应用启动及工具依赖、签名完整性，最后生成 DMG。AV3A 解码器注册会被检查；不把个人歌曲上传为测试素材。CI 无法代替真实 Mac 上的人工交互与听音验收。

第三方解码器来源与使用限制见 OPEN_SOURCE.md。

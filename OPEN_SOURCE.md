# 开源与第三方组件说明

本文记录“声匣缓存转换器”仓库中的自有代码、构建工具和运行时依赖，便于维护者决定如何发布源码与安装包。

## 本项目代码的许可证

当前仓库尚未附带 `LICENSE` 文件，因此**尚未授予他人复制、修改或再分发本项目代码的许可**。GitHub 上公开可见不等于选择了开源许可证。仓库所有者应先决定许可证，再添加对应的 `LICENSE` 文件。

## 构建和运行组件

| 组件 | 用途 | 当前情况 |
| --- | --- | --- |
| PyInstaller 6.21.0 | 将 Python 界面打包为 Windows 程序 | PyInstaller 使用 GPLv2-or-later，并带有 bootloader exception；详见其 [COPYING 文件](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/COPYING.txt)。 |
| Yaoplayer/mpv AV3A core | 解码网易云缓存中的 AV3A 音频 | 由构建者从本机指定目录提供，未提交到本仓库。打包该核心前，应核对所用发行包的许可和再分发条件。 |
| FFmpeg | 探测、封装 MP3 标签和封面 | 本次本机安装包使用 Gyan.dev FFmpeg 8.1.2 essentials build，随附说明标记为 GPL v3，并指向 FFmpeg 源码提交 [`38b88335f9`](https://github.com/FFmpeg/FFmpeg/commit/38b88335f9)。FFmpeg 二进制不会提交到本仓库。 |
| Inno Setup 7 | 生成 Windows 安装程序 | 仅为构建时工具，不随应用安装。官方说明商业用途需要相应许可，详见 [许可信息](https://jrsoftware.org/isorder.php)。 |

## 发布安装包前

- 本仓库的 `.gitignore` 排除 `build/` 和 `artifacts/`，避免把大型程序目录和安装包误提交到 Git。
- 如果发布包含 FFmpeg 的安装包，应按该 FFmpeg 构建的 GPL v3 条款提供相应源码及构建资料，并保留所需版权与许可文本。
- Yaoplayer/mpv AV3A core 的许可需按实际使用的发行包单独确认。
- 当前源代码依赖公开歌曲信息服务补充歌名、歌手、封面和歌词。音频解码和转换在本机完成，音频文件不会上传。

本说明不是法律意见；实际发布者应以所选二进制发行包附带的许可文件和构建信息为准。

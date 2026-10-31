# 开源与第三方组件说明

本文记录“声匣缓存转换器”仓库中的自有代码、构建工具和运行时依赖，便于维护者决定如何发布源码与安装包。

## 本项目代码的许可证

本项目自有代码采用 [MIT License](LICENSE)，允许商业使用、复制、修改和再分发；再分发时需保留版权和许可声明。该许可证不覆盖下文列出的第三方组件，它们仍受各自许可证约束。

## 构建和运行组件

| 组件 | 用途 | 当前情况 |
| --- | --- | --- |
| PyInstaller 6.21.0 | 将 Python 界面打包为 Windows 程序 | PyInstaller 使用 GPLv2-or-later，并带有 bootloader exception；详见其 [COPYING 文件](https://github.com/pyinstaller/pyinstaller/blob/v6.21.0/COPYING.txt)。 |
| Yaoplayer/mpv AV3A core | 解码网易云缓存中的 AV3A 音频 | 本次构建使用 Yaoplayer 项目的 mpv core。上游项目代码采用 [MIT License](vendor-tools/licenses/mpv-Yaozhi/LICENSE.md)；核心发行包还可能包含具有独立许可的第三方组件，使用者应同时遵守其随包许可。核心二进制由构建者从本机目录提供，不提交到本仓库。 |
| FFmpeg | 探测、封装 MP3 标签和封面 | 本次本机安装包使用 Gyan.dev FFmpeg 8.1.2 essentials build，随附说明标记为 GPL v3，并指向 FFmpeg 源码提交 [`38b88335f9`](https://github.com/FFmpeg/FFmpeg/commit/38b88335f9)。FFmpeg 二进制不会提交到本仓库。 |
| Inno Setup 7 | 生成 Windows 安装程序 | 仅为构建时工具，不随应用安装。官方说明商业用途需要相应许可，详见 [许可信息](https://jrsoftware.org/isorder.php)。 |

## 发布安装包前

- 本仓库的 `.gitignore` 排除 `build/` 和 `artifacts/`，避免把大型程序目录和安装包误提交到 Git。
- 安装包内包含 FFmpeg 的 `LICENSE` 与 `README.txt`，其中记录 GPL v3 声明和上游源码提交 `38b88335f9`。公开再分发本安装包时，应按 GPL v3 条款提供对应源码及构建资料，并保留所需版权与许可文本。
- 安装包内包含 Yaoplayer 上游项目的 MIT 许可文本；mpv core 发行包内若另有第三方组件和许可，应一并核对并按其条款处理。
- 当前源代码依赖公开歌曲信息服务补充歌名、歌手、封面和歌词。音频解码和转换在本机完成，音频文件不会上传。

本说明不是法律意见；实际发布者应以所选二进制发行包附带的许可文件和构建信息为准。

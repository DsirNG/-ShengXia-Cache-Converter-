<p align="center">
  <img src="assets/shengxia.png" alt="声匣 Logo" width="160">
</p>

# NCM Converter

网易云音乐缓存与下载文件转换工具，原名“声匣缓存转换器”。

## 下载文件（.ncm）转换

在“输入类型”选择“下载文件（.ncm）”，选择包含 NCM 文件的输入目录和独立的输出目录。
默认推荐“还原源品质”：解密后保留原始 MP3 / FLAC 等音频编码，不重新压缩；也可以统一输出 MP3 或 FLAC。
MP3 / FLAC 会保留 NCM 内嵌的歌名、歌手、专辑和封面，无需联网。支持当前目录批量转换，单个损坏文件不会中止其他文件。
转换为 FLAC 不会提升有损源音质。输出文件名附带输入文件名摘要，避免同名歌曲互相覆盖。

源码运行先安装 `python -m pip install -r requirements.txt`。命令行示例：

```powershell
python process_cache.py --input-type ncm --source 'C:\Music\Downloads' --output 'C:\Music\Converted' --format source --ffprobe 'C:\tools\ffprobe.exe'
```

转码为 MP3 / FLAC 时另传 `--ffmpeg`；NCM 模式无需 AV3A 解码器，也不会请求在线歌曲服务。
解密逻辑从同作者 [aural-music 的 ncm.js](https://github.com/DsirNG/aural-music/blob/main/public/api/ncm.js) 移植，内嵌标签使用 Mutagen 写入。
本次测试使用合成的 NCM 样本；不同客户端版本生成的真实下载文件还需要进一步试用确认。

我做声匣，是想把自己电脑里的网易云音乐缓存整理成能在本地播放器播放的文件。它是一款 Windows / macOS 桌面工具，支持把 .uc 缓存转换成 MP3 或 FLAC，也能补全歌曲信息、封面和歌词。

最新版本：[v0.1.6 安装包](https://github.com/DsirNG/-ShengXia-Cache-Converter-/releases/tag/v0.1.6)。

## macOS

[macOS v0.1.7 下载](https://github.com/DsirNG/-ShengXia-Cache-Converter-/releases/tag/v0.1.7)：Apple Silicon 与 Intel 原生 DMG，包含音频工具，需要 macOS 15 或更新系统。安装、缓存目录、签名状态和构建说明见 [MACOS.md](MACOS.md)。

## 快速开始

1. 在 [Releases](https://github.com/DsirNG/-ShengXia-Cache-Converter-/releases) 下载 Windows x64 安装包；如果尚未发布安装包，可按下方说明从源码构建。
2. 打开声匣，选择网易云音乐的 Cache/Cache 缓存目录。
3. 选择输出目录和“还原源品质”、MP3 或 FLAC，开始转换；处理中可暂停并继续。

## 试听示例

我用自己创作并发布的《梳限训考》做了一份 [试听示例](examples/梳限训考-试听示例.mp3)，方便你先听听实际转换效果。这段音频约 27 秒，MP3、44.1 kHz、双声道。示例音频由我提供，授权不包含在项目代码的 MIT 许可证内；如需另作使用，请先联系我。

仓库只放了这一份由我提供的试听示例，没有收录其他歌曲或原始缓存。使用时请处理你有权使用的音频。

## 常见问题

- **转成 FLAC 后还有破音？** FLAC 只保存解码后的声音，无法修复源缓存中已有的失真。
- **为什么没有歌名或封面？** 元数据补全需要网络，并取决于公开服务是否有对应记录。
- **能转换所有缓存吗？** 目前针对项目适配的 .uc 格式，格式变化可能导致转换失败。
- **会上传歌曲吗？** 音频在本机处理。启用元数据补全时仅请求歌曲信息、封面和歌词。

## 功能

- 选择 `.uc` 缓存目录和输出目录。
- “还原源品质”保留普通音频的原始容器。遇到 AV3A 时，原音频保存在 `originals/`，另生成供普通播放器播放的立体声 FLAC；兼容版本不保留原始空间效果。也可统一转换为 320 kbps MP3 或立体声 FLAC。
- 音质档位读取自缓存 `.info` 的 `level` 字段；记录中的资源 MD5 与缓存文件名、资源大小均匹配时，显示“已确认”。支持标准、较高、极高 HQ、无损 SQ、高清臻音、超清母带、臻音全景声；缺失、损坏或不匹配时显示“档位未知”。此校验是资源记录绑定，不是逐字节音频 MD5 验证。
- 编码和声道数单独展示，不再作为网易云档位名称。已有结果可在原输出目录点击“刷新”，根据仍存在的源缓存重新确认档位。
- 主窗口提供“转换列表”，可查看歌曲、歌手、确认的音质档位、源编码/声道、格式与状态；转换中自动刷新，双击歌曲或使用按钮可打开音频。
- 转换中可暂停和继续；暂停会在当前解码或编码步骤结束后生效。
- 自动检测解码后的峰值并预留余量，避免输出时削波。
- 要重新转换已有的同格式文件，请勾选“覆盖同格式的已有文件”。
- 可联网补充歌名、歌手、封面和歌词。音频转换在本机进行。
- 安装后可从开始菜单启动，也可以创建桌面快捷方式。

## 源码结构

- `gui.py`：独立 Tkinter 图形界面。
- `process_cache.py`：缓存处理模块，默认路径使用当前用户目录，可通过环境变量覆盖。
- `assets/shengxia.png`：声匣图形 logo。
- `assets/shengxia.ico`：Windows 程序和安装包图标。
- `installer/shengxia.iss`：Inno Setup 安装包配置。
- `build.ps1`：构建便携程序并生成单文件安装包。

## 构建要求

- Windows x64
- Python 3.12
- `python -m pip install -r requirements-build.txt`
- AV3A 解码器目录（包含 `Yaoplayer.com` 和运行所需文件）
- FFmpeg `bin` 目录（包含 `ffmpeg.exe`、`ffprobe.exe`）
- Inno Setup 7 编译器 `ISCC.exe`

可以通过参数或环境变量传入工具目录：

```powershell
.\build.ps1 `
  -MpvCoreDir 'C:\path\to\mpv-core' `
  -FfmpegBinDir 'C:\path\to\ffmpeg\bin' `
  -IsccPath 'C:\Program Files\Inno Setup 7\ISCC.exe'
```

也可以设置 `MPV_CORE_DIR`、`FFMPEG_BIN_DIR`、`INNO_SETUP_COMPILER` 后运行 `.\build.ps1`。

构建出的安装包在 `artifacts\ShengXiaCacheConverter-Setup-0.1.6-x64.exe`。安装程序默认安装到当前用户的 `%LOCALAPPDATA%\Programs\ShengXiaCacheConverter`，不需要管理员权限。

## 数据与网络

音频解码、转换和文件写入都在本机完成。启用元数据补全时，程序会访问处理脚本配置的公开元数据服务，以及返回的封面和歌词地址；不会上传音频文件。断网时仍可转换音频，但歌名等信息可能缺失。

请使用你有权处理的缓存文件。`.uc` 的解码流程针对当前脚本适配的缓存格式，不保证兼容网易云音乐所有版本或未来变更。

第三方软件和授权说明见 [OPEN_SOURCE.md](OPEN_SOURCE.md)。

我将项目自有代码以 [MIT License](LICENSE) 开源，允许商业使用、修改和再分发。第三方软件不由本项目许可证覆盖，请遵循各自许可证。

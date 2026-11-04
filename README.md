<p align="center">
  <img src="assets/shengxia.png" alt="声匣 Logo" width="160">
</p>

# 声匣缓存转换器

我做声匣，是想把自己电脑里的网易云音乐缓存整理成能在本地播放器播放的文件。它是一款 Windows 桌面工具，支持把 .uc 缓存转换成 MP3 或 FLAC，也能补全歌曲信息、封面和歌词。

## 快速开始

1. 在 [Releases](https://github.com/DsirNG/-ShengXia-Cache-Converter-/releases) 下载 Windows x64 安装包；如果尚未发布安装包，可按下方说明从源码构建。
2. 打开声匣，选择网易云音乐的 Cache/Cache 缓存目录。
3. 选择输出目录和 MP3 或 FLAC 格式，开始转换。

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
- 可选“还原源品质”逐字节恢复 XOR 解码后的缓存音频容器，不重新编码、不降采样或混成双声道；也可转换为 320 kbps 立体声 MP3 或 FLAC。转换编码不能恢复源文件已经损失的信息。
- 转换结果文件名、音频备注标签和 `catalog.json` 会标注按缓存源编码参数推定的网易云音质档位（如标准、极高、无损、高清臻音或超清母带）；依据不足时标为“品质未知”。导出为 320 kbps MP3 或 FLAC 不会提高源音质。
- 臻音全景声等空间音频类型无法仅凭解码后的普通码率/采样率可靠识别；多声道源会注明声道数，并标记空间类别未确认。
- 主窗口提供“转换列表”，可查看歌曲、歌手、推定音质、格式与状态；转换中自动刷新，双击歌曲或使用按钮可打开音频。
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

构建出的安装包在 `artifacts\ShengXiaCacheConverter-Setup-0.1.3-x64.exe`。安装程序默认安装到当前用户的 `%LOCALAPPDATA%\Programs\ShengXiaCacheConverter`，不需要管理员权限。

## 数据与网络

音频解码、转换和文件写入都在本机完成。启用元数据补全时，程序会访问处理脚本配置的公开元数据服务，以及返回的封面和歌词地址；不会上传音频文件。断网时仍可转换音频，但歌名等信息可能缺失。

请使用你有权处理的缓存文件。`.uc` 的解码流程针对当前脚本适配的缓存格式，不保证兼容网易云音乐所有版本或未来变更。

第三方软件和授权说明见 [OPEN_SOURCE.md](OPEN_SOURCE.md)。

我将项目自有代码以 [MIT License](LICENSE) 开源，允许商业使用、修改和再分发。第三方软件不由本项目许可证覆盖，请遵循各自许可证。

<p align="center">
  <img src="assets/shengxia.png" alt="声匣 Logo" width="160">
</p>

# 声匣缓存转换器

声匣是一个 Windows 桌面工具，用于把本机网易云音乐 `.uc` 缓存整理成高品质 MP3 或 FLAC，便于在系统播放器中播放和人工检查。

## 快速开始

1. 在 [Releases](https://github.com/DsirNG/-ShengXia-Cache-Converter-/releases) 下载 Windows x64 安装包；如果尚未发布安装包，可按下方说明从源码构建。
2. 打开声匣，选择网易云音乐的 Cache/Cache 缓存目录。
3. 选择输出目录和 MP3 或 FLAC 格式，开始转换。

## 试听示例

项目作者提供的 [《梳限训考》试听示例](examples/梳限训考-试听示例.mp3) 用于演示缓存转换结果。文件约 27 秒，MP3、44.1 kHz、双声道。可下载后用本地播放器试听。该音频是示例素材，不属于项目 MIT 代码许可证的授权范围；再使用请联系作者。

仓库不包含歌曲或缓存文件。演示时请使用自己拥有展示和再分发权利的音频。仅将歌曲上传到音乐平台，不代表已获得词曲和录音制品的全部授权。

## 常见问题

- **转成 FLAC 后还有破音？** FLAC 只保存解码后的声音，无法修复源缓存中已有的失真。
- **为什么没有歌名或封面？** 元数据补全需要网络，并取决于公开服务是否有对应记录。
- **能转换所有缓存吗？** 目前针对项目适配的 .uc 格式，格式变化可能导致转换失败。
- **会上传歌曲吗？** 音频在本机处理。启用元数据补全时仅请求歌曲信息、封面和歌词。

## 功能

- 选择 `.uc` 缓存目录和输出目录。
- 默认转换为 320 kbps 立体声 MP3，也可选择 FLAC 保存解码后的立体声音频。FLAC 无法恢复源文件已经损失的信息，也不保留原有多声道。
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

构建出的安装包在 `artifacts\ShengXiaCacheConverter-Setup-0.1.2-x64.exe`。安装程序默认安装到当前用户的 `%LOCALAPPDATA%\Programs\ShengXiaCacheConverter`，不需要管理员权限。

## 数据与网络

音频解码、转换和文件写入都在本机完成。启用元数据补全时，程序会访问处理脚本配置的公开元数据服务，以及返回的封面和歌词地址；不会上传音频文件。断网时仍可转换音频，但歌名等信息可能缺失。

请使用自己有权处理的缓存文件。`.uc` 的解码流程针对当前脚本适配的缓存格式，不保证兼容网易云音乐所有版本或未来变更。

第三方软件和授权说明见 [OPEN_SOURCE.md](OPEN_SOURCE.md)。

本项目自有代码采用 [MIT License](LICENSE)，允许商业使用、修改和再分发。第三方软件不由本项目许可证覆盖，请遵循各自许可证。

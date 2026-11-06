from __future__ import annotations

import queue
import json
import os
import ctypes
import subprocess
import sys
import threading
import traceback
from contextlib import redirect_stdout
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from runtime_support import default_cache_dir, tool_paths, open_path

import process_cache
from cache_quality import resolve_cache_quality


APP_TITLE = "NCM Converter"
DEFAULT_SOURCE = default_cache_dir()
DEFAULT_OUTPUT = Path.home() / "Documents/声匣转换结果"


def enable_high_dpi() -> None:
    """Keep Tk controls crisp on high-resolution and mixed-DPI Windows displays."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


enable_high_dpi()


class QueueWriter:
    def __init__(self, messages: queue.Queue):
        self.messages = messages
        self.buffer = ""

    def write(self, text: str) -> int:
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line:
                self.messages.put(("log", line))
        return len(text)

    def flush(self) -> None:
        if self.buffer:
            self.messages.put(("log", self.buffer))
            self.buffer = ""


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x700")
        self.minsize(760, 600)
        self.configure(bg="#f4f7f5")
        self.messages: queue.Queue = queue.Queue()
        self.source_var = tk.StringVar(value=str(DEFAULT_SOURCE))
        self.input_type_var = tk.StringVar(value="客户端缓存（.uc）")
        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.limit_var = tk.StringVar(value="0")
        self.force_var = tk.BooleanVar(value=False)
        self.quality_var = tk.StringVar(value="MP3 320 kbps（推荐，兼容性好）")
        self.status_var = tk.StringVar(value="就绪")
        self.running = False
        self.pause_gate = threading.Event()
        self.pause_gate.set()
        self.catalog_signature = None
        self.track_paths: dict[str, str] = {}
        self.brand_icon = None
        bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        logo_path = bundle / "assets" / "shengxia.png"
        if logo_path.is_file():
            try:
                original_icon = tk.PhotoImage(file=str(logo_path))
                shrink = max(1, (original_icon.width() + 63) // 64)
                self.brand_icon = original_icon.subsample(shrink, shrink)
                self.iconphoto(True, self.brand_icon)
            except tk.TclError:
                self.brand_icon = None
        self._build_ui()
        if os.environ.get("SHENGXIA_SMOKE_TEST") == "1":
            self.after(500, self.destroy)
        self.after(100, self._drain_messages)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        ui_font = "Helvetica Neue" if sys.platform == "darwin" else "Microsoft YaHei UI"
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f4f7f5")
        style.configure("Title.TLabel", font=(ui_font, 18, "bold"), background="#f4f7f5", foreground="#18352b")
        style.configure("Hint.TLabel", font=(ui_font, 9), background="#f4f7f5", foreground="#596b62")
        style.configure("TLabel", background="#f4f7f5", font=(ui_font, 10))
        style.configure("TButton", font=(ui_font, 10), padding=(10, 6))
        style.configure("Accent.TButton", font=(ui_font, 10, "bold"), padding=(16, 8))

        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)
        brand_row = ttk.Frame(root)
        brand_row.pack(anchor="w")
        if self.brand_icon is not None:
            ttk.Label(brand_row, image=self.brand_icon).pack(side="left", padx=(0, 10))
        ttk.Label(brand_row, text=APP_TITLE, style="Title.TLabel").pack(side="left")
        ttk.Label(root, text="网易云音乐缓存与下载文件转换工具", style="Hint.TLabel").pack(anchor="w", pady=(4, 8))
        mode_row = ttk.Frame(root)
        mode_row.pack(fill="x", pady=(0, 6))
        ttk.Label(mode_row, text="输入类型", width=10).pack(side="left")
        self.input_mode = ttk.Combobox(mode_row, textvariable=self.input_type_var, state="readonly",
                                      values=("客户端缓存（.uc）", "下载文件（.ncm）"), width=28)
        self.input_mode.pack(side="left")
        self.input_mode.bind("<<ComboboxSelected>>", self._change_input_type)

        self._folder_row(root, "输入目录", self.source_var, self._choose_source)
        self._folder_row(root, "输出目录", self.output_var, self._choose_output)

        opts = ttk.Frame(root)
        opts.pack(fill="x", pady=(12, 4))
        ttk.Label(opts, text="处理数量（0 = 全部）").pack(side="left")
        ttk.Entry(opts, textvariable=self.limit_var, width=8).pack(side="left", padx=(10, 22))
        ttk.Label(opts, text="联网补全歌名、歌手、封面和歌词").pack(side="left")
        quality = ttk.Frame(root)
        quality.pack(fill="x", pady=(7, 0))
        ttk.Label(quality, text="输出品质").pack(side="left")
        ttk.Combobox(quality, textvariable=self.quality_var, state="readonly", width=42, values=("还原源品质（特殊编码输出兼容FLAC）", "MP3 320 kbps（推荐，兼容性好）", "FLAC（转换为立体声 FLAC）")).pack(side="left", padx=10)
        ttk.Checkbutton(root, text="覆盖同格式的已有文件（重新转换时勾选）", variable=self.force_var).pack(anchor="w", pady=(7, 0))
        ttk.Label(root, text="缓存模式可联网补全信息；NCM 下载文件在本机解密并保留内嵌歌名、歌手和封面，无需联网。“还原源品质”保留原始编码；转为 FLAC 不会提升有损音源的音质。", style="Hint.TLabel", wraplength=720).pack(anchor="w", pady=(5, 10))

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(4, 8))
        self.start_btn = ttk.Button(actions, text="开始转换", style="Accent.TButton", command=self.start)
        self.start_btn.pack(side="left")
        self.pause_btn = ttk.Button(actions, text="暂停转换", command=self.toggle_pause, state="disabled")
        self.pause_btn.pack(side="left", padx=(8, 0))
        self.open_btn = ttk.Button(actions, text="打开输出目录", command=self.open_output)
        self.open_btn.pack(side="left", padx=10)
        self.spinner = ttk.Progressbar(actions, mode="indeterminate", length=170)
        self.spinner.pack(side="right", padx=(8, 0))
        ttk.Label(actions, textvariable=self.status_var).pack(side="right")

        self.results_tabs = ttk.Notebook(root)
        self.results_tabs.pack(fill="both", expand=True, pady=(4, 0))

        list_frame = ttk.Frame(self.results_tabs, padding=8)
        self.results_tabs.add(list_frame, text="转换列表")
        list_actions = ttk.Frame(list_frame)
        list_actions.pack(fill="x", pady=(0, 6))
        ttk.Label(list_actions, text="当前输出目录中的转换记录", style="Hint.TLabel").pack(side="left")
        ttk.Button(list_actions, text="刷新", command=lambda: self.refresh_catalog(force=True)).pack(side="right", padx=(6, 0))
        ttk.Button(list_actions, text="打开选中音频", command=self.open_selected_track).pack(side="right")
        columns = ("title", "artist", "quality", "codec", "format", "status")
        self.track_list = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        for key, label, width in (("title", "歌曲", 250), ("artist", "歌手", 170),
                                  ("quality", "网易云音质", 220), ("codec", "源编码 / 声道", 150), ("format", "格式", 90),
                                  ("status", "状态", 90)):
            self.track_list.heading(key, text=label)
            self.track_list.column(key, width=width, minwidth=70, anchor="w", stretch=key in ("title", "artist"))
        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.track_list.yview)
        self.track_list.configure(yscrollcommand=list_scroll.set)
        self.track_list.pack(side="left", fill="both", expand=True)
        list_scroll.pack(side="right", fill="y")
        self.track_list.bind("<Double-1>", lambda _event: self.open_selected_track())

        log_frame = ttk.LabelFrame(self.results_tabs, text="处理日志", padding=8)
        self.results_tabs.add(log_frame, text="处理日志")
        self.log = tk.Text(log_frame, height=14, wrap="word", font=("Consolas", 9), bg="#ffffff", fg="#25352d", relief="flat", padx=8, pady=8)
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set, state="disabled")
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.refresh_catalog(force=True)

    def _folder_row(self, parent, label, variable, command) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label, width=10).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(row, text="浏览…", command=command).pack(side="right")

    def _choose_source(self) -> None:
        path = filedialog.askdirectory(title="选择输入文件所在目录", initialdir=self.source_var.get())
        if path:
            self.source_var.set(path)

    def _change_input_type(self, _event=None) -> None:
        if self.input_type_var.get().startswith("下载"):
            self.quality_var.set("还原源品质（特殊编码输出兼容FLAC）")
            if self.source_var.get() == str(DEFAULT_SOURCE):
                self.source_var.set(str(Path.home() / "Downloads"))

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(title="选择转换结果目录", initialdir=self.output_var.get(), mustexist=False)
        if path:
            self.output_var.set(path)
            self.refresh_catalog(force=True)

    def _append_log(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self) -> None:
        source = Path(self.source_var.get().strip()).expanduser()
        output = Path(self.output_var.get().strip()).expanduser()
        if not source.is_dir():
            messagebox.showerror(APP_TITLE, f"缓存目录不存在：\n{source}")
            return
        if source.resolve() == output.resolve():
            messagebox.showerror(APP_TITLE, "输出目录不能与缓存目录相同，请另选一个目录。")
            return
        try:
            limit = int(self.limit_var.get().strip() or "0")
            if limit < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_TITLE, "处理数量须为 0 或正整数。")
            return

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.status_var.set("正在处理…")
        self.spinner.start(12)
        self.running = True
        self.pause_gate.set()
        self.pause_btn.configure(text="暂停转换", state="normal")
        self.catalog_signature = None
        self.results_tabs.select(0)
        self.refresh_catalog(force=True)
        self.after(900, self._refresh_while_running)
        force = self.force_var.get()
        selected_quality = self.quality_var.get()
        output_format = "source" if selected_quality.startswith("还原源品质") else "flac" if selected_quality.startswith("FLAC") else "mp3"
        input_type = "ncm" if self.input_type_var.get().startswith("下载") else "cache"
        threading.Thread(target=self._worker, args=(source, output, limit, force, output_format, input_type), daemon=True).start()

    def toggle_pause(self) -> None:
        if not self.running:
            return
        if self.pause_gate.is_set():
            self.pause_gate.clear()
            self.pause_btn.configure(text="继续转换")
            self.status_var.set("暂停请求中…当前安全步骤完成后暂停")
            self._append_log("已请求暂停；正在完成当前安全步骤。")
        else:
            self.pause_gate.set()
            self.pause_btn.configure(text="暂停转换")
            self.status_var.set("正在继续转换…")
            self._append_log("继续转换。")

    def _pause_checkpoint(self) -> None:
        if self.pause_gate.is_set():
            return
        self.messages.put(("paused", None))
        self.pause_gate.wait()
        self.messages.put(("resumed", None))

    def _worker(self, source: Path, output: Path, limit: int, force: bool, output_format: str, input_type: str = "cache") -> None:
        try:
            bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            mpv, ffmpeg, ffprobe = tool_paths(bundle)
            required = [("FFprobe", ffprobe)]
            if input_type == "cache":
                required.append(("AV3A 解码器", mpv))
            if input_type == "cache" or output_format != "source":
                required.append(("FFmpeg", ffmpeg))
            for label, path in required:
                if not path.exists():
                    raise FileNotFoundError(f"缺少{label}：{path}")
            args = ["process_cache.py", "--source", str(source), "--output", str(output),
                    "--mpv", str(mpv), "--ffmpeg", str(ffmpeg), "--ffprobe", str(ffprobe),
                    "--limit", str(limit), "--format", output_format, "--input-type", input_type]
            if force:
                args.append("--force")
            old_argv = sys.argv
            original_run = subprocess.run

            def run_without_console(*run_args, **run_kwargs):
                if os.name == "nt":
                    startup = subprocess.STARTUPINFO()
                    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startup.wShowWindow = subprocess.SW_HIDE
                    run_kwargs.setdefault("startupinfo", startup)
                    run_kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return original_run(*run_args, **run_kwargs)

            sys.argv = args
            try:
                # process_cache uses subprocess.run for the AV3A decoder and FFmpeg.
                # Keep their console windows hidden while stdout/stderr remain captured.
                subprocess.run = run_without_console
                process_cache.pause_checkpoint = self._pause_checkpoint
                with redirect_stdout(QueueWriter(self.messages)):
                    code = process_cache.main()
            finally:
                process_cache.pause_checkpoint = lambda: None
                subprocess.run = original_run
                sys.argv = old_argv
            self.messages.put(("done", code))
        except Exception:
            self.messages.put(("error", traceback.format_exc()))

    def _drain_messages(self) -> None:
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == "log":
                    self._append_log(value)
                elif kind == "done":
                    self._finish(value == 0, "处理完成" if value == 0 else "处理结束，存在失败项")
                elif kind == "paused":
                    self.spinner.stop()
                    self.status_var.set("已暂停；可点击“继续转换”接着处理")
                    self._append_log("转换已在安全位置暂停。")
                elif kind == "resumed":
                    self.spinner.start(12)
                    self.status_var.set("正在处理…")
                elif kind == "error":
                    self._append_log(value)
                    self._finish(False, "发生错误")
        except queue.Empty:
            pass
        self.after(100, self._drain_messages)

    def _finish(self, success: bool, status: str) -> None:
        self.running = False
        self.pause_gate.set()
        self.spinner.stop()
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(text="暂停转换", state="disabled")
        self.status_var.set(status)
        self.refresh_catalog(force=True)
        if success:
            messagebox.showinfo(APP_TITLE, f"{status}。\n结果目录：\n{self.output_var.get()}")
        else:
            messagebox.showwarning(APP_TITLE, f"{status}，请查看处理日志。\n结果目录：\n{self.output_var.get()}")

    def open_output(self) -> None:
        path = Path(self.output_var.get().strip())
        if path.exists():
            import os
            open_path(path)
        else:
            messagebox.showinfo(APP_TITLE, "输出目录尚未创建；开始转换后会自动创建。")

    def _refresh_while_running(self) -> None:
        if self.running:
            self.refresh_catalog()
            self.after(900, self._refresh_while_running)

    def refresh_catalog(self, force: bool = False) -> None:
        catalog = Path(self.output_var.get().strip()).expanduser() / "catalog.json"
        if not catalog.is_file():
            signature = None
            tracks = []
        else:
            try:
                stat = catalog.stat()
                signature = (stat.st_mtime_ns, stat.st_size)
                if not force and signature == self.catalog_signature:
                    return
                data = json.loads(catalog.read_text(encoding="utf-8"))
                tracks = data.get("tracks", []) if isinstance(data, dict) else []
            except (OSError, json.JSONDecodeError):
                return
        self.catalog_signature = signature
        for item in self.track_list.get_children():
            self.track_list.delete(item)
        self.track_paths.clear()
        for index, track in enumerate(tracks):
            title = str(track.get("title") or "未知歌曲")
            artist = str(track.get("artist") or "未知歌手")
            if track.get("input_type") == "ncm":
                quality = "下载文件（原始编码）"
            else:
                evidence = resolve_cache_quality(Path(data.get("source", "")) / str(track.get("cache_file", "")))
                quality = evidence["quality_label"] + ("（已确认）" if evidence["quality_status"] == "confirmed" else "")
            codec = f"{track.get("source_codec", "未知")} / {track.get("source_channels", 0)} 声道"
            track_path = str(track.get("audio_path") or "")
            output_format = str(track.get("output_format") or Path(track_path).suffix.lstrip(".") or "—").upper()
            status = {"ready": "已完成", "failed": "失败", "pending": "处理中"}.get(track.get("status"), str(track.get("status") or "—"))
            row_id = f"track-{index}"
            self.track_list.insert("", "end", iid=row_id, values=(title, artist, quality, codec, output_format, status))
            self.track_paths[row_id] = track_path

    def open_selected_track(self) -> None:
        selection = self.track_list.selection()
        if not selection:
            messagebox.showinfo(APP_TITLE, "请先选择一首歌曲。")
            return
        path = Path(self.track_paths.get(selection[0], ""))
        if not path.is_absolute():
            path = Path(self.output_var.get().strip()).expanduser() / path
        if path.is_file():
            open_path(path)
        else:
            messagebox.showwarning(APP_TITLE, f"找不到音频文件：\n{path}")


if __name__ == "__main__":
    App().mainloop()

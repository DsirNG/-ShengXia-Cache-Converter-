from __future__ import annotations

import queue
import os
import subprocess
import sys
import threading
import traceback
from contextlib import redirect_stdout
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import process_cache


APP_TITLE = "声匣缓存转换器"
DEFAULT_SOURCE = Path.home() / "AppData/Local/NetEase/CloudMusic/Cache/Cache"
DEFAULT_OUTPUT = Path.home() / "Documents/声匣转换结果"


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
        self.geometry("780x600")
        self.minsize(700, 520)
        self.configure(bg="#f4f7f5")
        self.messages: queue.Queue = queue.Queue()
        self.source_var = tk.StringVar(value=str(DEFAULT_SOURCE))
        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.limit_var = tk.StringVar(value="0")
        self.force_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="就绪")
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
        self.after(100, self._drain_messages)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f4f7f5")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"), background="#f4f7f5", foreground="#18352b")
        style.configure("Hint.TLabel", font=("Microsoft YaHei UI", 9), background="#f4f7f5", foreground="#596b62")
        style.configure("TLabel", background="#f4f7f5", font=("Microsoft YaHei UI", 10))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(10, 6))
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(16, 8))

        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)
        brand_row = ttk.Frame(root)
        brand_row.pack(anchor="w")
        if self.brand_icon is not None:
            ttk.Label(brand_row, image=self.brand_icon).pack(side="left", padx=(0, 10))
        ttk.Label(brand_row, text="声匣缓存转换器", style="Title.TLabel").pack(side="left")
        ttk.Label(root, text="选择 .uc 缓存目录和输出目录，转换为系统播放器可播放的 MP3。", style="Hint.TLabel").pack(anchor="w", pady=(4, 16))

        self._folder_row(root, "缓存目录", self.source_var, self._choose_source)
        self._folder_row(root, "输出目录", self.output_var, self._choose_output)

        opts = ttk.Frame(root)
        opts.pack(fill="x", pady=(12, 4))
        ttk.Label(opts, text="处理数量（0 = 全部）").pack(side="left")
        ttk.Entry(opts, textvariable=self.limit_var, width=8).pack(side="left", padx=(10, 22))
        ttk.Label(opts, text="联网补全歌名、歌手、封面和歌词").pack(side="left")
        ttk.Checkbutton(root, text="覆盖已生成的 MP3", variable=self.force_var).pack(anchor="w", pady=(7, 0))
        ttk.Label(root, text="处理时会按原脚本行为联网查询歌曲信息，并可能获取封面和歌词；音频解码与转换在本机完成。", style="Hint.TLabel", wraplength=720).pack(anchor="w", pady=(5, 10))

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(4, 8))
        self.start_btn = ttk.Button(actions, text="开始转换", style="Accent.TButton", command=self.start)
        self.start_btn.pack(side="left")
        self.open_btn = ttk.Button(actions, text="打开输出目录", command=self.open_output)
        self.open_btn.pack(side="left", padx=10)
        self.spinner = ttk.Progressbar(actions, mode="indeterminate", length=170)
        self.spinner.pack(side="right", padx=(8, 0))
        ttk.Label(actions, textvariable=self.status_var).pack(side="right")

        log_frame = ttk.LabelFrame(root, text="处理日志", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.log = tk.Text(log_frame, height=14, wrap="word", font=("Consolas", 9), bg="#ffffff", fg="#25352d", relief="flat", padx=8, pady=8)
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set, state="disabled")
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _folder_row(self, parent, label, variable, command) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label, width=10).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(row, text="浏览…", command=command).pack(side="right")

    def _choose_source(self) -> None:
        path = filedialog.askdirectory(title="选择网易云缓存目录", initialdir=self.source_var.get())
        if path:
            self.source_var.set(path)

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(title="选择转换结果目录", initialdir=self.output_var.get(), mustexist=False)
        if path:
            self.output_var.set(path)

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
        force = self.force_var.get()
        threading.Thread(target=self._worker, args=(source, output, limit, force), daemon=True).start()

    def _worker(self, source: Path, output: Path, limit: int, force: bool) -> None:
        try:
            bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            mpv = bundle / "tools" / "mpv" / "Yaoplayer.com"
            ffmpeg = bundle / "tools" / "ffmpeg" / "ffmpeg.exe"
            ffprobe = bundle / "tools" / "ffmpeg" / "ffprobe.exe"
            for label, path in (("AV3A 解码器", mpv), ("FFmpeg", ffmpeg), ("FFprobe", ffprobe)):
                if not path.exists():
                    raise FileNotFoundError(f"缺少{label}：{path}")
            args = ["process_cache.py", "--source", str(source), "--output", str(output),
                    "--mpv", str(mpv), "--ffmpeg", str(ffmpeg), "--ffprobe", str(ffprobe),
                    "--limit", str(limit)]
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
                with redirect_stdout(QueueWriter(self.messages)):
                    code = process_cache.main()
            finally:
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
                elif kind == "error":
                    self._append_log(value)
                    self._finish(False, "发生错误")
        except queue.Empty:
            pass
        self.after(100, self._drain_messages)

    def _finish(self, success: bool, status: str) -> None:
        self.spinner.stop()
        self.start_btn.configure(state="normal")
        self.status_var.set(status)
        if success:
            messagebox.showinfo(APP_TITLE, f"{status}。\n结果目录：\n{self.output_var.get()}")
        else:
            messagebox.showwarning(APP_TITLE, f"{status}，请查看处理日志。\n结果目录：\n{self.output_var.get()}")

    def open_output(self) -> None:
        path = Path(self.output_var.get().strip())
        if path.exists():
            import os
            os.startfile(path)
        else:
            messagebox.showinfo(APP_TITLE, "输出目录尚未创建；开始转换后会自动创建。")


if __name__ == "__main__":
    App().mainloop()

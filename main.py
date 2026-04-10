import os
import threading
import queue
import time
import json
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


class YouTubeDownloaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("YouTube Video/Audio Downloader")
        self.root.geometry("980x620")
        self.root.minsize(900, 560)

        self.ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.video_choices: dict[str, str] = {}
        self.audio_choices: dict[str, str] = {}
        self.filename_templates: dict[str, str] = {
            "Title (Clean)": "%(title)s",
            "Uploader - Title": "%(uploader)s - %(title)s",
            "UploadDate - Title": "%(upload_date>%Y-%m-%d)s - %(title)s",
            "Title [VideoID]": "%(title)s [%(id)s]",
        }
        self.history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_history.json")
        self.download_history: list[dict[str, str]] = []
        self.current_thread: threading.Thread | None = None
        self.pause_event = threading.Event()
        self.cancel_event = threading.Event()
        self.is_downloading = False

        self.url_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="video")
        self.save_path_var = tk.StringVar(value=os.path.expanduser("~"))
        self.quality_var = tk.StringVar()
        self.template_var = tk.StringVar(value="Title (Clean)")
        self.status_var = tk.StringVar(value="Ready")
        self.title_var = tk.StringVar(value="Title: -")

        self._build_ui()
        self._set_mode_defaults()
        self.root.after(120, self._process_ui_queue)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill="both", expand=True)

        top_pane = ttk.Panedwindow(container, orient="horizontal")
        top_pane.pack(fill="both", expand=True)

        left_panel = ttk.Frame(top_pane, padding=(0, 0, 10, 0))
        right_panel = ttk.Frame(top_pane)
        top_pane.add(left_panel, weight=3)
        top_pane.add(right_panel, weight=2)

        header = ttk.Label(
            left_panel,
            text="YouTube Downloader",
            font=("Segoe UI Semibold", 16),
        )
        header.pack(anchor="w")

        subheader = ttk.Label(
            left_panel,
            text="Download video or audio with selectable quality",
            foreground="#555",
        )
        subheader.pack(anchor="w", pady=(0, 12))

        url_frame = ttk.Frame(left_panel)
        url_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(url_frame, text="YouTube URL:").pack(anchor="w")
        url_input_row = ttk.Frame(url_frame)
        url_input_row.pack(fill="x", pady=(4, 0))

        self.url_entry = ttk.Entry(url_input_row, textvariable=self.url_var)
        self.url_entry.pack(side="left", fill="x", expand=True)

        self.fetch_button = ttk.Button(
            url_input_row,
            text="Fetch Qualities",
            command=self.fetch_qualities,
        )
        self.fetch_button.pack(side="left", padx=(8, 0))

        self.title_label = ttk.Label(left_panel, textvariable=self.title_var)
        self.title_label.pack(anchor="w", pady=(0, 10))

        mode_frame = ttk.LabelFrame(left_panel, text="Download Mode", padding=10)
        mode_frame.pack(fill="x", pady=(0, 10))

        ttk.Radiobutton(
            mode_frame,
            text="Video",
            variable=self.mode_var,
            value="video",
            command=self._on_mode_change,
        ).pack(side="left", padx=(0, 12))

        ttk.Radiobutton(
            mode_frame,
            text="Audio Only",
            variable=self.mode_var,
            value="audio",
            command=self._on_mode_change,
        ).pack(side="left")

        quality_frame = ttk.Frame(left_panel)
        quality_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(quality_frame, text="Quality:").pack(anchor="w")

        self.quality_combo = ttk.Combobox(
            quality_frame,
            textvariable=self.quality_var,
            state="readonly",
        )
        self.quality_combo.pack(fill="x", pady=(4, 0))

        template_frame = ttk.Frame(left_panel)
        template_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(template_frame, text="Filename Template (Auto-cleaned):").pack(anchor="w")

        self.template_combo = ttk.Combobox(
            template_frame,
            textvariable=self.template_var,
            values=list(self.filename_templates.keys()),
            state="readonly",
        )
        self.template_combo.pack(fill="x", pady=(4, 0))
        self.template_combo.current(0)

        save_frame = ttk.Frame(left_panel)
        save_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(save_frame, text="Save To:").pack(anchor="w")
        save_row = ttk.Frame(save_frame)
        save_row.pack(fill="x", pady=(4, 0))

        self.save_entry = ttk.Entry(save_row, textvariable=self.save_path_var)
        self.save_entry.pack(side="left", fill="x", expand=True)

        self.browse_button = ttk.Button(save_row, text="Browse", command=self.pick_folder)
        self.browse_button.pack(side="left", padx=(8, 0))

        action_frame = ttk.Frame(left_panel)
        action_frame.pack(fill="x", pady=(6, 8))

        self.download_button = ttk.Button(
            action_frame,
            text="Start Download",
            command=self.start_download,
        )
        self.download_button.pack(side="left")

        self.pause_button = ttk.Button(
            action_frame,
            text="Pause",
            command=self.toggle_pause,
            state="disabled",
        )
        self.pause_button.pack(side="left", padx=(8, 0))

        self.cancel_button = ttk.Button(
            action_frame,
            text="Cancel",
            command=self.cancel_download,
            state="disabled",
        )
        self.cancel_button.pack(side="left", padx=(8, 0))

        self.status_label = ttk.Label(action_frame, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=(12, 0))

        self.progress = ttk.Progressbar(left_panel, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(4, 10))

        log_frame = ttk.LabelFrame(left_panel, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=10, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

        history_frame = ttk.LabelFrame(right_panel, text="Download History", padding=10)
        history_frame.pack(fill="both", expand=True)

        history_columns = ("time", "mode", "quality", "status", "file")
        self.history_tree = ttk.Treeview(history_frame, columns=history_columns, show="headings", height=14)
        self.history_tree.heading("time", text="Time")
        self.history_tree.heading("mode", text="Mode")
        self.history_tree.heading("quality", text="Quality")
        self.history_tree.heading("status", text="Status")
        self.history_tree.heading("file", text="File")

        self.history_tree.column("time", width=150, anchor="w")
        self.history_tree.column("mode", width=80, anchor="center")
        self.history_tree.column("quality", width=120, anchor="w")
        self.history_tree.column("status", width=80, anchor="center")
        self.history_tree.column("file", width=280, anchor="w")
        self.history_tree.pack(side="left", fill="both", expand=True)

        history_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scroll.set)
        history_scroll.pack(side="right", fill="y")

        history_btn_frame = ttk.Frame(right_panel)
        history_btn_frame.pack(fill="x", pady=(8, 0))

        self.clear_history_button = ttk.Button(history_btn_frame, text="Clear History", command=self.clear_history)
        self.clear_history_button.pack(side="left")

        self._load_history()

    def _on_mode_change(self) -> None:
        self._set_mode_defaults()

    def _set_mode_defaults(self) -> None:
        if self.mode_var.get() == "video":
            options = list(self.video_choices.keys())
        else:
            options = list(self.audio_choices.keys())

        self.quality_combo["values"] = options
        if options:
            self.quality_combo.current(0)
            self.quality_var.set(options[0])
        else:
            self.quality_var.set("")

    def _log(self, message: str) -> None:
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.fetch_button.config(state=state)
        self.download_button.config(state=state)
        self.pause_button.config(state="normal" if busy else "disabled")
        self.cancel_button.config(state="normal" if busy else "disabled")

    def _load_history(self) -> None:
        if not os.path.exists(self.history_file):
            self.download_history = []
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as handle:
                self.download_history = json.load(handle)
        except Exception:
            self.download_history = []

        for item in self.download_history[-300:]:
            self.history_tree.insert(
                "",
                "end",
                values=(
                    item.get("time", "-"),
                    item.get("mode", "-"),
                    item.get("quality", "-"),
                    item.get("status", "-"),
                    item.get("file", "-"),
                ),
            )

    def _save_history(self) -> None:
        try:
            with open(self.history_file, "w", encoding="utf-8") as handle:
                json.dump(self.download_history[-500:], handle, indent=2, ensure_ascii=False)
        except Exception as exc:
            self._log(f"Failed to save history: {exc}")

    def _add_history(self, mode: str, quality: str, status: str, file_name: str) -> None:
        row = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "quality": quality,
            "status": status,
            "file": file_name,
        }
        self.download_history.append(row)
        self.history_tree.insert("", "end", values=(row["time"], row["mode"], row["quality"], row["status"], row["file"]))
        self._save_history()

    def clear_history(self) -> None:
        if not messagebox.askyesno("Confirm", "Clear all download history?"):
            return

        self.download_history.clear()
        for row_id in self.history_tree.get_children():
            self.history_tree.delete(row_id)
        self._save_history()
        self._log("History cleared.")

    def toggle_pause(self) -> None:
        if not self.is_downloading:
            return

        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.config(text="Pause")
            self.status_var.set("Downloading...")
            self._log("Download resumed.")
        else:
            self.pause_event.set()
            self.pause_button.config(text="Resume")
            self.status_var.set("Paused")
            self._log("Download paused.")

    def cancel_download(self) -> None:
        if not self.is_downloading:
            return

        self.cancel_event.set()
        self.pause_event.clear()
        self.pause_button.config(text="Pause")
        self.status_var.set("Canceling...")
        self._log("Cancel requested. Stopping current download...")

    def pick_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.save_path_var.get() or os.path.expanduser("~"))
        if folder:
            self.save_path_var.set(folder)

    def fetch_qualities(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a YouTube URL first.")
            return

        self._set_busy(True)
        self.status_var.set("Fetching quality options...")
        self._log("Fetching available qualities from YouTube...")

        thread = threading.Thread(target=self._fetch_qualities_worker, args=(url,), daemon=True)
        thread.start()

    def _fetch_qualities_worker(self, url: str) -> None:
        started = time.perf_counter()
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 15,
            "retries": 1,
            "fragment_retries": 1,
            "extractor_retries": 1,
            # IPv6 routing can be unstable on some networks; forcing IPv4 avoids long connect delays.
            "source_address": "0.0.0.0",
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if "entries" in info:
                entries = info.get("entries") or []
                if not entries:
                    raise RuntimeError("Playlist is empty.")
                info = entries[0]

            formats = info.get("formats", [])
            title = info.get("title", "Unknown title")

            video_choices: dict[str, str] = {}
            audio_choices: dict[str, str] = {}

            video_heights = sorted(
                {f.get("height") for f in formats if f.get("vcodec") != "none" and f.get("height")},
                reverse=True,
            )
            if video_heights:
                video_choices["Best available"] = "bestvideo+bestaudio/best"
                for height in video_heights:
                    label = f"{height}p"
                    selector = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
                    if label not in video_choices:
                        video_choices[label] = selector
            else:
                video_choices["Best available"] = "best"

            audio_abrs = sorted(
                {
                    int(round(float(f.get("abr"))))
                    for f in formats
                    if f.get("vcodec") == "none" and f.get("abr")
                },
                reverse=True,
            )
            audio_choices["Best available audio"] = "bestaudio"
            for abr in audio_abrs:
                label = f"~{abr} kbps"
                selector = f"bestaudio[abr<={abr}]/bestaudio"
                if label not in audio_choices:
                    audio_choices[label] = selector

            elapsed = time.perf_counter() - started
            self.ui_queue.put(("formats_loaded", {"title": title, "video": video_choices, "audio": audio_choices}))
            self.ui_queue.put(("log", f"Quality fetch finished in {elapsed:.1f}s."))
        except Exception as exc:
            elapsed = time.perf_counter() - started
            self.ui_queue.put(("error", f"Failed to fetch qualities after {elapsed:.1f}s: {exc}"))

    def start_download(self) -> None:
        url = self.url_var.get().strip()
        save_path = self.save_path_var.get().strip()
        mode = self.mode_var.get()
        selected_label = self.quality_var.get().strip()

        if not url:
            messagebox.showwarning("Missing URL", "Please enter a YouTube URL first.")
            return

        if not save_path:
            messagebox.showwarning("Missing Folder", "Please choose a destination folder.")
            return

        if not os.path.isdir(save_path):
            messagebox.showwarning("Invalid Folder", "The selected folder does not exist.")
            return

        choices = self.video_choices if mode == "video" else self.audio_choices
        if not choices:
            messagebox.showwarning(
                "No Qualities",
                "Please click 'Fetch Qualities' first to load available options.",
            )
            return

        if selected_label not in choices:
            messagebox.showwarning("No Quality Selected", "Please choose a quality option.")
            return

        format_selector = choices[selected_label]
        selected_template = self.template_var.get().strip()

        if selected_template not in self.filename_templates:
            messagebox.showwarning("Template Error", "Please choose a valid filename template.")
            return

        self.progress["value"] = 0
        self.pause_event.clear()
        self.cancel_event.clear()
        self.pause_button.config(text="Pause")
        self._set_busy(True)
        self.is_downloading = True
        self.status_var.set("Downloading...")
        self._log(f"Starting {mode} download with quality: {selected_label}")

        thread = threading.Thread(
            target=self._download_worker,
            args=(url, save_path, mode, selected_label, format_selector, selected_template),
            daemon=True,
        )
        self.current_thread = thread
        thread.start()

    def _download_worker(
        self,
        url: str,
        save_path: str,
        mode: str,
        selected_label: str,
        format_selector: str,
        selected_template: str,
    ) -> None:
        def progress_hook(data: dict) -> None:
            if self.cancel_event.is_set():
                raise DownloadError("Canceled by user.")

            while self.pause_event.is_set() and not self.cancel_event.is_set():
                time.sleep(0.2)

            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                downloaded = data.get("downloaded_bytes", 0)
                if total:
                    pct = max(0, min(100, (downloaded / total) * 100))
                    self.ui_queue.put(("progress", pct))
            elif status == "finished":
                self.ui_queue.put(("progress", 100))

        name_pattern = self.filename_templates[selected_template]
        output_template = os.path.join(save_path, f"{name_pattern}.%(ext)s")

        ydl_opts = {
            "outtmpl": output_template,
            "format": format_selector,
            "noplaylist": True,
            "progress_hooks": [progress_hook],
            "windowsfilenames": True,
            "restrictfilenames": True,
        }

        if mode == "audio":
            ydl_opts["format"] = format_selector

        downloaded_path = "-"

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_path = ydl.prepare_filename(info)
            self.ui_queue.put(
                (
                    "done",
                    {
                        "message": "Download completed successfully.",
                        "mode": mode,
                        "quality": selected_label,
                        "file": os.path.basename(downloaded_path),
                    },
                )
            )
        except DownloadError:
            if self.cancel_event.is_set():
                self.ui_queue.put(
                    (
                        "canceled",
                        {
                            "message": "Download canceled.",
                            "mode": mode,
                            "quality": selected_label,
                            "file": os.path.basename(downloaded_path) if downloaded_path != "-" else "-",
                        },
                    )
                )
            else:
                self.ui_queue.put(("error", f"Download failed."))
        except Exception as exc:
            self.ui_queue.put(("error", f"Download failed: {exc}"))

    def _process_ui_queue(self) -> None:
        while True:
            try:
                event, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            if event == "formats_loaded":
                data = payload if isinstance(payload, dict) else {}
                self.video_choices = data.get("video", {})
                self.audio_choices = data.get("audio", {})
                title = data.get("title", "Unknown title")
                self.title_var.set(f"Title: {title}")
                self._set_mode_defaults()
                self.status_var.set("Qualities loaded")
                self._log("Quality options loaded.")
                self._set_busy(False)

            elif event == "progress":
                value = float(payload) if payload is not None else 0.0
                self.progress["value"] = value

            elif event == "done":
                info = payload if isinstance(payload, dict) else {}
                self.status_var.set("Completed")
                self._log(str(info.get("message", "Download completed successfully.")))
                self._add_history(
                    str(info.get("mode", "-")),
                    str(info.get("quality", "-")),
                    "Done",
                    str(info.get("file", "-")),
                )
                self._set_busy(False)
                self.is_downloading = False
                messagebox.showinfo("Success", str(info.get("message", "Download completed successfully.")))

            elif event == "canceled":
                info = payload if isinstance(payload, dict) else {}
                self.status_var.set("Canceled")
                self.progress["value"] = 0
                self._log(str(info.get("message", "Download canceled.")))
                self._add_history(
                    str(info.get("mode", "-")),
                    str(info.get("quality", "-")),
                    "Canceled",
                    str(info.get("file", "-")),
                )
                self._set_busy(False)
                self.is_downloading = False

            elif event == "error":
                self.status_var.set("Error")
                self._log(str(payload))
                self._add_history(
                    self.mode_var.get(),
                    self.quality_var.get() or "-",
                    "Error",
                    "-",
                )
                self._set_busy(False)
                self.is_downloading = False
                messagebox.showerror("Error", str(payload))

            elif event == "log":
                self._log(str(payload))

        self.root.after(120, self._process_ui_queue)


def main() -> None:
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()

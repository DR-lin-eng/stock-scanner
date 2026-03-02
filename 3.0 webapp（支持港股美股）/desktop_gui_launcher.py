"""
股票分析系统桌面 GUI 启动器

功能：
- 启动/停止 Flask Web 服务
- 显示服务状态与实时日志
- GUI 内置配置中心（快速配置 + JSON 编辑）
- 一键打开 Web 页面
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable
from urllib import request

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk


IS_FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
SERVER_SCRIPT = APP_DIR / "flask_web_server.py"
DEFAULT_PORT = 5000
CONFIG_PATH = APP_DIR / "config.json"
SAMPLE_CONFIG_NAME = "config - 示例.json"
ALT_SAMPLE_CONFIG_NAME = "config_sample.json"


def _resolve_sample_config_path() -> Path:
    candidates = [
        APP_DIR / SAMPLE_CONFIG_NAME,
        APP_DIR / ALT_SAMPLE_CONFIG_NAME,
        BUNDLE_DIR / SAMPLE_CONFIG_NAME,
        BUNDLE_DIR / ALT_SAMPLE_CONFIG_NAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return APP_DIR / SAMPLE_CONFIG_NAME


SAMPLE_CONFIG_PATH = _resolve_sample_config_path()


def build_default_config() -> dict[str, Any]:
    """当示例文件缺失时使用的最小默认配置。"""
    return {
        "api_keys": {
            "openai": "",
            "anthropic": "",
            "zhipu": "",
            "siliconflow": "",
            "notes": "请填入您的API密钥",
        },
        "ai": {
            "model_preference": "openai",
            "models": {
                "openai": "gpt-4.1-nano",
                "anthropic": "claude-3-haiku-20240307",
                "zhipu": "chatglm_turbo",
                "siliconflow": "Qwen/Qwen2.5-7B-Instruct",
            },
            "max_tokens": 4000,
            "temperature": 0.7,
            "api_base_urls": {
                "openai": "https://api.openai.com/v1",
                "siliconflow": "https://api.siliconflow.cn/v1",
            },
            "json_mode": {
                "enabled": False,
                "provider": "siliconflow",
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "temperature": 0.2,
                "max_tokens": 1800,
                "max_news_items": 30,
            },
        },
        "analysis_weights": {"technical": 0.4, "fundamental": 0.4, "sentiment": 0.2},
        "analysis_params": {
            "max_news_count": 100,
            "technical_period_days": 365,
            "financial_indicators_count": 25,
            "main_prompt_news_max_items": 12,
            "main_prompt_news_max_chars": 1200,
        },
        "web_auth": {
            "enabled": False,
            "password": "",
            "session_timeout": 3600,
        },
        "_metadata": {
            "version": "desktop-gui-default",
            "description": "GUI自动生成的默认配置",
        },
    }


class DesktopLauncher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.process: subprocess.Popen[str] | None = None
        self.process_lock = threading.Lock()
        self.log_queue: Queue[str] = Queue()
        self.auto_open_var = tk.BooleanVar(value=True)
        self.status_text_var = tk.StringVar(value="服务状态：未启动")
        self._closing = False

        self.model_preference_var = tk.StringVar(value="openai")
        self.preferred_model_var = tk.StringVar(value="")
        self.preferred_api_base_url_var = tk.StringVar(value="")
        self.openai_key_var = tk.StringVar(value="")
        self.anthropic_key_var = tk.StringVar(value="")
        self.zhipu_key_var = tk.StringVar(value="")
        self.siliconflow_key_var = tk.StringVar(value="")
        self.web_auth_enabled_var = tk.BooleanVar(value=False)
        self.web_auth_password_var = tk.StringVar(value="")
        self.web_auth_timeout_var = tk.StringVar(value="3600")

        self._build_window()
        self._build_widgets()
        self._set_running_controls(False)
        self._poll_log_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.load_config_to_editor(create_if_missing=False)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{DEFAULT_PORT}"

    def _build_window(self) -> None:
        self.root.title("股票分析系统 - 桌面启动器")
        self.root.geometry("1080x720")
        self.root.minsize(860, 560)

    def _build_widgets(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)

        title_label = ttk.Label(
            container,
            text="股票分析桌面控制台",
            font=("Microsoft YaHei UI", 16, "bold"),
        )
        title_label.pack(anchor="w")

        self.status_label = tk.Label(
            container,
            textvariable=self.status_text_var,
            font=("Microsoft YaHei UI", 11, "bold"),
            fg="#C0392B",
            pady=6,
        )
        self.status_label.pack(anchor="w")

        control_frame = ttk.Frame(container)
        control_frame.pack(fill="x", pady=(4, 10))

        self.start_btn = ttk.Button(control_frame, text="启动服务", command=self.start_server)
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ttk.Button(control_frame, text="停止服务", command=self.stop_server)
        self.stop_btn.pack(side="left", padx=(0, 8))

        self.browser_btn = ttk.Button(control_frame, text="打开网页", command=self.open_browser)
        self.browser_btn.pack(side="left", padx=(0, 8))

        self.config_btn = ttk.Button(control_frame, text="配置中心", command=self.open_config_center)
        self.config_btn.pack(side="left", padx=(0, 8))

        self.clear_btn = ttk.Button(control_frame, text="清空日志", command=self.clear_logs)
        self.clear_btn.pack(side="left", padx=(0, 8))

        auto_open_check = ttk.Checkbutton(
            control_frame,
            text="服务就绪后自动打开网页",
            variable=self.auto_open_var,
        )
        auto_open_check.pack(side="right")

        info_label = ttk.Label(
            container,
            text=f"访问地址：{self.base_url}    配置文件：{CONFIG_PATH.name}    运行目录：{APP_DIR}",
            font=("Microsoft YaHei UI", 9),
        )
        info_label.pack(anchor="w", pady=(0, 8))

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)

        self.log_tab = ttk.Frame(self.notebook)
        self.config_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.log_tab, text="运行日志")
        self.notebook.add(self.config_tab, text="配置中心")

        self._build_log_tab()
        self._build_config_tab()

    def _build_log_tab(self) -> None:
        self.log_text = scrolledtext.ScrolledText(
            self.log_tab,
            wrap="word",
            height=24,
            font=("Consolas", 10),
            background="#111111",
            foreground="#E8E8E8",
            insertbackground="#FFFFFF",
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

    def _build_config_tab(self) -> None:
        wrapper = ttk.Frame(self.config_tab, padding=8)
        wrapper.pack(fill="both", expand=True)

        path_label = ttk.Label(
            wrapper,
            text=f"配置路径：{CONFIG_PATH}",
            font=("Microsoft YaHei UI", 9),
        )
        path_label.pack(anchor="w", pady=(0, 6))

        quick_group = ttk.LabelFrame(wrapper, text="快速配置（常用项）", padding=8)
        quick_group.pack(fill="x", pady=(0, 8))

        self._create_form_row(
            quick_group,
            0,
            "首选模型提供方",
            widget_type="combobox",
            variable=self.model_preference_var,
            values=["openai", "anthropic", "zhipu", "siliconflow"],
        )
        self._create_form_row(
            quick_group,
            1,
            "首选模型名称",
            widget_type="entry",
            variable=self.preferred_model_var,
        )
        self._create_form_row(
            quick_group,
            2,
            "首选提供方 API Base URL",
            widget_type="entry",
            variable=self.preferred_api_base_url_var,
        )
        self._create_form_row(
            quick_group,
            3,
            "OpenAI Key",
            widget_type="entry",
            variable=self.openai_key_var,
            show="*",
        )
        self._create_form_row(
            quick_group,
            4,
            "Anthropic Key",
            widget_type="entry",
            variable=self.anthropic_key_var,
            show="*",
        )
        self._create_form_row(
            quick_group,
            5,
            "智谱 Key",
            widget_type="entry",
            variable=self.zhipu_key_var,
            show="*",
        )
        self._create_form_row(
            quick_group,
            6,
            "SiliconFlow Key",
            widget_type="entry",
            variable=self.siliconflow_key_var,
            show="*",
        )

        auth_row = ttk.Frame(quick_group)
        auth_row.grid(row=7, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Checkbutton(auth_row, text="启用 Web 密码鉴权", variable=self.web_auth_enabled_var).pack(
            side="left"
        )
        ttk.Label(auth_row, text="密码").pack(side="left", padx=(16, 6))
        ttk.Entry(auth_row, textvariable=self.web_auth_password_var, width=20, show="*").pack(
            side="left"
        )
        ttk.Label(auth_row, text="超时(秒)").pack(side="left", padx=(16, 6))
        ttk.Entry(auth_row, textvariable=self.web_auth_timeout_var, width=10).pack(side="left")

        quick_btn_row = ttk.Frame(quick_group)
        quick_btn_row.grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(
            quick_btn_row,
            text="从 JSON 提取快速配置",
            command=self.extract_quick_config_from_editor,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            quick_btn_row,
            text="应用快速配置到 JSON",
            command=self.apply_quick_config_to_editor,
        ).pack(side="left")

        json_btn_row = ttk.Frame(wrapper)
        json_btn_row.pack(fill="x", pady=(0, 6))
        ttk.Button(json_btn_row, text="加载配置", command=self.reload_config).pack(side="left", padx=(0, 8))
        ttk.Button(json_btn_row, text="保存配置", command=self.save_config_from_editor).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(json_btn_row, text="格式化 JSON", command=self.format_editor_json).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(json_btn_row, text="从示例重置", command=self.reset_config_from_sample).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(json_btn_row, text="验证 JSON", command=self.validate_editor_json).pack(side="left")

        self.config_text = scrolledtext.ScrolledText(
            wrapper,
            wrap="none",
            height=20,
            font=("Consolas", 10),
            background="#0F172A",
            foreground="#E2E8F0",
            insertbackground="#FFFFFF",
        )
        self.config_text.pack(fill="both", expand=True)

    def _create_form_row(
        self,
        parent: ttk.LabelFrame,
        row: int,
        label_text: str,
        widget_type: str,
        variable: tk.Variable,
        values: list[str] | None = None,
        show: str | None = None,
    ) -> None:
        ttk.Label(parent, text=label_text, width=24).grid(row=row, column=0, sticky="w", pady=4)

        if widget_type == "combobox":
            widget = ttk.Combobox(parent, textvariable=variable, values=values or [], width=46)
            widget.state(["readonly"])
        else:
            kwargs: dict[str, Any] = {"textvariable": variable, "width": 68}
            if show is not None:
                kwargs["show"] = show
            widget = ttk.Entry(parent, **kwargs)

        widget.grid(row=row, column=1, sticky="ew", pady=4)
        parent.columnconfigure(1, weight=1)

    def _is_running(self) -> bool:
        with self.process_lock:
            return self.process is not None and self.process.poll() is None

    def _get_process(self) -> subprocess.Popen[str] | None:
        with self.process_lock:
            return self.process

    def _set_process(self, process: subprocess.Popen[str] | None) -> None:
        with self.process_lock:
            self.process = process

    def _safe_after(self, callback: Callable[[], None]) -> None:
        try:
            if self.root.winfo_exists():
                self.root.after(0, callback)
        except tk.TclError:
            pass

    def _set_status(self, text: str, color: str) -> None:
        self.status_text_var.set(text)
        self.status_label.configure(fg=color)

    def _set_running_controls(self, is_running: bool) -> None:
        self.start_btn.configure(state="disabled" if is_running else "normal")
        self.stop_btn.configure(state="normal" if is_running else "disabled")

    def _enqueue_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_log_queue(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except Empty:
                break
            self._append_log(line)

        if self.root.winfo_exists():
            self.root.after(120, self._poll_log_queue)

    def _build_server_command(self) -> list[str]:
        if IS_FROZEN:
            return [sys.executable, "--run-server"]
        return [sys.executable, str(SERVER_SCRIPT)]

    def start_server(self) -> None:
        if self._is_running():
            self._enqueue_log("启动请求忽略：服务已在运行。")
            return

        if not IS_FROZEN and not SERVER_SCRIPT.exists():
            messagebox.showerror("启动失败", f"未找到服务入口文件：{SERVER_SCRIPT.name}")
            return

        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONUNBUFFERED", "1")

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        cmd = self._build_server_command()
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(APP_DIR),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                creationflags=creationflags,
            )
        except Exception as exc:
            messagebox.showerror("启动失败", f"无法启动服务进程：{exc}")
            return

        self._set_process(process)
        self._set_running_controls(True)
        self._set_status("服务状态：启动中", "#D18A00")
        self._enqueue_log(f"正在启动服务：{' '.join(cmd)}")

        threading.Thread(target=self._read_process_output, args=(process,), daemon=True).start()
        threading.Thread(target=self._wait_for_ready, daemon=True).start()

    def stop_server(self) -> None:
        process = self._get_process()
        if process is None or process.poll() is not None:
            self._enqueue_log("停止请求忽略：服务未运行。")
            self._set_process(None)
            self._set_running_controls(False)
            self._set_status("服务状态：未启动", "#C0392B")
            return

        self._enqueue_log("正在停止服务...")
        threading.Thread(target=self._terminate_process, args=(process, False), daemon=True).start()

    def _wait_for_ready(self) -> None:
        max_attempts = 60
        for _ in range(max_attempts):
            if not self._is_running():
                return
            if self._health_check():
                self._enqueue_log("服务健康检查通过。")
                self._safe_after(lambda: self._set_status("服务状态：运行中", "#1F8B4C"))
                if self.auto_open_var.get():
                    self._safe_after(self.open_browser)
                return
            time.sleep(0.5)

        if self._is_running():
            self._enqueue_log("未能在 30 秒内完成健康检查，服务可能仍在启动中。")
            self._safe_after(lambda: self._set_status("服务状态：运行中（健康检查超时）", "#D18A00"))

    def _health_check(self) -> bool:
        status_url = f"{self.base_url}/api/status"
        try:
            with request.urlopen(status_url, timeout=2) as resp:
                if resp.status != 200:
                    return False
                payload_raw = resp.read().decode("utf-8", errors="ignore")
                if not payload_raw.strip():
                    return True
                payload = json.loads(payload_raw)
                return bool(payload.get("success", True))
        except Exception:
            return False

    def _read_process_output(self, process: subprocess.Popen[str]) -> None:
        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.rstrip()
                if line:
                    self._enqueue_log(line)

        return_code = process.wait()
        self._enqueue_log(f"服务进程已退出，返回码：{return_code}")
        self._safe_after(self._on_process_exit)

    def _terminate_process(self, process: subprocess.Popen[str], close_after: bool) -> None:
        try:
            process.terminate()
        except Exception as exc:
            self._enqueue_log(f"终止服务时发生异常：{exc}")

        try:
            process.wait(timeout=6)
        except subprocess.TimeoutExpired:
            self._enqueue_log("服务未在 6 秒内退出，执行强制结束。")
            try:
                process.kill()
                process.wait(timeout=2)
            except Exception as exc:
                self._enqueue_log(f"强制结束失败：{exc}")

        if close_after:
            self._safe_after(self.root.destroy)

    def _on_process_exit(self) -> None:
        proc = self._get_process()
        if proc is None or proc.poll() is not None:
            self._set_process(None)
            self._set_running_controls(False)
            if not self._closing:
                self._set_status("服务状态：未启动", "#C0392B")

    def open_browser(self) -> None:
        webbrowser.open(self.base_url)
        self._enqueue_log(f"已尝试打开浏览器：{self.base_url}")

    def open_config_center(self) -> None:
        self.notebook.select(self.config_tab)
        self.load_config_to_editor(create_if_missing=True)

    def clear_logs(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._enqueue_log("日志已清空。")

    def _ensure_runtime_config_exists(self) -> bool:
        if CONFIG_PATH.exists():
            return True

        try:
            if SAMPLE_CONFIG_PATH.exists():
                shutil.copyfile(SAMPLE_CONFIG_PATH, CONFIG_PATH)
                self._enqueue_log(f"检测到 {CONFIG_PATH.name} 不存在，已从示例创建。")
            else:
                with CONFIG_PATH.open("w", encoding="utf-8") as fp:
                    json.dump(build_default_config(), fp, ensure_ascii=False, indent=4)
                    fp.write("\n")
                self._enqueue_log(f"检测到示例配置缺失，已创建默认 {CONFIG_PATH.name}。")
            return True
        except Exception as exc:
            messagebox.showerror("配置初始化失败", f"无法创建 {CONFIG_PATH.name}：{exc}")
            return False

    def load_config_to_editor(self, create_if_missing: bool) -> None:
        if create_if_missing and not self._ensure_runtime_config_exists():
            return

        if not CONFIG_PATH.exists():
            self._set_editor_text("{}\n")
            self._enqueue_log(f"未找到 {CONFIG_PATH.name}，配置编辑器显示空对象。")
            return

        try:
            raw = CONFIG_PATH.read_text(encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("读取配置失败", f"无法读取 {CONFIG_PATH}：{exc}")
            return

        if not raw.strip():
            raw = "{}"

        self._set_editor_text(raw if raw.endswith("\n") else f"{raw}\n")
        self._enqueue_log(f"已加载配置文件：{CONFIG_PATH.name}")
        self.extract_quick_config_from_editor(show_message=False)

    def reload_config(self) -> None:
        self.load_config_to_editor(create_if_missing=True)

    def save_config_from_editor(self) -> None:
        try:
            data = self._get_editor_json()
        except ValueError as exc:
            messagebox.showerror("保存失败", str(exc))
            return

        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with CONFIG_PATH.open("w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=4)
                fp.write("\n")
        except Exception as exc:
            messagebox.showerror("保存失败", f"写入配置文件失败：{exc}")
            return

        self._set_editor_json(data)
        self._enqueue_log(f"配置已保存：{CONFIG_PATH.name}")
        messagebox.showinfo("保存成功", f"配置已保存到：\n{CONFIG_PATH}")

    def format_editor_json(self) -> None:
        try:
            data = self._get_editor_json()
        except ValueError as exc:
            messagebox.showerror("格式化失败", str(exc))
            return

        self._set_editor_json(data)
        self._enqueue_log("JSON 格式化完成。")

    def validate_editor_json(self) -> None:
        try:
            self._get_editor_json()
        except ValueError as exc:
            messagebox.showerror("JSON 校验失败", str(exc))
            return

        self._enqueue_log("JSON 校验通过。")
        messagebox.showinfo("校验通过", "当前 JSON 配置语法正确。")

    def reset_config_from_sample(self) -> None:
        if not SAMPLE_CONFIG_PATH.exists():
            messagebox.showerror(
                "重置失败",
                f"未找到示例配置文件：{SAMPLE_CONFIG_NAME} 或 {ALT_SAMPLE_CONFIG_NAME}",
            )
            return

        should_reset = messagebox.askyesno(
            "确认重置",
            "将用示例配置覆盖编辑器内容（未保存修改会丢失），是否继续？",
        )
        if not should_reset:
            return

        try:
            raw = SAMPLE_CONFIG_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception as exc:
            messagebox.showerror("重置失败", f"读取示例配置失败：{exc}")
            return

        self._set_editor_json(data)
        self.extract_quick_config_from_editor(show_message=False)
        self._enqueue_log("已从示例配置重置编辑器内容。")

    def extract_quick_config_from_editor(self, show_message: bool = True) -> None:
        try:
            data = self._get_editor_json()
        except ValueError as exc:
            messagebox.showerror("提取失败", str(exc))
            return

        self._update_quick_vars_from_data(data)
        self._enqueue_log("已从 JSON 提取快速配置。")
        if show_message:
            messagebox.showinfo("提取完成", "快速配置已根据 JSON 更新。")

    def apply_quick_config_to_editor(self) -> None:
        try:
            data = self._get_editor_json()
        except ValueError as exc:
            messagebox.showerror("应用失败", str(exc))
            return

        data_copy = copy.deepcopy(data)
        try:
            self._apply_quick_vars_to_data(data_copy)
        except ValueError as exc:
            messagebox.showerror("应用失败", str(exc))
            return

        self._set_editor_json(data_copy)
        self._enqueue_log("已将快速配置写入 JSON 编辑器。")
        messagebox.showinfo("应用完成", "快速配置已写入 JSON 编辑器（尚未保存到文件）。")

    def _set_editor_text(self, text: str) -> None:
        self.config_text.delete("1.0", "end")
        self.config_text.insert("1.0", text)

    def _set_editor_json(self, data: dict[str, Any]) -> None:
        formatted = json.dumps(data, ensure_ascii=False, indent=4)
        self._set_editor_text(f"{formatted}\n")

    def _get_editor_json(self) -> dict[str, Any]:
        raw = self.config_text.get("1.0", "end").strip()
        if not raw:
            raise ValueError("配置编辑器为空，请输入有效 JSON。")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 解析失败：第 {exc.lineno} 行, 第 {exc.colno} 列：{exc.msg}") from exc

        if not isinstance(data, dict):
            raise ValueError("配置根节点必须是 JSON 对象。")

        return data

    def _update_quick_vars_from_data(self, data: dict[str, Any]) -> None:
        api_keys = data.get("api_keys", {})
        ai = data.get("ai", {})
        models = ai.get("models", {})
        api_base_urls = ai.get("api_base_urls", {})
        web_auth = data.get("web_auth", {})

        provider = str(ai.get("model_preference", "openai") or "openai").strip()
        if provider not in {"openai", "anthropic", "zhipu", "siliconflow"}:
            provider = "openai"

        self.model_preference_var.set(provider)
        self.preferred_model_var.set(str(models.get(provider, "") or ""))
        self.preferred_api_base_url_var.set(str(api_base_urls.get(provider, "") or ""))

        self.openai_key_var.set(str(api_keys.get("openai", "") or ""))
        self.anthropic_key_var.set(str(api_keys.get("anthropic", "") or ""))
        self.zhipu_key_var.set(str(api_keys.get("zhipu", "") or ""))
        self.siliconflow_key_var.set(str(api_keys.get("siliconflow", "") or ""))

        self.web_auth_enabled_var.set(bool(web_auth.get("enabled", False)))
        self.web_auth_password_var.set(str(web_auth.get("password", "") or ""))
        self.web_auth_timeout_var.set(str(web_auth.get("session_timeout", 3600) or 3600))

    def _apply_quick_vars_to_data(self, data: dict[str, Any]) -> None:
        provider = self.model_preference_var.get().strip() or "openai"
        if provider not in {"openai", "anthropic", "zhipu", "siliconflow"}:
            raise ValueError("首选模型提供方无效，必须是 openai/anthropic/zhipu/siliconflow。")

        api_keys = data.setdefault("api_keys", {})
        if not isinstance(api_keys, dict):
            raise ValueError("当前 JSON 中 api_keys 不是对象，请先修正后重试。")
        api_keys["openai"] = self.openai_key_var.get().strip()
        api_keys["anthropic"] = self.anthropic_key_var.get().strip()
        api_keys["zhipu"] = self.zhipu_key_var.get().strip()
        api_keys["siliconflow"] = self.siliconflow_key_var.get().strip()

        ai = data.setdefault("ai", {})
        if not isinstance(ai, dict):
            raise ValueError("当前 JSON 中 ai 不是对象，请先修正后重试。")
        ai["model_preference"] = provider

        models = ai.setdefault("models", {})
        if not isinstance(models, dict):
            raise ValueError("当前 JSON 中 ai.models 不是对象，请先修正后重试。")
        model_name = self.preferred_model_var.get().strip()
        if model_name:
            models[provider] = model_name

        api_base_urls = ai.setdefault("api_base_urls", {})
        if not isinstance(api_base_urls, dict):
            raise ValueError("当前 JSON 中 ai.api_base_urls 不是对象，请先修正后重试。")
        api_base_url = self.preferred_api_base_url_var.get().strip()
        if api_base_url:
            api_base_urls[provider] = api_base_url

        web_auth = data.setdefault("web_auth", {})
        if not isinstance(web_auth, dict):
            raise ValueError("当前 JSON 中 web_auth 不是对象，请先修正后重试。")
        web_auth["enabled"] = bool(self.web_auth_enabled_var.get())
        web_auth["password"] = self.web_auth_password_var.get()

        timeout_text = self.web_auth_timeout_var.get().strip()
        try:
            timeout_val = int(timeout_text)
            if timeout_val <= 0:
                raise ValueError
        except ValueError as exc:
            raise ValueError("Web 鉴权会话超时必须是正整数（单位秒）。") from exc
        web_auth["session_timeout"] = timeout_val

    def _on_close(self) -> None:
        self._closing = True
        process = self._get_process()

        if process is not None and process.poll() is None:
            should_close = messagebox.askyesno(
                "确认退出",
                "服务仍在运行，是否先停止服务再退出？",
            )
            if not should_close:
                self._closing = False
                return

            self._enqueue_log("窗口关闭：准备停止服务并退出。")
            threading.Thread(target=self._terminate_process, args=(process, True), daemon=True).start()
            return

        self.root.destroy()


def run_server_mode() -> None:
    os.chdir(str(APP_DIR))

    # 确保日志输出实时刷新，便于 GUI 子进程读取。
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    try:
        from flask_web_server import main as flask_server_main
    except Exception:
        print("Failed to import flask_web_server.main. Traceback:")
        traceback.print_exc()
        return

    flask_server_main()


def run_gui_mode() -> None:
    root = tk.Tk()
    DesktopLauncher(root)
    root.mainloop()


def main() -> None:
    if "--run-server" in sys.argv[1:]:
        run_server_mode()
        return

    run_gui_mode()


if __name__ == "__main__":
    main()

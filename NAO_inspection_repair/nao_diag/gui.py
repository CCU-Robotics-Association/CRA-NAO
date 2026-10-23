# -*- coding: utf-8 -*-
"""
@ Project            : NAO 机器人验修工具箱
@ Description        : 机器人验修桌面界面
@ Author             : XCrane
"""
from __future__ import unicode_literals
import json
import os
import sys
import threading
import traceback
try:
    import Queue as queue
    import Tkinter as tk
    import tkFileDialog as filedialog
    import tkMessageBox as messagebox
    import tkSimpleDialog as simpledialog
    import ttk
except ImportError:
    import queue
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
from .compat import ensure_dir, json_safe, to_text
from .config import load_config
from .runner import list_tests, run_robot

PROFILE_LABELS = {
    "Quick": "quick",
    "Guided": "guided",
    "Full": "full",
}
LANGUAGE_LABELS = {
    "自动": "auto",
    "中文": "Chinese",
    "英文": "English",
}
STATUS_TEXT = {
    "PENDING": "等待",
    "RUNNING": "进行中",
    "PASS": "通过",
    "WARN": "警告",
    "FAIL": "失败",
    "SKIP": "未执行",
    "ERROR": "异常",
}
VERDICT_TEXT = {
    "ACCEPT": "通过",
    "ACCEPT_WITH_NOTES": "复核",
    "REJECT": "未通过",
}
DEFAULT_ROBOT_ID = "01"

def application_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def default_report_dir():
    if getattr(sys, "frozen", False):
        home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        documents = os.path.join(home, "Documents")
        return os.path.join(documents, "NAO_Reports")
    return os.path.join(application_dir(), "reports")

class GuiOptions(object):
    pass

class GuiBridge(object):

    def __init__(self, event_queue, cancel_event):
        self.event_queue = event_queue
        self.cancel_event = cancel_event

    def log(self, line):
        self.event_queue.put(("log", to_text(line)))

    def progress(self, event, payload):
        self.event_queue.put(("progress", (event, payload)))

    def prompt(self, kind, message, **details):
        if self.cancel_event.is_set():
            return False if kind in ("yes_no", "token") else None
        request = {
            "kind": kind,
            "message": to_text(message),
            "details": details,
            "ready": threading.Event(),
            "answer": None,
        }
        self.event_queue.put(("prompt", request))
        while not request["ready"].wait(0.10):
            if self.cancel_event.is_set():
                return False if kind in ("yes_no", "token") else None
        return request["answer"]


class NaoToolboxApp(object):
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.worker = None
        self.cancel_event = None
        self.running = False
        self.current_output_dir = None
        self.last_paths = None
        self.last_payload = None
        self.result_data = {}
        self.test_rows = []
        self.input_widgets = []
        self.browse_buttons = []
        self.active_test_id = None
        self.log_line_count = 0

        self.robot_id_var = tk.StringVar(value=DEFAULT_ROBOT_ID)
        self.ip_var = tk.StringVar(value="")
        self.port_var = tk.StringVar(value="9559")
        self.profile_var = tk.StringVar(value="Guided")
        self.voice_var = tk.BooleanVar(value=True)
        self.language_var = tk.StringVar(value="自动")
        self.verbose_var = tk.BooleanVar(value=False)
        self.collect_logs_var = tk.BooleanVar(value=False)
        self.allow_motion_var = tk.BooleanVar(value=False)
        self.allow_walk_var = tk.BooleanVar(value=False)
        self.output_var = tk.StringVar(value=default_report_dir())
        self.config_var = tk.StringVar(value="")
        self.ssh_user_var = tk.StringVar(value="nao")
        self.ssh_port_var = tk.StringVar(value="22")
        self.ssh_key_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="就绪")
        self.current_var = tk.StringVar(value="尚未开始检查")
        self.count_var = tk.StringVar(value="通过 0  警告 0  失败 0  未执行 0  异常 0")

        self._configure_window()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._build_main()
        self._refresh_tests()
        self._apply_profile_state()
        self._apply_log_fields_state()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._poll_events)

    def _configure_window(self):
        self.root.title("NAO 机器人验修工具箱")
        self.root.geometry("1200x820")
        self.root.minsize(960, 680)
        style = ttk.Style(self.root)
        themes = style.theme_names()
        if "vista" in themes:
            style.theme_use("vista")
        elif "xpnative" in themes:
            style.theme_use("xpnative")
        style.configure("TLabel", font=("Microsoft YaHei UI", 9))
        style.configure("TButton", font=("Microsoft YaHei UI", 9))
        style.configure("TCheckbutton", font=("Microsoft YaHei UI", 9))
        style.configure("TLabelframe.Label", font=("Microsoft YaHei UI", 9))
        style.configure("Treeview", font=("Microsoft YaHei UI", 9), rowheight=23)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9))

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="打开报告目录", command=self.open_output_folder)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件(F)", menu=file_menu)

        tool_menu = tk.Menu(menubar, tearoff=False)
        tool_menu.add_command(label="选择全部项目", command=self.select_all_tests)
        tool_menu.add_command(label="清除项目选择", command=self.clear_test_selection)
        tool_menu.add_separator()
        tool_menu.add_command(label="清空日志显示", command=self.clear_log)
        menubar.add_cascade(label="工具(U)", menu=tool_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助(H)", menu=help_menu)
        self.root.configure(menu=menubar)

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(6, 5))
        bar.pack(side=tk.TOP, fill=tk.X)
        self.connect_button = ttk.Button(
            bar, text="测试连接", width=11, command=self.start_connection_test)
        self.connect_button.pack(side=tk.LEFT, padx=(0, 4))
        self.start_button = ttk.Button(
            bar, text="开始检查", width=11, command=self.start_run)
        self.start_button.pack(side=tk.LEFT, padx=(0, 4))
        self.stop_button = ttk.Button(
            bar, text="停止后续项目", width=13, command=self.request_stop,
            state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 12))
        self.report_button = ttk.Button(
            bar, text="打开最近报告", width=13, command=self.open_report,
            state=tk.DISABLED)
        self.report_button.pack(side=tk.LEFT, padx=(0, 4))
        self.folder_button = ttk.Button(
            bar, text="打开输出目录", width=13, command=self.open_output_folder)
        self.folder_button.pack(side=tk.LEFT, padx=(0, 4))

    def _build_main(self):
        pane = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 5))
        left = ttk.Frame(pane, width=360)
        right = ttk.Frame(pane)
        pane.add(left, weight=0)
        pane.add(right, weight=1)
        self._build_left(left)
        self._build_right(right)

        def place_sash():
            try:
                pane.sashpos(0, 385)
            except (AttributeError, tk.TclError):
                pass

        self.root.after_idle(place_sash)

    def _entry_row(self, parent, row, label, variable, width=24, browse=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=6, pady=3)
        entry = ttk.Entry(parent, textvariable=variable, width=width)
        entry.grid(row=row, column=1, sticky=tk.EW, padx=(2, 4), pady=3)
        self.input_widgets.append(entry)
        if browse is not None:
            button = ttk.Button(parent, text="浏览...", width=7, command=browse)
            button.grid(row=row, column=2, padx=(0, 6), pady=3)
            self.browse_buttons.append(button)
        return entry

    def _build_left(self, parent):
        parent.columnconfigure(0, weight=1)

        robot_box = ttk.LabelFrame(parent, text="机器人信息", padding=(4, 4))
        robot_box.grid(row=0, column=0, sticky=tk.EW, padx=(0, 6), pady=(0, 5))
        robot_box.columnconfigure(1, weight=1)
        self._entry_row(robot_box, 0, "机器人编号", self.robot_id_var)
        self._entry_row(robot_box, 1, "IP 地址", self.ip_var)
        self._entry_row(robot_box, 2, "NAOqi 端口", self.port_var)

        options = ttk.LabelFrame(parent, text="检查设置", padding=(4, 4))
        options.grid(row=1, column=0, sticky=tk.EW, padx=(0, 6), pady=(0, 5))
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="验收模式").grid(row=0, column=0, sticky=tk.W, padx=6, pady=3)
        self.profile_combo = ttk.Combobox(
            options, textvariable=self.profile_var, state="readonly",
            values=("Quick", "Guided", "Full"), width=21)
        self.profile_combo.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=(2, 6), pady=3)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_changed)
        self.input_widgets.append(self.profile_combo)

        ttk.Label(options, text="播报语言").grid(row=1, column=0, sticky=tk.W, padx=6, pady=3)
        self.language_combo = ttk.Combobox(
            options, textvariable=self.language_var, state="readonly",
            values=("自动", "中文", "英文"), width=21)
        self.language_combo.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=(2, 6), pady=3)
        self.input_widgets.append(self.language_combo)

        checks = ttk.Frame(options)
        checks.grid(row=2, column=0, columnspan=3, sticky=tk.EW, padx=4, pady=(3, 1))
        self.voice_check = ttk.Checkbutton(checks, text="通过后语音播报", variable=self.voice_var)
        self.voice_check.grid(row=0, column=0, sticky=tk.W, padx=2)
        self.verbose_check = ttk.Checkbutton(checks, text="详细日志", variable=self.verbose_var)
        self.verbose_check.grid(row=0, column=1, sticky=tk.W, padx=8)
        self.logs_check = ttk.Checkbutton(
            checks, text="采集系统日志", variable=self.collect_logs_var,
            command=self._on_log_option_changed)
        self.logs_check.grid(row=1, column=0, sticky=tk.W, padx=2, pady=2)
        self.motion_check = ttk.Checkbutton(
            checks, text="允许关节动作", variable=self.allow_motion_var,
            command=self._on_motion_changed)
        self.motion_check.grid(row=2, column=0, sticky=tk.W, padx=2, pady=2)
        self.walk_check = ttk.Checkbutton(
            checks, text="允许短距离行走", variable=self.allow_walk_var,
            command=self._on_walk_changed)
        self.walk_check.grid(row=2, column=1, sticky=tk.W, padx=8, pady=2)
        self.input_widgets.extend([
            self.voice_check, self.verbose_check, self.logs_check,
            self.motion_check, self.walk_check,
        ])

        paths = ttk.LabelFrame(parent, text="报告与日志", padding=(4, 4))
        paths.grid(row=2, column=0, sticky=tk.EW, padx=(0, 6), pady=(0, 5))
        paths.columnconfigure(1, weight=1)
        self._entry_row(paths, 0, "报告目录", self.output_var, browse=self._browse_output)
        self._entry_row(paths, 1, "配置 JSON", self.config_var, browse=self._browse_config)
        self._entry_row(paths, 2, "SSH 私钥", self.ssh_key_var, browse=self._browse_ssh_key)
        ttk.Label(paths, text="SSH 用户").grid(row=3, column=0, sticky=tk.W, padx=6, pady=3)
        ssh_line = ttk.Frame(paths)
        ssh_line.grid(row=3, column=1, columnspan=2, sticky=tk.EW, padx=(2, 6), pady=3)
        ssh_line.columnconfigure(0, weight=1)
        ssh_user = ttk.Entry(ssh_line, textvariable=self.ssh_user_var, width=13)
        ssh_user.grid(row=0, column=0, sticky=tk.EW)
        ttk.Label(ssh_line, text=" 端口 ").grid(row=0, column=1)
        ssh_port = ttk.Entry(ssh_line, textvariable=self.ssh_port_var, width=6)
        ssh_port.grid(row=0, column=2)
        self.input_widgets.extend([ssh_user, ssh_port])
        self.ssh_field_widgets = paths.grid_slaves(row=2) + paths.grid_slaves(row=3)

        test_box = ttk.LabelFrame(parent, text="验收项目（可多选）", padding=(4, 4))
        test_box.grid(row=3, column=0, sticky=tk.NSEW, padx=(0, 6))
        test_box.rowconfigure(0, weight=1)
        test_box.columnconfigure(0, weight=1)
        list_frame = ttk.Frame(test_box)
        list_frame.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.test_list = tk.Listbox(
            list_frame, selectmode=tk.EXTENDED, exportselection=False,
            font=("Microsoft YaHei UI", 9), relief=tk.SUNKEN, borderwidth=1)
        test_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.test_list.yview)
        self.test_list.configure(yscrollcommand=test_scroll.set)
        self.test_list.grid(row=0, column=0, sticky=tk.NSEW)
        test_scroll.grid(row=0, column=1, sticky=tk.NS)
        buttons = ttk.Frame(test_box)
        buttons.grid(row=1, column=0, sticky=tk.W, pady=(4, 0))
        self.select_all_button = ttk.Button(buttons, text="全选", width=7, command=self.select_all_tests)
        self.select_all_button.pack(side=tk.LEFT, padx=(0, 3))
        self.clear_selection_button = ttk.Button(buttons, text="清除", width=7, command=self.clear_test_selection)
        self.clear_selection_button.pack(side=tk.LEFT)
        self.input_widgets.extend([self.test_list, self.select_all_button, self.clear_selection_button])
        parent.rowconfigure(3, weight=1)

    def _build_right(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        result_box = ttk.LabelFrame(parent, text="验收结果", padding=(5, 5))
        result_box.grid(row=0, column=0, sticky=tk.NSEW, pady=(0, 5))
        result_box.columnconfigure(0, weight=1)
        result_box.rowconfigure(2, weight=1)
        info = ttk.Frame(result_box)
        info.grid(row=0, column=0, sticky=tk.EW, pady=(0, 4))
        info.columnconfigure(0, weight=1)
        ttk.Label(info, textvariable=self.current_var).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(info, textvariable=self.count_var).grid(row=1, column=0, sticky=tk.W)
        self.progress = ttk.Progressbar(result_box, orient=tk.HORIZONTAL, mode="determinate")
        self.progress.grid(row=1, column=0, sticky=tk.EW, pady=(0, 5))

        tree_frame = ttk.Frame(result_box)
        tree_frame.grid(row=2, column=0, sticky=tk.NSEW)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        columns = ("status", "label", "summary", "duration")
        self.result_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        self.result_tree.heading("status", text="状态")
        self.result_tree.heading("label", text="测试项目")
        self.result_tree.heading("summary", text="结果摘要")
        self.result_tree.heading("duration", text="耗时")
        self.result_tree.column("status", width=82, minwidth=76, anchor=tk.CENTER, stretch=False)
        self.result_tree.column("label", width=170, minwidth=125, stretch=False)
        self.result_tree.column("summary", width=320, minwidth=180)
        self.result_tree.column("duration", width=70, minwidth=62, anchor=tk.E, stretch=False)
        tree_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        tree_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.result_tree.xview)
        self.result_tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        self.result_tree.grid(row=0, column=0, sticky=tk.NSEW)
        tree_y.grid(row=0, column=1, sticky=tk.NS)
        tree_x.grid(row=1, column=0, sticky=tk.EW)
        self.result_tree.tag_configure("PASS", foreground="#176b32")
        self.result_tree.tag_configure("WARN", foreground="#8a5b00")
        self.result_tree.tag_configure("FAIL", foreground="#a51d19")
        self.result_tree.tag_configure("ERROR", foreground="#8b1a52")
        self.result_tree.tag_configure("SKIP", foreground="#666666")
        self.result_tree.tag_configure("RUNNING", foreground="#005a9e")
        self.result_tree.bind("<Double-1>", self._show_result_details)

        log_box = ttk.LabelFrame(parent, text="运行日志", padding=(5, 5))
        log_box.grid(row=1, column=0, sticky=tk.NSEW)
        log_box.rowconfigure(0, weight=1)
        log_box.columnconfigure(0, weight=1)
        self.log_text = tk.Text(
            log_box, wrap=tk.NONE, state=tk.DISABLED, relief=tk.SUNKEN,
            borderwidth=1, background="white", font=("Consolas", 9))
        log_y = ttk.Scrollbar(log_box, orient=tk.VERTICAL, command=self.log_text.yview)
        log_x = ttk.Scrollbar(log_box, orient=tk.HORIZONTAL, command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=log_y.set, xscrollcommand=log_x.set)
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW)
        log_y.grid(row=0, column=1, sticky=tk.NS)
        log_x.grid(row=1, column=0, sticky=tk.EW)
        action_line = ttk.Frame(log_box)
        action_line.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(4, 0))
        ttk.Button(action_line, text="清空显示", width=9, command=self.clear_log).pack(side=tk.RIGHT)

    def _build_statusbar(self):
        bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(5, 2))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(bar, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Label(bar, text="紧急情况请现场扶稳机器人并按流程断电",
                  foreground="#9b1c1c").pack(side=tk.RIGHT)

    def _profile(self):
        return PROFILE_LABELS.get(self.profile_var.get(), "guided")

    def _on_profile_changed(self, _event=None):
        self._apply_profile_state()
        self._refresh_tests()

    def _switch_to_full_profile(self):
        if self._profile() == "full":
            return
        self.profile_var.set("Full")
        self._refresh_tests()

    def _apply_profile_state(self):
        full = self._profile() == "full"
        if not full:
            self.allow_motion_var.set(False)
            self.allow_walk_var.set(False)
        if not self.running:
            self.motion_check.configure(state=tk.NORMAL)
            self.walk_check.configure(state=tk.NORMAL)

    def _on_motion_changed(self):
        if self.allow_motion_var.get():
            self._switch_to_full_profile()
        else:
            self.allow_walk_var.set(False)

    def _on_walk_changed(self):
        if self.allow_walk_var.get():
            self._switch_to_full_profile()
            self.allow_motion_var.set(True)
            messagebox.showwarning(
                "安全警告",
                "行走测试需要在平整防滑且有人看护的场地进行。\n\n",
                parent=self.root,
            )

    def _on_log_option_changed(self):
        self._apply_log_fields_state()
        self._refresh_tests()

    def _apply_log_fields_state(self):
        show = bool(self.collect_logs_var.get())
        for widget in getattr(self, "ssh_field_widgets", []):
            if show:
                widget.grid()
            else:
                widget.grid_remove()

    def _refresh_tests(self):
        self.test_list.configure(state=tk.NORMAL)
        self.test_list.delete(0, tk.END)
        self.test_rows = []
        for test_id, label, _function, _profiles in list_tests(self._profile()):
            if test_id == "logs" and not self.collect_logs_var.get():
                continue
            self.test_rows.append((test_id, label))
            self.test_list.insert(tk.END, "%-17s %s" % (test_id, label))
        self.select_all_tests()
        if self.running:
            self.test_list.configure(state=tk.DISABLED)

    def select_all_tests(self):
        if str(self.test_list.cget("state")) != str(tk.DISABLED):
            self.test_list.selection_set(0, tk.END)

    def clear_test_selection(self):
        if str(self.test_list.cget("state")) != str(tk.DISABLED):
            self.test_list.selection_clear(0, tk.END)

    def _selected_test_ids(self):
        return [self.test_rows[int(index)][0] for index in self.test_list.curselection()]

    def _browse_output(self):
        chosen = filedialog.askdirectory(
            parent=self.root, title="选择报告目录", initialdir=self.output_var.get() or application_dir())
        if chosen:
            self.output_var.set(chosen)

    def _browse_config(self):
        chosen = filedialog.askopenfilename(
            parent=self.root, title="选择配置 JSON",
            filetypes=(("JSON 配置", "*.json"), ("所有文件", "*.*")))
        if chosen:
            self.config_var.set(chosen)

    def _browse_ssh_key(self):
        chosen = filedialog.askopenfilename(parent=self.root, title="选择 SSH 私钥")
        if chosen:
            self.ssh_key_var.set(chosen)

    def _validated_inputs(self, connection_only=False):
        ip = to_text(self.ip_var.get()).strip()
        if not ip:
            raise ValueError("请输入机器人的 IP 地址")
        try:
            port = int(self.port_var.get())
        except (TypeError, ValueError):
            raise ValueError("NAOqi 端口必须是数字")
        if port < 1 or port > 65535:
            raise ValueError("NAOqi 端口必须在 1 到 65535 之间")
        collect_logs = bool(self.collect_logs_var.get()) and not connection_only
        ssh_port = 22
        if collect_logs:
            try:
                ssh_port = int(self.ssh_port_var.get())
            except (TypeError, ValueError):
                raise ValueError("SSH 端口必须是数字")
            if not 1 <= ssh_port <= 65535:
                raise ValueError("SSH 端口必须在 1 到 65535 之间")
        config_path = to_text(self.config_var.get()).strip() or None
        if config_path and not os.path.isfile(config_path):
            raise ValueError("配置文件不存在：%s" % config_path)
        ssh_key = (to_text(self.ssh_key_var.get()).strip() or None) if collect_logs else None
        if ssh_key and not os.path.isfile(ssh_key):
            raise ValueError("SSH 私钥不存在：%s" % ssh_key)
        output = os.path.abspath(to_text(self.output_var.get()).strip() or "reports")
        ensure_dir(output)
        selected = ["connection"] if connection_only else self._selected_test_ids()
        if not selected:
            raise ValueError("请至少选择一个测试项目")

        options = GuiOptions()
        options.config = load_config(config_path)
        options.profile = self._profile()
        options.port = port
        options.output = output
        options.interactive = options.profile in ("guided", "full") and not connection_only
        options.voice = bool(self.voice_var.get())
        options.language = LANGUAGE_LABELS.get(self.language_var.get(), "auto")
        options.allow_motion = bool(self.allow_motion_var.get())
        options.allow_walk = bool(self.allow_walk_var.get())
        options.assume_yes = False
        options.only = ",".join(selected)
        options.skip = ""
        options.collect_logs = collect_logs
        options.ssh_user = to_text(self.ssh_user_var.get()).strip() or "nao"
        options.ssh_port = ssh_port
        options.ssh_key = ssh_key
        options.log_dir = []
        options.verbose = bool(self.verbose_var.get())
        robot = {
            "robot_id": to_text(self.robot_id_var.get()).strip() or DEFAULT_ROBOT_ID,
            "ip": ip,
            "port": port,
            "notes": "GUI",
        }
        return robot, options, selected

    def start_connection_test(self):
        self._start_run(connection_only=True)

    def start_run(self):
        self._start_run(connection_only=False)

    def _start_run(self, connection_only=False):
        if self.running:
            return
        try:
            robot, options, selected = self._validated_inputs(connection_only)
        except Exception as exc:
            messagebox.showerror("无法开始", to_text(exc), parent=self.root)
            return
        self.cancel_event = threading.Event()
        bridge = GuiBridge(self.events, self.cancel_event)
        options.cancel_event = self.cancel_event
        options.event_sink = bridge.log
        options.progress_callback = bridge.progress
        options.prompt_handler = bridge.prompt
        self.last_paths = None
        self.last_payload = None
        self.current_output_dir = None
        self.active_test_id = None
        self.result_data = {}
        self.report_button.configure(state=tk.DISABLED)
        self._prepare_result_rows(selected)
        self.clear_log()
        self._append_log("准备连接 %s (%s:%d)" % (robot["robot_id"], robot["ip"], robot["port"]))
        self._set_running(True)
        self.current_var.set("正在启动检查...")
        self.status_var.set("正在连接机器人")
        self.worker = threading.Thread(
            target=self._run_worker, args=(robot, options))
        self.worker.daemon = True
        try:
            self.worker.start()
        except Exception as exc:
            self._handle_error({
                "message": "无法启动后台检查线程：%s" % to_text(exc),
                "traceback": traceback.format_exc(),
            })

    def _run_worker(self, robot, options):
        try:
            try:
                import naoqi  # noqa: F401
            except ImportError as exc:
                raise RuntimeError(
                    "无法导入 pynaoqi：%s。请通过 run_gui.bat 启动，或重新构建包含 SDK 的 EXE。" %
                    to_text(exc))
            payload, paths = run_robot(robot, options.config, options)
            self.events.put(("done", (payload, paths)))
        except Exception as exc:
            self.events.put(("error", {
                "message": to_text(exc),
                "traceback": traceback.format_exc(),
            }))

    def _prepare_result_rows(self, selected):
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        label_by_id = dict((item[0], item[1]) for item in self.test_rows)
        self.progress.configure(maximum=max(len(selected), 1), value=0)
        for test_id in selected:
            self.result_tree.insert(
                "", tk.END, iid=test_id,
                values=(STATUS_TEXT["PENDING"], label_by_id.get(test_id, test_id),
                        "等待执行", ""),
                tags=("PENDING",))
        self._update_counts()

    def _set_running(self, running):
        self.running = bool(running)
        self.connect_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.start_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_button.configure(state=tk.NORMAL if running else tk.DISABLED)
        for widget in self.input_widgets + self.browse_buttons:
            try:
                widget.configure(state=tk.DISABLED if running else tk.NORMAL)
            except tk.TclError:
                pass
        if not running:
            self.profile_combo.configure(state="readonly")
            self.language_combo.configure(state="readonly")
            self._apply_profile_state()

    def request_stop(self):
        if not self.running or self.cancel_event is None:
            return
        if self.cancel_event.is_set():
            return
        self.cancel_event.set()
        self.stop_button.configure(state=tk.DISABLED)
        self.status_var.set("已请求停止；等待当前项目安全结束")
        self._append_log("已请求停止，当前项目结束后退出。")

    def _poll_events(self):
        processed = 0
        try:
            while processed < 200:
                try:
                    event, payload = self.events.get_nowait()
                except queue.Empty:
                    break
                processed += 1
                try:
                    if event == "log":
                        self._append_log(payload)
                    elif event == "progress":
                        self._handle_progress(payload[0], payload[1])
                    elif event == "prompt":
                        self._handle_prompt(payload)
                    elif event == "done":
                        self._handle_done(payload[0], payload[1])
                    elif event == "error":
                        self._handle_error(payload)
                except Exception:
                    self._append_log("事件处理异常：\n%s" % traceback.format_exc())
        finally:
            try:
                if self.root.winfo_exists():
                    self.root.after(1 if processed >= 200 else 80, self._poll_events)
            except tk.TclError:
                pass

    def _handle_progress(self, event, payload):
        if event == "run_started":
            self.current_output_dir = payload.get("output_dir")
            self.progress.configure(maximum=max(int(payload.get("total", 1)), 1))
        elif event == "test_started":
            test_id = payload.get("test_id")
            self.active_test_id = test_id
            label = payload.get("label", test_id)
            self.current_var.set("正在检查：%s" % label)
            self.status_var.set("第 %s / %s 项" % (
                payload.get("index", 0), payload.get("total", 0)))
            self._set_tree_status(test_id, "RUNNING", label, "正在检查...", "")
            self.result_tree.see(test_id)
        elif event == "test_finished":
            result = payload.get("result", {})
            self._show_result(result)
            if result.get("id") == self.active_test_id:
                self.active_test_id = None
            self.progress.configure(value=int(payload.get("index", 0)))
        elif event == "run_cancelled":
            self.current_var.set("已停止后续项目，正在生成部分报告...")
        elif event == "run_finished":
            self.current_var.set("正在整理报告...")
        elif event == "run_error":
            self.status_var.set("运行发生异常")

    def _set_tree_status(self, test_id, status, label, summary, duration):
        status_value = STATUS_TEXT.get(status, status)
        values = (status_value, label, to_text(summary), duration)
        if self.result_tree.exists(test_id):
            self.result_tree.item(test_id, values=values, tags=(status,))
        else:
            self.result_tree.insert("", tk.END, iid=test_id, values=values, tags=(status,))

    def _show_result(self, result):
        test_id = result.get("id", "unknown")
        self.result_data[test_id] = result
        duration = "%d ms" % int(result.get("duration_ms", 0))
        self._set_tree_status(
            test_id, result.get("status", "ERROR"), result.get("label", test_id),
            result.get("summary", ""), duration)
        self._update_counts()

    def _update_counts(self):
        counts = dict((key, 0) for key in ("PASS", "WARN", "FAIL", "SKIP", "ERROR"))
        for result in self.result_data.values():
            status = result.get("status")
            if status in counts:
                counts[status] += 1
        self.count_var.set("通过 %(PASS)d  警告 %(WARN)d  失败 %(FAIL)d  未执行 %(SKIP)d  异常 %(ERROR)d" % counts)

    def _handle_prompt(self, request):
        if self.cancel_event is not None and self.cancel_event.is_set():
            request["answer"] = False
            request["ready"].set()
            return
        kind = request.get("kind")
        message = request.get("message", "")
        details = request.get("details", {})
        try:
            if kind == "yes_no":
                answer = self._ask_operator_confirmation(message)
            elif kind == "continue":
                answer = self._ask_continue(message)
            elif kind == "token":
                token = to_text(details.get("token", ""))
                answer = self._ask_token(message, token)
            else:
                answer = simpledialog.askstring("需要输入", message, parent=self.root)
            request["answer"] = answer
        except Exception as exc:
            request["answer"] = False
            self._append_log("人工确认窗口异常：%s" % to_text(exc))
        finally:
            request["ready"].set()

    def _ask_operator_confirmation(self, message):
        answer = {"value": False}
        window = tk.Toplevel(self.root)
        window.title("人工检查确认")
        window.resizable(False, False)
        window.transient(self.root)
        body = ttk.Frame(window, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Message(
            body, text=message, width=520, font=("Microsoft YaHei UI", 9),
            background=self.root.cget("background"), justify=tk.LEFT).pack(
                fill=tk.X, pady=(0, 10))

        if "camera_top.bmp" in message or "camera_bottom.bmp" in message:
            image_line = ttk.Frame(body)
            image_line.pack(fill=tk.X, pady=(0, 10))
            artifact_dir = os.path.join(self.current_output_dir or "", "artifacts")
            top_path = os.path.join(artifact_dir, "camera_top.bmp")
            bottom_path = os.path.join(artifact_dir, "camera_bottom.bmp")
            top_button = ttk.Button(
                image_line, text="查看上摄像头图片",
                command=lambda: self._open_path(top_path))
            top_button.pack(side=tk.LEFT, padx=(0, 5))
            bottom_button = ttk.Button(
                image_line, text="查看下摄像头图片",
                command=lambda: self._open_path(bottom_path))
            bottom_button.pack(side=tk.LEFT)
            if not os.path.isfile(top_path):
                top_button.configure(state=tk.DISABLED)
            if not os.path.isfile(bottom_path):
                bottom_button.configure(state=tk.DISABLED)

        buttons = ttk.Frame(body)
        buttons.pack(fill=tk.X)

        def finish(value):
            answer["value"] = bool(value)
            window.destroy()

        ttk.Button(buttons, text="正常", width=11,
                   command=lambda: finish(True)).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(buttons, text="异常", width=11,
                   command=lambda: finish(False)).pack(side=tk.RIGHT)
        ttk.Button(
            buttons, text="停止后续项目", width=13,
            command=lambda: (self.request_stop(), finish(False))).pack(side=tk.LEFT)
        window.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        self._show_modal(window)
        return answer["value"]

    def _ask_continue(self, message):
        answer = {"value": False}
        window = tk.Toplevel(self.root)
        window.title("现场操作")
        window.resizable(False, False)
        window.transient(self.root)
        body = ttk.Frame(window, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Message(
            body, text=message + "\n\n操作完成后点击“继续”。", width=520,
            font=("Microsoft YaHei UI", 9), background=self.root.cget("background"),
            justify=tk.LEFT).pack(fill=tk.X, pady=(0, 10))
        buttons = ttk.Frame(body)
        buttons.pack(fill=tk.X)

        def finish(value, stop=False):
            if stop:
                self.request_stop()
            answer["value"] = bool(value)
            window.destroy()

        ttk.Button(buttons, text="继续", width=11,
                   command=lambda: finish(True)).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="停止后续项目", width=13,
                   command=lambda: finish(False, True)).pack(side=tk.LEFT)
        window.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        self._show_modal(window)
        return answer["value"]

    def _ask_token(self, message, token):
        answer = {"value": ""}
        window = tk.Toplevel(self.root)
        window.title("运动安全确认")
        window.resizable(False, False)
        window.transient(self.root)
        body = ttk.Frame(window, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Message(
            body, text=message, width=560, font=("Microsoft YaHei UI", 9),
            background=self.root.cget("background"), justify=tk.LEFT).pack(
                fill=tk.X, pady=(0, 8))
        ttk.Label(body, text="请输入安全口令：%s" % token).pack(anchor=tk.W)
        value = tk.StringVar()
        entry = ttk.Entry(body, textvariable=value, width=34)
        entry.pack(fill=tk.X, pady=(3, 10))
        buttons = ttk.Frame(body)
        buttons.pack(fill=tk.X)

        def finish(result="", stop=False):
            if stop:
                self.request_stop()
            answer["value"] = to_text(result or "")
            window.destroy()

        ttk.Button(buttons, text="确认口令", width=11,
                   command=lambda: finish(value.get())).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="跳过此项", width=11,
                   command=lambda: finish("")).pack(side=tk.RIGHT, padx=(0, 5))
        ttk.Button(buttons, text="停止后续项目", width=13,
                   command=lambda: finish("", True)).pack(side=tk.LEFT)
        window.protocol("WM_DELETE_WINDOW", lambda: finish(""))
        window.bind("<Return>", lambda _event: finish(value.get()))
        self._show_modal(window, focus_widget=entry)
        return answer["value"]

    def _show_modal(self, window, focus_widget=None):
        window.update_idletasks()
        x = self.root.winfo_rootx() + max((self.root.winfo_width() - window.winfo_width()) // 2, 0)
        y = self.root.winfo_rooty() + max((self.root.winfo_height() - window.winfo_height()) // 2, 0)
        window.geometry("+%d+%d" % (x, y))
        window.grab_set()
        if focus_widget is not None:
            focus_widget.focus_set()
        else:
            window.focus_force()
        self.root.wait_window(window)

    def _handle_done(self, payload, paths):
        for result in payload.get("results", []):
            self._show_result(result)
        self.last_payload = payload
        self.last_paths = paths
        self.current_output_dir = os.path.dirname(paths.get("html", ""))
        self.active_test_id = None
        self._set_running(False)
        self.report_button.configure(state=tk.NORMAL)
        self.progress.configure(value=self.progress.cget("maximum"))
        verdict = VERDICT_TEXT.get(payload.get("verdict"), payload.get("verdict", "未知"))
        overall = payload.get("overall_status", "")
        self.current_var.set("检查完成：验收结论 %s" % verdict)
        self.status_var.set("检查完成（%s）" % overall)
        self._update_counts()
        message = "验收结论：%s\n总体状态：%s\n\n报告：%s" % (
            verdict, overall, paths.get("html", ""))
        if payload.get("verdict") == "ACCEPT":
            messagebox.showinfo("检查完成", message, parent=self.root)
        else:
            messagebox.showwarning("检查完成", message, parent=self.root)

    def _handle_error(self, payload):
        self._append_log(payload.get("traceback", ""))
        reason = to_text(payload.get("message", "未知错误"))
        has_error_result = False
        for item in self.result_tree.get_children():
            values = self.result_tree.item(item, "values")
            if not values:
                continue
            tags = self.result_tree.item(item, "tags")
            current = to_text(tags[0]) if tags else "PENDING"
            if current in ("PENDING", "RUNNING"):
                status = "ERROR" if current == "RUNNING" else "SKIP"
                summary = ("运行异常：%s" % reason if status == "ERROR" else
                           "因运行异常，本项目未执行")
                has_error_result = has_error_result or status == "ERROR"
                result = {
                    "id": item, "label": values[1], "status": status,
                    "summary": summary, "duration_ms": 0,
                    "metrics": {}, "details": [], "artifacts": [],
                }
                self._show_result(result)
        if not has_error_result:
            self._show_result({
                "id": "run_error", "label": "启动检查", "status": "ERROR",
                "summary": reason, "duration_ms": 0,
                "metrics": {}, "details": [], "artifacts": [],
            })
        self.active_test_id = None
        self._set_running(False)
        self.current_var.set("检查未完成")
        self.status_var.set("启动或运行发生异常")
        messagebox.showerror("检查失败", reason, parent=self.root)

    def _append_log(self, line):
        text = to_text(line).rstrip("\r\n") + "\n"
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_line_count += max(text.count("\n"), 1)
        if self.log_line_count > 5000:
            remove_count = self.log_line_count - 4500
            self.log_text.delete("1.0", "%d.0" % (remove_count + 1))
            self.log_line_count -= remove_count
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.log_line_count = 0

    def _show_result_details(self, _event=None):
        selected = self.result_tree.selection()
        if not selected:
            return
        result = self.result_data.get(selected[0])
        if not result:
            return
        window = tk.Toplevel(self.root)
        window.title("项目详情 - %s" % result.get("label", result.get("id", "")))
        window.geometry("720x500")
        window.transient(self.root)
        text_widget = tk.Text(window, wrap=tk.WORD, font=("Consolas", 9), relief=tk.SUNKEN)
        scroll = ttk.Scrollbar(window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scroll.set)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=6)
        detail = json.dumps(json_safe(result), ensure_ascii=False, indent=2, sort_keys=True)
        text_widget.insert("1.0", to_text(detail))
        text_widget.configure(state=tk.DISABLED)

    def open_report(self):
        path = self.last_paths.get("html") if self.last_paths else None
        if not path or not os.path.isfile(path):
            messagebox.showinfo("打开报告", "当前还没有可打开的报告。", parent=self.root)
            return
        self._open_path(path)

    def open_output_folder(self):
        path = self.current_output_dir or to_text(self.output_var.get()).strip()
        if not path:
            return
        try:
            ensure_dir(path)
            self._open_path(path)
        except Exception as exc:
            messagebox.showerror("打开目录失败", to_text(exc), parent=self.root)

    def _open_path(self, path):
        try:
            if hasattr(os, "startfile"):
                os.startfile(os.path.abspath(path))
            else:
                raise RuntimeError("当前系统不支持自动打开文件")
        except Exception as exc:
            messagebox.showerror("打开失败", to_text(exc), parent=self.root)

    def show_about(self):
        messagebox.showinfo(
            "关于",
            "NAO 机器人验修工具箱\n"
            "Edited by XCrane\n",
            parent=self.root,
        )

    def _on_close(self):
        if self.running:
            if messagebox.askyesno(
                    "检查正在进行",
                    "不能在机器人动作或采样中直接关闭工具。\n\n"
                    "是否请求在当前项目安全结束后停止？窗口会暂时保留。",
                    parent=self.root):
                self.request_stop()
            return
        self.root.destroy()


def main():
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    root = tk.Tk()
    NaoToolboxApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

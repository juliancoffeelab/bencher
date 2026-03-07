import os
import queue
import shlex
import subprocess
import threading
import time

import dearpygui.dearpygui as dpg
import psutil
from dearpygui_ext.themes import create_theme_imgui_light
from matplotlib import font_manager


class ProtectedData:
    """A thread-safe wrapper encapsulating data and its associated mutex."""

    def __init__(self, initial_value=None):
        self._data = initial_value
        self._lock = threading.Lock()

    def get(self):
        """Safely retrieves the current value under a lock."""
        with self._lock:
            return self._data

    def set(self, value):
        """Safely updates the value under a lock."""
        with self._lock:
            self._data = value


# 1. Thread-safe communication
data_queue = queue.Queue(maxsize=2)
stop_event = threading.Event()

# Global state to track the active thread
current_thread = ProtectedData(None)
monitoring_active = ProtectedData(False)


class ExitEvent(Exception):
    pass


def cleanup_process_tree(proc_obj):
    """
    Terminates and kills a psutil.Process tree starting from proc_obj.
    """
    try:
        # 1. Capture all descendants before signaling the parent
        descendants = proc_obj.children(recursive=True)
        all_procs = descendants + [proc_obj]

        # 2. Attempt graceful termination for the entire group
        for p in all_procs:
            try:
                p.terminate()
            except psutil.NoSuchProcess:
                pass

        # 3. Wait up to 3 seconds for processes to exit
        _gone, alive = psutil.wait_procs(all_procs, timeout=3)

        # 4. Forcefully kill any processes that are still active
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass

    except psutil.NoSuchProcess:
        # The main process object was already gone
        pass


def data_producer(cmd_list):
    """Starts a subprocess and monitors its CPU and Memory usage

    At the end, sends summary stats and signals with None."""
    proc = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    p = psutil.Process(proc.pid)
    p.cpu_percent(interval=None)

    cpu_history = []
    mem_history = []
    timestamps = []

    # Post-mortem tracking
    peak_mem = 0
    start_time = time.time()

    try:
        while proc.poll() is None:
            if stop_event.is_set():
                raise ExitEvent()

            current_time = time.time() - start_time

            cpu_val = p.cpu_percent(interval=None)
            mem_info = p.memory_info()
            mem_val_gb = mem_info.rss / (1024 * 1024 * 1024)

            # Track peak memory
            if mem_val_gb > peak_mem:
                peak_mem = mem_val_gb

            # Post mortem
            cpu_times = p.cpu_times()
            switches = p.num_ctx_switches()

            timestamps.append(current_time)
            cpu_history.append(cpu_val)
            mem_history.append(mem_val_gb)

            try:
                data_queue.put_nowait(
                    {
                        "type": "live",
                        "payload": [
                            list(timestamps),
                            list(cpu_history),
                            list(mem_history),
                        ],
                    }
                )
            except queue.Full:
                pass

            time.sleep(0.5)

        # 2. Final Snapshot (Post-Mortem)
        total_duration = time.time() - start_time

        summary = {
            "type": "summary",
            "payload": {
                "duration": total_duration,
                "user_time": cpu_times.user,
                "sys_time": cpu_times.system,
                "peak_mem_gb": peak_mem,
                "v_switches": switches.voluntary,
                "iv_switches": switches.involuntary,
                "exit_code": proc.returncode,
            },
        }
        data_queue.put(summary)
    except ExitEvent:
        print("Finished early...")
    finally:
        cleanup_process_tree(p)

        proc.wait()
        data_queue.put(None)


def initialize_gui():
    """Sets up the DPG context and viewport."""
    dpg.create_context()
    dpg.create_viewport(title="Process Resource Monitor", width=1000, height=600)
    dpg.setup_dearpygui()
    dpg.show_viewport()


def keyboard_callback(_sender, app_data):
    """Closes the app when Escape is pressed."""
    # app_data is the key code
    if app_data == dpg.mvKey_Escape:
        print("Escape pressed. Exiting...")
        stop_event.set()
        dpg.stop_dearpygui()


def restart_process(_sender, _app_data, _user_data):
    """Callback to handle process restarts cleanly."""
    # 1. Signal and wait for the old process to stop
    stop_event.set()
    if current_thread.get() and current_thread.get().is_alive():
        current_thread.get().join(timeout=2.0)

    # 2. Flush the queue to prevent drawing stale data
    while not data_queue.empty():
        try:
            data_queue.get_nowait()
        except queue.Empty:
            break

    # 3. Reset synchronization states and GUI elements
    stop_event.clear()
    dpg.set_value("cpu_series", [[], []])
    dpg.set_value("mem_series", [[], []])
    dpg.configure_item("summary_win", show=False)

    # 4. Parse the new command
    cmd_str = dpg.get_value("cmd_input")
    try:
        cmd_list = shlex.split(cmd_str)
    except ValueError:
        cmd_list = cmd_str.split()

    if not cmd_list:
        return

    # 5. Launch the new thread
    monitoring_active.set(True)
    current_thread.set(threading.Thread(target=data_producer, args=(cmd_list,)))
    current_thread.get().start()


def run_app():
    """Main application loop."""
    initialize_gui()

    with dpg.handler_registry():
        dpg.add_key_press_handler(callback=keyboard_callback)

    dpg.set_exit_callback(lambda: stop_event.set())

    # Font Management
    try:
        families = ["Helvetica", "DejaVu Sans", "Verdana", "Geneva"]
        font_path = None
        for family in families:
            path = font_manager.findfont(font_manager.FontProperties(family=family))
            if os.path.exists(path) and "ttf" in path.lower():
                font_path = path
                print(f"Found font: {font_path}")
                break

        if font_path:
            with dpg.font_registry():
                system_font = dpg.add_font(font_path, 20)
                dpg.bind_font(system_font)
        else:
            raise RuntimeError("Required fonts not found.")

    except Exception:
        print("Couldn't find any system font, fallback to 1.5 scale")
        dpg.set_global_font_scale(1.5)

    theme = create_theme_imgui_light()
    dpg.bind_theme(theme)

    with dpg.window(label="Dashboard", tag="main_window"):
        dpg.add_text("Process Telemetry")

        # UI Additions for dynamic restarts
        dpg.add_input_text(
            label="Command",
            default_value="python fib.py 50",
            tag="cmd_input",
            width=300,
        )
        dpg.add_button(label="Run / Restart", callback=restart_process)

        dpg.add_separator()

    dpg.set_primary_window("main_window", True)

    plot_configs = [
        {
            "tag": "cpu_series",
            "y_axis": "cpu_y_axis",
            "x_axis": "x_axis_cpu",
            "label": "CPU Usage (%)",
            "pos": [20, 150],  # Shifted Y position down to accommodate inputs
        },
        {
            "tag": "mem_series",
            "y_axis": "mem_y_axis",
            "x_axis": "x_axis_mem",
            "label": "Memory Usage (GB)",
            "pos": [510, 150],  # Shifted Y position down
        },
    ]

    for cfg in plot_configs:
        with dpg.window(label=cfg["label"], width=470, height=350, pos=cfg["pos"]):
            with dpg.plot(height=-1, width=-1):
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag=cfg["x_axis"])
                dpg.add_plot_axis(dpg.mvYAxis, label=cfg["label"], tag=cfg["y_axis"])
                dpg.add_line_series([], [], tag=cfg["tag"], parent=cfg["y_axis"])

    # Summary Window (initially hidden)
    with dpg.window(
        label="Final Process Summary",
        modal=True,
        show=False,
        tag="summary_win",
        width=400,
        height=300,
        pos=[300, 200],
    ):
        dpg.add_text("", tag="summary_text")

    # Initial start
    cmd_str = dpg.get_value("cmd_input")
    initial_cmd = shlex.split(cmd_str)
    monitoring_active.set(True)
    current_thread.set(threading.Thread(target=data_producer, args=(initial_cmd,)))
    current_thread.get().start()

    while dpg.is_dearpygui_running():
        if monitoring_active.get():
            try:
                msg = data_queue.get_nowait()

                if msg is None:
                    monitoring_active.set(False)
                elif msg["type"] == "live":
                    times, cpu, mem = msg["payload"]
                    dpg.set_value("cpu_series", [times, cpu])
                    dpg.set_value("mem_series", [times, mem])

                    for cfg in plot_configs:
                        dpg.fit_axis_data(cfg["x_axis"])
                        dpg.fit_axis_data(cfg["y_axis"])

                elif msg["type"] == "summary":
                    s = msg["payload"]
                    report = (
                        f"Execution Finished\n"
                        f"{'-' * 30}\n"
                        f"Total Duration:  {s['duration']:.2f}s\n"
                        f"User CPU Time:   {s['user_time']:.2f}s\n"
                        f"System CPU Time: {s['sys_time']:.2f}s\n"
                        f"Peak RAM (RSS):  {s['peak_mem_gb']:.4f} GB\n"
                        f"Voluntary Ctx:   {s['v_switches']}\n"
                        f"Involuntary Ctx: {s['iv_switches']}\n"
                        f"Exit Code:       {s['exit_code']}"
                    )
                    dpg.set_value("summary_text", report)
                    dpg.configure_item("summary_win", show=True)

            except queue.Empty:
                pass

        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    print("Hello from bencher")
    run_app()

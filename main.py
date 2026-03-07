import os
import queue
import subprocess
import threading
import time

import dearpygui.dearpygui as dpg
import psutil
from dearpygui_ext.themes import create_theme_imgui_light
from matplotlib import font_manager

# 1. Thread-safe communication
data_queue = queue.Queue(maxsize=2)


def data_producer():
    """Starts a subprocess and monitors its CPU and Memory usage, then sends summary stats."""
    cmd = [
        "python",
        "fib.py",
        "35",
    ]
    proc = subprocess.Popen(
        cmd,
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

    finally:
        if proc.poll() is None:
            proc.terminate()
        data_queue.put(None)


def initialize_gui():
    """Sets up the DPG context and viewport."""
    dpg.create_context()
    dpg.create_viewport(title="Process Resource Monitor", width=1000, height=600)
    dpg.setup_dearpygui()
    dpg.show_viewport()


def run_app():
    """Main application loop."""
    initialize_gui()

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
        dpg.add_separator()

    dpg.set_primary_window("main_window", True)

    plot_configs = [
        {
            "tag": "cpu_series",
            "y_axis": "cpu_y_axis",
            "x_axis": "x_axis_cpu",
            "label": "CPU Usage (%)",
            "pos": [20, 100],
        },
        {
            "tag": "mem_series",
            "y_axis": "mem_y_axis",
            "x_axis": "x_axis_mem",
            "label": "Memory Usage (GB)",
            "pos": [510, 100],
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

    thread = threading.Thread(target=data_producer, daemon=True)
    thread.start()

    monitoring_active = True

    while dpg.is_dearpygui_running():
        if monitoring_active:
            try:
                msg = data_queue.get_nowait()

                if msg is None:
                    monitoring_active = False
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

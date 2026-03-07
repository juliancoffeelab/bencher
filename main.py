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
    """Starts a subprocess and monitors its CPU and Memory usage."""
    # Start a dummy process
    cmd = [
        "python",
        "-c",
        "import time; [i**2 for i in range(10000000)]; time.sleep(100)",
    ]
    proc = subprocess.Popen(cmd)

    p = psutil.Process(proc.pid)
    # Initial call to set the base for cpu_percent
    p.cpu_percent(interval=None)

    cpu_history = []
    mem_history = []
    timestamps = []
    start_time = time.time()

    try:
        while proc.poll() is None:
            current_time = time.time() - start_time

            cpu_val = p.cpu_percent(interval=None)
            mem_val = p.memory_info().rss / (1024 * 1024 * 1024)  # GB

            timestamps.append(current_time)
            cpu_history.append(cpu_val)
            mem_history.append(mem_val)

            try:
                # Send copies of the lists to avoid thread-safety issues during rendering
                data_queue.put_nowait(
                    [list(timestamps), list(cpu_history), list(mem_history)]
                )
            except queue.Full:
                pass

            time.sleep(0.5)
    finally:
        if proc.poll() is None:
            proc.terminate()


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
        dpg.add_text("Subprocess Telemetry (Full Rescaling & Diagnostics)")
        dpg.add_separator()

    dpg.set_primary_window("main_window", True)

    # Plot configuration for dynamic access
    plot_configs = [
        {
            "tag": "cpu_series",
            "y_axis": "cpu_y_axis",
            "x_axis": "x_axis_cpu",
            "label": "CPU Usage (%)",
        },
        {
            "tag": "mem_series",
            "y_axis": "mem_y_axis",
            "x_axis": "x_axis_mem",
            "label": "Memory Usage (GB)",
        },
    ]

    for i, cfg in enumerate(plot_configs):
        with dpg.window(
            label=cfg["label"], width=450, height=350, pos=[i * 460 + 20, 100]
        ):
            with dpg.plot(height=-1, width=-1):
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag=cfg["x_axis"])
                dpg.add_plot_axis(dpg.mvYAxis, label=cfg["label"], tag=cfg["y_axis"])
                dpg.add_line_series([], [], tag=cfg["tag"], parent=cfg["y_axis"])

    thread = threading.Thread(target=data_producer, daemon=True)
    thread.start()

    while dpg.is_dearpygui_running():
        try:
            # Attempt to get the latest data from the producer thread
            times, cpu, mem = data_queue.get_nowait()

            # Update the series data
            dpg.set_value("cpu_series", [times, cpu])
            dpg.set_value("mem_series", [times, mem])

            # Explicitly fit the axes to the data to prevent "vanishing" lines
            for cfg in plot_configs:
                dpg.fit_axis_data(cfg["x_axis"])
                dpg.fit_axis_data(cfg["y_axis"])

        except queue.Empty:
            pass

        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    print("Hello from bencher")
    run_app()

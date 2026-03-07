import os
import queue
import threading
import time

import dearpygui.dearpygui as dpg
import numpy as np
from dearpygui_ext.themes import create_theme_imgui_light
from matplotlib import font_manager

# 1. Thread-safe communication
data_queue = queue.Queue(maxsize=2)


def data_producer(x_data):
    """Mock background thread generating sine data."""
    frame = 0
    while True:
        y_offset = frame * 0.1
        series_data = []

        # Calculate for both series
        for idx in range(2):
            y_vals = (np.sin(np.array(x_data) + y_offset + (idx * np.pi / 2))).tolist()
            series_data.append(y_vals)

        # Push to queue (non-blocking or overwrite if full)
        try:
            data_queue.put_nowait(series_data)
        except queue.Full:
            pass

        frame += 1
        time.sleep(0.016)  # Mock ~60Hz data rate


def initialize_gui():
    """Sets up the DPG context and viewport."""
    dpg.create_context()
    dpg.create_viewport(title="Structured Plotting", width=1000, height=600)
    dpg.setup_dearpygui()
    dpg.show_viewport()


def run_app():
    """Main application loop."""
    # 1. Initialize Context
    initialize_gui()

    # 2. Apply Theme
    theme = create_theme_imgui_light()
    dpg.bind_theme(theme)

    # 3. Load System Font
    try:
        families = ["Helvetica", "DejaVu Sans", "Verdana", "Geneva"]
        font_path = None
        for family in families:
            path = font_manager.findfont(font_manager.FontProperties(family=family))
            if os.path.exists(path) and "ttf" in path.lower():
                font_path = path
                print(f"Found font:\n{font_path}")
                break
        if not font_path:
            raise RuntimeError("Required fonts not found.")
        with dpg.font_registry():
            system_font = dpg.add_font(font_path, 20)
            dpg.bind_font(system_font)
    except Exception:
        print("Couldn't find any system font, fallback to 1.5 scale")
        dpg.set_global_font_scale(1.5)

    # 4. Build Primary Dashboard
    with dpg.window(label="Dashboard", tag="main_window"):
        dpg.add_text("Automated GPU Plotting (Dual Series - Threaded)")
        dpg.add_separator()

    dpg.set_primary_window("main_window", True)

    # Tracking variables
    active_series = []
    x_data = np.linspace(0, 10, 100).tolist()
    total_initial_plots = 2

    # 5. Pre-spawn Two Plots Automatically
    for i in range(1, total_initial_plots + 1):
        s_tag = f"series_{i}"
        active_series.append(s_tag)

        with dpg.window(
            label=f"Plot Window {i}",
            width=450,
            height=350,
            pos=[(i - 1) * 460 + 20, 100],
        ):
            with dpg.plot(height=-1, width=-1):
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)")
                y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Amplitude")
                dpg.add_line_series(x_data, [], tag=s_tag, parent=y_axis)

    # --- Start the background thread ---
    thread = threading.Thread(target=data_producer, args=(x_data,), daemon=True)
    thread.start()

    # 6. Main Render Loop
    while dpg.is_dearpygui_running():
        # Grab data from the thread if available
        try:
            latest_data = data_queue.get_nowait()
            for idx, tag in enumerate(active_series):
                dpg.set_value(tag, [x_data, latest_data[idx]])
        except queue.Empty:
            pass

        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    print("Hello from bencher")
    run_app()

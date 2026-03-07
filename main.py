import os

import dearpygui.dearpygui as dpg
import numpy as np
from dearpygui_ext.themes import create_theme_imgui_light
from matplotlib import font_manager


def initialize_gui():
    """Sets up the DPG context and viewport."""
    dpg.create_context()
    dpg.create_viewport(title="Structured Plotting", width=800, height=600)
    dpg.setup_dearpygui()
    dpg.show_viewport()


def run_app():
    """Main application loop."""
    # 1. Initialize
    initialize_gui()

    # 2. Apply Theme
    theme = create_theme_imgui_light()
    dpg.bind_theme(theme)

    # 3. Load System Font Cross-Platform
    try:
        families = ["Helvetica", "DejaVu Sans", "Verdana", "Geneva"]
        font_path = None

        for family in families:
            path = font_manager.findfont(font_manager.FontProperties(family=family))
            if os.path.exists(path) and "ttf" in path.lower():
                font_path = path
                break

        if not font_path:
            raise RuntimeError("no fonts")

        with dpg.font_registry():
            system_font = dpg.add_font(font_path, 20)
            dpg.bind_font(system_font)
    except Exception:
        dpg.set_global_font_scale(2)
        pass

    # 4. Build UI
    with dpg.window(label="Dashboard", tag="main_window"):
        dpg.add_text("Native GPU Plotting (Main Loop Only)")
        dpg.add_button(label="Spawn New Live Plot", tag="spawn_btn")
        dpg.add_separator()

    dpg.set_primary_window("main_window", True)

    # Tracking for loop updates
    active_series = []
    plot_count = 0
    x_data = np.linspace(0, 10, 100).tolist()
    frame = 0

    # 5. Main Render Loop
    while dpg.is_dearpygui_running():
        # Check for click on button to spawn new windows
        if dpg.is_item_clicked("spawn_btn"):
            plot_count += 1
            s_tag = f"series_{plot_count}"

            with dpg.window(label=f"Plot {plot_count}", width=400, height=300):
                with dpg.plot(height=-1, width=-1):
                    dpg.add_plot_axis(dpg.mvXAxis, label="x")

                    y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="y")
                    dpg.add_line_series(x_data, [], tag=s_tag, parent=y_axis)

            active_series.append(s_tag)

        # Update all active series every frame
        y_offset = frame * 0.1
        for tag in active_series:
            y_data = (np.sin(np.array(x_data) + y_offset)).tolist()
            dpg.set_value(tag, [x_data, y_data])

        frame += 1
        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    run_app()

import dearpygui.dearpygui as dpg
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# Use a non-interactive backend to ensure the buffer is captured without pop-ups
matplotlib.use("Agg")


def create_plot(data_x, data_y, title="Data Visualization"):
    """Generates a Matplotlib figure and axis."""
    fig, ax = plt.subplots(figsize=(5, 4), dpi=100)
    ax.plot(data_x, data_y, color="#3498db", linewidth=2)
    ax.set_title(title)
    ax.grid(True, linestyle="--", alpha=0.6)
    return fig, ax


def get_texture_data(fig):
    """Converts a Matplotlib figure into a DPG-compatible RGBA float array."""
    fig.canvas.draw()
    # Extract buffer and normalize to 0.0 - 1.0 range for DPG float format
    raw_data = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    float_data = raw_data.astype(np.float32) / 255.0
    width, height = fig.canvas.get_width_height()
    return float_data, width, height


def update_plot_texture(texture_tag, fig):
    """Updates an existing DPG texture with new figure data."""
    new_data, w, h = get_texture_data(fig)
    dpg.set_value(texture_tag, new_data)


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

    # 2. Get hardware scaling ratio after viewport is live
    ratio = dpg.get_app_configuration().get("pixel_ratio", 1.0)

    # 3. Generate initial plot data
    fig, ax = create_plot([0, 1, 2, 3], [10, 25, 15, 30])
    pixel_data, w, h = get_texture_data(fig)

    # 4. Register Texture
    with dpg.texture_registry():
        dpg.add_raw_texture(
            width=w,
            height=h,
            default_value=pixel_data,
            format=dpg.mvFormat_Float_rgba,
            tag="plot_texture",
        )

    # 5. Build UI
    with dpg.window(label="Dashboard", tag="main_window"):
        dpg.add_text("Embedded Matplotlib Figure")
        dpg.add_image(
            "plot_texture",
            width=w / ratio,
            height=h / ratio,
        )

    dpg.set_primary_window("main_window", True)

    # 6. Start Render Loop
    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    run_app()

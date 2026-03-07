import dearpygui.dearpygui as dpg
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# Ensure a non-interactive backend is used for buffer stability
matplotlib.use("Agg")


def get_plot_data(fig):
    fig.canvas.draw()
    # Convert the RGBA buffer to a normalized float32 array
    data = (
        np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8).astype(np.float32)
        / 255.0
    )
    return data, fig.canvas.get_width_height()


dpg.create_context()
dpg.create_viewport(
    title="Matplotlib Integration",
    width=800,
    height=600,
)
dpg.setup_dearpygui()

# Viewport must be shown before querying the hardware pixel ratio
dpg.show_viewport()

# Retrieve the actual scaling ratio of the monitor
cfg = dpg.get_app_configuration()
ratio = cfg.get("pixel_ratio", 1.0)

# Create the plot
fig, ax = plt.subplots(figsize=(5, 4), dpi=100)
ax.plot([0, 1, 2], [10, 20, 10])
ax.set_title("Corrected Alignment")
data, (w, h) = get_plot_data(fig)

with dpg.texture_registry():
    dpg.add_raw_texture(
        width=w,
        height=h,
        default_value=data,
        format=dpg.mvFormat_Float_rgba,
        tag="plot_tex",
    )

with dpg.window(tag="PrimaryWindow"):
    # The image size must be divided by the ratio to map physical pixels to logical units
    dpg.add_image(
        "plot_tex",
        width=w / ratio,
        height=h / ratio,
    )

dpg.set_primary_window("PrimaryWindow", True)

while dpg.is_dearpygui_running():
    dpg.render_dearpygui_frame()

dpg.destroy_context()

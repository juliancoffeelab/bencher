import dearpygui.dearpygui as dpg
import matplotlib.pyplot as plt
import numpy as np
from dearpygui_ext.themes import create_theme_imgui_light


def get_plot_data(fig):
    fig.canvas.draw()
    # Explicit conversion to float32 RGBA prevents SegFaults
    rgba = (
        np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8).astype(np.float32)
        / 255.0
    )
    return rgba, fig.canvas.get_width_height()


dpg.create_context()

fig, ax = plt.subplots(figsize=(5, 4), dpi=100)
ax.plot([0, 1, 2], [10, 20, 10], label="Success")
ax.legend()
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
    dpg.add_text("Final Corrected Integration")
    dpg.add_image("plot_tex")

dpg.bind_theme(create_theme_imgui_light())
dpg.create_viewport(
    title="Stable Plot", width=800, height=600, pixel_scaling_toolbar=True
)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("PrimaryWindow", True)
dpg.start_dearpygui()
dpg.destroy_context()

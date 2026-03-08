import os
import queue
import shlex
import signal
import subprocess
import threading
import time
from typing import Any, Literal, TypedDict

import dearpygui.dearpygui as dpg  # type: ignore
import psutil
from dearpygui_ext.themes import create_theme_imgui_light  # type: ignore
from matplotlib import font_manager


class StatData(TypedDict):
    kind: Literal["live", "summary"]
    payload: Any


class ProtectedData:
    """A thread-safe wrapper encapsulating data and its associated mutex."""

    def __init__(self, initial_value=None):
        self._data = initial_value
        self._lock = threading.Lock()

    # TODO: needs to return a mutex guard/contextmanager on its own
    # otherwise problematic with reference objects
    def get(self):
        """Safely retrieves the current value under a lock."""
        with self._lock:
            return self._data

    def set(self, value):
        """Safely updates the value under a lock."""
        with self._lock:
            self._data = value


# 1. Thread-safe communication
data_queue: queue.Queue[StatData | None] = queue.Queue(maxsize=0)
stop_event = threading.Event()

# Global state to track the active thread
current_thread = ProtectedData(None)
monitoring_active = ProtectedData(False)


class ExitEvent(Exception):
    pass


def cleanup_process_group(proc: subprocess.Popen):
    """
    Terminates and kills a process group spawned with start_new_session=True.
    This replaces the recursive psutil tree traversal.
    """
    pid = proc.pid
    try:
        if os.name == "posix":
            os.killpg(pid, signal.SIGTERM)
        elif os.name == "nt":
            os.kill(pid, signal.CTRL_BREAK_EVENT)
    except ProcessLookupError:
        print(f"Process {pid} no longer exists")
        pass

    try:
        proc.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "posix":
                os.killpg(pid, signal.SIGKILL)
            elif os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except ProcessLookupError:
            print(f"Process {pid} no longer exists")
            pass
    print(f"Process {pid} is done")


def data_producer(cmd_list: Any):
    """Starts a subprocess and monitors its CPU and Memory usage

    At the end, sends summary stats and signals with None."""
    proc = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    print(f"Proc {proc.pid} is starting..")

    # Initialize the primary psutil Process object
    parent = psutil.Process(proc.pid)

    cpu_history = []
    mem_history = []
    timestamps = []

    # Post-mortem tracking
    peak_mem = 0.0
    start_time = time.time()

    # Store aggregated totals for the final summary
    last_cpu_times = None
    last_switches = None

    try:
        all_processes = {parent}
        while proc.poll() is None:
            if stop_event.is_set():
                # NOTE: don't forget to raise at the end of the loop
                break

            current_time = time.time() - start_time

            try:
                # Gather the parent and all descendants
                descendants = parent.children(recursive=True)
                # Add them, but never clea
                #
                # It's sort of a leak, but we don't expect you to spawn
                # billion processes.
                all_processes |= set(descendants)

                current_cpu_sum = 0.0
                current_mem_sum = 0.0

                # Temporary containers for aggregated summary data
                temp_user_time = 0.0
                temp_sys_time = 0.0
                temp_v_switches = 0
                temp_iv_switches = 0

                for p in all_processes:
                    try:
                        # Summing metrics across the tree
                        current_cpu_sum += p.cpu_percent(interval=None)
                        current_mem_sum += p.memory_info().rss / (1024 * 1024)

                        # Accumulate time and switch data
                        c_times = p.cpu_times()
                        temp_user_time += c_times.user
                        temp_sys_time += c_times.system

                        switches = p.num_ctx_switches()
                        temp_v_switches += switches.voluntary
                        temp_iv_switches += switches.involuntary
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Process might have ended between gathering the list
                        # and inspection
                        continue

                if current_mem_sum > peak_mem:
                    peak_mem = current_mem_sum

                # Update the last known good statistics
                last_cpu_times = (temp_user_time, temp_sys_time)
                last_switches = (temp_v_switches, temp_iv_switches)

                timestamps.append(current_time)
                cpu_history.append(current_cpu_sum)
                mem_history.append(current_mem_sum)

                data_queue.put_nowait(
                    {
                        "kind": "live",
                        "payload": [
                            list(timestamps),
                            list(cpu_history),
                            list(mem_history),
                        ],
                    }
                )
            except psutil.NoSuchProcess:
                break
            except queue.Full:
                pass

            time.sleep(0.5)
        try:
            stdout, stderr = proc.communicate(timeout=0.0)
        except subprocess.TimeoutExpired:
            stdout, stderr = "[didnt finish]", "[didnt finish]"
        total_duration = time.time() - start_time

        summary: StatData = {
            "kind": "summary",
            "payload": {
                "duration": total_duration,
                "user_time": last_cpu_times[0] if last_cpu_times else 0.0,
                "sys_time": last_cpu_times[1] if last_cpu_times else 0.0,
                "peak_mem_mb": peak_mem,
                "v_switches": last_switches[0] if last_switches else 0,
                "iv_switches": last_switches[1] if last_switches else 0,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            },
        }
        data_queue.put(summary)

        if stop_event.is_set():
            raise ExitEvent()
    except ExitEvent:
        print("Finished early...")
    finally:
        cleanup_process_group(parent)

        proc.wait()
        data_queue.put(None)


def initialize_gui():
    """Sets up the DPG context and viewport."""
    dpg.create_context()
    dpg.create_viewport(title="Process Resource Monitor", width=1000, height=600)
    dpg.setup_dearpygui()
    dpg.show_viewport()


def keyboard_callback(sender, app_data):
    """Closes the app when Escape is pressed."""
    # app_data is the key code
    if app_data == dpg.mvKey_Escape:
        print("Escape pressed. Exiting...")
        stop_event.set()
        current_thread.get().join(timeout=3.0)
        dpg.stop_dearpygui()
    elif app_data == dpg.mvKey_Return:
        restart_process(sender, None, None)


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
            default_value="\
python3 -c 'import time; [2**i for i in range(100000)]'\
",
            tag="cmd_input",
            width=1000,
        )
        dpg.add_button(label="Run / Restart", callback=restart_process)
        dpg.add_button(label="Stop", callback=lambda: stop_event.set())

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
            "label": "Memory Usage (MB)",
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
                elif msg["kind"] == "live":
                    times, cpu, mem = msg["payload"]
                    dpg.set_value("cpu_series", [times, cpu])
                    dpg.set_value("mem_series", [times, mem])

                    for cfg in plot_configs:
                        dpg.fit_axis_data(cfg["x_axis"])
                        dpg.fit_axis_data(cfg["y_axis"])

                elif msg["kind"] == "summary":
                    s = msg["payload"]
                    report = (
                        f"Execution Finished\n"
                        f"{'-' * 30}\n"
                        f"Total Duration:  {s['duration']:.2f}s\n"
                        f"User CPU Time:   {s['user_time']:.2f}s\n"
                        f"System CPU Time: {s['sys_time']:.2f}s\n"
                        f"Peak RAM (RSS):  {s['peak_mem_mb']:.4f} MB\n"
                        f"Voluntary Ctx:   {s['v_switches']}\n"
                        f"Involuntary Ctx: {s['iv_switches']}\n"
                        f"Exit Code:       {s['exit_code']}\n"
                        f"stdout: {s['stdout']}\n"
                        f"stderr: {s['stderr']}\n"
                    )
                    dpg.set_value("summary_text", report)
                    dpg.configure_item("summary_win", show=True)

            except queue.Empty:
                pass

        dpg.render_dearpygui_frame()

    dpg.destroy_context()


def main():
    print("Hello from bencher")
    run_app()


if __name__ == "__main__":
    main()

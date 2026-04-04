import sys
import os

from PyQt5 import QtCore
from PyQt5 import QtGui
import gi

from .rosbag import RosbagRecorder
gi.require_version("Gst", "1.0")
gi.require_version('GstVideo', '1.0') 
from gi.repository import Gst, GstVideo

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QWidget, QLabel, QGridLayout

from rcl_interfaces.msg import Log
from .msgs import WaypointMessage

from .config import CAMERA_FRONT, CAMERA_BOTTOM, PIPELINE_DESCRIPTION, WAYPOINT_LAUNCH
import rclpy
import rclpy.executors
from rclpy.node import Node
from rclpy.action import ActionClient

from vortex_msgs.action import WaypointManager
from geometry_msgs.msg import PointStamped, Point, Quaternion
from vortex_msgs.msg import Waypoint

from vortex_utils.python_utils import euler_to_quat

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot, QProcess
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QColor, QTextCharFormat
from .gui_ui import Ui_MainWindow
from ament_index_python.packages import get_package_share_directory

# All ROS to Qt Signals
class RosBridge(QObject):
    log_message = pyqtSignal(str)
    killswitch_updated = pyqtSignal(bool)
    operation_mode_updated = pyqtSignal(int)


class RosGuiNode(Node):
    def __init__(self, bridge: RosBridge):
        super().__init__("ros_gui_node")
        self._bridge = bridge
        
        self._action_client = ActionClient(self, WaypointManager, "/orca/waypoint_manager")
        self.create_subscription(Log, "/rosout", self._on_rosout, 10)
        self.current_goal_handle = None
        
        self.get_logger().info("[INFO] ROS GUI Node Started")
        
    def _on_rosout(self, msg: Log):
        LEVEL = {10: "DEBUG", 20: "INFO", 30: "WARN", 40: "ERROR", 50: "FATAL"}
        level = LEVEL.get(msg.level, "INFO")
        text = f"[{level}] [{msg.name}]: {msg.msg}"
        self._bridge.log_message.emit(text)
        
    def send_waypoint(self, goal: WaypointManager.Goal):
        if not self._action_client.wait_for_server(timeout_sec=1.0):
            self.get_logger().error("Waypoint manager server unavailable")
            return

        future = self._action_client.send_goal_async(goal)
        future.add_done_callback(self.goal_response_callback)
        
    def goal_response_callback(self, future):
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().warn("Goal rejected")
            return

        self.current_goal_handle = goal_handle
        self.get_logger().info("Goal accepted")

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)
    
    def result_callback(self, future):
        result = future.result().result
        self.get_logger().info("Goal completed")
        self.current_goal_handle = None
        
    def abort_waypoint(self):
        if self.current_goal_handle is not None:
            cancel_future = self.current_goal_handle.cancel_goal_async()
            cancel_future.add_done_callback(self.cancel_done_callback)
            self.get_logger().info("Abort requested")
        else:
            self.get_logger().warn("No active waypoint to abort")
    
    def cancel_done_callback(self, future):
        cancel_response = future.result()
        if len(cancel_response.goals_canceling) > 0:
            self.get_logger().info("Goal successfully canceled")
        else:
            self.get_logger().info("Goal failed to cancel")
        self.current_goal_handle = None
    
    

    # ROS → Qt
    """
    def _on_message(self, msg: String):
        self._bridge.message_received.emit(msg.data)

    def _timer_callback(self):
        self._bridge.message_received.emit("[timer tick]")

    # Qt → ROS  (called via executor.create_task)
    def publish_message(self, text: str):
        msg = String()
        msg.data = text
        self._pub.publish(msg)
        self.get_logger().info(f"Published: {text}")
    """

class RosSpinThread(QThread):
    def __init__(self, executor):
        super().__init__()
        self._executor = executor

    def run(self):
        self._executor.spin()

    def stop(self):
        self._executor.shutdown(timeout_sec=1.0)
        self.quit()
        self.wait()

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, node: RosGuiNode, executor, bridge: RosBridge):
        super().__init__()
        self.setupUi(self)
        self._node = node
        self._executor = executor
        
        self.vortex_logo.setPixmap(QtGui.QPixmap(os.path.join(get_package_share_directory("gui"), "resources", "logo.png")).scaled(400, 400, Qt.KeepAspectRatio))
        
        one_window = True;
        if one_window:
            main_tab = self.centralWidget()
        
            tabs = QtWidgets.QTabWidget()
            tabs.addTab(main_tab, "Controls")
            tabs.addTab(StatisticsWindow(), "Video")
            
            self.setCentralWidget(tabs)
        else:
            self.second_window.show_on_screen(1)
        
        
        self.processes: dict[str, QProcess] = {}
        self.DEFAULT_COLOR_FONT = self.terminal_output.currentCharFormat()
        
        self.launch_drone.toggled.connect(lambda checked, k="waypoints": self.on_proc_toggle("waypoints", WAYPOINT_LAUNCH, checked))
        self.waypoint_submit.clicked.connect(self.build_waypoint_payload)
        self.waypoint_abort.clicked.connect(self.abort_waypoint)
        
        self.build_topic_selector()
        
        bridge.log_message.connect(self.add_terminal_output)
        bridge.killswitch_updated.connect(lambda state: self.update_killswitch(state))
        bridge.operation_mode_updated.connect(lambda mode: self.update_operation_mode(mode))
    
    """
    @pyqtSlot(str)
    def _on_message_received(self, data: str):
        # ✅ Safe: already on Qt main thread via queued signal
        self._recv_display.setText(data)self, ax: int, ay: int, aw: int, ah: int) -> None:
        return super().update(ax, ay, aw, ah)
    """
    
    def update_killswitch(self, state: bool):
        if state: self.killswitch_status.setStyleSheet("background-color: red;")
        else: self.killswitch_status.setStyleSheet("background-color: green;")
    
    def update_operation_mode(self, mode: int):
        modes = {1: "AUTONOMOUS", 2: "MANUAL", 3: "REFERENCE"}
        self.operation_mode.setText(modes.get(mode))
        
    
    def build_topic_selector(self):
        self.rosbag_recorders: dict[str, "RosbagRecorder"] = {}
        self.refresh_btn.clicked.connect(self.fetch_topics)
        self.rosbag_topics.activated.connect(self._on_topic_selected)  # type: ignore
        self.rosbag_selected_topics.itemDoubleClicked.connect(self._remove_topic)  # type: ignore
        self.rosbag_start.clicked.connect(self.start_rosbag)

        self._topic_proc = QProcess(self)
        self._topic_proc.setProcessChannelMode(QProcess.MergedChannels)  # type: ignore
        self._topic_proc.finished.connect(self._on_topics_fetched)  # type: ignore

        self.fetch_topics()
        
    """
    def start_ssh_tmux(self):
        try:
            import subprocess

            cmd = [
                "tmux", "new-session", "-d", "-s", "name",
                "ssh", "-i", SSH_KEY,
                "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=60",
                "-o", "ServerAliveCountMax=10",
                SSH_HOST
            ]
            subprocess.run(cmd, check=False)
            self.add_terminal_output("SSH Connected")
        except Exception as e:
            self.add_terminal_output(f"SSH Failed to connect: {e}")
    """


    def fetch_topics(self):
        if self._topic_proc.state() != QProcess.NotRunning: return 
        self._topic_proc.start("/bin/bash", ["-c", "source /opt/ros/humble/setup.bash && ros2 topic list"])
        
    def start_rosbag(self):
        topics = self.get_selected_topics()
        name = self.rosbag_name.text().strip() or f"bag_{len(self.rosbag_recorders)}"

        if not topics: self.add_terminal_output("[WARN] No topics selected for recording"); return

        recorder = RosbagRecorder(topics=topics, compression=True, name=name)
        recorder.start()
        self.rosbag_recorders[name] = recorder
        self._add_rosbag_row(name)
        self.add_terminal_output(f"[INFO] Started rosbag '{name}': {topics}")
        
    def _add_rosbag_row(self, name: str):
        item = QtWidgets.QListWidgetItem().sizeHint(QtCore.QSize(0, 36))  # type: ignore
        item.setSizeHint(QtCore.QSize(0, 36))

        row_widget = QtWidgets.QWidget()
        row_widget.setStyleSheet("background: transparent;")
        layout = QtWidgets.QHBoxLayout(row_widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        label = QtWidgets.QLabel(name)
        label.setStyleSheet("color: white;")

        stop_btn = QtWidgets.QPushButton("Stop")
        stop_btn.setFixedWidth(70)
        stop_btn.setStyleSheet("background-color: red; color: white;")
        stop_btn.clicked.connect(lambda _, n=name: self.stop_rosbag(n))  # type: ignore

        layout.addWidget(label, stretch=1)
        layout.addWidget(stop_btn)

        self.rosbag_active_list.addItem(item)
        self.rosbag_active_list.setItemWidget(item, row_widget)

        # Store reference so stop_rosbag can find the item
        item.setData(Qt.UserRole, name)  # type: ignore

    def stop_rosbag(self, name: str):
        recorder = self.rosbag_recorders.pop(name, None)
        if recorder is not None:
            recorder.stop()   # adjust to whatever your RosbagRecorder API exposes
            self.add_terminal_output(f"[INFO] Stopped rosbag '{name}'")

        # Remove the row from the list widget
        for i in range(self.rosbag_active_list.count()):
            item = self.rosbag_active_list.item(i)
            if item.data(Qt.UserRole) == name:  # type: ignore
                self.rosbag_active_list.takeItem(i)
                break

    def _on_topics_fetched(self, exit_code: int, _):
        raw = bytes(self._topic_proc.readAllStandardOutput()).decode("utf-8", errors="replace")

        if exit_code != 0:
            self.add_terminal_output(f"[ERROR] ros2 topic list failed: {raw.strip()}")
            return

        topics = sorted(line.strip() for line in raw.splitlines() if line.strip())
        if not topics:
            return

        self.rosbag_topics.blockSignals(True)
        self.rosbag_topics.clear()
        for topic in topics:
            self.rosbag_topics.addItem(topic)
        self.rosbag_topics.setCurrentIndex(-1)
        self.rosbag_topics.blockSignals(False)


    def _on_topic_selected(self, index: int):
        topic = self.rosbag_topics.itemText(index)
        if topic not in [self.rosbag_selected_topics.item(i).text() for i in range(self.rosbag_selected_topics.count())]:
            self.rosbag_selected_topics.addItem(topic)
        self.rosbag_topics.setCurrentIndex(-1)


    def _remove_topic(self, item: QtWidgets.QListWidgetItem):
        self.rosbag_selected_topics.takeItem(self.rosbag_selected_topics.row(item))


    def get_selected_topics(self) -> list[str]:
        return [self.rosbag_selected_topics.item(i).text() for i in range(self.rosbag_selected_topics.count())]
    
    def on_proc_toggle(self, name: str, param: str, checked: bool):
        if checked:
            self.start_target(name, param)
        else:
            self.stop_target(name)
            
    def start_target(self, name: str, param: str):
        share_dir = get_package_share_directory("gui")
        script = os.path.join(share_dir, "scripts", "launch.sh")

        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels) # type: ignore
        p.readyReadStandardOutput.connect(lambda proc=p, k=name: self.on_proc_output(k, proc)) # type: ignore
        p.finished.connect(lambda exit_code, exit_status, k=name: self.on_proc_finished(k, exit_code, exit_status)) # type: ignore
        self.processes[name] = p

        self.add_terminal_output(f"Starting {name}")
        p.start("/bin/bash", [script, name, param])

        if name == "waypoints":
            self.launch_drone.setStyleSheet("background-color: red;")
            self.launch_drone.setText("Stop Drone")
        if name == "fsm":
            self.start_fsm.setStyleSheet("background-color: red;")
            self.start_fsm.setText("Stop FSM")

    def stop_target(self, name: str):
        p = self.processes.get(name)
        self.add_terminal_output(f"Stopping {name}")

        if p is not None:
            p.terminate()
            if not p.waitForFinished(10000):
                p.kill()

        if name == "waypoints":
            self.launch_drone.setText("Start Drone")

    def on_proc_output(self, key: str, proc: QProcess):
        data = proc.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        self.add_terminal_output(f"[{key}] {text.rstrip()}")

    def on_proc_finished(self, key: str, exit_code: int, exit_status):
        self.add_terminal_output(
            f"[{key}] Finished exit_code={exit_code}, exit_status={exit_status}"
        )
        self.processes.pop(key, None)

        if key == "waypoints":
            self.launch_drone.setText("Start waypoints")
            self.launch_drone.setStyleSheet("background-color: green;")

    def build_waypoint_payload(self):
        try:
            msg = WaypointMessage(
                mode=self.waypoint_mode.currentIndex(),
                convergence_cm=self.convergence_cm.text(),
                position={
                    "x": self.waypoint_pose_x.text(),
                    "y": self.waypoint_pose_y.text(),
                    "z": self.waypoint_pose_z.text()
                },
                rpy={
                    "roll": self.waypoint_pose_roll.text(),
                    "pitch": self.waypoint_pose_pitch.text(),
                    "yaw": self.waypoint_pose_yaw.text()
                }
            )
            self._executor.create_task(self._node.send_waypoint, msg)

        except Exception as e:
            self.terminal_output.appendPlainText(f"[WARN] Invalid input: {e}")

    def abort_waypoint(self):
        self._executor.create_task(self._node.abort_waypoint)
        
    def add_terminal_output(self, text: str):
        fmt = QTextCharFormat(self.DEFAULT_COLOR_FONT)

        if "INFO" in text or "info" in text:
            fmt.setForeground(QColor("blue"))
            self.terminal_output_2.setCurrentCharFormat(fmt)
            self.terminal_output_2.appendPlainText(text)
        elif "WARN" in text or "warning" in text:
            fmt.setForeground(QColor("orange"))
        elif "ERROR" in text or "error" in text:
            fmt.setForeground(QColor("red"))

        self.terminal_output.setCurrentCharFormat(fmt)
        self.terminal_output.appendPlainText(text)
        self.terminal_output.setCurrentCharFormat(self.DEFAULT_COLOR_FONT)
        
class GstVideoWidget(QWidget):
    def __init__(self, pipeline_desc: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #000;")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )

        self.setAttribute(QtCore.Qt.WidgetAttribute(97), True)  # ← keep X11 window alive

        self._pipeline_desc = pipeline_desc
        self._pipeline = None
        self._started = False

    def paintEngine(self):
        return None

    def showEvent(self, event):
        super().showEvent(event)
        if not self._started:
            self._started = True
            self.winId()
            QtWidgets.QApplication.processEvents()
            self.start()
        # No re-embed on subsequent shows — window handle never changes

    def start(self):
        self._pipeline = Gst.parse_launch(self._pipeline_desc)
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("sync-message::element", self._on_sync_message)
        self._pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        if self._pipeline:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None
        self._started = False

    def _on_sync_message(self, bus, msg):
        if msg.get_structure().get_name() == "prepare-window-handle":
            msg.src.set_window_handle(self.winId())

class GraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        

class StatisticsWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video")

        ports = [CAMERA_FRONT, CAMERA_BOTTOM]
        self.cam_widgets = []

        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(5, 5, 5, 5)
        grid.setSpacing(2)
        positions = [(0, 0), (0, 1)]

        for port, pos in zip(ports, positions):
            pipeline_desc = (
                f'udpsrc port={port} caps="application/x-rtp,media=video,'
                f'clock-rate=90000,encoding-name=H265,payload=96" '
                f'! rtph265depay ! h265parse ! avdec_h265 '
                f'! videoconvert ! xvimagesink name=sink sync=false'
            )

            widget = GstVideoWidget(pipeline_desc, parent=self)
            self.cam_widgets.append(widget)

            grid.addWidget(widget, pos[0], pos[1])
            grid.setRowStretch(pos[0], 1)
            grid.setColumnStretch(pos[1], 1)

        self.setLayout(grid)

    def stop(self):
        for w in self.cam_widgets:
            w.stop()

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    from gi.repository import GLib
    import threading
    Gst.init(None)
    
    app = QApplication(sys.argv)
    
    glib_loop = GLib.MainLoop()
    glib_thread = threading.Thread(target=glib_loop.run, daemon=True)
    glib_thread.start()

    bridge = RosBridge()

    rclpy.init()
    node = RosGuiNode(bridge)
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)

    ros_thread = RosSpinThread(executor)
    ros_thread.start()

    window = MainWindow(node, executor, bridge)
    window.show()

    app.exec()

    glib_loop.quit()          # stop GLib first
    glib_thread.join(timeout=2.0)
    ros_thread.stop()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
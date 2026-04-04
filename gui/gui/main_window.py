import os
import sys
import json
import tempfile

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QByteArray, QProcess, Qt
from PyQt5.QtGui import QGuiApplication, QTextCharFormat, QColor
from PyQt5.QtWidgets import QMainWindow, QWidget
import yaml
from .rosbag import RosbagRecorder

from ament_index_python.packages import get_package_share_directory

from .gui_ui import Ui_MainWindow
from .video_widget import StatisticsWindow


from .config import WAYPOINT_LAUNCH, ROS_NODE_LAUNCH, START_FSM

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # WINDOW MANAGER
        self.second_window = StatisticsWindow()

        one_window = True;
        if one_window:
            main_tab = self.centralWidget()
        
            tabs = QtWidgets.QTabWidget()
            tabs.setStyleSheet("color: white;")
            tabs.addTab(main_tab, "Controls")
            tabs.addTab(self.second_window, "Video")
            
            self.setCentralWidget(tabs)
        else:
            self.second_window.show_on_screen(1)
            
        self.vortex_logo.setPixmap(QtGui.QPixmap(os.path.join(get_package_share_directory("gui"), "resources", "logo.png")).scaled(400, 400, Qt.KeepAspectRatio))

        # VARIABLES
        self.DEFAULT_COLOR_FONT = self.terminal_output.currentCharFormat()
        self.processes: dict[str, QProcess] = {}
        
        self.build_param_panel()
        self.build_topic_selector()
        
        
        # ROS NODE SETUP
        self.ros_node = QProcess(self)
        self.ros_node.setProcessChannelMode(QProcess.MergedChannels)  # type: ignore
        self.ros_node.readyReadStandardOutput.connect(lambda: self.on_proc_output("ros_node", self.ros_node))  # type: ignore
        self.ros_node.start("python3", [ROS_NODE_LAUNCH])

        # BUTTON SIGNALS
        self.launch_drone.toggled.connect(lambda checked, k="waypoints": self.on_proc_toggle("waypoints", WAYPOINT_LAUNCH, checked))
        self.waypoint_submit.clicked.connect(self.build_waypoint_payload)
        self.waypoint_abort.clicked.connect(self.abort_waypoint)
        self.start_fsm.clicked.connect(lambda checked, k="fsm": self.on_proc_toggle("fsm", START_FSM, True))
   
            
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


    def fetch_topics(self):
        if self._topic_proc.state() != QProcess.NotRunning: return 
        self._topic_proc.start("/bin/bash", ["-c", "source /opt/ros/humble/setup.bash && ros2 topic list"])
        
    def start_rosbag(self):
        topics = self.get_selected_topics()
        self.rosbag_selected_topics.clear()
        name = self.rosbag_name.text().strip() or f"bag_{len(self.rosbag_recorders)}"

        if not topics: self.add_terminal_output("[WARN] No topics selected for recording"); return

        recorder = RosbagRecorder(topics=topics, compression=True, name=name)
        recorder.start()
        self.rosbag_recorders[name] = recorder
        self._add_rosbag_row(name)
        self.add_terminal_output(f"[INFO] Started rosbag '{name}': {topics}")
        
    def _add_rosbag_row(self, name: str):
        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(QtCore.QSize(0, 36))

        row_widget = QtWidgets.QWidget()
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

        item.setData(Qt.UserRole, name)  # type: ignore

    def stop_rosbag(self, name: str):
        recorder = self.rosbag_recorders.pop(name, None)
        if recorder is not None:
            recorder.stop() 
            self.add_terminal_output(f"[INFO] Stopped rosbag '{name}'")

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
   
   
    ###################
    # PROCESS HANDLER #
    ###################

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

    ####################
    # WAYPOINT HANDLER #
    ####################

    @staticmethod
    def waypoint_parse(text: str, default: float = 0.0):
        try:
            return float(text.strip())
        except ValueError:
            return default

    def build_waypoint_payload(self):
        try:
            mode = self.waypoint_mode.currentIndex()
            convergence_threshold = self.waypoint_parse(self.waypoint_cm.text(), default=0.1)

            x = self.waypoint_parse(self.waypoint_pose_x.text())
            y = self.waypoint_parse(self.waypoint_pose_y.text())
            z = self.waypoint_parse(self.waypoint_pose_z.text())
            roll = self.waypoint_parse(self.waypoint_pose_roll.text())
            pitch = self.waypoint_parse(self.waypoint_pose_pitch.text())
            yaw = self.waypoint_parse(self.waypoint_pose_yaw.text())

            msg = {
                "type": "waypoint",
                "mode": mode,
                "convergence_cm": convergence_threshold,
                "position": {"x": x, "y": y, "z": z},
                "rpy": {"roll": roll, "pitch": pitch, "yaw": yaw},
            }
            self.send_message(msg)

        except Exception as e:
            self.terminal_output.appendPlainText(f"[WARN] Invalid input: {e}")

    def abort_waypoint(self):
        msg = {"type": "abort_waypoint"}
        self.send_message(msg)

    ##################
    # HELPER METHODS #
    ##################

    def send_message(self, msg: dict | None):
        if msg is None:
            return
        line = (json.dumps(msg) + "\n").encode("utf-8")
        self.ros_node.write(QByteArray(line))
        
    def on_ros_node_output(self):
        data = bytes(self.ros_node.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self.add_terminal_output(data)

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


    ##########
    # PARAMS #
    ##########
    
    def build_param_panel(self):
        panel = QWidget()
        panel.setStyleSheet("background-color: #333; color: white;")
        layout = QtWidgets.QVBoxLayout(panel)
        
        top = QtWidgets.QHBoxLayout()
        self.param_node_input = QtWidgets.QLineEdit(placeholderText="Node name") # type: ignore 
        self.fetch_params_button = QtWidgets.QPushButton("Load Params")
        self.fetch_params_button.clicked.connect(self.fetch_params) # type: ignore
        top.addWidget(self.param_node_input, stretch=1)
        top.addWidget(self.fetch_params_button)
        
        self.param_table = QtWidgets.QTableWidget(0,2)
        self.param_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.param_table.horizontalHeader().setStretchLastSection(True)
        self.param_table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
        self.param_table.itemChanged.connect(self.on_param_changed) # type: ignore
        self.modified_params: set[str] = set()
        
        self.apply_button = QtWidgets.QPushButton("Apply Changes")
        self.apply_button.clicked.connect(self.apply_param_changes) # type: ignore
        
        layout.addLayout(top)
        layout.addWidget(self.param_table)
        layout.addWidget(self.apply_button)
        
        # Process
        self.dump_proc = QProcess(self)
        self.dump_proc.setProcessChannelMode(QProcess.MergedChannels) # type: ignore
        self.dump_proc.finished.connect(self.on_dump_finished) # type: ignore
        
        self.widget.layout().addWidget(panel)
        
    
    def fetch_params(self):
        node = self.param_node_input.text().strip()
        if not node:
            self.add_terminal_output("[WARN] Node name cannot be empty")
            return

        self.modified_params.clear()
        self.fetch_params_button.setEnabled(False)
        self.add_terminal_output(f"Fetching parameters for node '{node}'...")

        node_filename = node.lstrip("/").replace("/", "_") + ".yaml"
        self.dump_tmp_dir = tempfile.mkdtemp()
        self.dump_tmp_file = os.path.join(self.dump_tmp_dir, node_filename)

        self.dump_proc.start(
            "/bin/bash",
            ["-c", f"source /opt/ros/humble/setup.bash && ros2 param dump {node} --output-dir {self.dump_tmp_dir}"]
        )

    def on_dump_finished(self, exit_code, _):
        self.fetch_params_button.setEnabled(True)
        err = bytes(self.dump_proc.readAllStandardOutput()).decode("utf-8", errors="replace").strip()

        if exit_code != 0:
            self.add_terminal_output(f"[ERROR] ros2 param dump failed: {err}")
            return

        try:
            with open(self.dump_tmp_file) as f:
                raw = f.read()
        except FileNotFoundError:
            self.add_terminal_output(f"[ERROR] Dump file not found: {self.dump_tmp_file}")
            return
        finally:
            import shutil
            shutil.rmtree(self.dump_tmp_dir, ignore_errors=True)

        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            self.add_terminal_output(f"[ERROR] Failed to parse YAML: {e}")
            return

        node = self.param_node_input.text().strip()
        try:
            params = data[node]["ros__parameters"]
        except (KeyError, TypeError):
            params = next(iter(data.values()), {}).get("ros__parameters", {})

        self.add_terminal_output(f"[INFO] Loaded {len(params)} parameters from {node}")
        self.populate_param_table(params)
        
    def populate_param_table(self, params: dict):
        self.param_table.blockSignals(True)
        self.param_table.setRowCount(0)
        
        for name, value in params.items():
            if (name == "qos_overrides" or name == "use_sim_time"):
                continue
            
            row = self.param_table.rowCount()
            self.param_table.insertRow(row)
            
            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable) # type: ignore
            
            val_item = QtWidgets.QTableWidgetItem(str(value))
            val_item.setData(Qt.UserRole, str(value)) # type: ignore
            
            self.param_table.setItem(row, 0, name_item)
            self.param_table.setItem(row, 1, val_item)

        self.param_table.blockSignals(False)
        
    def on_param_changed(self, item: QtWidgets.QTableWidgetItem):
        if item.column() != 1:
            return
        original = item.data(Qt.UserRole)
        name = self.param_table.item(item.row(), 0).text()
        
        if item.text() != original:
            self.modified_params.add(name)
            item.setForeground(QColor("orange"))
        else:
            self.modified_params.discard(name)
            item.setForeground(QColor("black"))
    
    def apply_param_changes(self):
        if not self.modified_params:
            self.add_terminal_output("[INFO] No parameter changes to apply")
            return
        
        node = self.param_node_input.text().strip()
        ros_params = {}
        
        for row in range(self.param_table.rowCount()):
            name = self.param_table.item(row, 0).text()
            if name in self.modified_params:
                ros_params[name] = self.param_table.item(row, 1).text()
        
        yaml_data = {node: {"ros__parameters": ros_params}}
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", prefix="ros2_params_", delete=False
        )
        yaml.dump(yaml_data, tmp)
        tmp.close()
        
        self.add_terminal_output(f"[INFO] Applying parameter changes to node")
        
        load_proc = QProcess(self)
        load_proc.setProcessChannelMode(QProcess.MergedChannels) # type: ignore
        load_proc.finished.connect( #type: ignore
            lambda code, _, p=load_proc, f=tmp.name: self.on_load_finished(code, p, f)
        )
        load_proc.start("ros2", ["param", "load", node, tmp.name])
        
    def on_load_finished(self, exit_code, proc: QProcess, tmp_file: str):
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        if exit_code == 0:
            self.add_terminal_output(f"[INFO] Parameters applied successfully: {out}")
            self.modified_params.clear()
            self.param_table.blockSignals(True)
            for row in range(self.param_table.rowCount()):
                item = self.param_table.item(row, 1)
                item.setForeground(QColor("black"))
                item.setData(Qt.UserRole, item.text())
            self.param_table.blockSignals(False)
        else:
            self.add_terminal_output(f"[ERROR] Failed to apply parameters: {out}")
        os.unlink(tmp_file)
        
    ###########
    # CLEANUP #
    ###########
    
    def closeEvent(self, a0: QtGui.QCloseEvent):
        self.ros_node.readyReadStandardOutput.disconnect() # type: ignore
        
        for _, p in list(self.processes.items()):
            p.readyReadStandardOutput.disconnect() # type: ignore
            p.finished.disconnect() # type: ignore
            p.terminate()
            if not p.waitForFinished(5000):

                p.kill()
        
        self.ros_node.terminate()
        if not self.ros_node.waitForFinished(5000):
            self.ros_node.kill()
            
        a0.accept()
    
                

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.showFullScreen()
    rc = app.exec_()
    sys.exit(rc)


if __name__ == "__main__":
    main()
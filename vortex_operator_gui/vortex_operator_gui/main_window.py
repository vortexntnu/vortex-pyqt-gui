"""Qt main window for the operator GUI.

Widgets are built in code (no .ui file) so the whole interface is readable and
diff-friendly in one place. The window connects to the GuiNode's signals for
live updates and calls the node's command methods on button presses.
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vortex_msgs.msg import OperationMode, WaypointMode

from .ros_interface import OPERATION_MODE_NAMES

# Waypoint modes in display order: (label, enum value).
WAYPOINT_MODES = [
    ('Full pose', WaypointMode.FULL_POSE),
    ('Only position', WaypointMode.ONLY_POSITION),
    ('Forward heading', WaypointMode.FORWARD_HEADING),
    ('Only orientation', WaypointMode.ONLY_ORIENTATION),
    ('Position and yaw', WaypointMode.POSITION_AND_YAW),
    ('XY and yaw', WaypointMode.XY_AND_YAW),
    ('XY forward dir', WaypointMode.XY_FORWARD_DIR),
    ('Level orientation', WaypointMode.LEVEL_ORIENTATION),
    ('Only Z', WaypointMode.ONLY_Z),
    ('Pos Z + level orientation', WaypointMode.POS_Z_LEVEL_ORIENTATION),
]

# Which pose fields each mode actually consumes. This mirrors
# compute_waypoint_goal() in vortex-utils/.../waypoint_utils.cpp: any field that
# the controller overrides with the current state is NOT an operator input and
# is greyed out here.
MODE_FIELDS = {
    WaypointMode.FULL_POSE: {'x', 'y', 'z', 'roll', 'pitch', 'yaw'},
    WaypointMode.ONLY_POSITION: {'x', 'y', 'z'},
    WaypointMode.FORWARD_HEADING: {'x', 'y', 'z'},        # heading auto from path
    WaypointMode.ONLY_ORIENTATION: {'roll', 'pitch', 'yaw'},
    WaypointMode.POSITION_AND_YAW: {'x', 'y', 'z', 'yaw'},  # roll/pitch leveled
    WaypointMode.XY_AND_YAW: {'x', 'y', 'yaw'},           # z held at current
    WaypointMode.XY_FORWARD_DIR: {'x', 'y'},              # z held, heading auto
    WaypointMode.LEVEL_ORIENTATION: set(),                # pos + yaw from current
    WaypointMode.ONLY_Z: {'z'},
    WaypointMode.POS_Z_LEVEL_ORIENTATION: {'z'},          # x/y/yaw from current
}


class MainWindow(QMainWindow):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setWindowTitle('Vortex Operator GUI')

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.addWidget(self._build_status_group())
        root.addWidget(self._build_command_group())
        if node.mission == 'pipeline':
            root.addWidget(self._build_pipeline_group())
        root.addWidget(self._build_waypoint_group())
        root.addWidget(self._build_status_log())

        self._connect_signals()
        self._update_field_states()

        # Poll the live operation-mode / killswitch display at 1 Hz.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.node.refresh_status)
        self._timer.start(1000)

    # -- status display ------------------------------------------------------
    def _build_status_group(self):
        box = QGroupBox('Status')
        layout = QFormLayout(box)
        self.conn_label = QLabel('connecting…')
        self.mode_label = QLabel('---')
        self.kill_label = QLabel('---')
        for lbl in (self.mode_label, self.kill_label, self.conn_label):
            font = lbl.font()
            font.setBold(True)
            lbl.setFont(font)
        layout.addRow('Connection:', self.conn_label)
        layout.addRow('Operation mode:', self.mode_label)
        layout.addRow('Killswitch:', self.kill_label)
        return box

    # -- mode / killswitch / mission commands --------------------------------
    def _build_command_group(self):
        box = QGroupBox('Commands')
        layout = QVBoxLayout(box)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('Set mode:'))
        for value in (OperationMode.AUTONOMOUS, OperationMode.MANUAL, OperationMode.REFERENCE):
            btn = QPushButton(OPERATION_MODE_NAMES[value])
            btn.clicked.connect(lambda _, v=value: self.node.set_operation_mode(v))
            mode_row.addWidget(btn)
        layout.addLayout(mode_row)

        kill_row = QHBoxLayout()
        kill_row.addWidget(QLabel('Killswitch:'))
        on_btn = QPushButton('ON')
        on_btn.clicked.connect(lambda: self.node.set_killswitch(True))
        off_btn = QPushButton('OFF')
        off_btn.clicked.connect(lambda: self.node.set_killswitch(False))
        kill_row.addWidget(on_btn)
        kill_row.addWidget(off_btn)
        layout.addLayout(kill_row)

        mission_row = QHBoxLayout()
        start = QPushButton('Start mission')
        start.clicked.connect(self.node.start_mission)
        reset = QPushButton('Reset origin')
        reset.clicked.connect(self.node.reset_origin)
        wipe = QPushButton('Wipe (mission/wipe)')
        wipe.clicked.connect(self.node.publish_wipe)
        mission_row.addWidget(start)
        mission_row.addWidget(reset)
        mission_row.addWidget(wipe)
        layout.addLayout(mission_row)
        return box

    # -- pipeline mission controls -------------------------------------------
    def _build_pipeline_group(self):
        box = QGroupBox('Pipeline mission')
        layout = QVBoxLayout(box)

        row = QHBoxLayout()

        start_mission_btn = QPushButton('Start mission')
        start_mission_btn.setToolTip('services.start_mission — kicks off the whole mission')
        start_mission_btn.clicked.connect(self.node.start_mission)

        start_following_btn = QPushButton('Start pipeline following')
        start_following_btn.setToolTip(
            'services.start_pipeline_following_trigger — releases the gate to '
            'start pipeline following')
        start_following_btn.clicked.connect(self.node.start_pipeline_following_trigger)

        end_pipeline_btn = QPushButton('End of pipeline')
        end_pipeline_btn.setToolTip(
            'services.end_of_pipeline — tell the FSM the pipeline has ended')
        end_pipeline_btn.clicked.connect(self.node.end_of_pipeline)

        row.addWidget(start_mission_btn)
        row.addWidget(start_following_btn)
        row.addWidget(end_pipeline_btn)
        layout.addLayout(row)
        return box

    # -- waypoint sender -----------------------------------------------------
    def _build_waypoint_group(self):
        box = QGroupBox('Send waypoint')
        layout = QVBoxLayout(box)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('Waypoint mode:'))
        self.mode_combo = QComboBox()
        for label, value in WAYPOINT_MODES:
            self.mode_combo.addItem(label, value)
        self.mode_combo.currentIndexChanged.connect(self._update_field_states)
        mode_row.addWidget(self.mode_combo, 1)
        layout.addLayout(mode_row)

        # Pose inputs in a grid: position (m) and orientation (deg).
        grid = QGridLayout()
        self.pose_fields = {}
        pose_spec = [
            ('x', 'X [m]', -10000, 10000), ('roll', 'Roll [deg]', -180, 180),
            ('y', 'Y [m]', -10000, 10000), ('pitch', 'Pitch [deg]', -180, 180),
            ('z', 'Z / depth [m]', -10000, 10000), ('yaw', 'Yaw [deg]', -180, 180),
        ]
        for i, (key, text, lo, hi) in enumerate(pose_spec):
            lbl = QLabel(text)
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            row, col = divmod(i, 2)
            grid.addWidget(lbl, row, col * 2)
            grid.addWidget(spin, row, col * 2 + 1)
            self.pose_fields[key] = (lbl, spin)
        layout.addLayout(grid)

        # Altitude controls.
        alt_row = QHBoxLayout()
        self.keep_alt_chk = QCheckBox('Keep altitude')
        self.keep_alt_chk.stateChanged.connect(self._update_field_states)
        self.des_alt_lbl = QLabel('Desired altitude [m]:')
        self.des_alt_spin = QDoubleSpinBox()
        self.des_alt_spin.setRange(0.0, 10000.0)
        self.des_alt_spin.setDecimals(3)
        self.des_alt_spin.setValue(1.0)
        self.req_conv_chk = QCheckBox('Require altitude convergence')
        alt_row.addWidget(self.keep_alt_chk)
        alt_row.addWidget(self.des_alt_lbl)
        alt_row.addWidget(self.des_alt_spin)
        alt_row.addWidget(self.req_conv_chk)
        alt_row.addStretch(1)
        layout.addLayout(alt_row)

        # Send / cancel. Goals always overwrite the current one (single
        # waypoint at a time), so no extra options are exposed.
        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel('Convergence threshold:'))
        self.conv_spin = QDoubleSpinBox()
        self.conv_spin.setRange(0.0, 100.0)
        self.conv_spin.setDecimals(3)
        self.conv_spin.setSingleStep(0.05)
        self.conv_spin.setValue(0.5)
        btn_row.addWidget(self.conv_spin)
        btn_row.addStretch(1)
        cancel_btn = QPushButton('Cancel current')
        cancel_btn.clicked.connect(self.node.cancel_waypoint)
        send_btn = QPushButton('Send waypoint')
        send_btn.clicked.connect(self._on_send_waypoint)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(send_btn)
        layout.addLayout(btn_row)
        return box

    def _build_status_log(self):
        box = QGroupBox('Status messages')
        layout = QVBoxLayout(box)
        self.status_label = QLabel('—')
        font = self.status_label.font()
        font.setBold(True)
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log)
        return box

    # -- greying logic -------------------------------------------------------
    def _update_field_states(self):
        mode = self.mode_combo.currentData()
        active = MODE_FIELDS.get(mode, set())
        keep_alt = self.keep_alt_chk.isChecked()
        for key, (lbl, spin) in self.pose_fields.items():
            enabled = key in active
            # When holding altitude, Z/depth is controlled by altitude instead.
            if key == 'z' and keep_alt:
                enabled = False
            lbl.setEnabled(enabled)
            spin.setEnabled(enabled)
        self.des_alt_lbl.setEnabled(keep_alt)
        self.des_alt_spin.setEnabled(keep_alt)
        self.req_conv_chk.setEnabled(keep_alt)

    def _on_send_waypoint(self):
        self.node.send_waypoint({
            'x': self.pose_fields['x'][1].value(),
            'y': self.pose_fields['y'][1].value(),
            'z': self.pose_fields['z'][1].value(),
            'roll': self.pose_fields['roll'][1].value(),
            'pitch': self.pose_fields['pitch'][1].value(),
            'yaw': self.pose_fields['yaw'][1].value(),
            'mode': self.mode_combo.currentData(),
            'keep_altitude': self.keep_alt_chk.isChecked(),
            'desired_altitude': self.des_alt_spin.value(),
            'require_altitude_convergence': self.req_conv_chk.isChecked(),
            'convergence_threshold': self.conv_spin.value(),
        })

    # -- signal wiring + slots ----------------------------------------------
    def _connect_signals(self):
        s = self.node.signals
        s.operation_mode.connect(self._on_operation_mode)
        s.killswitch.connect(self._on_killswitch)
        s.status.connect(self._on_status)
        s.waypoint_feedback.connect(self.status_label.setText)
        s.connected.connect(self._on_connected)

    def _on_operation_mode(self, value):
        self.mode_label.setText(OPERATION_MODE_NAMES.get(value, f'UNKNOWN ({value})'))

    def _on_killswitch(self, engaged):
        self.kill_label.setText('ON' if engaged else 'OFF')
        self.kill_label.setStyleSheet(
            'color: #c0392b;' if engaged else 'color: #27ae60;')

    def _on_status(self, text):
        self.status_label.setText(text)
        self.log.appendPlainText(text)

    def _on_connected(self, connected):
        self.conn_label.setText('online' if connected else 'offline')
        self.conn_label.setStyleSheet(
            'color: #27ae60;' if connected else 'color: #c0392b;')

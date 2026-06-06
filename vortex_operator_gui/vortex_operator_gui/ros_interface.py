"""ROS 2 side of the operator GUI.

The :class:`GuiNode` owns all clients/publishers and runs inside a background
executor thread. It never touches Qt widgets directly; instead it emits Qt
signals (via :class:`RosSignals`) that the GUI thread connects to. This is the
golden rule for ROS + Qt: ROS callbacks run off the GUI thread, so all
communication back to the widgets goes through thread-safe signals.
"""

import math

from PyQt5.QtCore import QObject, pyqtSignal

from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)

from std_msgs.msg import Bool, Empty
from std_srvs.srv import Trigger

from geometry_msgs.msg import Point, Quaternion
from vortex_msgs.action import WaypointManager
from vortex_msgs.msg import OperationMode, Waypoint
from vortex_msgs.srv import (
    GetOperationMode,
    SetKillswitch,
    SetOperationMode,
)

# Human-readable names for the OperationMode enum.
OPERATION_MODE_NAMES = {
    OperationMode.AUTONOMOUS: 'AUTONOMOUS',
    OperationMode.MANUAL: 'MANUAL',
    OperationMode.REFERENCE: 'REFERENCE',
}


def quaternion_from_euler(roll: float, pitch: float, yaw: float) -> Quaternion:
    """Convert roll/pitch/yaw (radians) to a geometry_msgs/Quaternion."""
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    q = Quaternion()
    q.w = cr * cp * cy + sr * sp * sy
    q.x = sr * cp * cy - cr * sp * sy
    q.y = cr * sp * cy + sr * cp * sy
    q.z = cr * cp * sy - sr * sp * cy
    return q


class RosSignals(QObject):
    """Thread-safe bridge from ROS callbacks to the Qt GUI thread."""

    operation_mode = pyqtSignal(int)     # OperationMode.operation_mode value
    killswitch = pyqtSignal(bool)        # True == killswitch engaged
    status = pyqtSignal(str)             # free-form status line (also logged)
    waypoint_feedback = pyqtSignal(str)  # live tracking line (not logged)
    connected = pyqtSignal(bool)         # is the status service reachable


class GuiNode(Node):
    """rclpy node holding every client/publisher used by the GUI."""

    def __init__(self):
        super().__init__('operator_gui_node')

        # Endpoint names come from the robot config (e.g. nautilus.yaml), loaded
        # by the launch file. Names are relative; the node's namespace (set at
        # launch, e.g. /nautilus) resolves them to /nautilus/<name>.
        names = {
            'set_operation_mode': self._p('services.set_operation_mode', 'set_operation_mode'),
            'set_killswitch': self._p('services.set_killswitch', 'set_killswitch'),
            'get_operation_mode': self._p('services.get_operation_mode', 'get_operation_mode'),
            'start_mission': self._p('services.start_mission', 'start_mission'),
            'reset_odom_origin': self._p('services.reset_odom_origin', 'reset_odom_origin'),
            'waypoint_manager': self._p('action_servers.waypoint_manager', 'waypoint_manager'),
            'mission_wipe': self._p('topics.mission_wipe', 'mission/wipe'),
            'operation_mode': self._p('topics.operation_mode', 'operation_mode'),
            'killswitch': self._p('topics.killswitch', 'killswitch'),
        }

        self.signals = RosSignals()

        self._set_op_cli = self.create_client(SetOperationMode, names['set_operation_mode'])
        self._set_kill_cli = self.create_client(SetKillswitch, names['set_killswitch'])
        self._get_op_cli = self.create_client(GetOperationMode, names['get_operation_mode'])
        # reset_odom_origin is std_srvs/Trigger (odom_transformer.cpp). start_mission
        # type was not found in the workspace; std_srvs/Trigger is assumed there.
        self._start_mission_cli = self.create_client(Trigger, names['start_mission'])
        self._reset_origin_cli = self.create_client(Trigger, names['reset_odom_origin'])
        self._wp_action = ActionClient(self, WaypointManager, names['waypoint_manager'])
        self._current_goal = None

        self._wipe_pub = self.create_publisher(Empty, names['mission_wipe'], 10)

        # Live state also arrives over topics, which the operation_mode_manager
        # publishes on every change (event-driven) — far faster than the 1 Hz
        # service poll. The topics are Reliable/Volatile/KeepLast(1), so we must
        # match that QoS, and a late-joining GUI gets nothing until the next
        # change: the service poll (refresh_status) still provides the initial
        # sync and the connection/liveness signal. The two are complementary.
        status_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self._op_mode_sub = self.create_subscription(
            OperationMode, names['operation_mode'], self._on_op_mode_msg, status_qos)
        self._kill_sub = self.create_subscription(
            Bool, names['killswitch'], self._on_kill_msg, status_qos)

        self.get_logger().info(
            f'Operator GUI node started (namespace: {self.get_namespace()})')

    def _p(self, name: str, default: str) -> str:
        return self.declare_parameter(name, default).value

    # -- generic async service call -----------------------------------------
    def _call(self, client, request, label, on_response=None):
        if not client.service_is_ready():
            self.signals.status.emit(f'{label}: service unavailable ({client.srv_name})')
            return
        future = client.call_async(request)

        def _done(fut):
            try:
                resp = fut.result()
            except Exception as exc:  # noqa: BLE001 - surface any failure to the GUI
                self.signals.status.emit(f'{label}: failed ({exc})')
                return
            if on_response is not None:
                on_response(resp)
            else:
                ok = getattr(resp, 'success', True)
                self.signals.status.emit(f"{label}: {'OK' if ok else 'rejected'}")

        future.add_done_callback(_done)

    def _apply_status_response(self, resp, label):
        """Update displays from any response carrying mode + killswitch."""
        self.signals.operation_mode.emit(resp.current_operation_mode.operation_mode)
        self.signals.killswitch.emit(resp.killswitch_status)
        self.signals.status.emit(f"{label}: {'OK' if resp.success else 'rejected'}")

    # -- live status subscriptions -------------------------------------------
    def _on_op_mode_msg(self, msg: OperationMode):
        """Instant operation-mode update pushed by the operation_mode_manager."""
        self.signals.operation_mode.emit(msg.operation_mode)

    def _on_kill_msg(self, msg: Bool):
        """Instant killswitch update pushed by the operation_mode_manager."""
        self.signals.killswitch.emit(msg.data)

    # -- status polling ------------------------------------------------------
    def refresh_status(self):
        """Poll get_operation_mode for initial sync, periodic resync and the
        connection/liveness signal. Live changes arrive faster via the topic
        subscriptions above; this guarantees the display is correct even for a
        GUI that started after the manager (the topics are volatile)."""
        if not self._get_op_cli.service_is_ready():
            self.signals.connected.emit(False)
            return
        future = self._get_op_cli.call_async(GetOperationMode.Request())

        def _done(fut):
            try:
                resp = fut.result()
            except Exception:  # noqa: BLE001
                self.signals.connected.emit(False)
                return
            self.signals.connected.emit(True)
            self.signals.operation_mode.emit(resp.current_operation_mode.operation_mode)
            self.signals.killswitch.emit(resp.killswitch_status)

        future.add_done_callback(_done)

    # -- commands ------------------------------------------------------------
    def set_operation_mode(self, mode_value: int):
        req = SetOperationMode.Request()
        req.requested_operation_mode.operation_mode = mode_value
        label = f'Set mode {OPERATION_MODE_NAMES.get(mode_value, mode_value)}'
        self._call(self._set_op_cli, req, label,
                   lambda r: self._apply_status_response(r, label))

    def set_killswitch(self, engaged: bool):
        req = SetKillswitch.Request()
        req.killswitch_on = engaged
        label = f"Killswitch {'ENGAGE' if engaged else 'RELEASE'}"
        self._call(self._set_kill_cli, req, label,
                   lambda r: self._apply_status_response(r, label))

    def start_mission(self):
        self._call(self._start_mission_cli, Trigger.Request(), 'Start mission')

    def reset_origin(self):
        self._call(self._reset_origin_cli, Trigger.Request(), 'Reset origin')

    def publish_wipe(self):
        self._wipe_pub.publish(Empty())
        self.signals.status.emit('Published mission/wipe (Empty)')

    # -- waypoint action -----------------------------------------------------
    def send_waypoint(self, wp: dict):
        """Send a single waypoint as a WaypointManager action goal.

        Only one waypoint at a time is supported: any in-flight goal is
        cancelled first (always overwrite / take priority).
        """
        if not self._wp_action.server_is_ready():
            self.signals.status.emit('Send waypoint: action server unavailable')
            return

        if self._current_goal is not None:
            self._current_goal.cancel_goal_async()
            self._current_goal = None

        waypoint = Waypoint()
        waypoint.pose.position = Point(x=wp['x'], y=wp['y'], z=wp['z'])
        waypoint.pose.orientation = quaternion_from_euler(
            math.radians(wp['roll']), math.radians(wp['pitch']), math.radians(wp['yaw'])
        )
        waypoint.waypoint_mode.mode = wp['mode']
        waypoint.keep_altitude = wp['keep_altitude']
        waypoint.desired_altitude = wp['desired_altitude']
        waypoint.require_altitude_convergence = wp['require_altitude_convergence']

        goal = WaypointManager.Goal()
        goal.waypoints = [waypoint]
        goal.convergence_threshold = wp['convergence_threshold']
        goal.persistent = False

        self.signals.status.emit('Send waypoint: sending goal…')
        future = self._wp_action.send_goal_async(goal, feedback_callback=self._wp_feedback)
        future.add_done_callback(self._wp_goal_response)

    def cancel_waypoint(self):
        if self._current_goal is None:
            self.signals.status.emit('No active waypoint goal to cancel')
            return
        self._current_goal.cancel_goal_async()
        self.signals.status.emit('Cancelling waypoint goal…')

    def _wp_goal_response(self, future):
        handle = future.result()
        if not handle.accepted:
            self.signals.status.emit('Waypoint goal rejected')
            return
        self._current_goal = handle
        self.signals.status.emit('Waypoint goal accepted')
        handle.get_result_async().add_done_callback(self._wp_result)

    def _wp_result(self, future):
        result = future.result().result
        self.signals.status.emit(
            f"Waypoint result: {'success' if result.success else 'failure'}")
        self._current_goal = None

    def _wp_feedback(self, feedback_msg):
        p = feedback_msg.feedback.current_waypoint.pose.position
        self.signals.waypoint_feedback.emit(
            f'Tracking waypoint ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})')

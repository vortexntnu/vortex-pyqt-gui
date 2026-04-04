import sys
import json
import threading


import rclpy.executors

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from geometry_msgs.msg import PointStamped, Point, Quaternion
from vortex_msgs.msg import Waypoint, WaypointMode
from vortex_msgs.action import WaypointManager

from vortex_utils.python_utils import euler_to_quat


class GuiNode(Node):
    def __init__(self):
        super().__init__("gui_node")

        self._action_client = ActionClient(
            self, WaypointManager, "/orca/waypoint_manager"
        )

        self.get_logger().info("GUI Node Started")

        self.current_goal_handle = None

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

    def convert_to_waypoint_goal(self, msg: dict):
        try:
            pos = msg["position"]
            rpy = msg["rpy"]

            goal = WaypointManager.Goal()
            wp_mode = WaypointMode()
            wp = Waypoint()
            

            wp.pose.position = Point(
                x=float(pos["x"]),
                y=float(pos["y"]),
                z=float(pos["z"]),
            )

            q = euler_to_quat(
                float(rpy["roll"]),
                float(rpy["pitch"]),
                float(rpy["yaw"]),
            )
            wp.pose.orientation = Quaternion(x=q[0], y=q[1], z=q[2], w=q[3])
            wp_mode.mode = msg["mode"]
            wp.waypoint_mode = wp_mode
            
            goal.waypoints = [wp]
            goal.convergence_threshold = float(msg["convergence_cm"])
            goal.persistent = False

            return goal

        except (KeyError, ValueError, TypeError) as e:
            self.get_logger().warn(f"Invalid payload: {e}")
            return None

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


def stdin_loop(node: GuiNode, executor: rclpy.executors.SingleThreadedExecutor):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            node.get_logger().warn(f"Bad JSON: {e}")
            continue

        msg_type = msg.get("type")
        if msg_type == "abort_waypoint":
            executor.create_task(node.abort_waypoint)
        elif msg_type == "waypoint":
            goal = node.convert_to_waypoint_goal(msg)
            if goal is not None:
                executor.create_task(node.send_waypoint, goal)


def main():
    rclpy.init()
    node = GuiNode()
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)

    t = threading.Thread(target=stdin_loop, args=(node, executor), daemon=True)
    t.start()

    executor.spin()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
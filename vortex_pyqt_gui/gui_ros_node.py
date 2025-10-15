from rclpy.node import Node
import numpy as np
import time
import subprocess

from std_msgs.msg import Int32
from std_msgs.msg import Float32

import importlib

from PyQt6 import QtGui


def get_msg_class(type_str):
    pkg, _, msg = type_str.partition("/msg/")
    module = importlib.import_module(f"{pkg}.msg")
    return getattr(module, msg)

class MyGuiNode(Node):
    def __init__(self, ui):
        super().__init__("ros2_hmi_node")
        self.ui = ui
        
        session_name = "add_two_ints_server"
        result = subprocess.run(f"tmux has-session -t {session_name}", shell=True)
        if result.returncode == 0:
            subprocess.run(f"tmux kill-session -t {session_name}", shell=True)
        else:
            self.get_logger().info("Session is not running")


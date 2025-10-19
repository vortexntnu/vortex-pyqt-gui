from rclpy.node import Node
import numpy as np
import time
import subprocess

from std_msgs.msg import Int32, Float32, String
from .auv_data_subscriber import AUVDataSubscriber
import importlib

from PyQt6 import QtGui
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

import pyqtgraph.opengl as gl


def get_msg_class(type_str):
    pkg, _, msg = type_str.partition("/msg/")
    module = importlib.import_module(f"{pkg}.msg")
    return getattr(module, msg)

class MyGuiNode(Node):
    def __init__(self, ui):

        super().__init__("Vortex_GUI_Node")
        self.ui = ui

        # Check if node setup has started
        self.get_logger().info("Node setup begun")

        # Initialize the subscriber node
        self.data_subscriber = AUVDataSubscriber(self.ui)

        # Set up a timer callback every 100 ms
        self.timer = QTimer()
        self.timer.timeout.connect(self.timer_callback)
        self.timer.start(100)

        # Create GL widget
        self.gl_view = gl.GLViewWidget()
        self.ui.rendererGrpBox.layout().addWidget(self.gl_view)
        self.gl_view.opts['distance'] = 40

        # Add coordinate axes
        axes = gl.GLAxisItem()
        axes.setSize(10,10,10)
        self.gl_view.addItem(axes)

        # Check if node setup has completed
        self.get_logger().info("Node setup properly")

    def timer_callback(self):
        pass


"""Entry point: spins the rclpy node in a background thread and runs Qt."""

import signal
import sys
import threading

import rclpy
from rclpy.executors import MultiThreadedExecutor

from PyQt5.QtWidgets import QApplication

from .main_window import MainWindow
from .ros_interface import GuiNode


def main(args=None):
    rclpy.init(args=args)
    node = GuiNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    # Let Ctrl-C in the terminal close the app.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    window = MainWindow(node)
    window.show()

    try:
        exit_code = app.exec_()
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()

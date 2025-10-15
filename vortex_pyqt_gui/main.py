import sys
import rclpy
from rclpy.executors import MultiThreadedExecutor

from PyQt6 import QtWidgets
from threading import Thread

from .gui_layout import Ui_MainWindow
from .gui_ros_node import MyGuiNode


def main(args=None):
    rclpy.init(args=args)
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)

    Vortex_Gui_Node  = MyGuiNode(ui)

    # Now we create a thread for the app, and let the ROS
    # node spin on the main thread
    executor = MultiThreadedExecutor()
    executor.add_node(Vortex_Gui_Node)
    executor.add_node(Vortex_Gui_Node.data_subscriber)

    thread = Thread(target=executor.spin)
    thread.start()
    Vortex_Gui_Node.get_logger().info("Spinning ROS node.")

    try:
        MainWindow.show()
        sys.exit(app.exec())

    finally:
        Vortex_Gui_Node.get_logger().info("Shutting down ROS node.")
        Vortex_Gui_Node.destroy_node()
        executor.shutdown()

if __name__ == '__main__':
    main()


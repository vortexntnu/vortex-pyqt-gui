import sys
import rclpy
from threading import Thread
from rclpy.executors import MultiThreadedExecutor
from PyQt5 import QtWidgets
import pyqtgraph as pg

from gui_node import GuiNode
from ros_bridge import RosBridge

class pyqt_plot_widget(pg.PlotWidget):
    def __init__(self, title="Test", parent=None):
        super().__init__(parent)
        self.setTitle(title)
        self.setBackground("#333")
        self.setLabel("left", "Value")
        self.setLabel("bottom", "Samples")
        self.addLegend()
        self.showGrid(x=True, y=True)
        


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # --- Central widget with layout ---
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        layout.addWidget(self.rpy_plot)


        # --- Data buffers ---
        self.buf = 300
        self.t = 0
        self.x = []
        self.roll_data, self.pitch_data, self.yaw_data = [], [], []
        self.odom_x_data, self.odom_y_data = [], []

        # --- Plot lines ---
        self.roll_line  = self.rpy_plot.plot([], [], pen=pg.mkPen('r', width=2), name="Roll")
        self.pitch_line = self.rpy_plot.plot([], [], pen=pg.mkPen('g', width=2), name="Pitch")
        self.yaw_line   = self.rpy_plot.plot([], [], pen=pg.mkPen('b', width=2), name="Yaw")

        # --- Connect signals ---
        bridge.new_rpy.connect(self.on_new_rpy)

    # --- Slots ---
    def on_new_rpy(self, roll: float, pitch: float, yaw: float):
        self.x.append(self.t)
        self.roll_data.append(roll)
        self.pitch_data.append(pitch)
        self.yaw_data.append(yaw)
        self.t += 1

        self.x          = self.x[-self.buf:]
        self.roll_data  = self.roll_data[-self.buf:]
        self.pitch_data = self.pitch_data[-self.buf:]
        self.yaw_data   = self.yaw_data[-self.buf:]

        self.roll_line.setData(self.x, self.roll_data)
        self.pitch_line.setData(self.x, self.pitch_data)
        self.yaw_line.setData(self.x, self.yaw_data)

    def on_new_odom(self, x: float, y: float):
        self.odom_x_data.append(x)
        self.odom_y_data.append(y)

        self.odom_x_data = self.odom_x_data[-self.buf:]
        self.odom_y_data = self.odom_y_data[-self.buf:]

        # Share the same x-axis time index as RPY
        t = list(range(len(self.odom_x_data)))
        self.odom_x_line.setData(t, self.odom_x_data)
        self.odom_y_line.setData(t, self.odom_y_data)

    def closeEvent(self, event):
        # Lets main() know the window closed so cleanup can run
        event.accept()


def main():
    rclpy.init()

    bridge = RosBridge()
    node = GuiNode(bridge)

    executor = MultiThreadedExecutor()
    executor.add_node(node)
    ros_thread = Thread(target=executor.spin, daemon=True)
    ros_thread.start()

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(bridge)
    window.show()

    try:
        sys.exit(app.exec_())
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
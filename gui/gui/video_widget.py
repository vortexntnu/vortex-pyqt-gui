from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QWidget
from .config import CAMERA_FRONT, CAMERA_BOTTOM, PIPELINE_DESCRIPTION

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GObject
GObject.threads_init()
Gst.init(None)


class GstFrameSource(QtCore.QObject):
    frame = QtCore.pyqtSignal(QtGui.QImage)
    info = QtCore.pyqtSignal(int, int, float)     # width, height, aspect

    def __init__(self, port: int, parent=None):
        super().__init__(parent)
        self.port = port
        self.pipeline = None
        self.appsink = None
        self._sent_info = False

    def start(self):
        self.pipeline = Gst.parse_launch(PIPELINE_DESCRIPTION.replace("PORT", str(self.port)))
        self.appsink = self.pipeline.get_by_name("sink")

        self.appsink.set_property("emit-signals", True)
        self.appsink.connect("new-sample", self._on_new_sample)
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.appsink = None
            self._sent_info = False

    def _on_new_sample(self, sink):
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.ERROR

        buf = sample.get_buffer()
        caps = sample.get_caps().get_structure(0)
        width = int(caps.get_value("width"))
        height = int(caps.get_value("height"))

        ok, mapinfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.ERROR

        frame_bytes = bytes(mapinfo.data)
        buf.unmap(mapinfo)

        img = QtGui.QImage(frame_bytes, width, height, 3 * width, QtGui.QImage.Format_RGB888)
        img = img.copy()

        if not self._sent_info:
            self._sent_info = True
            self.info.emit(width, height, (width / height) if height else 0.0)

        self.frame.emit(img)
        return Gst.FlowReturn.OK


class VideoWidget(QWidget):
    def __init__(self, content_widget, parent=None):
        super().__init__(parent)

        self.content = content_widget

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.content)

        self.setStyleSheet("background: #000;")

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.content.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )



class StatisticsWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video")

        ports = [CAMERA_BOTTOM, CAMERA_FRONT]
        self.cam_labels = []
        self.cam_widgets = []
        self.cam_sources = []

        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)

        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        

        for _, (port, pos) in enumerate(zip(ports, positions)):
            label = QtWidgets.QLabel(self)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background: #333;")

            widget = VideoWidget(label, self)


            source = GstFrameSource(port, parent=self)
            source.frame.connect(
                lambda image, lbl=label: self.update_pixmap(image, lbl)
            )
            source.start()

            self.cam_labels.append(label)
            self.cam_widgets.append(widget)
            self.cam_sources.append(source)

            grid.addWidget(widget, pos[0], pos[1])
            grid.setRowStretch(pos[0], 1)
            grid.setColumnStretch(pos[1], 1)

        self.setLayout(grid)

    def show_on_screen(self, index: int = 1):
        screens = QGuiApplication.screens()
        screen = screens[index] if len(screens) > index else screens[0]
        rect = screen.availableGeometry()
        self.resize(rect.size())
        self.move(rect.topLeft())
        self.showFullScreen()

    @QtCore.pyqtSlot(QtGui.QImage)
    def update_pixmap(self, image: QtGui.QImage, cam: QtWidgets.QLabel):
        pm = QtGui.QPixmap.fromImage(image)
        scaled = pm.scaled(
            cam.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio
        )
        cam.setPixmap(scaled)

    def stop(self):
        for source in self.cam_sources:
            source.stop()

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)

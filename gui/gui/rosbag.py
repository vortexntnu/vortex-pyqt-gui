import os
import datetime
import signal
from PyQt5.QtCore import QProcess


class RosbagRecorder:
    def __init__(self, output_dir="bags", topics=None, storage="sqlite3", compression=False, name="default"):
        self.name = name
        self.output_dir = output_dir
        self.topics = topics or []
        self.storage = storage
        self.compression = compression
        self.process = None

    def start(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bag_path = os.path.join(self.output_dir, f"rosbag_{self.name}_{timestamp}")

        args = ["bag", "record", "-o", bag_path, "--storage", self.storage]

        if self.compression:
            args += ["--compression-mode", "file", "--compression-format", "zstd"]

        if self.topics:
            args += self.topics

        self.process = QProcess()
        self.process.start("ros2", args)

    def stop(self):
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            return

        os.kill(self.process.processId(), signal.SIGINT)
        self.process.waitForFinished(5000)
        self.process = None
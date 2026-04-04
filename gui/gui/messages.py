#Test
def build_topic_selector(self):
    label = QtWidgets.QLabel("ROS2 Topics")
    label.setStyleSheet("color: white; font-weight: bold;")

    refresh_btn = QtWidgets.QPushButton("⟳")
    refresh_btn.setFixedWidth(32)
    refresh_btn.setToolTip("Refresh topics")
    refresh_btn.clicked.connect(self.fetch_ros2_topics)

    header = QtWidgets.QHBoxLayout()
    header.addWidget(label, stretch=1)
    header.addWidget(refresh_btn)

    self.topic_tree = QtWidgets.QTreeWidget()
    self.topic_tree.setHeaderHidden(True)
    self.topic_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
    self.topic_tree.setMaximumHeight(50)

    # Reusable process
    self._topic_proc = QProcess(self)
    self._topic_proc.setProcessChannelMode(QProcess.MergedChannels)  # type: ignore
    self._topic_proc.finished.connect(self._on_topics_fetched)  # type: ignore

    # Auto-refresh every 60 seconds
    self._topic_timer = QTimer(self)
    self._topic_timer.setInterval(60_000)
    self._topic_timer.timeout.connect(self.fetch_ros2_topics)  # type: ignore
    self._topic_timer.start()

    QtWidgets.QVBoxLayout(self.rosbag_widget)
    self.rosbag_widget.layout().addLayout(header)
    self.rosbag_widget.layout().addWidget(self.topic_tree)

    self.fetch_ros2_topics()


def fetch_ros2_topics(self):
    if self._topic_proc.state() != QProcess.NotRunning:  # type: ignore
        return  # silently skip if a fetch is already in progress

    self._topic_proc.start(
        "/bin/bash",
        ["-c", "source /opt/ros/humble/setup.bash && ros2 topic list"]
    )


def _on_topics_fetched(self, exit_code: int, _):
    raw = bytes(self._topic_proc.readAllStandardOutput()).decode("utf-8", errors="replace")

    if exit_code != 0:
        self.add_terminal_output(f"[ERROR] ros2 topic list failed: {raw.strip()}")
        return

    topics = sorted(line.strip() for line in raw.splitlines() if line.strip())
    if not topics:
        return

    # Preserve checked state across refreshes
    previously_checked = {
        item.text(0)
        for item in self._all_topic_items()
        if item.checkState(0) == Qt.Checked  # type: ignore
    }

    self.topic_tree.blockSignals(True)
    self.topic_tree.clear()

    from collections import defaultdict
    groups: dict[str, list[str]] = defaultdict(list)
    for topic in topics:
        parts = topic.strip("/").split("/")
        ns = parts[0] if len(parts) > 1 else "(root)"
        groups[ns].append(topic)

    for ns, ns_topics in sorted(groups.items()):
        parent = QtWidgets.QTreeWidgetItem([f"/{ns}"])
        parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)  # type: ignore
        for t in ns_topics:
            child = QtWidgets.QTreeWidgetItem([t])
            child.setFlags(child.flags() | Qt.ItemIsUserCheckable)  # type: ignore
            child.setCheckState(
                0,
                Qt.Checked if t in previously_checked else Qt.Unchecked  # type: ignore
            )
            parent.addChild(child)
        self.topic_tree.addTopLevelItem(parent)

    self.topic_tree.blockSignals(False)


def _all_topic_items(self) -> list[QtWidgets.QTreeWidgetItem]:
    """Returns all leaf (topic) items across all namespace groups."""
    items = []
    root = self.topic_tree.invisibleRootItem()
    for i in range(root.childCount()):         # namespace groups
        ns_item = root.child(i)
        for j in range(ns_item.childCount()):  # topic leaves
            items.append(ns_item.child(j))
    return items


def get_selected_topics(self) -> list[str]:
    return [
        item.text(0)
        for item in self._all_topic_items()
        if item.checkState(0) == Qt.Checked  # type: ignore
    ]
    
    
####

def build_topic_selector(self):
    self.refresh_btn.clicked.connect(self.fetch_ros2_topics)
    self.rosbag_topics.activated.connect(self._on_topic_selected)  # type: ignore
    self.rosbag_selected_topics.itemDoubleClicked.connect(self._remove_topic)  # type: ignore

    self._topic_proc = QProcess(self)
    self._topic_proc.setProcessChannelMode(QProcess.MergedChannels)  # type: ignore
    self._topic_proc.finished.connect(self._on_topics_fetched)  # type: ignore

    self.fetch_ros2_topics()


def fetch_ros2_topics(self):
    if self._topic_proc.state() != QProcess.NotRunning: return
    self._topic_proc.start("/bin/bash", ["-c", "source /opt/ros/humble/setup.bash && ros2 topic list"])


def _on_topics_fetched(self, exit_code: int, _):
    raw = bytes(self._topic_proc.readAllStandardOutput()).decode("utf-8", errors="replace")

    if exit_code != 0:
        self.add_terminal_output(f"[ERROR] ros2 topic list failed: {raw.strip()}")
        return

    topics = sorted(line.strip() for line in raw.splitlines() if line.strip())
    if not topics:
        return

    self.rosbag_topics.blockSignals(True)
    self.rosbag_topics.clear()
    for topic in topics:
        self.rosbag_topics.addItem(topic)
    self.rosbag_topics.setCurrentIndex(-1)   # keep placeholder visible
    self.rosbag_topics.blockSignals(False)


def _on_topic_selected(self, index: int):
    """Append the chosen topic to the list, ignoring duplicates."""
    topic = self.rosbag_topics.itemText(index)
    if not topic:
        return
    existing = {
        self.rosbag_selected_topics.item(i).text()
        for i in range(self.rosbag_selected_topics.count())
    }
    if topic not in existing:
        self.rosbag_selected_topics.addItem(topic)
    # Reset combo back to placeholder so the same topic can be re-added
    # after removal without the user needing to change selection first.
    self.rosbag_topics.setCurrentIndex(-1)


def _remove_topic(self, item: QtWidgets.QListWidgetItem):
    self.rosbag_selected_topics.takeItem(self.rosbag_selected_topics.row(item))


def get_selected_topics(self) -> list[str]:
    return [self.rosbag_selected_topics.item(i).text() for i in range(self.rosbag_selected_topics.count())]

    def start_ssh_tmux(self):
        try:
            import subprocess

            cmd = [
                "tmux", "new-session", "-d", "-s", "name",
                "ssh", "-i", SSH_KEY,
                "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=60",
                "-o", "ServerAliveCountMax=10",
                SSH_HOST
            ]
            subprocess.run(cmd, check=False)
            self.add_terminal_output("SSH Connected")
        except Exception as e:
            self.add_terminal_output(f"SSH Failed to connect: {e}")
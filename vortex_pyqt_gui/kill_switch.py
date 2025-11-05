from PyQt6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QMessageBox
from PyQt6.QtCore import Qt

class KillSwitch(QWidget):
    def __init__(self, parent=None, on_kill=None, on_reactivate=None):
        super().__init__(parent)

        self.RED_STYLE = """
            QPushButton {
                background-color: red;
                color: black;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: darkred;
            }
        """
        self.GREEN_STYLE = """
            QPushButton {
                background-color: green;
                color: black;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: darkgreen;
            }
        """

        self.button = QPushButton("Kill Thrusters")
        self.button.setStyleSheet(self.RED_STYLE)

        layout = QVBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.on_kill = on_kill
        self.on_reactivate = on_reactivate

        self.button.clicked.connect(self.verify_kill_switch_step1)

    def verify_kill_switch_step1(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Kill Switch – Step 1")
        msg.setText("Are you sure you want to initiate shutdown?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        response = msg.exec()

        if response == QMessageBox.StandardButton.Yes:
            self.verify_kill_switch_step2()

    def verify_kill_switch_step2(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Kill Switch – Final Confirmation")
        msg.setText("This will immediately shut down the system. Proceed?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        response = msg.exec()

        if response == QMessageBox.StandardButton.Yes:
            self.trigger_kill_switch()

    def trigger_kill_switch(self):
        if self.on_kill:
            self.on_kill()

        self.button.setText("Reactivate Thrusters")
        self.button.setStyleSheet(self.GREEN_STYLE)

        self.button.clicked.disconnect()
        self.button.clicked.connect(self.reactivate_thrusters)

    def reactivate_thrusters(self):
        if self.on_reactivate:
            self.on_reactivate()

        self.button.setText("Kill Thrusters")
        self.button.setStyleSheet(self.RED_STYLE)

        self.button.clicked.disconnect()
        self.button.clicked.connect(self.verify_kill_switch_step1)
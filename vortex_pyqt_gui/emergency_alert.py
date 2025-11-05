from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt

class EmergencyAlert(QWidget):
    def __init__(self, parent=None, on_confirm=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(255, 0, 0, 180);")
        self.setGeometry(parent.rect())
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Big red warning label
        self.label = QLabel(" EMERGENCY: LEAK DETECTED ")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        layout.addWidget(self.label)

        # Confirmation button
        self.confirm_button = QPushButton("Confirm and Dismiss")
        self.confirm_button.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: red;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
                border: 2px solid red;
            }
            QPushButton:hover {
                background-color: lightgray;
            }
        """)
        layout.addWidget(self.confirm_button)

        self.setLayout(layout)

        # Blinking background effect
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_background)
        self.blink_timer.start(500)
        self.blink_state = True

        if on_confirm:
            self.confirm_button.clicked.connect(on_confirm)

    def toggle_background(self):
        if self.blink_state:
            self.setStyleSheet("background-color: rgba(120, 0, 0, 180);")
        else:
            self.setStyleSheet("background-color: rgba(255, 0, 0, 180);")
        self.blink_state = not self.blink_state
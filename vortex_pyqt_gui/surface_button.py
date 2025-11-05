from PyQt6.QtWidgets import QWidget, QPushButton, QVBoxLayout

class SurfaceButton(QWidget):
    def __init__(self, parent=None, on_surface=None):
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

        self.button = QPushButton("Surface")
        self.button.setStyleSheet(self.RED_STYLE)

        layout = QVBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)

        if on_surface:
            self.button.clicked.connect(on_surface)
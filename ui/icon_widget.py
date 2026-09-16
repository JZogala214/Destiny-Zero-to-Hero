from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap


class IconWidget(QLabel):

    def set_icon(self, filepath):
        pixmap = QPixmap(filepath)
        self.setPixmap(pixmap)
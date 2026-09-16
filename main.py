import sys

from PyQt6.QtWidgets import QApplication

from paths import MANIFEST_DB
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    window = MainWindow(manifest_path=str(MANIFEST_DB))
    window.resize(980, 720)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    sys.exit(main())

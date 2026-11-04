import sys
from PySide6 import QtWidgets

# Importerer vinduet fra graf_tegner.py
from graf_tegner import MultiLiveDataWindow

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MultiLiveDataWindow()
    window.show()
    sys.exit(app.exec())
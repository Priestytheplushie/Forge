from PySide6.QtWidgets import QStyle, QApplication
from PySide6.QtGui import QIcon


class IconProvider:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IconProvider, cls).__new__(cls)

            app_style = QApplication.style()
            cls._instance._folder_icon = app_style.standardIcon(
                QStyle.StandardPixmap.SP_DirIcon
            )
            cls._instance._file_icon = app_style.standardIcon(
                QStyle.StandardPixmap.SP_FileIcon
            )
        return cls._instance

    def folder_icon(self) -> QIcon:
        return self._folder_icon

    def file_icon(self, file_path: str = "") -> QIcon:

        return self._file_icon

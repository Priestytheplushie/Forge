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


from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtCore import QFileInfo
from ..assets.icon_map import get_pyforge_script_icon


class CustomIconProvider(QFileIconProvider):
    """
    An icon provider that returns a custom icon for PyForge scripts
    and falls back to the default system icons for everything else.
    """

    def icon(self, info):

        if isinstance(info, QFileInfo) and info.suffix() == "pfscript":
            return get_pyforge_script_icon()

        return super().icon(info)

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QDialogButtonBox,
    QWidget,
    QHBoxLayout,
)
from PySide6.QtCore import Qt
from ..assets.icon_map import get_pyforge_object_icon, get_status_icon


class LegendEntry(QWidget):
    """A single row in the legend dialog."""

    def __init__(self, icon, name, description, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)

        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(16, 16))

        text_layout = QVBoxLayout()
        name_label = QLabel(f"<b>{name}</b>")
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #888888;")

        text_layout.addWidget(name_label)
        text_layout.addWidget(desc_label)

        layout.addWidget(icon_label)
        layout.addLayout(text_layout)
        layout.addStretch()


class ObjectBrowserLegendDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Object Browser Legend")
        self.setMinimumWidth(350)

        main_layout = QVBoxLayout(self)

        main_layout.addWidget(
            LegendEntry(
                get_pyforge_object_icon("instance"),
                "Instance",
                "A live object in memory.",
            )
        )
        main_layout.addWidget(
            LegendEntry(
                get_pyforge_object_icon("class"), "Class", "A class definition."
            )
        )
        main_layout.addWidget(
            LegendEntry(
                get_pyforge_object_icon("function"),
                "Function / Method",
                "A callable function or method.",
            )
        )
        main_layout.addWidget(
            LegendEntry(get_pyforge_object_icon("module"), "Module", "A Python module.")
        )
        main_layout.addWidget(
            LegendEntry(
                get_pyforge_object_icon("attribute_simple"),
                "Attribute",
                "A simple attribute (int, str, etc.).",
            )
        )
        main_layout.addWidget(
            LegendEntry(
                get_pyforge_object_icon("attribute_collection"),
                "Collection",
                "A list, dict, or other collection.",
            )
        )
        main_layout.addWidget(
            LegendEntry(
                get_pyforge_object_icon("special_group"),
                "Special Group",
                "A pre-defined group of objects provided by PyForge.",
            )
        )

        main_layout.addWidget(
            LegendEntry(
                get_status_icon("pin"),
                "Pinned Subscription",
                "This instance is permanently watched for changes.",
            )
        )
        main_layout.addWidget(
            LegendEntry(
                get_status_icon("eye"),
                "Temporary Subscription",
                "This instance is watched because it is expanded.",
            )
        )

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

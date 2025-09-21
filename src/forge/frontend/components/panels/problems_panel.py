from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QStyle,
    QStackedWidget,
    QLabel,
    QFileIconProvider,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, Signal, Slot, QFileInfo

SEVERITY_MAP = {
    1: "Error",
    2: "Warning",
    3: "Information",
    4: "Hint",
}


class ProblemsPanel(QWidget):
    """
    A widget that displays LSP diagnostics in a tree view, grouped by file,
    and shows a message when no problems are detected.
    """

    problem_clicked = Signal(str, int, int)

    def __init__(self, icon_provider: QFileIconProvider, parent=None):
        super().__init__(parent)
        self.icon_provider = icon_provider
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget(self)

        self.tree_view = QTreeView()
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree_view.setRootIsDecorated(False)
        self.tree_view.setAlternatingRowColors(True)

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Description", "File", "Location"])
        self.tree_view.setModel(self.model)

        self.no_problems_label = QLabel(
            "No problems have been detected in the workspace."
        )
        self.no_problems_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.stack.addWidget(self.tree_view)
        self.stack.addWidget(self.no_problems_label)

        self.layout().addWidget(self.stack)

        self.icon_error = self.style().standardIcon(
            QStyle.StandardPixmap.SP_MessageBoxCritical
        )
        self.icon_warning = self.style().standardIcon(
            QStyle.StandardPixmap.SP_MessageBoxWarning
        )
        self.icon_info = self.style().standardIcon(
            QStyle.StandardPixmap.SP_MessageBoxInformation
        )
        self.icon_hint = self.style().standardIcon(
            QStyle.StandardPixmap.SP_FileDialogInfoView
        )
        self.severity_icons = {
            1: self.icon_error,
            2: self.icon_warning,
            3: self.icon_info,
            4: self.icon_hint,
        }

        self.tree_view.doubleClicked.connect(self.on_problem_double_clicked)

    @Slot(dict)
    def update_diagnostics(self, diagnostics_by_uri: dict):
        """
        Clears and rebuilds the tree view with the latest diagnostics.
        """
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Description", "File", "Location"])

        total_problems = sum(len(diags) for diags in diagnostics_by_uri.values())

        if total_problems == 0:
            self.stack.setCurrentWidget(self.no_problems_label)
            return
        else:
            self.stack.setCurrentWidget(self.tree_view)

        for uri, diagnostics in diagnostics_by_uri.items():
            if not diagnostics:
                continue

            file_info = QFileInfo(uri.replace("file:///", "").replace("file://", ""))
            file_icon = self.icon_provider.icon(file_info)

            file_item = QStandardItem(
                file_icon, f"{file_info.fileName()} ({len(diagnostics)})"
            )
            file_item.setEditable(False)
            self.model.appendRow(file_item)

            for diag in diagnostics:
                line = diag["range"]["start"]["line"]
                char = diag["range"]["start"]["character"]

                severity = diag.get("severity", 4)

                desc_item = QStandardItem(
                    self.severity_icons.get(severity), diag["message"]
                )
                desc_item.setData(
                    {"uri": uri, "line": line, "char": char}, Qt.ItemDataRole.UserRole
                )
                desc_item.setEditable(False)

                file_name_item = QStandardItem(str(file_info.dir().dirName()))
                file_name_item.setEditable(False)

                loc_item = QStandardItem(f"{line + 1}:{char + 1}")
                loc_item.setEditable(False)

                file_item.appendRow([desc_item, file_name_item, loc_item])

        self.tree_view.expandAll()
        for i in range(self.model.columnCount()):
            self.tree_view.resizeColumnToContents(i)

    @Slot()
    def on_problem_double_clicked(self, index):
        item = self.model.itemFromIndex(index)
        if not item:
            return

        problem_data = item.data(Qt.ItemDataRole.UserRole)
        if problem_data:
            self.problem_clicked.emit(
                problem_data["uri"], problem_data["line"], problem_data["char"]
            )

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QFrame,
    QCheckBox,
    QComboBox,
    QPlainTextEdit,
    QGroupBox,
    QTreeView,
    QFileSystemModel,
    QDialogButtonBox,
    QWidget,
    QMessageBox,
    QMenu,
)
from PySide6.QtCore import Qt, QDir, QTimer, QPoint
from PySide6.QtGui import QDesktopServices, QAction
from pathlib import Path
import os
import shutil
import git
import tempfile


class NewProjectDialog(QDialog):
    def __init__(self, main_controller, parent=None):
        super().__init__(parent)
        self.main_controller = main_controller
        self.setWindowTitle("Create New Project")
        self.setMinimumSize(800, 600)

        self.temp_dir = tempfile.mkdtemp(prefix="forge-project-preview-")
        self.project_path = ""
        self.imported_files = []

        main_layout = QHBoxLayout(self)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        actions_group = QGroupBox("Start From")
        actions_layout = QVBoxLayout(actions_group)
        self.import_button = QPushButton("Import Files/Folders...")
        self.clear_imports_button = QPushButton("Clear Imported Files")
        actions_layout.addWidget(self.import_button)
        actions_layout.addWidget(self.clear_imports_button)

        location_group = QGroupBox("Project Location")
        location_layout = QFormLayout(location_group)
        self.name_edit = QLineEdit()
        self.path_edit = QLineEdit(str(Path.home() / "Documents"))
        path_button = QPushButton("Browse...")
        path_button.clicked.connect(self._browse_for_path)
        path_hbox = QHBoxLayout()
        path_hbox.addWidget(self.path_edit)
        path_hbox.addWidget(path_button)
        location_layout.addRow("Project Name:", self.name_edit)
        location_layout.addRow("Location:", path_hbox)

        language_group = QGroupBox("Language and Framework")
        language_layout = QVBoxLayout(language_group)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "Java"])
        language_layout.addWidget(self.lang_combo)

        self.python_group = QGroupBox("Python Options")
        python_layout = QVBoxLayout(self.python_group)
        self.venv_check = QCheckBox("Create a virtual environment (.venv)")
        self.venv_check.setChecked(True)
        python_layout.addWidget(self.venv_check)
        python_layout.addWidget(QLabel("Initial requirements.txt (optional):"))
        self.reqs_edit = QPlainTextEdit()
        self.reqs_edit.setPlaceholderText("e.g., fastapi\nrequests\n")
        python_layout.addWidget(self.reqs_edit)

        self.java_group = QGroupBox("Java Options (Placeholder)")
        java_layout = QVBoxLayout(self.java_group)
        self.maven_check = QCheckBox("Initialize as Maven project")
        java_layout.addWidget(self.maven_check)
        self.java_group.setVisible(False)

        language_layout.addWidget(self.python_group)
        language_layout.addWidget(self.java_group)

        git_group = QGroupBox("Source Control")
        git_layout = QFormLayout(git_group)
        self.git_check = QCheckBox("Initialize a new Git repository")
        self.git_check.setChecked(True)
        git_layout.addRow(self.git_check)
        self.gitignore_combo = QComboBox()
        self.gitignore_combo.addItems(["None", "Python", "Java"])
        git_layout.addRow("Add .gitignore:", self.gitignore_combo)
        git_layout.addWidget(
            self._create_help_label(
                ".gitignore tells Git which files to intentionally ignore."
            )
        )
        self.license_combo = QComboBox()
        self.license_combo.addItems(["None", "MIT", "Apache 2.0", "GPLv3", "LGPLv3"])
        git_layout.addRow("Add a license:", self.license_combo)
        license_help = self._create_help_label(
            'The license determines how others can use your code. <a href="https://choosealicense.com/">Learn more.</a>'
        )
        license_help.setOpenExternalLinks(True)
        git_layout.addWidget(license_help)

        left_layout.addWidget(actions_group)
        left_layout.addWidget(location_group)
        left_layout.addWidget(language_group)
        left_layout.addWidget(git_group)
        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Project Preview:"))
        self.preview_tree = QTreeView()
        self.preview_model = QFileSystemModel()
        self.preview_model.setFilter(
            QDir.Filter.NoDotAndDotDot | QDir.Filter.AllEntries
        )
        self.preview_tree.setModel(self.preview_model)
        self.preview_tree.hideColumn(1)
        self.preview_tree.hideColumn(2)
        self.preview_tree.hideColumn(3)
        self.preview_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        right_layout.addWidget(self.preview_tree)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Create Project")
        self.ok_button.setEnabled(False)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        right_layout.addWidget(button_box)

        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 1)

        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(300)
        self.update_timer.timeout.connect(self._update_preview)

        self.lang_combo.currentTextChanged.connect(self._schedule_update)
        self.name_edit.textChanged.connect(self._schedule_update)
        self.path_edit.textChanged.connect(self._schedule_update)
        self.git_check.toggled.connect(self._schedule_update)
        self.gitignore_combo.currentTextChanged.connect(self._schedule_update)
        self.license_combo.currentTextChanged.connect(self._schedule_update)
        self.venv_check.toggled.connect(self._schedule_update)
        self.reqs_edit.textChanged.connect(self._schedule_update)
        self.import_button.clicked.connect(self._import_files)
        self.clear_imports_button.clicked.connect(self._clear_imports)
        self.preview_tree.customContextMenuRequested.connect(self._preview_context_menu)

        self._update_and_validate()
        self._update_preview()

    def _create_help_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("color: #888888; font-style: italic;")
        label.setWordWrap(True)
        return label

    def _browse_for_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Location")
        if path:
            self.path_edit.setText(path)

    def _schedule_update(self):
        self._update_and_validate()
        self.update_timer.start()

    def _update_language_options(self):
        is_python = self.lang_combo.currentText() == "Python"
        self.python_group.setVisible(is_python)
        self.java_group.setVisible(not is_python)
        self.gitignore_combo.model().item(1).setEnabled(is_python)
        self.gitignore_combo.model().item(2).setEnabled(not is_python)
        if is_python and self.gitignore_combo.currentText() == "Java":
            self.gitignore_combo.setCurrentText("Python")
        elif not is_python and self.gitignore_combo.currentText() == "Python":
            self.gitignore_combo.setCurrentText("Java")

    def _update_and_validate(self):
        name = self.name_edit.text().strip()
        path = self.path_edit.text().strip()
        is_valid = bool(name and path and os.path.isdir(path))
        self.ok_button.setEnabled(is_valid)
        self.project_path = str(Path(path) / name) if is_valid else ""

    def _update_preview(self):
        self._update_language_options()
        self.gitignore_combo.setEnabled(self.git_check.isChecked())
        self.license_combo.setEnabled(self.git_check.isChecked())

        for item in Path(self.temp_dir).iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        preview_root = Path(self.temp_dir)
        (preview_root / "src").mkdir(exist_ok=True)

        for file_path_str in self.imported_files:
            file_path = Path(file_path_str)
            shutil.copy(file_path, preview_root / file_path.name)

        if self.git_check.isChecked():
            (preview_root / ".git").mkdir(exist_ok=True)
            if self.gitignore_combo.currentText() != "None":
                (preview_root / ".gitignore").touch()
            if self.license_combo.currentText() != "None":
                (preview_root / "LICENSE").touch()

        if self.lang_combo.currentText() == "Python":
            if self.venv_check.isChecked():
                (preview_root / ".venv").mkdir(exist_ok=True)
            if self.reqs_edit.toPlainText().strip():
                (preview_root / "requirements.txt").touch()

        self.preview_model.setRootPath("")
        self.preview_tree.setRootIndex(self.preview_model.setRootPath(self.temp_dir))

    def _import_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Import Files")
        if files:
            self.imported_files.extend(files)
            self._schedule_update()

    def _clear_imports(self):
        self.imported_files.clear()
        self._schedule_update()

    def _preview_context_menu(self, point: QPoint):
        index = self.preview_tree.indexAt(point)
        if not index.isValid():
            return

        file_path_str = self.preview_model.filePath(index)
        file_path = Path(file_path_str)

        original_path = next(
            (p for p in self.imported_files if Path(p).name == file_path.name), None
        )
        if not original_path:
            return

        menu = QMenu(self)
        delete_action = QAction(f"Remove '{file_path.name}' from Project", self)
        delete_action.triggered.connect(
            lambda: self._remove_imported_file(original_path)
        )
        menu.addAction(delete_action)
        menu.exec(self.preview_tree.viewport().mapToGlobal(point))

    def _remove_imported_file(self, original_path_to_remove: str):
        self.imported_files.remove(original_path_to_remove)
        self._schedule_update()

    def accept(self):
        if not self.project_path:
            return
        try:
            proj_dir = Path(self.project_path)
            if proj_dir.exists():
                QMessageBox.critical(
                    self, "Error", "A directory with that name already exists."
                )
                return

            shutil.copytree(self.temp_dir, proj_dir, dirs_exist_ok=True)

            if (
                self.lang_combo.currentText() == "Python"
                and self.reqs_edit.toPlainText().strip()
            ):
                (proj_dir / "requirements.txt").write_text(self.reqs_edit.toPlainText())

            if self.git_check.isChecked():
                if not (proj_dir / ".git").exists():
                    git.Repo.init(str(proj_dir))

                gitignore_type = self.gitignore_combo.currentText()
                if gitignore_type == "Python":
                    (proj_dir / ".gitignore").write_text(
                        "# Python\n\n__pycache__/\n.venv/\n*.pyc\n"
                    )
                elif gitignore_type == "Java":
                    (proj_dir / ".gitignore").write_text("# Java\n\n*.class\n*.jar\n")

                if self.license_combo.currentText() != "None":
                    (proj_dir / "LICENSE").write_text(
                        f"Placeholder for {self.license_combo.currentText()} license."
                    )

            super().accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Project Creation Failed", f"An error occurred: {e}"
            )
        finally:
            self.cleanup()

    def reject(self):
        self.cleanup()
        super().reject()

    def cleanup(self):
        self.preview_model.setRootPath("")
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

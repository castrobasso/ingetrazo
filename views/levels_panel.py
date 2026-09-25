# SPDX-License-Identifier: GPL-3.0-or-later
"""Panel lateral con los niveles (plantas) del edificio y las guías de alzado."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDockWidget, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from core.i18n import tr


class Level:
    """Un nivel de planta arquitectónica (nombre + altura en metros)."""

    def __init__(self, name: str, elevation: float):
        self.name = name
        self.elevation = float(elevation)

    def __repr__(self):
        return f"{self.name} @ {self.elevation:.2f} m"


class _LevelDialog(QDialog):
    """Diálogo reutilizable para crear o editar un nivel."""

    def __init__(self, parent, title: str, name: str = "", elevation: float = 0.0):
        super().__init__(parent)
        self.setWindowTitle(title)

        form = QFormLayout(self)

        self.name_edit = QLineEdit(name)
        form.addRow(tr("Name:"), self.name_edit)

        self.elev_spin = QDoubleSpinBox()
        self.elev_spin.setRange(-1000.0, 1000.0)
        self.elev_spin.setDecimals(2)
        self.elev_spin.setSingleStep(0.30)
        self.elev_spin.setSuffix(" m")
        self.elev_spin.setValue(elevation)
        form.addRow(tr("Elevation:"), self.elev_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def result(self):
        return self.name_edit.text().strip(), self.elev_spin.value()


class LevelsPanel(QDockWidget):
    """Panel derecho con la lista de niveles y el botón de guías."""

    # Se emite cada vez que algo cambia (añadir / editar / borrar / toggle guías).
    levelsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(tr("Levels"), parent)
        self.setObjectName("levels_tray")

        self._levels: list[Level] = []
        self._guides_visible = False

        # --- Contenedor principal ---
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Botón de guías en alzado (arriba del todo) ---
        self.guides_btn = QPushButton("📐 " + tr("Elevation guides"))
        self.guides_btn.setCheckable(True)
        self.guides_btn.setToolTip(tr(
            "Show horizontal guides at each level's elevation.\n"
            "When ON, drawing tools snap to these heights in elevation views."
        ))
        self.guides_btn.toggled.connect(self._on_toggle_guides)
        self.guides_btn.setStyleSheet(
            "QPushButton { padding: 6px; font-weight: bold; }"
            "QPushButton:checked { background: #f37329; color: white; }"
        )
        layout.addWidget(self.guides_btn)

        # --- Lista de niveles ---
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._edit_level)
        layout.addWidget(self.list, 1)

        # --- Botones + / ✏️ / 🗑 ---
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("+ " + tr("Add"))
        self.add_btn.setToolTip(tr("Add a new level"))
        self.add_btn.clicked.connect(self._add_level)

        self.edit_btn = QPushButton("✏️ " + tr("Edit"))
        self.edit_btn.setToolTip(tr("Edit the selected level"))
        self.edit_btn.clicked.connect(self._edit_selected)

        self.del_btn = QPushButton("🗑️ " + tr("Delete"))
        self.del_btn.setToolTip(tr("Delete the selected level"))
        self.del_btn.clicked.connect(self._delete_level)

        for b in (self.add_btn, self.edit_btn, self.del_btn):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        # --- Etiqueta informativa abajo ---
        hint = QLabel(tr(
            "Tip: double-click a level to edit it."))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(hint)

        self.setWidget(widget)

    # ---------- API pública (la usa main_window.py y el viewport) ----------

    @property
    def levels(self) -> list[Level]:
        return list(self._levels)

    @property
    def guides_visible(self) -> bool:
        return self._guides_visible

    def elevations(self) -> list[float]:
        """Alturas ordenadas (para pintar guías y para el snap)."""
        return sorted({lv.elevation for lv in self._levels})

    # ---------- Acciones de la UI ----------

    def _refresh_list(self):
        self.list.clear()
        for lv in sorted(self._levels, key=lambda l: l.elevation):
            item = QListWidgetItem(
                f"{lv.name}    —    {lv.elevation:+.2f} m")
            item.setData(Qt.UserRole, lv)
            self.list.addItem(item)

    def _selected_level(self) -> Level | None:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _add_level(self):
        default_name = tr("Level {n}", n=len(self._levels) + 1)
        dlg = _LevelDialog(self, tr("New level"), default_name, 0.0)
        if dlg.exec() != QDialog.Accepted:
            return
        name, elev = dlg.result()
        if not name:
            return
        self._levels.append(Level(name, elev))
        self._refresh_list()
        self.levelsChanged.emit()

    def _edit_selected(self):
        lv = self._selected_level()
        if lv is None:
            QMessageBox.information(
                self, tr("Edit level"),
                tr("Select a level in the list first."))
            return
        self._edit_level()

    def _edit_level(self, _item=None):
        lv = self._selected_level()
        if lv is None:
            return
        dlg = _LevelDialog(self, tr("Edit level"), lv.name, lv.elevation)
        if dlg.exec() != QDialog.Accepted:
            return
        name, elev = dlg.result()
        if not name:
            return
        lv.name = name
        lv.elevation = elev
        self._refresh_list()
        self.levelsChanged.emit()

    def _delete_level(self):
        lv = self._selected_level()
        if lv is None:
            return
        ans = QMessageBox.question(
            self, tr("Delete level"),
            tr("Delete level '{name}'?", name=lv.name),
            QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        self._levels.remove(lv)
        self._refresh_list()
        self.levelsChanged.emit()

    def _on_toggle_guides(self, checked: bool):
        self._guides_visible = checked
        self.levelsChanged.emit()
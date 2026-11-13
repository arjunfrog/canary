from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QSizePolicy, QWidget

from ... import audit, sim
from .. import theme
from ..widgets import Panel
from ..widgets.limits_chart import LimitsChart
from ..widgets.text import plain, primary_button, when
from .placeholder import GAP, Page, PageHeader


class LimitsPage(Page):
    """Where tracing works and where it fails, from the saved simulation. Failures are shown as plainly as successes."""

    def __init__(self, window=None):
        super().__init__(window)
        self.data: dict | None = None
        self.selected = 0
        self.header = PageHeader("Limits", "How often the right copy is named, and a wrong one, by the number of questions leaked.")

        self.missing = Panel()
        self.message = plain("", 14, role="muted", wrap=True)
        self.run_button = primary_button("Run the simulation")
        self.run_button.clicked.connect(self.run_simulation)
        row = QHBoxLayout()
        row.addWidget(self.run_button)
        row.addStretch(1)
        self.missing.body.addWidget(self.message)
        self.missing.body.addLayout(row)
        self.missing.setSizePolicy(self.missing.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Maximum)

        self.picker_panel = Panel("What kind of leak")
        self.picker_panel.setFixedWidth(340)
        self.picker_group = QButtonGroup(self)
        self.picker_group.setExclusive(True)
        self.picker = self.picker_panel.body
        self.picker.setSpacing(2)
        self.picker.setContentsMargins(6, 6, 6, 8)

        self.chart_panel = Panel("")
        self.sentence = plain("", 14, wrap=True)
        self.sentence.setMinimumHeight(40)
        self.chart = LimitsChart()
        self.note = plain("", 12, role="muted", wrap=True)
        for widget in (self.sentence, self.chart, self.note):
            self.chart_panel.body.addWidget(widget, 1 if widget is self.chart else 0)

        self.loaded = QWidget()
        loaded = QHBoxLayout(self.loaded)
        loaded.setContentsMargins(0, 0, 0, 0)
        loaded.setSpacing(GAP)
        loaded.addWidget(self.picker_panel, 0)
        loaded.addWidget(self.chart_panel, 1)

        layout = self.frame(self)
        layout.addWidget(self.header)
        layout.addWidget(self.missing)
        layout.addWidget(self.loaded, 1)
        layout.addStretch(0)
        self._buttons: list[QPushButton] = []
        self._show_missing("Loading the saved simulation.", can_run=False)

    @property
    def title(self):
        return self.chart_panel.title

    def _show_missing(self, words: str, can_run: bool = True) -> None:
        self.message.setText(words)
        self.run_button.setVisible(can_run)
        self.missing.setVisible(True)
        self.loaded.setVisible(False)

    def refresh(self) -> None:
        """Draw from the saved file. The simulation is never run from here."""
        self.data = sim.load_limits()
        if self.data is None:
            exists = sim.limits_path().exists()
            self._show_missing("The saved simulation cannot be read. Run it again to replace it. A run takes a few seconds."
                               if exists else "The simulation has not been run on this laptop yet, so there is no chart to "
                               "show. A run takes a few seconds.")
            return
        self.missing.setVisible(False)
        self.loaded.setVisible(True)
        if len(self._buttons) != len(self.data["scenarios"]):
            for old in self._buttons:
                self.picker_group.removeButton(old)
                old.setParent(None)
                old.deleteLater()
            self._buttons = []
            for index, scenario in enumerate(self.data["scenarios"]):
                choice = QPushButton(scenario["title"])
                choice.setProperty("choice", True)
                choice.setCheckable(True)
                choice.setFont(theme.body(14))
                choice.setCursor(Qt.CursorShape.PointingHandCursor)
                choice.clicked.connect(lambda _=False, i=index: self.select(i))
                self.picker_group.addButton(choice)
                self.picker.addWidget(choice)
                self._buttons.append(choice)
            self.picker.addStretch(1)
        self.select(min(self.selected, len(self._buttons) - 1))

    def select(self, index: int) -> None:
        self.selected = index
        scenario = self.data["scenarios"][index]
        self._buttons[index].setChecked(True)
        self.chart_panel.set_title(scenario["title"])
        self.sentence.setText(scenario["sentence"])
        self.chart.set_points(scenario["points"])
        rates = self.data["rates"]
        flat = all(p["traced_right"] == p["lead_right"] == p["lead_wrong"] == 0 for p in scenario["points"])
        self.note.setText(
            ("All three lines sit at 0%: no copy is ever named, right or wrong. " if flat else "") +
            f"Simulation, not field results: {self.data['trials']:,} runs per point among {scenario['candidates']:,} "
            f"candidate copies, run {when(self.data['generated_at'])}. Misread rates are {self.data['rates_source']}: "
            f"typed values {rates['typed_value']:.0%}, retold values {rates['retold_value']:.0%}, "
            f"photo values {rates['photo_value']:.0%}, photo option order {rates['photo_order']:.0%}. "
            "Misreads are treated as independent, which real photos may not be.")

    def run_simulation(self) -> None:
        self._show_missing("Running the simulation.", can_run=False)
        self.repaint()
        try:
            sim.run_sim()
        except OSError as exc:
            self._show_missing(f"The simulation could not be saved. {exc}")
            return
        if self.app_window is not None:
            audit.record(self.app_window.conn, "simulation run", {"from": "limits screen"})
        self.refresh()

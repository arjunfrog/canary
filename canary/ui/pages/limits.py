from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QVBoxLayout, QWidget

from ... import audit, sim
from ..widgets import BubbleToggle, RuledSection
from ..widgets.limits_chart import LimitsChart
from ..widgets.text import caption, heading, plain, primary_button, when
from .placeholder import Page


class LimitsPage(Page):
    """Where tracing works and where it fails, from the saved simulation. Failures are shown as plainly as successes."""

    def __init__(self, window=None):
        super().__init__(window)
        self.data: dict | None = None
        self.selected = 0
        section = RuledSection("Limits")
        self.message = plain("", 18, role="muted", wrap=True)
        self.run_button = primary_button("Run the simulation")
        self.run_button.clicked.connect(self.run_simulation)
        missing = QHBoxLayout()
        missing.addWidget(self.run_button)
        missing.addStretch(1)
        self.missing = QWidget()
        box = QVBoxLayout(self.missing)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)
        box.addWidget(self.message)
        box.addLayout(missing)
        box.addStretch(1)

        self.picker_group = QButtonGroup(self)
        self.picker_group.setExclusive(True)
        self.picker = QVBoxLayout()
        self.picker.setSpacing(2)
        self.picker.addWidget(caption("What kind of leak"))
        self.picker_box = QWidget()
        self.picker_box.setLayout(self.picker)
        self.picker_box.setFixedWidth(420)
        self.title = heading("", 28, semibold=True)
        self.sentence = plain("", 17, wrap=True)
        self.sentence.setMinimumHeight(74)
        self.chart = LimitsChart()
        self.note = plain("", 14, role="muted", wrap=True)
        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(self.title)
        right.addWidget(self.sentence)
        right.addWidget(self.chart, 1)
        right.addWidget(self.note)
        self.loaded = QWidget()
        row = QHBoxLayout(self.loaded)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(40)
        row.addWidget(self.picker_box, 0)
        row.addLayout(right, 1)
        section.body.addWidget(self.missing)
        section.body.addWidget(self.loaded, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(section, 1)
        self._buttons: list[BubbleToggle] = []
        self._show_missing("Loading the saved simulation.", can_run=False)

    def marks(self) -> list[bool]:
        """One mark per kind of leak, black for the ones where a copy can be named."""
        if not self.data:
            return [False] * 7
        return [max(p["lead_right"] for p in s["points"]) > 0 for s in self.data["scenarios"]]

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
            self._show_missing("The saved simulation cannot be read. Run it again to replace it." if exists else
                               "The simulation has not been run on this laptop yet, so there is no chart to show.")
            return
        self.missing.setVisible(False)
        self.loaded.setVisible(True)
        if len(self._buttons) != len(self.data["scenarios"]):
            for button in self._buttons:
                self.picker_group.removeButton(button)
                button.setParent(None)
                button.deleteLater()
            self._buttons = []
            for index, scenario in enumerate(self.data["scenarios"]):
                button = BubbleToggle(scenario["title"])
                button.clicked.connect(lambda _=False, i=index: self.select(i))
                self.picker_group.addButton(button)
                self.picker.addWidget(button)
                self._buttons.append(button)
            self.picker.addStretch(1)
        self.select(min(self.selected, len(self._buttons) - 1))

    def select(self, index: int) -> None:
        self.selected = index
        scenario = self.data["scenarios"][index]
        self._buttons[index].setChecked(True)
        self.title.setText(scenario["title"])
        self.sentence.setText(scenario["sentence"])
        self.chart.set_points(scenario["points"])
        rates = self.data["rates"]
        self.note.setText(
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
        if self.app_window is not None:
            self.app_window.marks.set_states(self.marks())

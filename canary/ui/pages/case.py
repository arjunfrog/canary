import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from ... import evidence
from .. import theme
from ..widgets import ClueTable, CustodyTimeline, Funnel, LeakView, Panel, Pill, VerdictBadge, divider
from ..widgets.text import (COPY_WORDS, STAGE_WORDS, button, caption, link_button, one_in, plain, primary_button,
                            read_time, when)
from .placeholder import GAP, Page, PageHeader

STAGE_PLURAL = {"translation": "translator copies", "print": "printed copies", None: "copies"}


def sentence(view) -> str:
    """One plain sentence about what the clues showed, for whoever is looking at the case."""
    read, matched = view.clues_read, view.clues_matched
    if view.verdict == "not_our_paper":
        count = len(view.questions)
        return f"None of the {count} questions read are from the paper. This looks like a fake."
    if view.verdict in ("traced", "strong_lead"):
        kind = COPY_WORDS.get(view.stage, "Copy").lower()
        if matched == read:
            fit = f"All {read} clues match {kind} {view.copy_no}."
        else:
            fit = f"{matched} of {read} clues match {kind} {view.copy_no}. The other {read - matched} look misread."
        if view.verdict == "traced":
            return fit + " No other copy comes close."
        return fit + " That is strong, but not yet certain: a person should check before acting."
    if view.verdict == "inconclusive":
        if read == 0:
            return "This is our paper, but it shows nothing that differs from copy to copy, so no copy can be named."
        return (f"Only {read} clue{'s' if read != 1 else ''} could be read. That many can match a copy by luck, "
                "so no copy is named.")
    if view.status == "unreadable":
        return "Too little of this could be read to say whose paper it is, or whether it is ours at all."
    if view.status == "failed":
        return "The leak is saved. Once the problem is fixed, choose \"Read it again\"."
    return "This leak has not been read yet."


class Figure(QWidget):
    """A cell in the figures strip: a small label over a value, with an optional line under it."""

    def __init__(self, label: str, value: QWidget, note: QWidget | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 10)
        layout.setSpacing(2)
        self.label = caption(label)
        layout.addWidget(self.label)
        layout.addWidget(value)
        if note is not None:
            layout.addWidget(note)
        layout.addStretch(1)


class CasePage(Page):
    """One leak, from where it surfaced to which copy it came from."""

    def __init__(self, window=None):
        super().__init__(window)
        self.view = None
        self.leak_id: int | None = None
        self.case_id: int | None = None
        self.empty = plain("Open a leak from the Leaks screen to see its case.", 14, role="muted")

        # header: what this is, and every action on it
        self.header = PageHeader("Case")
        self.replay_label = Pill("", "waiting", px=12)
        self.back = button("Back to leaks")
        self.back.clicked.connect(lambda: self.app_window.show_page("leaks"))
        self.copy_link = button("Copy link")
        self.copy_link.clicked.connect(self._copy_link)
        self.read_again = primary_button("Read it again")
        self.read_again.clicked.connect(self._read_again)
        self.save_copy = button("Save a copy")
        self.save_copy.clicked.connect(self._save_copy)
        self.issue = primary_button("Issue evidence file")
        self.issue.clicked.connect(self._issue_evidence)
        for widget in (self.replay_label, self.back, self.copy_link, self.read_again, self.save_copy, self.issue):
            self.header.actions.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)

        # the figures strip: the verdict first, then the numbers behind it
        self.banner = VerdictBadge("inconclusive", px=14)
        self.copy_number = plain("", 22, weight=QFont.Weight.DemiBold)
        self.copy_kind = plain("", 12, role="muted", wrap=True)
        self.matched_value = plain("", 22, weight=QFont.Weight.DemiBold)
        self.risk_figure = plain("", 22, weight=QFont.Weight.DemiBold)
        self.read_in = plain("", 12, role="muted")
        self.figures = Panel()
        self.figures.body.setContentsMargins(0, 0, 0, 0)
        strip = QHBoxLayout()
        strip.setSpacing(0)
        self.verdict_cell = Figure("Verdict", self.banner)
        self.copy_cell = Figure("Copy", self.copy_number, self.copy_kind)
        self.matched_cell = Figure("Clues that match", self.matched_value)
        self.risk_cell = Figure("Chance of a match this good by luck", self.risk_figure, self.read_in)
        self.cell_rules = [divider(vertical=True) for _ in range(3)]
        strip.addWidget(self.verdict_cell, 5)
        for rule, cell, stretch in zip(self.cell_rules, (self.copy_cell, self.matched_cell, self.risk_cell), (3, 2, 4)):
            strip.addWidget(rule)
            strip.addWidget(cell, stretch)
        self.figures.body.addLayout(strip)
        self.figures.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        # the leak, with where it surfaced
        self.leak_section = Panel("The leak")
        self.chat, self.sender = plain("", 14, selectable=True), plain("", 14, selectable=True)
        self.posted, self.link = plain("", 14), plain("", 14, role="link", selectable=True)
        self.chat.setFont(theme.body(14, QFont.Weight.DemiBold))
        self.posted.setProperty("role", "muted")
        source = QGridLayout()
        source.setHorizontalSpacing(14)
        source.setVerticalSpacing(2)
        source.addWidget(self.chat, 0, 0)
        source.addWidget(self.sender, 0, 1)
        source.addWidget(self.posted, 0, 2)
        source.addWidget(self.link, 1, 0, 1, 3)
        source.setColumnStretch(2, 1)
        self.leak_view = LeakView()
        self.leak_note = plain("Questions from the real paper are tinted blue.", 12, role="muted")
        self.leak_section.body.addLayout(source)
        self.leak_section.body.addWidget(divider())
        self.leak_section.body.addWidget(self.leak_view, 1)
        self.leak_section.body.addWidget(self.leak_note)

        # narrowing it down
        self.funnel_section = Panel("Narrowing it down")
        self.sentence = plain("", 14, wrap=True)
        self.sentence.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.funnel = Funnel()
        self.funnel.setFixedHeight(150)
        self.funnel.progress.connect(self._on_progress)
        self.fit_value = plain("", 20, weight=QFont.Weight.DemiBold)
        self.risk_value = self.risk_figure          # the chance falls in the strip while the funnel plays
        self.step_note = plain("", 12, role="muted")
        self.play_again = link_button("Play again")
        self.play_again.clicked.connect(self.funnel.play)
        step = QHBoxLayout()
        step.setSpacing(10)
        step.addWidget(self.step_note)
        step.addWidget(self.play_again)
        step.addStretch(1)
        side = QVBoxLayout()
        side.setSpacing(1)
        side.addWidget(caption("Copies that still fit"))
        side.addWidget(self.fit_value)
        side.addLayout(step)
        side.addStretch(1)
        side_box = QWidget()
        side_box.setLayout(side)
        side_box.setFixedWidth(196)
        self.funnel_row = QWidget()
        row = QHBoxLayout(self.funnel_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        row.addWidget(self.funnel, 1)
        row.addWidget(side_box)
        self.funnel_section.body.addWidget(self.sentence)
        self.funnel_section.body.addWidget(self.funnel_row)

        self.upper = QWidget()
        upper = QHBoxLayout(self.upper)
        upper.setContentsMargins(0, 0, 0, 0)
        upper.setSpacing(GAP)
        upper.addWidget(self.leak_section, 5)
        upper.addWidget(self.funnel_section, 7, Qt.AlignmentFlag.AlignTop)

        # the copy and who held it, the clues, the response
        self.custody_section = Panel("Who held it", scroll=True)
        self.stage_words = plain("", 14, weight=QFont.Weight.DemiBold)
        self.issued_caption, self.issued_to = caption("Issued to"), plain("", 14, wrap=True)
        self.timeline = CustodyTimeline()
        for widget in (self.stage_words, self.issued_caption, self.issued_to):
            self.custody_section.body.addWidget(widget)
        self.custody_section.body.addSpacing(4)
        self.custody_section.body.addWidget(self.timeline)
        self.custody_section.body.addStretch(1)

        self.clue_section = Panel("Clues", flush=True)
        self.clue_note = plain("", 12, role="muted")
        self.clue_section.actions.addWidget(self.clue_note)
        self.clue_table = ClueTable()
        self.clue_section.body.addWidget(self.clue_table, 1)

        self.response_section = Panel("Exposed questions and response", scroll=True)
        self.response_summary = plain("", 14, wrap=True)
        self.response_advice = plain("", 14, weight=QFont.Weight.DemiBold, wrap=True)
        self.response_list = plain("", 13, role="muted", wrap=True)
        self.evidence_note = plain("", 12, role="muted", wrap=True, selectable=True)
        for widget in (self.response_summary, self.response_advice, self.response_list):
            self.response_section.body.addWidget(widget)
        self.response_section.body.addStretch(1)
        self.response_section.body.addWidget(divider())
        self.response_section.body.addWidget(self.evidence_note)

        self.lower = QWidget()
        lower = QHBoxLayout(self.lower)
        lower.setContentsMargins(0, 0, 0, 0)
        lower.setSpacing(GAP)
        lower.addWidget(self.custody_section, 4)
        lower.addWidget(self.clue_section, 4)
        lower.addWidget(self.response_section, 5)
        self.lower.setMinimumHeight(180)

        self.content = QWidget()
        column = self.frame(self.content)
        column.addWidget(self.header)
        column.addWidget(self.figures)
        column.addWidget(self.upper)
        column.addWidget(self.lower, 1)
        self.column = column
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.content)
        self.scroll.viewport().setAutoFillBackground(False)
        self.content.setAutoFillBackground(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addWidget(self.empty)
        outer.addWidget(self.scroll, 1)
        self.empty.setVisible(True)
        self.scroll.setVisible(False)

    # ---- the window's calls

    def on_lock(self) -> None:
        self.funnel.stop()

    def show_case(self, view, play: bool = True) -> None:
        self.view, self.leak_id, self.case_id = view, view.leak_id, view.case_id
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.empty.setVisible(False)
        self.scroll.setVisible(True)
        self.scroll.verticalScrollBar().setValue(0)
        replay = view.replay_label is not None
        self.header.title.setText(f"Case {view.case_id}" if view.case_id is not None else f"Leak {view.leak_id}")
        self.header.set_subtitle(f"{view.chat} · {when(view.posted_at)}")
        self.back.setVisible(not replay)
        self.replay_label.setVisible(replay)
        self.replay_label.set(view.replay_label or "", "waiting")

        self.chat.setText(view.chat)
        self.sender.setText(view.sender)
        self.posted.setText(when(view.posted_at))
        self.link.setText(view.message_url or "No link: this leak was added by hand")
        self.link.setProperty("role", "link" if view.message_url else "muted")
        self.link.style().unpolish(self.link)
        self.link.style().polish(self.link)
        self.copy_link.setVisible(bool(view.message_url))
        self.copy_link.setText("Copy link")

        self.leak_view.show_leak(view)
        self.leak_note.setVisible(self.leak_view.highlighted > 0)

        named = view.verdict in ("traced", "strong_lead") and view.copy_no is not None
        has_funnel = bool(view.steps) and view.verdict in ("traced", "strong_lead", "inconclusive")
        decided = view.verdict in ("traced", "strong_lead", "inconclusive")
        self.banner.set_verdict(view.verdict or view.status,
                                note=(view.error or "The reason was not recorded.") if view.status == "failed" else None)
        self.sentence.setText(sentence(view))
        self.read_again.setVisible(view.status == "failed" and not replay)
        self._show_figures(view, decided)
        top = Qt.AlignmentFlag(0) if decided else Qt.AlignmentFlag.AlignTop
        self.upper.layout().setAlignment(self.funnel_section, top)     # level with the leak when there is a funnel
        if decided:                                    # the case fits one screen: a short top row, the details below
            self.upper.setFixedHeight(262)
            self.column.setStretchFactor(self.upper, 0)
        else:                                          # nothing below: the leak itself gets the room
            self.upper.setMinimumHeight(0)
            self.upper.setMaximumHeight(16777215)
            self.column.setStretchFactor(self.upper, 1)

        self.funnel_section.set_title("Narrowing it down" if has_funnel else "What happened")
        self.funnel_row.setVisible(has_funnel)
        if has_funnel:
            self.funnel.set_steps(view.candidates, view.steps, named, seed=view.leak_id)
            self._on_progress(float(self.funnel.steps()))
            if play:
                self.funnel.play()
        else:
            self.funnel.set_steps(0, [], False)

        self.lower.setVisible(decided)
        if decided:
            self._show_copy(view, named)
        self._show_response(view, named)

    # ---- parts

    def _show_figures(self, view, decided: bool) -> None:
        """The figures strip: what the verdict rests on, for every state that has numbers behind it."""
        cells = (self.copy_cell, self.matched_cell, self.risk_cell)
        for label in (self.copy_number, self.copy_kind, self.matched_value, self.risk_figure, self.read_in):
            label.setText("")                          # nothing from an earlier case may linger
        shown = cells if decided else ()
        if decided:
            self.copy_cell.label.setText("Copy")
            self.risk_cell.label.setText("Chance of a match this good by luck")
            self.read_in.setText(read_time(view.elapsed_ms))
        elif view.verdict == "not_our_paper":
            questions = len(view.questions)
            self.copy_cell.label.setText("Questions read")
            self.copy_number.setText(f"{questions}")
            self.matched_cell.label.setText("Matching the bank")
            self.matched_value.setText(f"{sum(1 for q in view.questions if q.question_id)}")
            self.risk_cell.label.setText("Called not ours when")
            self.risk_figure.setText("Under 20% match")
            self.read_in.setText("and at least 5 questions are legible")
            shown = cells
        elif view.status == "unreadable":
            self.copy_cell.label.setText("Questions read")
            self.copy_number.setText(f"{len(view.questions)}")
            self.risk_cell.label.setText("Why there is no verdict")
            self.risk_figure.setText("Too damaged")
            self.read_in.setText("Close to our questions, but too damaged to match or to call a fake.")
            shown = (self.copy_cell, self.risk_cell)
        for cell, rule in zip(cells, self.cell_rules):
            cell.setVisible(cell in shown)
            rule.setVisible(cell in shown)

    def _show_copy(self, view, named: bool) -> None:
        self.stage_words.setText(STAGE_WORDS.get(view.stage, "Stage not known"))
        self.matched_cell.label.setText("Clues that match" if named else "Clues read")
        self.matched_value.setText(f"{view.clues_matched} of {view.clues_read}" if named else f"{view.clues_read}")
        self.risk_figure.setText(one_in(view.expected_false_matches))
        if named:
            self.copy_number.setText(f"{view.copy_no}")
            self.copy_kind.setText(COPY_WORDS[view.stage])
            holder = ", ".join(p for p in (view.holder_name, (view.holder_role or "").lower(), view.holder_organisation) if p)
            self.issued_to.setText(holder or "Not recorded. Run the seed to load the copies.")
        else:
            self.copy_number.setText("None named")
            self.copy_kind.setText("Not enough clues to name one fairly.")
            self.issued_to.setText("")
        self.issued_caption.setVisible(named)
        self.issued_to.setVisible(named)
        self.custody_section.setVisible(named)
        self.timeline.set_events(view.custody if named else [], view.custody_ok)
        self.clue_table.set_clues(view.clues, named)
        shown = self.clue_table.row_count()
        self.clue_note.setText(f"{view.clues_matched} of {view.clues_read} match this copy" if named
                               else f"{shown} read, none marked as a match")

    def _show_response(self, view, named: bool) -> None:
        response = view.response
        self.response_section.setVisible(response is not None)
        can_issue = named and view.replay_label is None and view.case_id is not None and view.holder_name is not None
        self.issue.setVisible(can_issue and not view.evidence_path)
        self.save_copy.setVisible(can_issue and bool(view.evidence_path))
        if response is None:
            return
        self.response_summary.setText(response["summary"])
        self.response_advice.setText(response["recommendation"])
        lines = []
        if response["exposed"]:
            numbers = ", ".join(str(q["position"]) for q in response["exposed"][:60])
            more = len(response["exposed"]) - 60
            lines.append(f"Exposed on the real paper: question {numbers}" + (f" and {more} more." if more > 0 else "."))
        swaps = [s for s in response.get("swaps", []) if s["reserve_id"]]
        if swaps:
            shown = "; ".join(f"question {s['position']} with reserve {s['reserve_id']} ({s['subject']}, {s['difficulty']})"
                              for s in swaps[:6])
            lines.append(f"Suggested swaps: {shown}" + (f"; and {len(swaps) - 6} more." if len(swaps) > 6 else "."))
        self.response_list.setText("\n".join(lines))
        self.response_list.setVisible(bool(lines))
        if view.evidence_path:
            lead = " It is marked as a lead only." if view.verdict == "strong_lead" else ""
            self.evidence_note.setText(f"Evidence file issued and signed.{lead} It is at {view.evidence_path}")
        elif can_issue:
            self.evidence_note.setText("\"Issue evidence file\" writes a signed file with the clues, the score and the "
                                       "handover log." + (" It will be marked as a lead only." if view.verdict == "strong_lead" else ""))
        else:
            self.evidence_note.setText("" if view.replay_label else "An evidence file is issued only when a copy is named.")
        self.evidence_note.setVisible(bool(self.evidence_note.text()))

    def _on_progress(self, position: float) -> None:
        view = self.view
        if view is None or not view.steps:
            return
        index = min(len(view.steps), int(position))
        total = view.candidates
        if index <= 0:
            self.fit_value.setText(f"{total:,} of {total:,}")
            self.risk_value.setText("Not yet known")
            self.step_note.setText(f"All {total:,} {STAGE_PLURAL.get(view.stage, 'copies')}, before any clue")
            return
        step = view.steps[index - 1]
        final = index >= len(view.steps)
        self.fit_value.setText(f"{self.funnel.count_at(index):,} of {total:,}")
        self.risk_value.setText(one_in(view.expected_false_matches if final else step["expected_false_matches"]))
        self.step_note.setText(f"After clue {index} of {len(view.steps)}")

    def _read_again(self) -> None:
        """Queue a failed leak again. The background thread picks it up and this screen updates when it is done."""
        window = self.app_window
        if self.view is None or window is None or window.locked or window.replay is not None:
            return
        from ... import leaks
        if leaks.read_again(window.conn, self.view.leak_id):
            window.open_leak(self.view.leak_id)

    def _copy_link(self) -> None:
        if self.view and self.view.message_url:
            QApplication.clipboard().setText(self.view.message_url)
            self.copy_link.setText("Link copied")

    def _issue_evidence(self) -> None:
        window = self.app_window
        if self.view is None or self.case_id is None or window is None or window.vault is None or window.locked:
            return
        try:
            path = evidence.build_evidence(window.conn, window.vault, self.case_id)
        except (evidence.NoEvidence, OSError) as exc:
            self.evidence_note.setText(f"The evidence file could not be written. {exc}")
            self.evidence_note.setVisible(True)
            return
        self.view.evidence_path = str(path)
        self._show_response(self.view, True)

    def _save_copy(self) -> None:
        if self.view is None or not self.view.evidence_path:
            return
        chosen = QFileDialog.getExistingDirectory(self, "Choose where to save a copy of the evidence file")
        if self.app_window is not None and self.app_window.locked:
            return                                             # it locked while the dialog was open
        if chosen:
            self.save_evidence_to(Path(chosen))

    def save_evidence_to(self, folder: Path) -> Path | None:
        """Copy the whole evidence folder (manifest, signature, key, leak) into the chosen place."""
        source = Path(self.view.evidence_path).parent
        target = folder / source.name
        try:
            shutil.copytree(source, target, dirs_exist_ok=True)
        except OSError as exc:
            self.evidence_note.setText(f"The copy could not be saved. {exc}")
            return None
        if self.app_window is not None:
            from ... import audit
            audit.record(self.app_window.conn, "evidence copy saved", {"case_id": self.case_id})
        self.evidence_note.setText(f"A copy was saved to {target}. The original is at {self.view.evidence_path}")
        return target

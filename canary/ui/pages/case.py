import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout,
                               QWidget)

from ... import evidence
from .. import theme
from ..widgets import ClueTable, CustodyTimeline, Funnel, LeakView, OMRNumber, RuledSection, VerdictBanner
from ..widgets.text import (COPY_WORDS, STAGE_WORDS, caption, heading, link_button, one_in, plain, primary_button,
                            read_time, when)
from .placeholder import Page

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
        return "The leak is saved. It can be analysed again once the problem is fixed."
    return "This leak has not been read yet."


class CasePage(Page):
    """One leak, from where it surfaced to which copy it came from."""

    def __init__(self, window=None):
        super().__init__(window)
        self.view = None
        self.leak_id: int | None = None
        self.case_id: int | None = None

        self.empty = plain("Open a leak from the Leaks screen to see its case.", 18, role="muted")
        self.back = link_button("Back to leaks")
        self.back.clicked.connect(lambda: self.app_window.show_page("leaks"))
        self.replay_label = plain("", 16, weight=QFont.Weight.Medium)
        self.replay_label.setStyleSheet(f"border: 1px solid {theme.CARBON.name()}; padding: 3px 10px;")
        top = QHBoxLayout()
        top.addWidget(self.back)
        top.addStretch(1)
        top.addWidget(self.replay_label)

        # where it surfaced
        self.source = RuledSection("Where it surfaced")
        self.chat, self.sender = plain("", 18, selectable=True), plain("", 18, selectable=True)
        self.posted, self.link = plain("", 18), plain("", 16, role="link", selectable=True)
        self.copy_link = link_button("Copy link")
        self.copy_link.clicked.connect(self._copy_link)
        grid = QGridLayout()
        grid.setHorizontalSpacing(40)
        grid.setVerticalSpacing(0)
        for column, (label, widget) in enumerate((("Chat", self.chat), ("Sender", self.sender), ("Posted", self.posted),
                                                  ("Link to the post", self.link))):
            grid.addWidget(caption(label), 0, column)
            grid.addWidget(widget, 1, column)
        grid.addWidget(self.copy_link, 1, 4)
        grid.setColumnStretch(5, 1)
        self.source.body.addLayout(grid)

        # the leak, and the funnel beside it
        self.leak_section = RuledSection("The leak")
        self.leak_view = LeakView()
        self.leak_view.setFixedHeight(388)
        self.leak_note = plain("Questions from the real paper are marked in yellow.", 14, role="muted")
        self.leak_section.body.addWidget(self.leak_view)
        self.leak_section.body.addWidget(self.leak_note)

        self.funnel_section = RuledSection("Narrowing it down")
        self.funnel = Funnel()
        self.funnel.setFixedHeight(250)
        self.funnel.progress.connect(self._on_progress)
        self.fit_caption, self.fit_value = caption("Copies that still fit"), heading("", 44, semibold=True)
        self.risk_caption, self.risk_value = caption("Chance a copy fits this well by luck"), heading("", 30, semibold=True)
        self.step_note = plain("", 14, role="muted")
        self.sentence = plain("", 16, wrap=True)
        self.read_in = plain("", 14, role="muted")
        self.play_again = link_button("Play again")
        self.play_again.clicked.connect(self.funnel.play)
        side = QVBoxLayout()
        side.setSpacing(0)
        for widget in (self.fit_caption, self.fit_value):
            side.addWidget(widget)
        side.addSpacing(6)
        for widget in (self.risk_caption, self.risk_value, self.step_note):
            side.addWidget(widget)
        side.addStretch(1)
        actions = QHBoxLayout()
        actions.addWidget(self.play_again)
        actions.addSpacing(20)
        actions.addWidget(self.read_in)
        actions.addStretch(1)
        side.addLayout(actions)
        side_box = QWidget()
        side_box.setLayout(side)
        side_box.setFixedWidth(300)
        self.funnel_row = QWidget()
        row = QHBoxLayout(self.funnel_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(28)
        row.addWidget(self.funnel, 1)
        row.addWidget(side_box)
        self.banner = VerdictBanner("inconclusive")
        self.funnel_section.body.setSpacing(12)
        self.funnel_section.body.addWidget(self.funnel_row)
        self.funnel_section.body.addWidget(self.sentence)
        self.funnel_section.body.addWidget(self.banner)
        self.funnel_section.body.addStretch(1)
        upper = QHBoxLayout()
        upper.setSpacing(40)
        upper.addWidget(self.leak_section, 4)
        upper.addWidget(self.funnel_section, 7)

        # the copy, who held it, the clues
        self.copy_section = RuledSection("The copy")
        self.stage_words = heading("", 26, semibold=True)
        self.copy_kind = plain("", 16, role="muted")
        self.omr_slot = QVBoxLayout()
        self.omr: OMRNumber | None = None
        self.issued_caption, self.issued_to = caption("Issued to"), plain("", 16, wrap=True)
        for widget in (self.stage_words, self.copy_kind):
            self.copy_section.body.addWidget(widget)
        self.copy_section.body.addSpacing(8)
        self.copy_section.body.addLayout(self.omr_slot)
        self.copy_section.body.addSpacing(8)
        self.copy_section.body.addWidget(self.issued_caption)
        self.copy_section.body.addWidget(self.issued_to)
        self.copy_section.body.addStretch(1)

        self.custody_section = RuledSection("Who held it")
        self.timeline = CustodyTimeline()
        self.custody_section.body.addWidget(self.timeline)
        self.custody_section.body.addStretch(1)

        self.clue_section = RuledSection("Clues")
        self.clue_note = plain("", 14, role="muted", wrap=True)
        self.clue_table = ClueTable()
        self.clue_section.body.addWidget(self.clue_note)
        self.clue_section.body.addWidget(self.clue_table)
        self.clue_section.body.addStretch(1)
        self.lower = QWidget()
        lower = QHBoxLayout(self.lower)
        lower.setContentsMargins(0, 0, 0, 0)
        lower.setSpacing(40)
        lower.addWidget(self.copy_section, 3)
        lower.addWidget(self.custody_section, 5)
        lower.addWidget(self.clue_section, 5)

        # exposed questions and response
        self.response_section = RuledSection("Exposed questions and response")
        self.response_summary = plain("", 16, wrap=True)
        self.response_advice = plain("", 16, weight=QFont.Weight.Medium, wrap=True)
        self.response_list = plain("", 15, role="muted", wrap=True)
        self.issue = primary_button("Issue evidence file")
        self.issue.clicked.connect(self._issue_evidence)
        self.save_copy = link_button("Save a copy")
        self.save_copy.clicked.connect(self._save_copy)
        self.evidence_note = plain("", 14, role="muted", wrap=True, selectable=True)
        evidence_row = QHBoxLayout()
        evidence_row.setSpacing(20)
        evidence_row.addWidget(self.issue)
        evidence_row.addWidget(self.save_copy)
        evidence_row.addWidget(self.evidence_note, 1)
        for widget in (self.response_summary, self.response_advice, self.response_list):
            self.response_section.body.addWidget(widget)
        self.response_section.body.addSpacing(10)
        self.response_section.body.addLayout(evidence_row)

        self.content = QWidget()
        column = QVBoxLayout(self.content)
        column.setContentsMargins(0, 0, 14, 0)
        column.setSpacing(0)
        column.addLayout(top)
        column.addSpacing(6)
        column.addWidget(self.source)
        column.addLayout(upper)
        column.addWidget(self.lower)
        column.addWidget(self.response_section)
        column.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.content)
        self.scroll.viewport().setAutoFillBackground(False)
        self.content.setAutoFillBackground(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.empty)
        outer.addWidget(self.scroll, 1)
        self.scroll.setVisible(False)

    # ---- the window's calls

    def marks(self) -> list[bool]:
        """One mark per clue, black when it was read."""
        if self.view is None:
            return [False] * 14
        return [c.read_ok for c in self.view.clues if c.kind] or [False] * 14

    def on_lock(self) -> None:
        self.funnel.stop()

    def show_case(self, view, play: bool = True) -> None:
        self.view, self.leak_id, self.case_id = view, view.leak_id, view.case_id
        self.empty.setVisible(False)
        self.scroll.setVisible(True)
        self.scroll.verticalScrollBar().setValue(0)
        replay = view.replay_label is not None
        self.back.setVisible(not replay)
        self.replay_label.setVisible(replay)
        self.replay_label.setText(view.replay_label or "")

        self.chat.setText(view.chat)
        self.sender.setText(view.sender)
        self.posted.setText(when(view.posted_at))
        self.link.setText(view.message_url or "No link: this leak was added by hand")
        self.link.setProperty("role", "link" if view.message_url else "muted")
        self.link.style().unpolish(self.link)
        self.link.style().polish(self.link)
        self.copy_link.setVisible(bool(view.message_url))

        self.leak_view.show_leak(view)
        self.leak_note.setVisible(self.leak_view.highlighted > 0)

        named = view.verdict in ("traced", "strong_lead") and view.copy_no is not None
        has_funnel = bool(view.steps) and view.verdict in ("traced", "strong_lead", "inconclusive")
        self.funnel_row.setVisible(has_funnel)
        self.banner.set_verdict(view.verdict or view.status,
                                note=(view.error or "The reason was not recorded.") if view.status == "failed" else None)
        self.sentence.setText(sentence(view))
        self.read_in.setText(read_time(view.elapsed_ms))
        if has_funnel:
            self.funnel.set_steps(view.candidates, view.steps, named, seed=view.leak_id)
            self._on_progress(float(self.funnel.steps()))
            if play:
                self.funnel.play()
        else:
            self.funnel.set_steps(0, [], False)

        decided = view.verdict in ("traced", "strong_lead", "inconclusive")
        self.lower.setVisible(decided)
        if decided:
            self._show_copy(view, named)
        self._show_response(view, named)

    # ---- parts

    def _show_copy(self, view, named: bool) -> None:
        self.stage_words.setText(STAGE_WORDS.get(view.stage, "Stage not known"))
        if self.omr is not None:
            self.omr_slot.removeWidget(self.omr)
            self.omr.setParent(None)                           # gone from the screen now, not when Qt gets round to it
            self.omr.deleteLater()
            self.omr = None
        if named:
            self.copy_kind.setText(f"{COPY_WORDS[view.stage]} number")
            self.omr = OMRNumber(view.copy_no, digits=4 if view.stage == "print" else 2)
            self.omr_slot.addWidget(self.omr, 0, Qt.AlignmentFlag.AlignLeft)
            holder = ", ".join(p for p in (view.holder_name, (view.holder_role or "").lower(), view.holder_organisation) if p)
            self.issued_to.setText(holder or "Not recorded. Run the seed to load the copies.")
        else:
            self.copy_kind.setText("No copy is named. There are not enough clues to do that fairly.")
            self.issued_to.setText("")
        self.issued_caption.setVisible(named)
        self.issued_to.setVisible(named)
        self.custody_section.setVisible(named)
        self.timeline.set_events(view.custody if named else [], view.custody_ok)
        self.clue_table.set_clues(view.clues, named)
        shown = self.clue_table.row_count()
        self.clue_note.setText(f"{view.clues_matched} of {view.clues_read} clues match this copy." if named
                               else f"{shown} clue{'s' if shown != 1 else ''} read. No copy is named, so none is marked as a match.")

    def _show_response(self, view, named: bool) -> None:
        response = view.response
        self.response_section.setVisible(response is not None)
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
                              for s in swaps[:8])
            lines.append(f"Suggested swaps: {shown}" + (f"; and {len(swaps) - 8} more." if len(swaps) > 8 else "."))
        self.response_list.setText("\n".join(lines))
        self.response_list.setVisible(bool(lines))
        can_issue = named and view.replay_label is None and view.case_id is not None and view.holder_name is not None
        self.issue.setVisible(can_issue and not view.evidence_path)
        self.save_copy.setVisible(can_issue and bool(view.evidence_path))
        if view.evidence_path:
            lead = " It is marked as a lead only." if view.verdict == "strong_lead" else ""
            self.evidence_note.setText(f"Evidence file issued and signed.{lead} It is at {view.evidence_path}")
        elif can_issue:
            self.evidence_note.setText("Writes a signed file with the clues, the score and the handover log."
                                       + (" It will be marked as a lead only." if view.verdict == "strong_lead" else ""))
        else:
            self.evidence_note.setText("" if view.replay_label else
                                       "An evidence file is issued only when a copy is named.")

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
            return
        self.view.evidence_path = str(path)
        self._show_response(self.view, True)

    def _save_copy(self) -> None:
        if self.view is None or not self.view.evidence_path:
            return
        chosen = QFileDialog.getExistingDirectory(self, "Choose where to save a copy of the evidence file")
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

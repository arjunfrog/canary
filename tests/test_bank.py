from canary.bank import load_bank


def test_counts():
    bank = load_bank()
    assert len(bank.questions) == 250
    assert len(bank.paper) == 180
    assert len(bank.traps) == 24
    assert len(bank.reserves) == 46


def test_paper_is_in_order_and_page_one_is_numeric_physics():
    paper = load_bank().paper
    assert [q.position for q in paper] == list(range(1, 181))
    assert all(q.kind == "numeric" and q.subject == "physics" for q in paper[:14])


def test_numeric_questions_have_one_real_set_and_eight_decoys():
    for q in load_bank().questions:
        if q.kind != "numeric":
            assert len(q.options) == 4 and q.options[q.correct_index]
            continue
        assert len(q.value_sets) == 9
        assert q.real.is_real and not any(d.is_real for d in q.decoys)
        assert len({v.stem for v in q.value_sets}) == 9
        assert all(len(set(v.options)) == 4 for v in q.value_sets)


def test_traps_are_biology_and_never_on_the_paper():
    assert all(q.subject == "biology" and q.position is None for q in load_bank().traps)

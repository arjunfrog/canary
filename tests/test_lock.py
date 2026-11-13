from canary.lock import LockGuard


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_four_wrong_tries_do_not_block():
    guard = LockGuard(clock=Clock())
    for _ in range(4):
        guard.failed()
    assert guard.blocked_for() == 0


def test_fifth_wrong_try_blocks_for_a_minute_then_clears():
    clock = Clock()
    guard = LockGuard(clock=clock)
    for _ in range(5):
        guard.failed()
    assert guard.blocked_for() == 60
    clock.now = 59
    assert guard.blocked_for() == 1
    clock.now = 61
    assert guard.blocked_for() == 0


def test_success_resets_the_count():
    guard = LockGuard(clock=Clock())
    for _ in range(4):
        guard.failed()
    guard.succeeded()
    for _ in range(4):
        guard.failed()
    assert guard.blocked_for() == 0

from serialscope.data import ChannelHistory
from serialscope.parsing import ChannelUpdate


class MutableClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


def test_history_uses_monotonic_elapsed_sample_times() -> None:
    clock = MutableClock()
    history = ChannelHistory(clock=clock)
    history.add_update(ChannelUpdate(("A",), (1,)))
    clock.value += 0.25
    history.add_update(ChannelUpdate(("A",), (2,)))
    clock.value += 1.5
    history.add_update(ChannelUpdate(("A",), (3,)))

    assert history.points("A") == ((0.0, 0.25, 1.75), (1, 2, 3))


def test_history_prunes_samples_outside_bounded_window() -> None:
    clock = MutableClock()
    history = ChannelHistory(window_seconds=60.0, clock=clock)
    history.add_update(ChannelUpdate(("A",), (1,)))
    clock.value += 59.0
    history.add_update(ChannelUpdate(("A",), (2,)))
    clock.value += 2.0
    history.add_update(ChannelUpdate(("A",), (3,)))

    assert history.points("A") == ((59.0, 61.0), (2, 3))


def test_default_history_retains_one_hour_and_remains_bounded() -> None:
    clock = MutableClock()
    history = ChannelHistory(clock=clock)
    history.add_update(ChannelUpdate(("A",), (1,)))
    clock.value += 3_599.0
    history.add_update(ChannelUpdate(("A",), (2,)))
    clock.value += 2.0
    history.add_update(ChannelUpdate(("A",), (3,)))

    assert history.points("A") == ((3_599.0, 3_601.0), (2, 3))


def test_history_tracks_partial_channel_updates_independently() -> None:
    clock = MutableClock()
    history = ChannelHistory(clock=clock)
    history.add_update(ChannelUpdate(("A", "B"), (1, 10), False))
    clock.value += 0.5
    history.add_update(ChannelUpdate(("A",), (2,), False))

    assert history.channel_names == ("A", "B")
    assert history.points("A") == ((0.0, 0.5), (1, 2))
    assert history.points("B") == ((0.0,), (10,))


def test_reset_clears_history_and_elapsed_origin() -> None:
    clock = MutableClock()
    history = ChannelHistory(clock=clock)
    history.add_update(ChannelUpdate(("A",), (1,)))

    history.reset()
    clock.value += 12.0
    history.add_update(ChannelUpdate(("B",), (2,)))

    assert history.points("A") == ((), ())
    assert history.points("B") == ((0.0,), (2,))

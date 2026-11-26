from datetime import UTC, datetime

import pytest

from beekeeper.factory.calendar import BERLIN
from beekeeper.factory.queue import Queue, load_queue, save_queue
from beekeeper.factory.slots import (
    TRANSITIONS,
    Slots,
    State,
    is_open,
    load_slots,
    release_dates,
    save_slots,
    stop,
    write_script,
)
from beekeeper.factory.store import StateError


def berlin(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=BERLIN)


NOW = berlin(2026, 11, 26, 12)  # Thursday
TUE = berlin(2026, 12, 1, 8)
THU = berlin(2026, 12, 3, 8)
TUE2 = berlin(2026, 12, 8, 8)
THU2 = berlin(2026, 12, 10, 8)


def three():
    q = Queue()
    q, a = q.add("Ведмідь у сплячці", "а було таке...", NOW)
    q, b = q.add("Їжак на співбесіді", "bible/stories/hedgehog.md", NOW)
    q, c = q.add("Вовк і Excel", "вовк сидить...", NOW)
    return q, a, b, c


# --- queue ---


def test_add_gives_increasing_ids_at_the_end():
    q, a, b, c = three()
    assert [a.id, b.id, c.id] == [1, 2, 3]
    assert q.ids() == [1, 2, 3]
    assert q.head() == a
    assert q.next_id == 4


def test_add_strips_and_refuses_empty_text():
    q, idea = Queue().add("  Назва  ", " текст ", NOW)
    assert (idea.title, idea.source) == ("Назва", "текст")
    with pytest.raises(StateError):
        Queue().add("  ", "текст", NOW)
    with pytest.raises(StateError):
        Queue().add("Назва", "", NOW)


def test_add_needs_aware_time():
    with pytest.raises(ValueError):
        Queue().add("a", "b", datetime(2026, 11, 26))


def test_edit_title_and_source():
    q, a, *_ = three()
    q2 = q.edit(a.id, title="Медунко")
    assert q2.get(a.id).title == "Медунко"
    assert q2.get(a.id).source == a.source
    assert q.get(a.id).title == a.title  # the old value is untouched
    q3 = q2.edit(a.id, source="новий текст")
    assert q3.get(a.id).source == "новий текст"
    with pytest.raises(StateError):
        q.edit(a.id)
    with pytest.raises(StateError):
        q.edit(a.id, title=" ")


def test_move_up_first_delete():
    q, a, b, c = three()
    assert q.move(c.id, 2).ids() == [1, 3, 2]
    assert q.up(b.id).ids() == [2, 1, 3]
    assert q.first(c.id).ids() == [3, 1, 2]
    assert q.delete(b.id).ids() == [1, 3]
    assert q.position(c.id) == 3


def test_refused_queue_ops():
    q, a, *_ = three()
    with pytest.raises(StateError, match="already first"):
        q.up(a.id)
    with pytest.raises(StateError):
        q.move(a.id, 0)
    with pytest.raises(StateError):
        q.move(a.id, 4)
    with pytest.raises(StateError, match="no idea #9"):
        q.delete(9)


def test_deleted_id_is_not_reused():
    q, *_ = three()
    q = q.delete(3)
    q, idea = q.add("ще", "ще", NOW)
    assert idea.id == 4


def test_take_and_put_back_to_the_head():
    q, a, b, c = three()
    q2, taken = q.take(b.id)
    assert taken == b and q2.ids() == [1, 3]
    q3 = q2.put_back(taken)
    assert q3.ids() == [2, 1, 3]
    with pytest.raises(StateError):
        q3.put_back(taken)


def test_queue_round_trip(tmp_path):
    q, *_ = three()
    path = tmp_path / "factory" / "queue.yaml"
    save_queue(q, path)
    assert load_queue(path) == q
    text = path.read_text(encoding="utf-8")
    assert "Ведмідь у сплячці" in text  # readable Ukrainian, not \u escapes
    assert not list(path.parent.glob(".*.tmp"))


def test_missing_queue_file_is_empty(tmp_path):
    assert load_queue(tmp_path / "queue.yaml") == Queue()


@pytest.mark.parametrize(
    "text, message",
    [
        ("- 1\n", "mapping"),
        ("items:\n  - {id: 1, title: a, source: b}\n", "missing 'added'"),
        ("items:\n  - {id: 0, title: a, source: b, added: '2026-11-26T12:00:00+01:00'}\n", "id"),
        ("items:\n  - {id: 1, title: a, source: b, added: '2026-11-26T12:00:00'}\n", "offset"),
        (
            "items:\n"
            "  - {id: 1, title: a, source: b, added: '2026-11-26T12:00:00+01:00'}\n"
            "  - {id: 1, title: c, source: d, added: '2026-11-26T12:00:00+01:00'}\n",
            "duplicate",
        ),
        (
            "next_id: 1\nitems:\n"
            "  - {id: 1, title: a, source: b, added: '2026-11-26T12:00:00+01:00'}\n",
            "next_id",
        ),
    ],
)
def test_broken_queue_file(tmp_path, text, message):
    path = tmp_path / "queue.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(StateError, match=message):
        load_queue(path)


def test_unquoted_yaml_timestamp_is_accepted(tmp_path):
    path = tmp_path / "queue.yaml"
    path.write_text(
        "items:\n  - {id: 1, title: a, source: b, added: 2026-11-26 12:00:00+01:00}\n",
        encoding="utf-8",
    )
    assert load_queue(path).get(1).added == NOW


# --- slots ---


def scripted_slot():
    q, a, *_ = three()
    slots = Slots().plan(TUE, a, NOW)
    q, slots = write_script(q, slots, TUE, "003-vedmid", berlin(2026, 11, 28, 2))
    return q, slots


SAT_SEND = berlin(2026, 11, 28, 7)


def walk(slots, *states, at=SAT_SEND):
    for state in states:
        slots = slots.advance(TUE, state, at)
    return slots


def test_plan_and_replan():
    q, a, b, _ = three()
    slots = Slots().plan(TUE, a, NOW)
    assert slots.get(TUE).state == State.PLANNED
    assert slots.get(TUE).times == {"planned": NOW}
    slots = slots.plan(TUE, b, NOW)
    assert slots.get(TUE).idea == b
    assert len(slots.items) == 1
    assert Slots() == slots.unplan(TUE)


def test_plan_refuses_non_slots_late_slots_and_bound_slots():
    _, a, *_ = three()
    with pytest.raises(StateError, match="not a release slot"):
        Slots().plan(berlin(2026, 12, 2, 8), a, NOW)
    with pytest.raises(StateError, match="too late"):
        Slots().plan(TUE, a, berlin(2026, 11, 28, 7))
    _, slots = scripted_slot()
    with pytest.raises(StateError, match="already scripted"):
        slots.plan(TUE, a, NOW)
    with pytest.raises(StateError, match="only a planned"):
        slots.unplan(TUE)


def test_plan_accepts_slot_in_utc():
    _, a, *_ = three()
    slots = Slots().plan(datetime(2026, 12, 1, 7, tzinfo=UTC), a, NOW)
    assert slots.get(TUE).release == TUE


def test_write_script_takes_the_idea_out_of_the_queue():
    q, slots = scripted_slot()
    slot = slots.get(TUE)
    assert slot.state == State.SCRIPTED
    assert slot.episode == "003-vedmid"
    assert q.ids() == [2, 3]


def test_write_script_uses_the_latest_text_of_the_idea():
    q, a, *_ = three()
    slots = Slots().plan(TUE, a, NOW)
    q = q.edit(a.id, title="Медунко")
    _, slots = write_script(q, slots, TUE, "003-medunko", NOW)
    assert slots.get(TUE).idea.title == "Медунко"


def test_full_happy_path_records_every_time():
    _, slots = scripted_slot()
    slots = walk(slots, State.SENT, State.SENT, State.ACCEPTED, State.BUILT, State.HANDED_OFF)
    slots = slots.advance(TUE, State.RELEASED, TUE)
    slot = slots.get(TUE)
    assert slot.state == State.RELEASED
    assert set(slot.times) == {
        "planned",
        "scripted",
        "sent",
        "accepted",
        "built",
        "handed_off",
        "released",
    }


def every_state_reachable():
    return [s for s in State if s != State.PLANNED]


@pytest.mark.parametrize("start", list(State))
@pytest.mark.parametrize("to", every_state_reachable())
def test_only_listed_transitions_pass(start, to):
    q, a, *_ = three()
    path = {
        State.PLANNED: [],
        State.SCRIPTED: [],
        State.SENT: [State.SENT],
        State.ACCEPTED: [State.SENT, State.ACCEPTED],
        State.BUILT: [State.SENT, State.ACCEPTED, State.BUILT],
        State.HANDED_OFF: [State.SENT, State.ACCEPTED, State.BUILT, State.HANDED_OFF],
        State.STOPPED: [State.SENT, State.STOPPED],
        State.RELEASED: [State.SENT, State.ACCEPTED, State.BUILT, State.HANDED_OFF],
    }[start]
    slots = Slots().plan(TUE, a, NOW)
    if start != State.PLANNED:
        _, slots = write_script(q, slots, TUE, "003-x", NOW)
    slots = walk(slots, *path)
    if start == State.RELEASED:
        slots = slots.advance(TUE, State.RELEASED, TUE)
    assert slots.get(TUE).state == start
    # a time when both stop and release would be allowed by the clock is impossible, so
    # check each target at the time it needs
    at = TUE if to == State.RELEASED else NOW
    episode = "003-x" if to == State.SCRIPTED else None
    if to in TRANSITIONS[start]:
        assert slots.advance(TUE, to, at, episode=episode).get(TUE).state == to
    else:
        with pytest.raises(StateError, match="refused"):
            slots.advance(TUE, to, at, episode=episode)


def test_refused_transition_changes_nothing():
    _, slots = scripted_slot()
    with pytest.raises(StateError):
        slots.advance(TUE, State.BUILT, NOW)
    assert slots.get(TUE).state == State.SCRIPTED


def test_scripted_needs_episode_and_only_there():
    _, a, *_ = three()
    slots = Slots().plan(TUE, a, NOW)
    with pytest.raises(StateError, match="episode"):
        slots.advance(TUE, State.SCRIPTED, NOW)
    _, slots = scripted_slot()
    with pytest.raises(StateError, match="episode"):
        slots.advance(TUE, State.SENT, NOW, episode="other")


def test_released_only_after_release_time():
    _, slots = scripted_slot()
    slots = walk(slots, State.SENT, State.ACCEPTED, State.BUILT, State.HANDED_OFF)
    with pytest.raises(StateError, match="not come"):
        slots.advance(TUE, State.RELEASED, berlin(2026, 12, 1, 7, 59))


def test_stop_returns_idea_to_queue_head_and_uses_up_the_slot():
    q, slots = scripted_slot()
    slots = walk(slots, State.SENT, State.ACCEPTED)
    q, slots = stop(q, slots, TUE, berlin(2026, 11, 30, 9))
    assert slots.get(TUE).state == State.STOPPED
    assert q.ids() == [1, 2, 3]
    # the stopped slot is not given to anyone; idea 1 waits for Thursday
    dates = release_dates(q, slots, berlin(2026, 11, 26, 12))
    assert [(i.id, d) for i, d in dates] == [(1, THU), (2, TUE2), (3, THU2)]


def test_stop_after_release_time_is_refused():
    q, slots = scripted_slot()
    slots = walk(slots, State.SENT, State.ACCEPTED, State.BUILT, State.HANDED_OFF)
    with pytest.raises(StateError, match="passed"):
        stop(q, slots, TUE, TUE)
    assert slots.get(TUE).state == State.HANDED_OFF


def test_stop_before_the_script_is_sent_is_refused():
    q, slots = scripted_slot()
    with pytest.raises(StateError, match="refused"):
        stop(q, slots, TUE, NOW)


def test_message_ids():
    _, slots = scripted_slot()
    slots = slots.set_message(TUE, "script", 41).set_message(TUE, "script", 42)
    slots = slots.set_message(TUE, "reel", 50)
    assert slots.get(TUE).messages == {"script": 42, "reel": 50}
    with pytest.raises(StateError):
        slots.set_message(TUE, "video", 1)
    with pytest.raises(StateError, match="no slot"):
        slots.set_message(THU, "script", 1)


# --- release dates ---


def test_release_dates_follow_the_queue_order():
    q, *_ = three()
    dates = release_dates(q, Slots(), NOW)
    assert [(i.id, d) for i, d in dates] == [(1, TUE), (2, THU), (3, TUE2)]
    dates = release_dates(q.first(3), Slots(), NOW)
    assert [(i.id, d) for i, d in dates] == [(3, TUE), (1, THU), (2, TUE2)]


def test_release_dates_skip_bound_slots_but_not_planned_ones():
    q, a, b, c = three()
    slots = Slots().plan(TUE, a, NOW)
    assert release_dates(q, slots, NOW)[0] == (a, TUE)  # planned: queue order still decides
    q, slots = write_script(q, slots, TUE, "003-x", NOW)
    dates = release_dates(q, slots, NOW)
    assert [(i.id, d) for i, d in dates] == [(2, THU), (3, TUE2)]


def test_release_dates_skip_slots_too_late_for_the_script():
    q, *_ = three()
    # Saturday 07:00 is the send deadline for Tuesday: from then on Tuesday is closed
    assert is_open(TUE, berlin(2026, 11, 28, 6, 59))
    assert not is_open(TUE, berlin(2026, 11, 28, 7))
    dates = release_dates(q, Slots(), berlin(2026, 11, 28, 7))
    assert [d for _, d in dates] == [THU, TUE2, THU2]


def test_release_dates_empty_queue():
    assert release_dates(Queue(), Slots(), NOW) == []


# --- slots file ---


def test_slots_round_trip(tmp_path):
    _, slots = scripted_slot()
    slots = walk(slots, State.SENT).set_message(TUE, "script", 42)
    _, a, b, _ = three()
    slots = slots.plan(THU, b, NOW)
    path = tmp_path / "slots.yaml"
    save_slots(slots, path)
    assert load_slots(path) == slots
    assert [s.release for s in load_slots(path).items] == [TUE, THU]


def test_missing_slots_file_is_empty(tmp_path):
    assert load_slots(tmp_path / "slots.yaml") == Slots()


IDEA = "{id: 1, title: a, source: b, added: '2026-11-26T12:00:00+01:00'}"


@pytest.mark.parametrize(
    "entry, message",
    [
        (f"{{release: '2026-12-02T08:00:00+01:00', state: planned, idea: {IDEA}}}", "release"),
        (f"{{release: '2026-12-01T08:00:00+01:00', state: dancing, idea: {IDEA}}}", "unknown"),
        (f"{{release: '2026-12-01T08:00:00+01:00', state: sent, idea: {IDEA}}}", "episode"),
        ("{release: '2026-12-01T08:00:00+01:00', state: planned}", "missing 'idea'"),
        (
            f"{{release: '2026-12-01T08:00:00+01:00', state: planned, idea: {IDEA},"
            " messages: {video: 1}}",
            "message",
        ),
    ],
)
def test_broken_slots_file(tmp_path, entry, message):
    path = tmp_path / "slots.yaml"
    path.write_text(f"slots:\n  - {entry}\n", encoding="utf-8")
    with pytest.raises(StateError, match=message):
        load_slots(path)


def test_duplicate_slot_in_file(tmp_path):
    entry = f"{{release: '2026-12-01T08:00:00+01:00', state: planned, idea: {IDEA}}}"
    path = tmp_path / "slots.yaml"
    path.write_text(f"slots:\n  - {entry}\n  - {entry}\n", encoding="utf-8")
    with pytest.raises(StateError, match="same release"):
        load_slots(path)

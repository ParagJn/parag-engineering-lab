"""Run events: the durable log, the live fan-out, what an event may contain, and the append-only guarantee."""
from __future__ import annotations

import asyncio
import sqlite3

import pytest

from app.models import InvalidInput, NotFoundError
from app.run.events import EVENT_TYPES, EventBus, clean_reason, format_comment, format_sse

pytestmark = pytest.mark.anyio


@pytest.fixture
def run(store, project):
    return store.runs.start(project.id, "requirements")


def types(events):
    return [e.type for e in events]


# ---- the vocabulary ---------------------------------------------------------------------------------------------

def test_the_event_vocabulary_is_exactly_the_one_the_screen_will_rely_on():
    assert EVENT_TYPES == (
        "run.started", "artefact.started", "artefact.attempt", "artefact.finished", "artefact.failed", "artefact.skipped", "build.round",
        "piece.started", "piece.finished", "piece.failed", "review.started", "review.finished", "review.paused", "gate.changed", "run.stopped", "run.finished",
    )
    assert len(set(EVENT_TYPES)) == len(EVENT_TYPES)


def test_an_event_type_outside_the_vocabulary_is_refused_and_nothing_is_stored(store, project, run):
    bus = EventBus(store)
    with pytest.raises(ValueError, match="unknown event type 'artefact.exploded'"):
        bus.publish(project.id, run.id, "artefact.exploded", {})
    assert store.run_events.list(project.id) == []


def test_heartbeat_and_dropped_are_not_event_types_because_they_are_never_stored(store):
    from app.run.events import DROPPED, HEARTBEAT

    assert HEARTBEAT not in EVENT_TYPES and DROPPED not in EVENT_TYPES


# ---- the durable log ---------------------------------------------------------------------------------------------------

def test_events_are_stored_with_strictly_increasing_ids_and_their_data(store, project, run):
    bus = EventBus(store)
    first = bus.publish(project.id, run.id, "run.started", {"phase": "requirements"})
    second = bus.publish(project.id, run.id, "artefact.started", {"key": "personas"})
    assert second.id > first.id > 0
    stored = store.run_events.list(project.id)
    assert [(e.id, e.type, e.data) for e in stored] == [(first.id, "run.started", {"phase": "requirements"}), (second.id, "artefact.started", {"key": "personas"})]
    assert stored[0].run_id == run.id and stored[0].at


def test_after_returns_exactly_the_later_events_and_nothing_twice(store, project, run):
    bus = EventBus(store)
    ids = [bus.publish(project.id, run.id, "artefact.started", {"key": str(i)}).id for i in range(5)]
    assert [e.id for e in store.run_events.list(project.id, after=ids[1])] == ids[2:]
    assert store.run_events.list(project.id, after=ids[-1]) == []
    assert [e.id for e in store.run_events.list(project.id, after=0)] == ids
    assert [e.id for e in store.run_events.list(project.id, limit=2)] == ids[:2]


def test_a_late_joiner_sees_the_whole_run_in_order(store, project, run):
    bus = EventBus(store)
    for i in range(4):
        bus.publish(project.id, run.id, "artefact.finished", {"key": str(i)})
    assert [e.data["key"] for e in store.run_events.list(project.id)] == ["0", "1", "2", "3"]


def test_events_are_scoped_to_their_project(store, project, run):
    other = store.projects.create(name="Other", actor="system")
    other_run = store.runs.start(other.id, "requirements")
    bus = EventBus(store)
    mine = bus.publish(project.id, run.id, "run.started", {})
    theirs = bus.publish(other.id, other_run.id, "run.started", {})
    assert [e.id for e in store.run_events.list(project.id)] == [mine.id]
    assert [e.id for e in store.run_events.list(other.id)] == [theirs.id]
    assert store.run_events.last_id(project.id) == mine.id and store.run_events.last_id(other.id) == theirs.id


def test_filtering_by_run_returns_only_that_runs_events(store, project):
    a, b = store.runs.start(project.id, "setup"), store.runs.start(project.id, "requirements")
    bus = EventBus(store)
    bus.publish(project.id, a.id, "run.started", {})
    bus.publish(project.id, b.id, "run.started", {})
    assert [e.run_id for e in store.run_events.list(project.id, run_id=b.id)] == [b.id]


def test_an_event_for_a_run_of_another_project_is_refused(store, project, run):
    other = store.projects.create(name="Other", actor="system")
    with pytest.raises(NotFoundError):
        store.run_events.append(other.id, run.id, "run.started", {})
    with pytest.raises(NotFoundError):
        store.run_events.append(project.id, "no-such-run", "run.started", {})


def test_an_unknown_project_has_no_events_to_list(store):
    with pytest.raises(NotFoundError):
        store.run_events.list("nope")


def test_a_negative_after_or_limit_is_refused(store, project):
    with pytest.raises(InvalidInput):
        store.run_events.list(project.id, after=-1)
    with pytest.raises(InvalidInput):
        store.run_events.list(project.id, limit=-1)


def test_an_oversize_event_is_refused_rather_than_stored(store, project, run):
    with pytest.raises(InvalidInput, match="limited to 20000 bytes"):
        store.run_events.append(project.id, run.id, "run.started", {"x": "y" * 30_000})
    assert store.run_events.list(project.id) == []


def test_event_data_must_be_json(store, project, run):
    with pytest.raises(InvalidInput, match="JSON"):
        store.run_events.append(project.id, run.id, "run.started", {"x": object()})


def test_the_log_is_append_only(store, project, run):
    EventBus(store).publish(project.id, run.id, "run.started", {})
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with store.db.write() as conn:
            conn.execute("UPDATE run_events SET type = 'run.finished'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with store.db.write() as conn:
            conn.execute("DELETE FROM run_events")
    assert types(store.run_events.list(project.id)) == ["run.started"]


# ---- the run record ---------------------------------------------------------------------------------------------------------

def test_a_run_is_started_and_ended_once(store, project):
    record = store.runs.start(project.id, "requirements")
    assert (record.status, record.finished_at, record.totals) == ("running", None, None)
    ended = store.runs.end(record.id, "finished", totals={"calls": 3})
    assert (ended.status, ended.totals) == ("finished", {"calls": 3}) and ended.finished_at
    with pytest.raises(Exception, match="already ended"):
        store.runs.end(record.id, "failed")


@pytest.mark.parametrize("status, reason, message", [
    ("running", None, "must be one of"), ("exploded", None, "must be one of"), ("stopped", "mood", "stop_reason must be one of"),
])
def test_a_bad_end_is_refused_and_the_run_stays_running(store, project, status, reason, message):
    record = store.runs.start(project.id, "requirements")
    with pytest.raises(InvalidInput, match=message):
        store.runs.end(record.id, status, stop_reason=reason)
    assert store.runs.get(project.id, record.id).status == "running"


def test_a_run_is_found_only_in_its_own_project(store, project):
    record = store.runs.start(project.id, "requirements")
    other = store.projects.create(name="Other", actor="system")
    with pytest.raises(NotFoundError):
        store.runs.get(other.id, record.id)
    assert store.runs.get(project.id, record.id).id == record.id


def test_runs_can_be_listed_by_phase_and_status(store, project):
    a = store.runs.start(project.id, "setup")
    store.runs.end(a.id, "finished")
    b = store.runs.start(project.id, "requirements")
    assert [r.id for r in store.runs.list(project.id)] == [a.id, b.id]
    assert [r.id for r in store.runs.list(project.id, status="running")] == [b.id]
    assert [r.id for r in store.runs.list(project.id, phase_key="setup")] == [a.id]


def test_a_run_for_an_unknown_project_is_refused(store):
    with pytest.raises(NotFoundError):
        store.runs.start("nope", "setup")


def test_runs_left_running_by_a_dead_process_are_marked_interrupted_at_start_up_and_say_so_in_the_log(store, project):
    live = store.runs.start(project.id, "requirements")
    done = store.runs.start(project.id, "setup")
    store.runs.end(done.id, "finished")
    assert store.runs.interrupt_unfinished() == 1
    record = store.runs.get(project.id, live.id)
    assert record.status == "interrupted" and record.finished_at and "backend stopped" in record.totals["note"]
    assert store.runs.get(project.id, done.id).status == "finished"          # a finished run is left alone
    [event] = store.run_events.list(project.id)
    assert event.type == "run.stopped" and event.data["status"] == "interrupted" and event.run_id == live.id
    assert store.runs.interrupt_unfinished() == 0                            # idempotent


# ---- live delivery ---------------------------------------------------------------------------------------------------------------

async def test_a_watcher_receives_events_live_and_in_order(store, project, run):
    bus = EventBus(store)
    watcher = bus.watch(project.id)
    sent = [bus.publish(project.id, run.id, "artefact.started", {"key": str(i)}) for i in range(3)]
    got = [await asyncio.wait_for(watcher.queue.get(), 1) for _ in range(3)]
    assert [e.id for e in got] == [e.id for e in sent]
    bus.unwatch(watcher)


async def test_two_watchers_both_receive_everything(store, project, run):
    bus = EventBus(store)
    a, b = bus.watch(project.id), bus.watch(project.id)
    bus.publish(project.id, run.id, "run.started", {})
    assert (await asyncio.wait_for(a.queue.get(), 1)).type == (await asyncio.wait_for(b.queue.get(), 1)).type == "run.started"
    assert bus.watcher_count == 2
    bus.unwatch(a), bus.unwatch(b)
    assert bus.watcher_count == 0


async def test_a_watcher_of_another_project_receives_nothing(store, project, run):
    other = store.projects.create(name="Other", actor="system")
    bus = EventBus(store)
    watcher = bus.watch(other.id)
    bus.publish(project.id, run.id, "run.started", {})
    await asyncio.sleep(0.05)
    assert watcher.queue.empty()
    bus.unwatch(watcher)


async def test_publishing_from_a_worker_thread_reaches_a_watcher_on_the_loop(store, project, run):
    bus = EventBus(store)
    watcher = bus.watch(project.id)
    await asyncio.to_thread(bus.publish, project.id, run.id, "artefact.finished", {"key": "x"})
    assert (await asyncio.wait_for(watcher.queue.get(), 1)).data == {"key": "x"}
    bus.unwatch(watcher)


async def test_a_stalled_watcher_is_dropped_with_a_marker_and_never_slows_the_publisher_or_the_other_watchers(store, project, run):
    bus = EventBus(store, queue_size=10)
    stalled, healthy = bus.watch(project.id), bus.watch(project.id)
    received: list[int] = []

    async def keep_up():
        while True:
            event = await healthy.queue.get()
            if event is None:
                return
            received.append(event.id)

    reader = asyncio.create_task(keep_up())
    stored = []
    for i in range(25):                                                     # publish never waits for either watcher
        stored.append(bus.publish(project.id, run.id, "artefact.started", {"key": str(i)}))
        await asyncio.sleep(0)                                              # let the healthy reader run; the stalled one never does
    await asyncio.sleep(0.05)

    assert stalled.state["dropped"] is True and healthy.state["dropped"] is False and bus.watcher_count == 1
    last = "unset"
    while not stalled.queue.empty():
        last = stalled.queue.get_nowait()
    assert last is None                                                     # the last thing it is told is "you were dropped"
    assert received == [e.id for e in stored]                               # the healthy one saw all 25, in order
    assert [e.id for e in store.run_events.list(project.id)] == [e.id for e in stored]   # and the log lost nothing
    reader.cancel()
    bus.unwatch(healthy)


async def test_a_dropped_watcher_can_catch_up_from_the_log_with_after(store, project, run):
    bus = EventBus(store, queue_size=10)
    stalled = bus.watch(project.id)
    stored = [bus.publish(project.id, run.id, "artefact.started", {"key": str(i)}) for i in range(25)]
    await asyncio.sleep(0.05)
    assert stalled.state["dropped"] is True
    items = []
    while not stalled.queue.empty():
        items.append(stalled.queue.get_nowait())
    assert items and items[-1] is None and items.count(None) == 1      # exactly one marker, and nothing after it
    seen = [i.id for i in items if i is not None]
    missed = store.run_events.list(project.id, after=seen[-1] if seen else 0)
    assert seen + [e.id for e in missed] == [e.id for e in stored]          # nothing lost, nothing repeated


async def test_a_watcher_that_keeps_up_is_never_dropped(store, project, run):
    bus = EventBus(store, queue_size=10)
    watcher = bus.watch(project.id)
    for i in range(40):
        bus.publish(project.id, run.id, "artefact.started", {"key": str(i)})
        await asyncio.wait_for(watcher.queue.get(), 1)
    assert watcher.state["dropped"] is False and bus.watcher_count == 1
    bus.unwatch(watcher)


async def test_unwatching_twice_is_harmless(store, project):
    bus = EventBus(store)
    watcher = bus.watch(project.id)
    bus.unwatch(watcher)
    bus.unwatch(watcher)
    assert bus.watcher_count == 0


# ---- what an event may contain -----------------------------------------------------------------------------------------------------

def test_a_reason_is_one_line_bounded_and_free_of_urls_and_secrets():
    text = "boom\nsecond line   with  gaps https://ica.example.invalid/v1/x?key=SECRET-123 and SECRET-123 again " + "x" * 500
    out = clean_reason(text, ["SECRET-123"])
    assert "\n" not in out and "SECRET-123" not in out and "https://" not in out and "[url removed]" in out
    assert len(out) <= 300 and out.startswith("boom second line with gaps")


def test_blank_secrets_are_ignored_rather_than_blanking_everything():
    assert clean_reason("hello world", ["", "  "]) == "hello world"


# ---- the wire format --------------------------------------------------------------------------------------------------------------------

def test_an_event_is_framed_as_id_event_and_one_json_data_line(store, project, run):
    event = EventBus(store).publish(project.id, run.id, "artefact.finished", {"key": "personas", "cost_usd": 0.01})
    frame = format_sse(event)
    lines = frame.split("\n")
    assert lines[0] == f"id: {event.id}" and lines[1] == "event: artefact.finished" and lines[2].startswith("data: {")
    assert frame.endswith("\n\n") and frame.count("\n") == 4                      # exactly one data line, so no event can split a frame
    import json

    data = json.loads(lines[2][len("data: "):])
    assert data["key"] == "personas" and data["run_id"] == run.id and data["at"] == event.at


def test_a_newline_in_event_data_cannot_break_the_frame(store, project, run):
    event = EventBus(store).publish(project.id, run.id, "artefact.failed", {"reason": "a\nb\r\nid: 99\n\nevent: run.finished"})
    frame = format_sse(event)
    assert frame.count("\n\n") == 1 and frame.count("\nevent:") == 1 and "\nid: 99" not in frame


def test_a_comment_frame_starts_with_a_colon_and_is_ignored_by_clients():
    assert format_comment("heartbeat") == ": heartbeat\n\n"

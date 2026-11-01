"""The sample project: the exact name, brief and policy note the recordings were made with (S12b).

Replay answers a call only when its prompt is IDENTICAL to a recorded one, and the prompt contains the project name, the brief and
the text of the policy note. So these three values are the key to every recording of the demo, and live here once: the demo scripts
import them, and `GET /api/sample` serves them to the "Load the sample project" button. Change one word and every recording misses.
"""
from __future__ import annotations

NAME = "Meeting Room Booking"
FILENAME = "meeting-room-policy.md"

BRIEF = (
    "Meeting Room Booking is a web application for office staff on floors two to four. "
    "Staff browse the available rooms, reserve a room for a time slot, and cancel a reservation they no longer need. "
    "The application must prevent two people from booking the same room for the same slot. "
    "It must respect office hours of eight to six on weekdays. "
    "An administrator can add, rename and retire rooms. "
    "Reporting, calendar integration and mobile apps are out of scope for the first release."
)

POLICY = b"""# Meeting Room Policy

## Booking rules

Staff may book a room for up to four hours at a time during office hours, which are 08:00 to 18:00 on weekdays.
A room cannot be booked twice for the same slot: the second request is refused.

## Cancellation

A booking can be cancelled free of charge up to 24 hours before it starts.
"""

"""Phase 10 — central weekday-aware date/window policy for the daily brief run.

One deterministic source of truth for every date the daily run uses. The 5:00 AM brief is
scheduled Monday–Friday only, so the window depends on the local run weekday:

- **Monday** (``monday_carryover``): absorb the weekend + prior-Friday carryover and surface
  unresolved prior-week items; lookback spans prior Friday → Monday run time.
- **Tuesday–Thursday** (``standard_weekday``): normal adjacent-business-day windows.
- **Friday** (``friday_next_week``): close the week and prepare the following workweek; lookahead
  extends through next Friday (weekend + next workweek).

Weekend handling (``skipped_weekend`` vs catch-up): a fresh Saturday/Sunday run with no missed
weekday context skips; a weekend launchd catch-up of a *missed* Friday resolves to the Friday
policy (``catch_up=True``) so Friday's next-week brief still gets generated.

Pure & deterministic: every function takes the run datetime as input (no clock read) and uses
``zoneinfo`` so DST is handled by real local dates, never UTC-only arithmetic. No stage computes
its own dates — they consume :class:`DailyBriefWindow`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/New_York"

_WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

LABEL_MONDAY = "monday_carryover"
LABEL_STANDARD = "standard_weekday"
LABEL_FRIDAY = "friday_next_week"
LABEL_SKIPPED_WEEKEND = "skipped_weekend"


@dataclass(frozen=True)
class DailyBriefWindow:
    """Deterministic weekday-aware date window for one daily brief run.

    All timestamp fields are ISO-8601 strings carrying the local UTC offset (e.g.
    ``2026-06-15T05:00:00-04:00``); date fields are ``YYYY-MM-DD``. Safe to serialize into the
    pipeline receipt, status file, and consumption-surface headers (no raw source content).
    """

    run_date: str
    run_weekday: str
    label: str
    previous_business_day: str
    next_business_day: str
    lookback_start: str
    lookback_end: str
    lookahead_start: str
    lookahead_end: str
    calendar_prep_start: str
    calendar_prep_end: str
    included_dates: list[str]
    explanation: str
    timezone: str = DEFAULT_TIMEZONE
    catch_up: bool = False

    def to_dict(self) -> dict[str, object]:
        """The ``date_policy`` block embedded in receipts / status files."""
        return asdict(self)

    @property
    def is_skipped_weekend(self) -> bool:
        return self.label == LABEL_SKIPPED_WEEKEND

    @property
    def carryover_section_label(self) -> str | None:
        """Extra presentation section title for this weekday, if any."""
        if self.label == LABEL_MONDAY:
            return "Prior Week / Weekend Carryover"
        if self.label == LABEL_FRIDAY:
            return "Next Week Prep"
        return None


def _localize(run_at_local: datetime, timezone: str) -> datetime:
    """Return ``run_at_local`` as a tz-aware datetime in ``timezone`` (DST-correct)."""
    zone = ZoneInfo(timezone)
    if run_at_local.tzinfo is None:
        return run_at_local.replace(tzinfo=zone)
    return run_at_local.astimezone(zone)


def _at_midnight(d: datetime) -> datetime:
    return datetime.combine(d.date(), time(0, 0), tzinfo=d.tzinfo)


def _end_of_day(d: datetime) -> datetime:
    return datetime.combine(d.date(), time(23, 59, 59), tzinfo=d.tzinfo)


def previous_business_day(d: datetime) -> datetime:
    """The most recent weekday strictly before ``d`` (skips Sat/Sun)."""
    cur = d - timedelta(days=1)
    while cur.weekday() >= 5:
        cur -= timedelta(days=1)
    return cur


def next_business_day(d: datetime) -> datetime:
    """The next weekday strictly after ``d`` (skips Sat/Sun)."""
    cur = d + timedelta(days=1)
    while cur.weekday() >= 5:
        cur += timedelta(days=1)
    return cur


def _most_recent_friday(d: datetime) -> datetime:
    """The Friday on/before ``d`` (``d`` itself if it is a Friday)."""
    cur = d
    while cur.weekday() != 4:
        cur -= timedelta(days=1)
    return cur


def _date_span(start: datetime, end: datetime) -> list[str]:
    """Inclusive list of every calendar date (``YYYY-MM-DD``) from ``start`` to ``end``."""
    out: list[str] = []
    cur = start.date()
    last = end.date()
    while cur <= last:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def compute_daily_brief_window(
    run_at_local: datetime,
    timezone: str = DEFAULT_TIMEZONE,
    *,
    last_successful_date: str | None = None,
) -> DailyBriefWindow:
    """Compute the weekday-aware window for a daily brief run.

    ``run_at_local`` is the local run datetime (naive is interpreted in ``timezone``; aware is
    converted). On a weekend, ``last_successful_date`` (``YYYY-MM-DD`` of the last *successful*
    run) decides catch-up vs skip: if the most-recent Friday has not yet succeeded, the run
    resolves to that Friday's policy with ``catch_up=True``; otherwise the window is
    ``skipped_weekend``.
    """
    local = _localize(run_at_local, timezone)

    # Weekend resolution → either catch up the missed Friday or skip.
    if local.weekday() >= 5:
        friday = _most_recent_friday(local)
        already_ran_friday = (
            last_successful_date is not None and last_successful_date >= friday.date().isoformat()
        )
        if already_ran_friday:
            return _skipped_weekend_window(local, timezone)
        # Catch up the missed Friday: run the Friday policy at Friday 05:00 local.
        target = friday.replace(hour=local.hour, minute=local.minute, second=0, microsecond=0)
        return _weekday_window(target, timezone, catch_up=True)

    return _weekday_window(local, timezone, catch_up=False)


def _skipped_weekend_window(local: datetime, timezone: str) -> DailyBriefWindow:
    friday = _most_recent_friday(local)
    monday = next_business_day(local)  # the upcoming Monday
    run_date = local.date().isoformat()
    return DailyBriefWindow(
        run_date=run_date,
        run_weekday=_WEEKDAY_NAMES[local.weekday()],
        label=LABEL_SKIPPED_WEEKEND,
        previous_business_day=friday.date().isoformat(),
        next_business_day=monday.date().isoformat(),
        lookback_start=_at_midnight(local).isoformat(),
        lookback_end=local.isoformat(),
        lookahead_start=local.isoformat(),
        lookahead_end=local.isoformat(),
        calendar_prep_start=local.isoformat(),
        calendar_prep_end=local.isoformat(),
        included_dates=[run_date],
        explanation=(
            f"Fresh {_WEEKDAY_NAMES[local.weekday()]} run with the most-recent Friday "
            f"({friday.date().isoformat()}) already successful — weekend run skipped; "
            "no fresh weekend brief is generated."
        ),
        timezone=timezone,
        catch_up=False,
    )


def _weekday_window(run: datetime, timezone: str, *, catch_up: bool) -> DailyBriefWindow:
    weekday = run.weekday()  # 0=Mon .. 4=Fri
    prev_bd = previous_business_day(run)
    next_bd = next_business_day(run)

    lookback_start = _at_midnight(prev_bd)
    lookback_end = run
    lookahead_start = run

    if weekday == 0:  # Monday → absorb weekend + prep the current workweek (through Friday)
        label = LABEL_MONDAY
        lookahead_end = _end_of_day(run + timedelta(days=4))  # Friday of run week
        explanation = (
            f"Monday carryover: lookback {prev_bd.date().isoformat()} (prior Friday) through "
            f"Monday {run.date().isoformat()} 05:00 incl. the weekend; lookahead through "
            f"{lookahead_end.date().isoformat()} (this workweek). Surfaces weekend-created items "
            "and unresolved prior-week carryover."
        )
    elif weekday == 4:  # Friday → close the week + prep the following workweek
        label = LABEL_FRIDAY
        lookahead_end = _end_of_day(run + timedelta(days=7))  # next Friday
        explanation = (
            f"Friday next-week prep: lookback {prev_bd.date().isoformat()} (Thursday) through "
            f"Friday {run.date().isoformat()} 05:00; lookahead through "
            f"{lookahead_end.date().isoformat()} (weekend + next workweek), next business day "
            f"{next_bd.date().isoformat()}. Surfaces next-week meetings/deadlines now."
            + (" Catch-up of a missed Friday run." if catch_up else "")
        )
    else:  # Tuesday–Thursday → standard adjacent-business-day windows
        label = LABEL_STANDARD
        lookahead_end = _end_of_day(next_bd)
        explanation = (
            f"Standard {_WEEKDAY_NAMES[weekday]} brief: lookback {prev_bd.date().isoformat()} "
            f"(previous business day) through {run.date().isoformat()} 05:00; lookahead through "
            f"the next business day {next_bd.date().isoformat()}."
        )

    calendar_prep_start = run
    calendar_prep_end = lookahead_end

    return DailyBriefWindow(
        run_date=run.date().isoformat(),
        run_weekday=_WEEKDAY_NAMES[weekday],
        label=label,
        previous_business_day=prev_bd.date().isoformat(),
        next_business_day=next_bd.date().isoformat(),
        lookback_start=lookback_start.isoformat(),
        lookback_end=lookback_end.isoformat(),
        lookahead_start=lookahead_start.isoformat(),
        lookahead_end=lookahead_end.isoformat(),
        calendar_prep_start=calendar_prep_start.isoformat(),
        calendar_prep_end=calendar_prep_end.isoformat(),
        included_dates=_date_span(lookback_start, lookahead_end),
        explanation=explanation,
        timezone=timezone,
        catch_up=catch_up,
    )

import Foundation
import EventKit

/// Export events from all calendars under named EventKit sources.
/// Default source: iCloud (includes shared calendars in that account).
/// Usage: eventkit_export [days] [limit] [sourcesCSV]
///   sourcesCSV default: "iCloud"
///   Example: eventkit_export 14 100 "iCloud"
///   Example: eventkit_export 14 100 "iCloud,BF-Personal"

func iso(_ d: Date) -> String {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime]
    return f.string(from: d)
}

func fail(_ msg: String) -> Never {
    let out: [String: Any] = ["ok": false, "error": msg]
    let data = try! JSONSerialization.data(withJSONObject: out)
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write("\n".data(using: .utf8)!)
    exit(2)
}

let args = CommandLine.arguments
let days = Int(args.count > 1 ? args[1] : "14") ?? 14
let limit = Int(args.count > 2 ? args[2] : "200") ?? 200
// Default: iCloud only — all calendars under that account, including shared.
let sourcesCSV = args.count > 3 ? args[3] : "iCloud"
let allowedSources = Set(
    sourcesCSV
        .split(separator: ",")
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
)
let boundedDays = max(1, min(days, 90))
let boundedLimit = max(1, min(limit, 500))

let store = EKEventStore()
let sem = DispatchSemaphore(value: 0)
var authErr: String? = nil

if #available(macOS 14.0, *) {
    store.requestFullAccessToEvents { ok, err in
        if !ok { authErr = err?.localizedDescription ?? "denied" }
        sem.signal()
    }
} else {
    store.requestAccess(to: .event) { ok, err in
        if !ok { authErr = err?.localizedDescription ?? "denied" }
        sem.signal()
    }
}
if sem.wait(timeout: .now() + 20) == .timedOut {
    fail("auth_timeout")
}
if let authErr = authErr {
    fail("auth:\(authErr)")
}

// ALL calendars for .event whose source title is in the allowlist.
// Includes shared iCloud calendars (they still report source title "iCloud").
// Do NOT filter by allowsContentModifications / isSubscribed / ownership —
// shared calendars must be included when under an allowed source.
let allCals = store.calendars(for: .event)
var selectedCals: [EKCalendar] = []
var inventory: [[String: Any]] = []
for cal in allCals {
    let srcTitle = cal.source?.title ?? ""
    let entry: [String: Any] = [
        "title": cal.title,
        "id": cal.calendarIdentifier,
        "source_title": srcTitle,
        "source_type": cal.source?.sourceType.rawValue as Any,
        "allows_content_modifications": cal.allowsContentModifications,
        "is_subscribed": cal.isSubscribed,
        "type": cal.type.rawValue,
        "selected": allowedSources.contains(srcTitle),
    ]
    inventory.append(entry)
    if allowedSources.contains(srcTitle) {
        selectedCals.append(cal)
    }
}

if selectedCals.isEmpty {
    fail("no_calendars_for_sources:\(sourcesCSV)")
}

let cal = Calendar.current
let start = cal.startOfDay(for: Date())
guard let end = cal.date(byAdding: .day, value: boundedDays, to: start) else {
    fail("bad_range")
}

// Explicit calendar list: only iCloud (or allowlisted) calendars, all of them including shared.
let predicate = store.predicateForEvents(withStart: start, end: end, calendars: selectedCals)
let events = store.events(matching: predicate)
    .sorted { $0.startDate < $1.startDate }
    .prefix(boundedLimit)

var items: [[String: Any]] = []
for e in events {
    items.append([
        "event_id": e.eventIdentifier ?? "",
        "calendar_title": e.calendar?.title ?? "",
        "calendar_id": e.calendar?.calendarIdentifier ?? "",
        "source_title": e.calendar?.source?.title ?? "",
        "summary": e.title ?? "",
        "location": e.location ?? "",
        "notes": String((e.notes ?? "").prefix(4000)),
        "start": iso(e.startDate),
        "end": iso(e.endDate),
        "all_day": e.isAllDay,
        "has_recurrence": e.hasRecurrenceRules,
        "url": e.url?.absoluteString ?? "",
        "availability": e.availability.rawValue,
        "calendar_allows_content_modifications": e.calendar?.allowsContentModifications ?? false,
        "calendar_is_subscribed": e.calendar?.isSubscribed ?? false,
    ])
}

// Per-calendar event counts in window (pre-limit) for proof
var perCalCounts: [String: Int] = [:]
for e in store.events(matching: predicate) {
    let key = e.calendar?.title ?? "(unknown)"
    perCalCounts[key, default: 0] += 1
}

let out: [String: Any] = [
    "ok": true,
    "start": iso(start),
    "end": iso(end),
    "days": boundedDays,
    "source_allowlist": Array(allowedSources).sorted(),
    "selected_calendar_count": selectedCals.count,
    "selected_calendars": selectedCals.map { [
        "title": $0.title,
        "id": $0.calendarIdentifier,
        "source_title": $0.source?.title ?? "",
        "allows_content_modifications": $0.allowsContentModifications,
        "is_subscribed": $0.isSubscribed,
    ] as [String: Any] },
    "inventory": inventory,
    "per_calendar_event_counts_in_window": perCalCounts,
    "exported": items.count,
    "items": items,
]
let data = try! JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
FileHandle.standardOutput.write("\n".data(using: .utf8)!)

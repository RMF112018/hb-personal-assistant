import Foundation
import EventKit

func iso(_ d: Date) -> String {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    // prefer without fractional for stability
    let f2 = ISO8601DateFormatter()
    f2.formatOptions = [.withInternetDateTime]
    return f2.string(from: d)
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
let limit = Int(args.count > 2 ? args[2] : "50") ?? 50
let boundedDays = max(1, min(days, 90))
let boundedLimit = max(1, min(limit, 200))

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

let cal = Calendar.current
let start = cal.startOfDay(for: Date())
guard let end = cal.date(byAdding: .day, value: boundedDays, to: start) else {
    fail("bad_range")
}
let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
let events = store.events(matching: predicate)
    .sorted { $0.startDate < $1.startDate }
    .prefix(boundedLimit)

var items: [[String: Any]] = []
for e in events {
    items.append([
        "event_id": e.eventIdentifier ?? "",
        "calendar_title": e.calendar?.title ?? "",
        "calendar_id": e.calendar?.calendarIdentifier ?? "",
        "source_title": e.calendar?.source.title ?? "",
        "summary": e.title ?? "",
        "location": e.location ?? "",
        "notes": String((e.notes ?? "").prefix(4000)),
        "start": iso(e.startDate),
        "end": iso(e.endDate),
        "all_day": e.isAllDay,
        "has_recurrence": e.hasRecurrenceRules,
        "url": e.url?.absoluteString ?? "",
        "availability": e.availability.rawValue
    ])
}
let out: [String: Any] = [
    "ok": true,
    "start": iso(start),
    "end": iso(end),
    "days": boundedDays,
    "exported": items.count,
    "items": items
]
let data = try! JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
FileHandle.standardOutput.write("\n".data(using: .utf8)!)

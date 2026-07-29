import Foundation
import EventKit

// Read-only EventKit source enumeration probe.
let store = EKEventStore()
let sources = store.sources.map { src -> [String: String] in
    return [
        "title": src.title,
        "identifier": src.sourceIdentifier,
        "type": String(describing: src.sourceType.rawValue),
    ]
}
let data = try! JSONSerialization.data(withJSONObject: sources, options: [.prettyPrinted])
if let s = String(data: data, encoding: .utf8) {
    print(s)
}

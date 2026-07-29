import Foundation
import Contacts

func fail(_ msg: String) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: ["ok": false, "error": msg])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write("\n".data(using: .utf8)!)
    exit(2)
}

let args = CommandLine.arguments
let limit = max(1, min(Int(args.count > 1 ? args[1] : "25") ?? 25, 200))
let sourcesCSV = args.count > 2 ? args[2] : "iCloud"
let allowed = Set(sourcesCSV.split(separator: ",").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty })

let store = CNContactStore()
let sem = DispatchSemaphore(value: 0)
var authErr: String? = nil
store.requestAccess(for: .contacts) { ok, err in
    if !ok { authErr = err?.localizedDescription ?? "denied" }
    sem.signal()
}
if sem.wait(timeout: .now() + 20) == .timedOut { fail("auth_timeout") }
if let authErr = authErr { fail("auth:\(authErr)") }

do {
    let containers = try store.containers(matching: nil)
    var inventory: [[String: Any]] = []
    var selected: [CNContainer] = []
    for c in containers {
        let selectedFlag = allowed.contains(c.name)
        inventory.append([
            "name": c.name,
            "identifier": c.identifier,
            "type": c.type.rawValue,
            "selected": selectedFlag,
        ])
        if selectedFlag { selected.append(c) }
    }
    if selected.isEmpty {
        // fall back: if iCloud missing by name, take any non-local? Still fail closed preferred
        fail("no_containers_for_sources:\(sourcesCSV) inventory:\(inventory)")
    }

    let keys: [CNKeyDescriptor] = [
        CNContactIdentifierKey as CNKeyDescriptor,
        CNContactGivenNameKey as CNKeyDescriptor,
        CNContactFamilyNameKey as CNKeyDescriptor,
        CNContactOrganizationNameKey as CNKeyDescriptor,
        CNContactEmailAddressesKey as CNKeyDescriptor,
        CNContactPhoneNumbersKey as CNKeyDescriptor,
        CNContactTypeKey as CNKeyDescriptor,
    ]
    var items: [[String: Any]] = []
    for c in selected {
        let pred = CNContact.predicateForContactsInContainer(withIdentifier: c.identifier)
        let contacts = try store.unifiedContacts(matching: pred, keysToFetch: keys)
        for person in contacts.prefix(limit) {
            if items.count >= limit { break }
            let emails = person.emailAddresses.map { [
                "label": CNLabeledValue<NSString>.localizedString(forLabel: $0.label ?? ""),
                "value": $0.value as String,
            ] as [String: Any] }
            let phones = person.phoneNumbers.map { [
                "label": CNLabeledValue<CNPhoneNumber>.localizedString(forLabel: $0.label ?? ""),
                "value": $0.value.stringValue,
            ] as [String: Any] }
            let isOrg = person.contactType == .organization
            items.append([
                "cn_id": person.identifier,
                "first_name": person.givenName,
                "last_name": person.familyName,
                "organization": person.organizationName,
                "contact_type": isOrg ? "organization" : "person",
                "container": c.name,
                "container_id": c.identifier,
                "emails": emails,
                "phones": phones,
            ])
        }
        if items.count >= limit { break }
    }
    let out: [String: Any] = [
        "ok": true,
        "container_allowlist": Array(allowed).sorted(),
        "inventory": inventory,
        "selected_containers": selected.map { ["name": $0.name, "id": $0.identifier] as [String: Any] },
        "total_exported": items.count,
        "exported": items.count,
        "items": items,
    ]
    let data = try JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write("\n".data(using: .utf8)!)
} catch {
    fail(String(describing: error))
}

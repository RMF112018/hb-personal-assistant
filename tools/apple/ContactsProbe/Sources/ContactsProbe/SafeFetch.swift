import Foundation
import Contacts

enum SafeFetch {
    static func containers() throws -> [[String: String]] {
        let store = CNContactStore()
        let containers = try store.containers(matching: nil)
        return containers.map { c in
            [
                "name": c.name,
                "identifier": c.identifier,
                "type": String(describing: c.type.rawValue),
            ]
        }
    }
}

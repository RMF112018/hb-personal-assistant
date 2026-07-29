import Foundation

do {
    let containers = try SafeFetch.containers()
    let data = try JSONSerialization.data(withJSONObject: containers, options: [.prettyPrinted])
    if let s = String(data: data, encoding: .utf8) {
        print(s)
    }
} catch {
    fputs("error: \(error)\n", stderr)
    exit(1)
}

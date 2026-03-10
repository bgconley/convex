import Foundation

package struct Settings: Sendable {
    package let backendURL: URL

    package init(backendURL: URL = URL(string: "http://10.25.0.50:8090/api/v1")!) {
        self.backendURL = backendURL
    }

    /// Load settings from UserDefaults, falling back to defaults.
    package static func load() -> Settings {
        let defaults = UserDefaults.standard
        if let urlString = defaults.string(forKey: "backendURL"),
           let url = URL(string: urlString) {
            return Settings(backendURL: url)
        }
        return Settings()
    }

    package func save() {
        UserDefaults.standard.set(backendURL.absoluteString, forKey: "backendURL")
    }
}

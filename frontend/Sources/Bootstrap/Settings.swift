import Foundation

package struct Settings: Sendable {
    package let backendURL: URL
    package let defaultTopK: Int
    package let defaultRerank: Bool
    package let defaultIncludeGraph: Bool

    package init(
        backendURL: URL = URL(string: "http://10.25.0.50:8090/api/v1")!,
        defaultTopK: Int = 10,
        defaultRerank: Bool = true,
        defaultIncludeGraph: Bool = true
    ) {
        self.backendURL = backendURL
        self.defaultTopK = defaultTopK
        self.defaultRerank = defaultRerank
        self.defaultIncludeGraph = defaultIncludeGraph
    }

    /// Load settings from UserDefaults, falling back to defaults.
    package static func load() -> Settings {
        let defaults = UserDefaults.standard
        let url: URL
        if let urlString = defaults.string(forKey: "backendURL"),
           let parsed = URL(string: urlString) {
            url = parsed
        } else {
            url = URL(string: "http://10.25.0.50:8090/api/v1")!
        }
        let topK = defaults.object(forKey: "defaultTopK") as? Int ?? 10
        let rerank = defaults.object(forKey: "defaultRerank") as? Bool ?? true
        let includeGraph = defaults.object(forKey: "defaultIncludeGraph") as? Bool ?? true
        return Settings(
            backendURL: url,
            defaultTopK: topK,
            defaultRerank: rerank,
            defaultIncludeGraph: includeGraph
        )
    }

    package func save() {
        let defaults = UserDefaults.standard
        defaults.set(backendURL.absoluteString, forKey: "backendURL")
        defaults.set(defaultTopK, forKey: "defaultTopK")
        defaults.set(defaultRerank, forKey: "defaultRerank")
        defaults.set(defaultIncludeGraph, forKey: "defaultIncludeGraph")
    }

    /// True if the user has explicitly configured the backend URL at least once.
    package static var hasBeenConfigured: Bool {
        UserDefaults.standard.string(forKey: "backendURL") != nil
    }
}

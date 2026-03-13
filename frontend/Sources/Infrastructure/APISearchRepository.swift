import Domain
import Foundation

package struct APISearchRepository: SearchPort, Sendable {
    private let client: APIClient

    package init(client: APIClient) {
        self.client = client
    }

    package func search(request: SearchRequest) async throws -> SearchResponse {
        try await client.post("search", body: request)
    }

    package func searchDocuments(request: SearchRequest) async throws -> DocumentSearchResponse {
        try await client.post("search/documents", body: request)
    }

    package func suggestions(query: String, limit: Int) async throws -> SearchSuggestionsResponse {
        let encoded = query.addingPercentEncoding(withAllowedCharacters: .urlQueryValueAllowed) ?? query
        return try await client.get("search/suggestions?q=\(encoded)&limit=\(limit)")
    }
}

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
}

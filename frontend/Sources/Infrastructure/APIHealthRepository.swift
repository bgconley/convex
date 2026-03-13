import Domain
import Foundation

package struct APIHealthRepository: HealthPort, Sendable {
    private let client: APIClient

    package init(client: APIClient) {
        self.client = client
    }

    package func checkHealth() async throws -> HealthStatus {
        try await client.get("health")
    }

    package func fetchStats() async throws -> SystemStats {
        try await client.get("stats")
    }
}

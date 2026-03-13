import Domain
import Foundation

package struct APIEntityRepository: EntityRepositoryPort, Sendable {
    private let client: APIClient

    package init(client: APIClient) {
        self.client = client
    }

    package func list(entityType: String?, limit: Int, offset: Int) async throws -> EntityListResponse {
        var path = "entities"
        var queryItems: [String] = []
        if let et = entityType { queryItems.append("entity_type=\(et)") }
        queryItems.append("limit=\(limit)")
        queryItems.append("offset=\(offset)")
        if !queryItems.isEmpty {
            path += "?" + queryItems.joined(separator: "&")
        }
        return try await client.get(path)
    }

    package func getDetail(id: UUID) async throws -> EntityDetailResponse {
        try await client.get("entities/\(id.uuidString)")
    }

    package func listEntityTypes() async throws -> [String] {
        let response: EntityTypeListResponse = try await client.get("entities/types")
        return response.entityTypes
    }

    package func getRelated(id: UUID, hops: Int) async throws -> [RelatedEntity] {
        try await client.get("entities/\(id.uuidString)/related?hops=\(hops)")
    }

    package func getDocumentEntities(documentId: UUID) async throws -> [DocumentEntity] {
        let response: DocumentEntitiesResponse = try await client.get(
            "documents/\(documentId.uuidString)/entities"
        )
        return response.entities
    }
}

import Domain
import Foundation

package struct APICollectionRepository: CollectionRepositoryPort, Sendable {
    private let client: APIClient

    package init(client: APIClient) {
        self.client = client
    }

    package func list(parentId: UUID?, limit: Int, offset: Int) async throws -> CollectionListResponse {
        var path = "collections?limit=\(limit)&offset=\(offset)"
        if let parentId {
            path += "&parent_id=\(parentId.uuidString)"
        }
        return try await client.get(path)
    }

    package func get(id: UUID) async throws -> Collection {
        try await client.get("collections/\(id.uuidString)")
    }

    package func create(name: String, description: String?, icon: String?, parentId: UUID?, filterJson: CollectionFilter?) async throws -> Collection {
        struct Body: Codable {
            let name: String
            let description: String?
            let icon: String?
            let parent_id: UUID?
            let filter_json: CollectionFilter?
        }
        return try await client.post("collections", body: Body(
            name: name, description: description, icon: icon, parent_id: parentId, filter_json: filterJson
        ))
    }

    package func update(id: UUID, name: String?, description: String?, icon: String?, parentId: UUID?, sortOrder: Int?) async throws -> Collection {
        struct Body: Codable {
            let name: String?
            let description: String?
            let icon: String?
            let parent_id: UUID?
            let sort_order: Int?
        }
        return try await client.patch("collections/\(id.uuidString)", body: Body(
            name: name, description: description, icon: icon, parent_id: parentId, sort_order: sortOrder
        ))
    }

    package func delete(id: UUID) async throws {
        try await client.delete("collections/\(id.uuidString)")
    }

    package func listTags() async throws -> [String] {
        let response: TagListResponse = try await client.get("documents/tags/all")
        return response.tags
    }
}

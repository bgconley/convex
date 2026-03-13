import Domain
import Foundation

package struct APIDocumentRepository: DocumentRepositoryPort, Sendable {
    private let client: APIClient

    package init(client: APIClient) {
        self.client = client
    }

    package func list(filters: DocumentFilters?) async throws -> DocumentListResponse {
        var path = "documents"
        var queryItems: [String] = []
        if let f = filters {
            if let ft = f.fileType { queryItems.append("file_type=\(ft)") }
            if let s = f.status { queryItems.append("status=\(s)") }
            if let c = f.collectionId { queryItems.append("collection_id=\(c.uuidString)") }
            if let tags = f.tags {
                for tag in tags {
                    let encoded = tag.addingPercentEncoding(withAllowedCharacters: .urlQueryValueAllowed) ?? tag
                    queryItems.append("tags=\(encoded)")
                }
            }
            queryItems.append("limit=\(f.limit)")
            queryItems.append("offset=\(f.offset)")
        }
        if !queryItems.isEmpty {
            path += "?" + queryItems.joined(separator: "&")
        }
        return try await client.get(path)
    }

    package func get(id: UUID) async throws -> Document {
        try await client.get("documents/\(id.uuidString)")
    }

    package func getContent(id: UUID, view: String) async throws -> DocumentContent {
        try await client.get("documents/\(id.uuidString)/content?view=\(view)")
    }

    package func upload(fileURL: URL) async throws -> DocumentUploadResponse {
        try await client.uploadMultipart("documents", fileURL: fileURL)
    }

    package func delete(id: UUID) async throws {
        try await client.delete("documents/\(id.uuidString)")
    }

    package func update(
        id: UUID,
        title: String?,
        tags: [String]?,
        isFavorite: Bool?,
        collectionId: UUID?,
        setCollection: Bool
    ) async throws -> Document {
        struct UpdateBody: Encodable {
            var title: String?
            var tags: [String]?
            var isFavorite: Bool?
            var collectionId: UUID?
            var setCollection: Bool
            enum CodingKeys: String, CodingKey {
                case title, tags
                case isFavorite = "is_favorite"
                case collectionId = "collection_id"
            }

            func encode(to encoder: Encoder) throws {
                var container = encoder.container(keyedBy: CodingKeys.self)
                try container.encodeIfPresent(title, forKey: .title)
                try container.encodeIfPresent(tags, forKey: .tags)
                try container.encodeIfPresent(isFavorite, forKey: .isFavorite)
                if setCollection {
                    try container.encode(collectionId, forKey: .collectionId)
                }
            }
        }
        return try await client.patch(
            "documents/\(id.uuidString)",
            body: UpdateBody(
                title: title,
                tags: tags,
                isFavorite: isFavorite,
                collectionId: collectionId,
                setCollection: setCollection
            )
        )
    }
}

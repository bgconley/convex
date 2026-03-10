import Foundation

package struct DocumentFilters: Sendable {
    package var fileType: String?
    package var status: String?
    package var collectionId: UUID?
    package var limit: Int
    package var offset: Int

    package init(
        fileType: String? = nil,
        status: String? = nil,
        collectionId: UUID? = nil,
        limit: Int = 50,
        offset: Int = 0
    ) {
        self.fileType = fileType
        self.status = status
        self.collectionId = collectionId
        self.limit = limit
        self.offset = offset
    }
}

package protocol DocumentRepositoryPort: Sendable {
    func list(filters: DocumentFilters?) async throws -> DocumentListResponse
    func get(id: UUID) async throws -> Document
    func getContent(id: UUID, view: String) async throws -> DocumentContent
    func upload(fileURL: URL) async throws -> DocumentUploadResponse
    func delete(id: UUID) async throws
    func update(id: UUID, title: String?, tags: [String]?, isFavorite: Bool?) async throws -> Document
}

package protocol SearchPort: Sendable {
    func search(request: SearchRequest) async throws -> SearchResponse
    func searchDocuments(request: SearchRequest) async throws -> DocumentSearchResponse
}

package struct HealthStatus: Sendable, Codable {
    package let status: String
    package let checks: [String: String]
}

package protocol HealthPort: Sendable {
    func checkHealth() async throws -> HealthStatus
}

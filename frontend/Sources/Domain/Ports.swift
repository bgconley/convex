import Foundation

package struct DocumentFilters: Sendable {
    package var fileType: String?
    package var status: String?
    package var collectionId: UUID?
    package var tags: [String]?
    package var limit: Int
    package var offset: Int

    package init(
        fileType: String? = nil,
        status: String? = nil,
        collectionId: UUID? = nil,
        tags: [String]? = nil,
        limit: Int = 50,
        offset: Int = 0
    ) {
        self.fileType = fileType
        self.status = status
        self.collectionId = collectionId
        self.tags = tags
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
    func update(
        id: UUID,
        title: String?,
        tags: [String]?,
        isFavorite: Bool?,
        collectionId: UUID?,
        setCollection: Bool
    ) async throws -> Document
}

package protocol SearchPort: Sendable {
    func search(request: SearchRequest) async throws -> SearchResponse
    func searchDocuments(request: SearchRequest) async throws -> DocumentSearchResponse
    func suggestions(query: String, limit: Int) async throws -> SearchSuggestionsResponse
}

package struct HealthStatus: Sendable, Codable {
    package let status: String
    package let checks: [String: String]

    package init(status: String, checks: [String: String]) {
        self.status = status
        self.checks = checks
    }
}

package protocol EntityRepositoryPort: Sendable {
    func list(entityType: String?, limit: Int, offset: Int) async throws -> EntityListResponse
    func listEntityTypes() async throws -> [String]
    func getDetail(id: UUID) async throws -> EntityDetailResponse
    func getRelated(id: UUID, hops: Int) async throws -> [RelatedEntity]
    func getDocumentEntities(documentId: UUID) async throws -> [DocumentEntity]
}

package protocol CollectionRepositoryPort: Sendable {
    func list(parentId: UUID?, limit: Int, offset: Int) async throws -> CollectionListResponse
    func get(id: UUID) async throws -> Collection
    func create(name: String, description: String?, icon: String?, parentId: UUID?, filterJson: CollectionFilter?) async throws -> Collection
    func update(id: UUID, name: String?, description: String?, icon: String?, parentId: UUID?, sortOrder: Int?) async throws -> Collection
    func delete(id: UUID) async throws
    func listTags() async throws -> [String]
}

package protocol HealthPort: Sendable {
    func checkHealth() async throws -> HealthStatus
    func fetchStats() async throws -> SystemStats
}

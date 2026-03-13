import Domain
import Foundation

package actor DocumentService {
    private let docRepo: any DocumentRepositoryPort

    package init(docRepo: any DocumentRepositoryPort) {
        self.docRepo = docRepo
    }

    package func list(filters: DocumentFilters? = nil) async throws -> DocumentListResponse {
        try await docRepo.list(filters: filters)
    }

    package func get(id: UUID) async throws -> Document {
        try await docRepo.get(id: id)
    }

    package func getContent(id: UUID, view: String = "structured") async throws -> DocumentContent {
        try await docRepo.getContent(id: id, view: view)
    }

    package func upload(fileURL: URL) async throws -> DocumentUploadResponse {
        try await docRepo.upload(fileURL: fileURL)
    }

    package func delete(id: UUID) async throws {
        try await docRepo.delete(id: id)
    }

    package func toggleFavorite(document: Document) async throws -> Document {
        try await docRepo.update(id: document.id, title: nil, tags: nil, isFavorite: !document.isFavorite, collectionId: nil)
    }

    package func setCollection(documentId: UUID, collectionId: UUID?) async throws -> Document {
        try await docRepo.update(id: documentId, title: nil, tags: nil, isFavorite: nil, collectionId: collectionId)
    }

    package func updateTags(documentId: UUID, tags: [String]) async throws -> Document {
        try await docRepo.update(id: documentId, title: nil, tags: tags, isFavorite: nil, collectionId: nil)
    }
}

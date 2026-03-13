import Domain
import Foundation

package actor EntityService {
    private let entityRepo: any EntityRepositoryPort

    package init(entityRepo: any EntityRepositoryPort) {
        self.entityRepo = entityRepo
    }

    package func list(
        entityType: String? = nil,
        limit: Int = 100,
        offset: Int = 0
    ) async throws -> EntityListResponse {
        try await entityRepo.list(entityType: entityType, limit: limit, offset: offset)
    }

    package func getDetail(id: UUID) async throws -> EntityDetailResponse {
        try await entityRepo.getDetail(id: id)
    }

    package func getRelated(id: UUID, hops: Int = 2) async throws -> [RelatedEntity] {
        try await entityRepo.getRelated(id: id, hops: hops)
    }

    package func getDocumentEntities(documentId: UUID) async throws -> [DocumentEntity] {
        try await entityRepo.getDocumentEntities(documentId: documentId)
    }
}

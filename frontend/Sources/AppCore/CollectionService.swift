import Domain
import Foundation

package actor CollectionService {
    private let collectionRepo: any CollectionRepositoryPort

    package init(collectionRepo: any CollectionRepositoryPort) {
        self.collectionRepo = collectionRepo
    }

    package func list(
        parentId: UUID? = nil,
        limit: Int = 100,
        offset: Int = 0
    ) async throws -> CollectionListResponse {
        try await collectionRepo.list(parentId: parentId, limit: limit, offset: offset)
    }

    package func get(id: UUID) async throws -> Collection {
        try await collectionRepo.get(id: id)
    }

    package func create(
        name: String,
        description: String? = nil,
        icon: String? = nil,
        parentId: UUID? = nil,
        filterJson: CollectionFilter? = nil
    ) async throws -> Collection {
        try await collectionRepo.create(name: name, description: description, icon: icon, parentId: parentId, filterJson: filterJson)
    }

    package func update(
        id: UUID,
        name: String? = nil,
        description: String? = nil,
        icon: String? = nil,
        parentId: UUID? = nil,
        sortOrder: Int? = nil
    ) async throws -> Collection {
        try await collectionRepo.update(id: id, name: name, description: description, icon: icon, parentId: parentId, sortOrder: sortOrder)
    }

    package func delete(id: UUID) async throws {
        try await collectionRepo.delete(id: id)
    }

    package func listTags() async throws -> [String] {
        try await collectionRepo.listTags()
    }
}

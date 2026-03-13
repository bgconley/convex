import Foundation

package struct Entity: Sendable, Equatable, Codable, Identifiable {
    package let id: UUID
    package let name: String
    package let entityType: String
    package let normalizedName: String
    package let description: String?
    package var documentCount: Int
    package var mentionCount: Int
    package let createdAt: Date
    package let updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id, name, description
        case entityType = "entity_type"
        case normalizedName = "normalized_name"
        case documentCount = "document_count"
        case mentionCount = "mention_count"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

package struct EntityListResponse: Sendable, Codable {
    package let entities: [Entity]
    package let total: Int
    package let limit: Int
    package let offset: Int
}

package struct RelatedEntity: Sendable, Equatable, Codable, Identifiable {
    package let name: String
    package let entityType: String
    package let normalizedName: String

    package var id: String { normalizedName + ":" + entityType }

    enum CodingKeys: String, CodingKey {
        case name
        case entityType = "entity_type"
        case normalizedName = "normalized_name"
    }
}

package struct EntityDocument: Sendable, Equatable, Codable, Identifiable {
    package let documentId: UUID
    package let title: String

    package var id: UUID { documentId }

    enum CodingKeys: String, CodingKey {
        case documentId = "document_id"
        case title
    }
}

package struct EntityDetailResponse: Sendable, Codable {
    package let entity: Entity
    package let documents: [EntityDocument]
    package let relatedEntities: [RelatedEntity]

    enum CodingKeys: String, CodingKey {
        case entity, documents
        case relatedEntities = "related_entities"
    }
}

/// Lightweight entity returned by GET /documents/{id}/entities.
package struct DocumentEntity: Sendable, Equatable, Codable, Identifiable {
    package let id: UUID
    package let name: String
    package let entityType: String
    package let normalizedName: String
    package var documentCount: Int
    package var mentionCount: Int

    enum CodingKeys: String, CodingKey {
        case id, name
        case entityType = "entity_type"
        case normalizedName = "normalized_name"
        case documentCount = "document_count"
        case mentionCount = "mention_count"
    }
}

package struct DocumentEntitiesResponse: Sendable, Codable {
    package let entities: [DocumentEntity]
}

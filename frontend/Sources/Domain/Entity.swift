import Foundation

package struct Entity: Sendable, Equatable, Codable, Identifiable {
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

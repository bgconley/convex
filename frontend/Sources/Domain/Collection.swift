import Foundation

package struct Collection: Sendable, Equatable, Codable, Identifiable {
    package let id: UUID
    package var name: String
    package var description: String?
    package var icon: String?
    package var parentId: UUID?
    package var sortOrder: Int
    package var filterJson: CollectionFilter?
    package var isSmart: Bool
    package let createdAt: Date
    package let updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id, name, description, icon
        case parentId = "parent_id"
        case sortOrder = "sort_order"
        case filterJson = "filter_json"
        case isSmart = "is_smart"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

package struct CollectionFilter: Sendable, Equatable, Codable {
    package var query: String?
    package var fileType: String?
    package var tags: [String]?

    package init(query: String? = nil, fileType: String? = nil, tags: [String]? = nil) {
        self.query = query
        self.fileType = fileType
        self.tags = tags
    }

    enum CodingKeys: String, CodingKey {
        case query
        case fileType = "file_type"
        case tags
    }
}

package struct CollectionListResponse: Sendable, Codable {
    package let collections: [Collection]
    package let total: Int
    package let limit: Int
    package let offset: Int
}

package struct TagListResponse: Sendable, Codable {
    package let tags: [String]
}

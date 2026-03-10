import Foundation

package struct Collection: Sendable, Equatable, Codable, Identifiable {
    package let id: UUID
    package var name: String
    package var description: String?
    package var icon: String?
    package var parentId: UUID?
    package var sortOrder: Int

    enum CodingKeys: String, CodingKey {
        case id, name, description, icon
        case parentId = "parent_id"
        case sortOrder = "sort_order"
    }
}

import Foundation

package struct SystemStats: Sendable, Codable, Equatable {
    package let documentCount: Int
    package let chunkCount: Int
    package let entityCount: Int
    package let totalFileSizeBytes: Int

    enum CodingKeys: String, CodingKey {
        case documentCount = "document_count"
        case chunkCount = "chunk_count"
        case entityCount = "entity_count"
        case totalFileSizeBytes = "total_file_size_bytes"
    }

    package var formattedFileSize: String {
        ByteCountFormatter.string(fromByteCount: Int64(totalFileSizeBytes), countStyle: .file)
    }
}

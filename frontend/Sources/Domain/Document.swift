import Foundation

package enum FileType: String, Sendable, Codable, CaseIterable {
    case pdf
    case markdown
    case docx
    case xlsx
    case txt
    case png
    case jpg
    case tiff

    package var iconName: String {
        switch self {
        case .pdf: "doc.richtext"
        case .markdown: "doc.text"
        case .docx: "doc.fill"
        case .xlsx: "tablecells"
        case .txt: "doc.plaintext"
        case .png, .jpg, .tiff: "photo"
        }
    }

    package var displayName: String {
        switch self {
        case .pdf: "PDF"
        case .markdown: "Markdown"
        case .docx: "Word"
        case .xlsx: "Excel"
        case .txt: "Text"
        case .png: "PNG"
        case .jpg: "JPEG"
        case .tiff: "TIFF"
        }
    }
}

package enum ProcessingStatus: String, Sendable, Codable {
    case uploading
    case stored
    case parsing
    case parsed
    case chunking
    case chunked
    case embedding
    case embedded
    case extractingEntities = "extracting_entities"
    case entitiesExtracted = "entities_extracted"
    case buildingGraph = "building_graph"
    case ready
    case failed

    package var isProcessing: Bool {
        switch self {
        case .ready, .failed:
            false
        default:
            true
        }
    }

    package var displayLabel: String {
        switch self {
        case .uploading: "Uploading..."
        case .stored: "Queued"
        case .parsing: "Parsing..."
        case .parsed: "Parsed"
        case .chunking: "Chunking..."
        case .chunked: "Chunked"
        case .embedding: "Embedding..."
        case .embedded: "Embedded"
        case .extractingEntities: "Extracting entities..."
        case .entitiesExtracted: "Entities extracted"
        case .buildingGraph: "Building graph..."
        case .ready: "Ready"
        case .failed: "Failed"
        }
    }
}

package struct Document: Sendable, Equatable, Codable, Identifiable {
    package let id: UUID
    package var title: String
    package let originalFilename: String
    package let fileType: FileType
    package let fileSizeBytes: Int
    package let mimeType: String
    package var status: ProcessingStatus
    package var pageCount: Int?
    package var wordCount: Int?
    package var language: String?
    package var author: String?
    package var tags: [String]
    package var isFavorite: Bool
    package var collectionId: UUID?
    package let createdAt: Date
    package var updatedAt: Date
    package var processedAt: Date?
    package var errorMessage: String?

    enum CodingKeys: String, CodingKey {
        case id, title, status, tags, language, author
        case originalFilename = "original_filename"
        case fileType = "file_type"
        case fileSizeBytes = "file_size_bytes"
        case mimeType = "mime_type"
        case pageCount = "page_count"
        case wordCount = "word_count"
        case isFavorite = "is_favorite"
        case collectionId = "collection_id"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case processedAt = "processed_at"
        case errorMessage = "error_message"
    }
}

package struct DocumentListResponse: Sendable, Codable {
    package let documents: [Document]
    package let total: Int
    package let limit: Int
    package let offset: Int
}

package struct DocumentUploadResponse: Sendable, Codable {
    package let id: UUID
    package let status: String
    package let message: String
    package let isDuplicate: Bool

    enum CodingKeys: String, CodingKey {
        case id, status, message
        case isDuplicate = "is_duplicate"
    }
}

package struct DocumentContent: Sendable, Codable {
    package let id: UUID
    package let format: String
    package let content: String
    package let originalUrl: String
    package let metadata: Document

    enum CodingKeys: String, CodingKey {
        case id, format, content, metadata
        case originalUrl = "original_url"
    }
}

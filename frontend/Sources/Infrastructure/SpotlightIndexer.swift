import CoreSpotlight
import Domain
import Foundation
import UniformTypeIdentifiers

package struct SpotlightIndexer: Sendable {
    private static let domainIdentifier = "com.cortex.documents"

    package init() {}

    /// Index documents with optional per-document entity names as keywords.
    package func indexDocuments(
        _ documents: [Document],
        entityNames: [UUID: [String]] = [:]
    ) async {
        let items = documents.compactMap { makeSearchableItem(from: $0, entityNames: entityNames[$0.id] ?? []) }
        guard !items.isEmpty else { return }
        try? await CSSearchableIndex.default().indexSearchableItems(items)
    }

    package func removeDocument(id: UUID) async {
        try? await CSSearchableIndex.default().deleteSearchableItems(
            withIdentifiers: [id.uuidString]
        )
    }

    package func removeAllDocuments() async {
        try? await CSSearchableIndex.default().deleteSearchableItems(
            withDomainIdentifiers: [Self.domainIdentifier]
        )
    }

    private func makeSearchableItem(from document: Document, entityNames: [String]) -> CSSearchableItem? {
        guard document.status == .ready else { return nil }

        let attributes = CSSearchableItemAttributeSet(contentType: utType(for: document.fileType))
        attributes.title = document.title
        attributes.contentDescription = document.contentPreview ?? metadataSummary(for: document)
        attributes.keywords = document.tags + entityNames + [document.fileType.displayName]
        if let author = document.author {
            attributes.authorNames = [author]
        }

        return CSSearchableItem(
            uniqueIdentifier: document.id.uuidString,
            domainIdentifier: Self.domainIdentifier,
            attributeSet: attributes
        )
    }

    private func metadataSummary(for document: Document) -> String {
        var parts: [String] = [document.fileType.displayName]
        if let pages = document.pageCount, pages > 0 {
            parts.append("\(pages) page\(pages == 1 ? "" : "s")")
        }
        if let words = document.wordCount, words > 0 {
            parts.append("\(words) words")
        }
        return parts.joined(separator: " · ")
    }

    private func utType(for fileType: FileType) -> UTType {
        switch fileType {
        case .pdf: .pdf
        case .markdown: .plainText
        case .docx: UTType("org.openxmlformats.wordprocessingml.document") ?? .data
        case .xlsx: UTType("org.openxmlformats.spreadsheetml.sheet") ?? .data
        case .txt: .plainText
        case .png: .png
        case .jpg: .jpeg
        case .tiff: .tiff
        }
    }
}

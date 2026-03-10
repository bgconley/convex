import SwiftUI
import PDFKit
import Domain
import AppCore
import Infrastructure

struct DocumentDetailView: View {
    let documentId: UUID
    let documentService: DocumentService
    let apiClient: APIClient
    let markdownRenderer: MarkdownRenderer
    let anchorId: String?
    let pageNumber: Int?

    @State private var document: Document?
    @State private var content: DocumentContent?
    @State private var originalData: Data?
    @State private var originalFileURL: URL?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if isLoading {
                ProgressView("Loading document...")
            } else if let errorMessage {
                ContentUnavailableView {
                    Label("Error", systemImage: "exclamationmark.triangle")
                } description: {
                    Text(errorMessage)
                }
            } else if let document {
                viewerForDocument(document)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .toolbar {
            if let document {
                ToolbarItem(placement: .principal) {
                    VStack(spacing: 2) {
                        Text(document.title)
                            .font(.headline)
                        HStack(spacing: 8) {
                            Label(document.fileType.displayName, systemImage: document.fileType.iconName)
                            if let pageCount = document.pageCount {
                                Text("\(pageCount) pages")
                            }
                            if let wordCount = document.wordCount {
                                Text("\(wordCount) words")
                            }
                            Text(document.status.displayLabel)
                        }
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .task(id: documentId) {
            await loadDocument()
        }
        .onDisappear {
            cleanupTempFile()
        }
        .onChange(of: documentId) { _, _ in
            cleanupTempFile()
        }
    }

    private func cleanupTempFile() {
        if let url = originalFileURL {
            try? FileManager.default.removeItem(at: url)
            originalFileURL = nil
        }
    }

    @ViewBuilder
    private func viewerForDocument(_ doc: Document) -> some View {
        switch doc.fileType {
        case .pdf:
            if let data = originalData {
                PDFDocumentView(data: data, pageNumber: pageNumber)
            } else {
                ProgressView("Loading PDF...")
            }

        case .png, .jpg, .tiff:
            if let data = originalData {
                ImageDocumentView(imageData: data)
            } else {
                ProgressView("Loading image...")
            }

        case .docx:
            if let content {
                HTMLDocumentView(
                    htmlContent: content.content,
                    originalURL: originalFileURL ?? URL(fileURLWithPath: "/dev/null"),
                    anchorId: anchorId
                )
            }

        case .xlsx:
            if let content {
                SpreadsheetView(
                    htmlContent: content.content,
                    originalURL: originalFileURL ?? URL(fileURLWithPath: "/dev/null"),
                    anchorId: anchorId
                )
            }

        case .markdown, .txt:
            if let content {
                contentViewerByFormat(content)
            }
        }
    }

    @ViewBuilder
    private func contentViewerByFormat(_ content: DocumentContent) -> some View {
        switch content.format {
        case "html":
            HTMLWebView(html: prepareHTML(content.content), anchorId: anchorId)
        case "markdown":
            MarkdownDocumentView(
                markdownSource: content.content,
                renderer: markdownRenderer
            )
        default:
            PlainTextView(content: content.content)
        }
    }

    private func loadDocument() async {
        isLoading = true
        errorMessage = nil

        do {
            let doc = try await documentService.get(id: documentId)
            document = doc

            switch doc.fileType {
            case .pdf, .png, .jpg, .tiff:
                let data = try await apiClient.getData("documents/\(documentId.uuidString)/original")
                originalData = data

            case .docx, .xlsx:
                let docContent = try await documentService.getContent(id: documentId)
                content = docContent
                let data = try await apiClient.getData("documents/\(documentId.uuidString)/original")
                let tempURL = FileManager.default.temporaryDirectory
                    .appendingPathComponent("\(documentId.uuidString)_\(doc.originalFilename)")
                try data.write(to: tempURL)
                originalFileURL = tempURL

            case .markdown, .txt:
                let docContent = try await documentService.getContent(id: documentId)
                content = docContent
            }

            isLoading = false
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }
}

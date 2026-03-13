import SwiftUI
import PDFKit
import Domain
import AppCore
import Infrastructure

struct DocumentDetailView: View {
    let documentId: UUID
    let documentService: DocumentService
    let entityService: EntityService
    let collectionService: CollectionService
    let apiClient: APIClient
    let markdownRenderer: MarkdownRenderer
    let anchorId: String?
    let pageNumber: Int?
    var onSelectEntity: ((UUID) -> Void)?

    @State private var document: Document?
    @State private var content: DocumentContent?
    @State private var originalData: Data?
    @State private var originalFileURL: URL?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var entities: [DocumentEntity] = []
    @State private var allTags: [String] = []
    @State private var newTagText = ""
    @State private var showTagEditor = false
    @State private var tagSuggestions: [String] = []
    @State private var selectedSuggestionIndex = -1

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
                VStack(spacing: 0) {
                    if !entities.isEmpty {
                        entityChipBar
                        Divider()
                    }
                    tagBar(document)
                    Divider()
                    viewerForDocument(document)
                }
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

    private var entityChipBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(entities) { entity in
                    EntityChipView(name: entity.name, entityType: entity.entityType) {
                        onSelectEntity?(entity.id)
                    }
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
        }
        .background(.bar)
    }

    private func tagBar(_ doc: Document) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                Image(systemName: "tag")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                ForEach(doc.tags, id: \.self) { tag in
                    HStack(spacing: 2) {
                        Text(tag)
                            .font(.caption)
                        Button {
                            Task { await removeTag(tag) }
                        } label: {
                            Image(systemName: "xmark")
                                .font(.system(size: 8, weight: .bold))
                        }
                        .buttonStyle(.plain)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.gray.opacity(0.15))
                    .clipShape(Capsule())
                }
                if showTagEditor {
                    tagEditorField
                } else {
                    Button {
                        showTagEditor = true
                        Task { await loadAllTags() }
                    } label: {
                        Image(systemName: "plus.circle")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                    .help("Add tag")
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
        }
        .background(.bar)
    }

    private var tagEditorField: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 4) {
                TextField("Tag", text: $newTagText)
                    .textFieldStyle(.plain)
                    .font(.caption)
                    .frame(width: 100)
                    .onChange(of: newTagText) { _, newValue in
                        updateTagSuggestions(newValue)
                    }
                    .onSubmit {
                        if selectedSuggestionIndex >= 0, selectedSuggestionIndex < tagSuggestions.count {
                            newTagText = tagSuggestions[selectedSuggestionIndex]
                        }
                        Task { await addTag() }
                    }
                    .onKeyPress(.upArrow) {
                        if !tagSuggestions.isEmpty {
                            selectedSuggestionIndex = max(0, selectedSuggestionIndex - 1)
                        }
                        return .handled
                    }
                    .onKeyPress(.downArrow) {
                        if !tagSuggestions.isEmpty {
                            selectedSuggestionIndex = min(tagSuggestions.count - 1, selectedSuggestionIndex + 1)
                        }
                        return .handled
                    }
                    .onKeyPress(.escape) {
                        if !tagSuggestions.isEmpty {
                            tagSuggestions = []
                            selectedSuggestionIndex = -1
                        } else {
                            showTagEditor = false
                            newTagText = ""
                        }
                        return .handled
                    }

                Button {
                    Task { await addTag() }
                } label: {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.caption)
                        .foregroundStyle(.green)
                }
                .buttonStyle(.plain)
                .disabled(newTagText.trimmingCharacters(in: .whitespaces).isEmpty)

                Button {
                    showTagEditor = false
                    newTagText = ""
                    tagSuggestions = []
                    selectedSuggestionIndex = -1
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.accentColor.opacity(0.1))
            .clipShape(Capsule())

            if !tagSuggestions.isEmpty {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(tagSuggestions.enumerated()), id: \.offset) { index, tag in
                        Button {
                            newTagText = tag
                            tagSuggestions = []
                            selectedSuggestionIndex = -1
                            Task { await addTag() }
                        } label: {
                            Text(tag)
                                .font(.caption)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(index == selectedSuggestionIndex ? Color.accentColor.opacity(0.2) : Color.clear)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .frame(width: 120)
                .background(.regularMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .shadow(radius: 4)
            }
        }
    }

    private func updateTagSuggestions(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespaces).lowercased()
        selectedSuggestionIndex = -1
        guard !trimmed.isEmpty, let doc = document else {
            tagSuggestions = []
            return
        }
        tagSuggestions = allTags.filter { tag in
            tag.lowercased().hasPrefix(trimmed) && !doc.tags.contains(tag)
        }.prefix(8).map { $0 }
    }

    private func addTag() async {
        let tag = newTagText.trimmingCharacters(in: .whitespaces).lowercased()
        guard !tag.isEmpty, let doc = document, !doc.tags.contains(tag) else { return }
        var tags = doc.tags
        tags.append(tag)
        do {
            let updated = try await documentService.updateTags(documentId: documentId, tags: tags)
            document = updated
            newTagText = ""
            tagSuggestions = []
            selectedSuggestionIndex = -1
            showTagEditor = false
        } catch {
            // Tag update failed silently
        }
    }

    private func removeTag(_ tag: String) async {
        guard let doc = document else { return }
        let tags = doc.tags.filter { $0 != tag }
        do {
            let updated = try await documentService.updateTags(documentId: documentId, tags: tags)
            document = updated
        } catch {
            // Tag removal failed silently
        }
    }

    private func loadAllTags() async {
        do {
            allTags = try await collectionService.listTags()
        } catch {
            // Best-effort
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
        entities = []

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

            // Load entities after document (non-blocking)
            if doc.status == .ready {
                do {
                    entities = try await entityService.getDocumentEntities(documentId: documentId)
                } catch {
                    // Entity loading is best-effort — don't fail the viewer
                }
            }
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }
}

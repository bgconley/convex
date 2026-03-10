import SwiftUI
import Domain
import AppCore
import Infrastructure
import UniformTypeIdentifiers

struct DocumentLibraryView: View {
    let documentService: DocumentService
    let ingestionService: IngestionService
    let thumbnailLoader: ThumbnailLoader
    let sidebarSelection: ContentView.SidebarItem
    @Binding var selectedDocumentId: UUID?

    @State private var documents: [Document] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var viewMode: ViewMode = .grid
    @State private var sortOrder: SortOrder = .dateAdded
    @State private var sortAscending = false
    @State private var showFileImporter = false
    @State private var importFileURLs: [URL]?
    @State private var isDropTargeted = false

    enum ViewMode: String, CaseIterable {
        case grid, list

        var iconName: String {
            switch self {
            case .grid: "square.grid.2x2"
            case .list: "list.bullet"
            }
        }
    }

    enum SortOrder: String, CaseIterable {
        case dateAdded = "Date Added"
        case title = "Title"
        case type = "Type"
        case fileSize = "Size"
    }

    var body: some View {
        Group {
            if isLoading && documents.isEmpty {
                ProgressView("Loading documents...")
            } else if documents.isEmpty {
                DocumentDropZone(onFilesDropped: importFiles)
            } else {
                documentListContent
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Button {
                    showFileImporter = true
                } label: {
                    Label("Import", systemImage: "plus")
                }
                .keyboardShortcut("i", modifiers: .command)
                .help("Import documents (Cmd+I)")
            }

            ToolbarItemGroup(placement: .automatic) {
                Picker("View Mode", selection: $viewMode) {
                    ForEach(ViewMode.allCases, id: \.self) { mode in
                        Image(systemName: mode.iconName)
                            .tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .help("Toggle grid/list view")

                Menu {
                    ForEach(SortOrder.allCases, id: \.self) { order in
                        Button {
                            if sortOrder == order {
                                sortAscending.toggle()
                            } else {
                                sortOrder = order
                                sortAscending = order == .title
                            }
                        } label: {
                            HStack {
                                Text(order.rawValue)
                                if sortOrder == order {
                                    Image(systemName: sortAscending ? "chevron.up" : "chevron.down")
                                }
                            }
                        }
                    }
                } label: {
                    Label("Sort", systemImage: "arrow.up.arrow.down")
                }
                .help("Sort documents")
            }
        }
        .fileImporter(
            isPresented: $showFileImporter,
            allowedContentTypes: DocumentDropZone.supportedTypes,
            allowsMultipleSelection: true
        ) { result in
            switch result {
            case .success(let urls):
                importFiles(urls)
            case .failure:
                break
            }
        }
        .sheet(item: importFileURLsBinding) { wrapper in
            ImportProgressView(
                fileURLs: wrapper.urls,
                ingestionService: ingestionService,
                documentService: documentService,
                onDismiss: {
                    importFileURLs = nil
                    Task { await loadDocuments() }
                }
            )
        }
        .task(id: sidebarSelection) {
            await loadDocuments()
        }
        .refreshable {
            await loadDocuments()
        }
        .navigationTitle(sidebarSelection.rawValue)
    }

    @ViewBuilder
    private var documentListContent: some View {
        Group {
            switch viewMode {
            case .grid:
                gridView
            case .list:
                listView
            }
        }
        .overlay {
            if isDropTargeted {
                DocumentDropZone(onFilesDropped: importFiles)
                    .background(.ultraThinMaterial)
            }
        }
        .onDrop(of: [.fileURL], isTargeted: $isDropTargeted) { providers in
            handleDrop(providers)
        }
    }

    private var gridView: some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 180), spacing: 16)], spacing: 16) {
                ForEach(sortedDocuments) { document in
                    DocumentGridItem(
                        document: document,
                        thumbnailLoader: thumbnailLoader,
                        onSelect: { selectedDocumentId = document.id },
                        onToggleFavorite: { Task { await toggleFavorite(document) } },
                        onDelete: { Task { await deleteDocument(document) } }
                    )
                }
            }
            .padding()
        }
    }

    private var listView: some View {
        Table(sortedDocuments, selection: $selectedDocumentId) {
            TableColumn("Title") { document in
                DocumentListRow(document: document)
            }
            TableColumn("Type") { document in
                Text(document.fileType.displayName)
                    .foregroundStyle(.secondary)
            }
            .width(ideal: 70)
            TableColumn("Date Added") { document in
                Text(document.createdAt, style: .date)
                    .foregroundStyle(.secondary)
            }
            .width(ideal: 100)
            TableColumn("Size") { document in
                Text(ByteCountFormatter.string(fromByteCount: Int64(document.fileSizeBytes), countStyle: .file))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            .width(ideal: 70)
        }
        .contextMenu(forSelectionType: UUID.self) { ids in
            if let id = ids.first, let document = sortedDocuments.first(where: { $0.id == id }) {
                Button {
                    Task { await toggleFavorite(document) }
                } label: {
                    Label(
                        document.isFavorite ? "Remove from Favorites" : "Add to Favorites",
                        systemImage: document.isFavorite ? "star.slash" : "star"
                    )
                }
                Divider()
                Button(role: .destructive) {
                    Task { await deleteDocument(document) }
                } label: {
                    Label("Delete", systemImage: "trash")
                }
            }
        }
    }

    private var sortedDocuments: [Document] {
        filteredDocuments.sorted { a, b in
            let result: Bool
            switch sortOrder {
            case .dateAdded:
                result = a.createdAt < b.createdAt
            case .title:
                result = a.title.localizedStandardCompare(b.title) == .orderedAscending
            case .type:
                result = a.fileType.displayName < b.fileType.displayName
            case .fileSize:
                result = a.fileSizeBytes < b.fileSizeBytes
            }
            return sortAscending ? result : !result
        }
    }

    // MARK: - Actions

    private func loadDocuments() async {
        isLoading = true
        defer { isLoading = false }

        let filters = filtersForSidebarSelection()
        do {
            let response = try await documentService.list(filters: filters)
            documents = response.documents
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func filtersForSidebarSelection() -> DocumentFilters? {
        switch sidebarSelection {
        case .allDocuments:
            return nil
        case .favorites:
            return nil // filtered client-side since backend filters don't include isFavorite
        case .pdfs:
            return DocumentFilters(fileType: "pdf")
        case .markdown:
            return DocumentFilters(fileType: "markdown")
        case .documents:
            return DocumentFilters(fileType: "docx")
        case .spreadsheets:
            return DocumentFilters(fileType: "xlsx")
        }
    }

    private var filteredDocuments: [Document] {
        switch sidebarSelection {
        case .favorites:
            return documents.filter(\.isFavorite)
        default:
            return documents
        }
    }

    private func importFiles(_ urls: [URL]) {
        importFileURLs = urls
    }

    private func toggleFavorite(_ document: Document) async {
        _ = try? await documentService.toggleFavorite(document: document)
        await loadDocuments()
    }

    private func deleteDocument(_ document: Document) async {
        try? await documentService.delete(id: document.id)
        await loadDocuments()
    }

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        Task { @MainActor in
            var urls: [URL] = []
            for provider in providers {
                guard provider.canLoadObject(ofClass: URL.self) else { continue }
                if let url = await loadURL(from: provider),
                   DocumentDropZone.supportedExtensions.contains(url.pathExtension.lowercased()) {
                    urls.append(url)
                }
            }
            if !urls.isEmpty {
                importFiles(urls)
            }
        }
        return true
    }

    private func loadURL(from provider: NSItemProvider) async -> URL? {
        await withCheckedContinuation { continuation in
            _ = provider.loadObject(ofClass: URL.self) { url, _ in
                continuation.resume(returning: url)
            }
        }
    }

    // MARK: - Import Sheet Binding

    private var importFileURLsBinding: Binding<ImportURLsWrapper?> {
        Binding(
            get: {
                guard let urls = importFileURLs else { return nil }
                return ImportURLsWrapper(urls: urls)
            },
            set: { newValue in
                if newValue == nil {
                    importFileURLs = nil
                }
            }
        )
    }
}

struct ImportURLsWrapper: Identifiable {
    let id = UUID()
    let urls: [URL]
}

import SwiftUI
import Domain
import AppCore
import Infrastructure
import UniformTypeIdentifiers

struct DocumentLibraryView: View {
    let documentService: DocumentService
    let searchService: SearchService
    let ingestionService: IngestionService
    let entityService: EntityService
    let thumbnailLoader: ThumbnailLoader
    let spotlightIndexer: SpotlightIndexer
    let sidebarSelection: ContentView.SidebarItem
    let collections: [Collection]
    let smartFilter: CollectionFilter?
    @Binding var selectedDocumentId: UUID?
    @Binding var entityFilter: ContentView.EntityFilter?
    @Binding var collectionId: UUID?

    private var manualCollections: [Collection] {
        collections.filter { !$0.isSmart }
    }

    @State private var documents: [Document] = []
    @State private var smartQueryDocumentIds: Set<UUID>?
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
        VStack(spacing: 0) {
            if let filter = entityFilter {
                entityFilterBanner(filter)
                Divider()
            }
            Group {
                if isLoading && documents.isEmpty {
                    ProgressView("Loading documents...")
                } else if filteredDocuments.isEmpty && entityFilter != nil {
                    ContentUnavailableView {
                        Label("No Documents", systemImage: "doc.on.doc")
                    } description: {
                        Text("No documents mention \"\(entityFilter?.entityName ?? "")\".")
                    }
                } else if documents.isEmpty {
                    DocumentDropZone(onFilesDropped: importFiles)
                } else {
                    documentListContent
                }
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
        .onChange(of: collectionId) { _, _ in
            Task { await loadDocuments() }
        }
        .onChange(of: smartFilter) { _, _ in
            Task { await loadDocuments() }
        }
        .refreshable {
            await loadDocuments()
        }
        .navigationTitle(smartFilter != nil ? "Smart Collection" : collectionId != nil ? "Collection" : sidebarSelection.rawValue)
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
                        collections: collections,
                        onSelect: { selectedDocumentId = document.id },
                        onToggleFavorite: { Task { await toggleFavorite(document) } },
                        onMoveToCollection: { collId in Task { await moveToCollection(document, collectionId: collId) } },
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
                if manualCollections.count > 0 {
                    Menu("Move to Collection") {
                        ForEach(manualCollections) { collection in
                            Button {
                                Task { await moveToCollection(document, collectionId: collection.id) }
                            } label: {
                                Label(collection.name, systemImage: collection.icon ?? "folder")
                            }
                        }
                        Divider()
                        Button("Remove from Collection") {
                            Task { await moveToCollection(document, collectionId: nil) }
                        }
                    }
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

        // If smart filter has a search query, run search to get matching doc IDs
        if let smartFilter, let query = smartFilter.query, !query.isEmpty {
            do {
                let searchFilters: SearchFilters? = smartFilter.fileType.map { SearchFilters(fileTypes: [$0]) }
                let searchResponse = try await searchService.searchDocuments(
                    query: query, topK: 200, filters: searchFilters
                )
                smartQueryDocumentIds = Set(searchResponse.results.map(\.documentId))
            } catch {
                smartQueryDocumentIds = Set()
            }
        } else {
            smartQueryDocumentIds = nil
        }

        let filters = filtersForSidebarSelection()
        do {
            let response = try await documentService.list(filters: filters)
            documents = response.documents
            errorMessage = nil
            // Index loaded documents in Spotlight with entity keywords (best-effort)
            let readyDocs = response.documents.filter { $0.status == .ready }
            var entityNames: [UUID: [String]] = [:]
            await withTaskGroup(of: (UUID, [String]).self) { group in
                for doc in readyDocs {
                    group.addTask {
                        let names = (try? await entityService.getDocumentEntities(documentId: doc.id))?.map(\.name) ?? []
                        return (doc.id, names)
                    }
                }
                for await (docId, names) in group {
                    entityNames[docId] = names
                }
            }
            await spotlightIndexer.indexDocuments(response.documents, entityNames: entityNames)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func filtersForSidebarSelection() -> DocumentFilters? {
        if let smartFilter {
            // Smart collections use server-side fileType + tags filters.
            // Query-based smart collections also need a generous limit so the
            // client-side search-ID intersection covers a wide enough set.
            let hasQuery = smartFilter.query != nil && !smartFilter.query!.isEmpty
            return DocumentFilters(
                fileType: smartFilter.fileType,
                tags: smartFilter.tags,
                limit: hasQuery ? 500 : 50
            )
        }
        if let collectionId {
            return DocumentFilters(collectionId: collectionId)
        }
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
        case .entities:
            return nil
        }
    }

    private var filteredDocuments: [Document] {
        var result: [Document]
        switch sidebarSelection {
        case .favorites:
            result = documents.filter(\.isFavorite)
        default:
            result = documents
        }
        if let filter = entityFilter {
            result = result.filter { filter.documentIds.contains($0.id) }
        }
        // fileType + tags are now server-side — only query IDs need client-side intersection
        if let queryIds = smartQueryDocumentIds {
            result = result.filter { queryIds.contains($0.id) }
        }
        return result
    }

    private func entityFilterBanner(_ filter: ContentView.EntityFilter) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "line.3.horizontal.decrease.circle.fill")
                .foregroundStyle(.secondary)
            Text("Filtered by entity:")
                .font(.callout)
                .foregroundStyle(.secondary)
            EntityChipView(name: filter.entityName, entityType: filter.entityType)
            Spacer()
            Button {
                entityFilter = nil
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
            .help("Clear entity filter")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(.bar)
    }

    private func importFiles(_ urls: [URL]) {
        importFileURLs = urls
    }

    private func toggleFavorite(_ document: Document) async {
        _ = try? await documentService.toggleFavorite(document: document)
        await loadDocuments()
    }

    private func moveToCollection(_ document: Document, collectionId: UUID?) async {
        _ = try? await documentService.setCollection(documentId: document.id, collectionId: collectionId)
        await loadDocuments()
    }

    private func deleteDocument(_ document: Document) async {
        try? await documentService.delete(id: document.id)
        await spotlightIndexer.removeDocument(id: document.id)
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

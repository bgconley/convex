import SwiftUI
import Bootstrap
import CoreSpotlight
import Domain
import AppCore

struct ContentView: View {
    let root: CompositionRoot
    @Environment(\.scenePhase) private var scenePhase
    @State private var healthStatus: String = "Checking..."
    @State private var selectedSidebarItem: SidebarItem = .allDocuments
    @State private var selectedDocumentId: UUID?
    @State private var selectedEntityId: UUID?
    @State private var searchHitAnchorId: String?
    @State private var searchHitPageNumber: Int?
    @State private var showSearchOverlay = false
    @State private var entityFilter: EntityFilter?
    @State private var collections: [Collection] = []
    @State private var selectedCollectionId: UUID?
    @State private var showNewCollectionSheet = false
    @State private var showNewSmartCollectionSheet = false
    @State private var availableTags: [String] = []
    @State private var availableEntityTypes: [String] = []
    @State private var didConnectWebSocket = false
    @State private var didStartSpotlightIndex = false

    struct EntityFilter {
        let entityId: UUID
        let entityName: String
        let entityType: String
        let documentIds: Set<UUID>
    }

    enum SidebarItem: String, Hashable {
        case allDocuments = "All Documents"
        case favorites = "Favorites"
        case pdfs = "PDFs"
        case markdown = "Markdown"
        case documents = "Word"
        case spreadsheets = "Excel"
        case entities = "Entities"

        var iconName: String {
            switch self {
            case .allDocuments: "doc.on.doc"
            case .favorites: "star"
            case .pdfs: "doc.richtext"
            case .markdown: "doc.text"
            case .documents: "doc.fill"
            case .spreadsheets: "tablecells"
            case .entities: "link"
            }
        }

        var isDocumentFilter: Bool {
            self != .entities
        }
    }

    private static let documentItems: [SidebarItem] = [
        .allDocuments, .favorites, .pdfs, .markdown, .documents, .spreadsheets
    ]

    var body: some View {
        NavigationSplitView {
            List(selection: sidebarSelectionBinding) {
                Section("Library") {
                    ForEach(Self.documentItems, id: \.self) { item in
                        Label(item.rawValue, systemImage: item.iconName)
                            .tag(item)
                    }
                }
                Section("Collections") {
                    ForEach(topLevelCollections) { collection in
                        collectionRow(collection, depth: 0)
                    }
                    Button {
                        showNewCollectionSheet = true
                    } label: {
                        Label("New Collection", systemImage: "plus")
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                    Button {
                        Task {
                            if availableTags.isEmpty {
                                await loadAvailableTags()
                            }
                            showNewSmartCollectionSheet = true
                        }
                    } label: {
                        Label("New Smart Collection", systemImage: "gearshape")
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                }
                Section("Knowledge Graph") {
                    Label(SidebarItem.entities.rawValue, systemImage: SidebarItem.entities.iconName)
                        .tag(SidebarItem.entities)
                }
            }
            .navigationTitle("Cortex")
            .listStyle(.sidebar)
        } content: {
            if selectedSidebarItem.isDocumentFilter {
                DocumentLibraryView(
                    documentService: root.documentService,
                    searchService: root.searchService,
                    ingestionService: root.ingestionService,
                    entityService: root.entityService,
                    thumbnailLoader: root.thumbnailLoader,
                    spotlightIndexer: root.spotlightIndexer,
                    sidebarSelection: selectedSidebarItem,
                    collections: collections,
                    smartFilter: selectedSmartFilter,
                    selectedDocumentId: librarySelectionBinding,
                    entityFilter: entityFilterBinding,
                    collectionId: $selectedCollectionId
                )
            } else {
                EntityBrowserView(
                    entityService: root.entityService,
                    selectedEntityId: $selectedEntityId
                )
            }
        } detail: {
            if selectedSidebarItem.isDocumentFilter {
                documentDetailPane
            } else {
                entityDetailPane
            }
        }
        .overlay {
            if showSearchOverlay {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
                    .onTapGesture {
                        showSearchOverlay = false
                    }

                VStack {
                    SearchOverlayView(
                        searchService: root.searchService,
                        collections: collections.filter { !$0.isSmart },
                        availableTags: availableTags,
                        availableEntityTypes: availableEntityTypes,
                        defaultTopK: root.settings.defaultTopK,
                        defaultRerank: root.settings.defaultRerank,
                        defaultIncludeGraph: root.settings.defaultIncludeGraph,
                        onSelectResult: { item in
                            searchHitAnchorId = item.anchorId
                            searchHitPageNumber = item.pageNumber
                            selectedEntityId = nil
                            entityFilter = nil
                            selectedCollectionId = nil
                            selectedDocumentId = item.documentId
                            selectedSidebarItem = .allDocuments
                        },
                        onSelectDocument: { item in
                            searchHitAnchorId = item.bestChunkAnchorId
                            searchHitPageNumber = item.bestChunkPage
                            selectedEntityId = nil
                            entityFilter = nil
                            selectedCollectionId = nil
                            selectedDocumentId = item.documentId
                            selectedSidebarItem = .allDocuments
                        },
                        onDismiss: {
                            showSearchOverlay = false
                        }
                    )
                    Spacer()
                }
            }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showSearchOverlay.toggle()
                } label: {
                    Label("Search", systemImage: "magnifyingglass")
                }
                .keyboardShortcut("k", modifiers: .command)
                .help("Search documents (Cmd+K)")
            }

            ToolbarItem(placement: .status) {
                HStack(spacing: 4) {
                    Circle()
                        .fill(healthStatus == "healthy" ? .green : .orange)
                        .frame(width: 8, height: 8)
                    Text(healthStatus)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .background {
            // Hidden buttons for global keyboard shortcuts
            VStack {
                Button("") {
                    selectedSidebarItem = .allDocuments
                    selectedCollectionId = nil
                    entityFilter = nil
                }
                .keyboardShortcut("1", modifiers: .command)

                Button("") {
                    // Jump to Collections: select first collection if available
                    if let first = topLevelCollections.first {
                        selectedCollectionId = first.id
                        selectedSidebarItem = .allDocuments
                        entityFilter = nil
                    }
                }
                .keyboardShortcut("2", modifiers: .command)

                Button("") {
                    selectedSidebarItem = .entities
                    selectedCollectionId = nil
                    entityFilter = nil
                }
                .keyboardShortcut("3", modifiers: .command)

                Button("") {
                    Task { await toggleSelectedFavorite() }
                }
                .keyboardShortcut("d", modifiers: .command)
            }
            .frame(width: 0, height: 0)
            .opacity(0)
        }
        .onContinueUserActivity(CSSearchableItemActionType) { activity in
            guard let identifier = activity.userInfo?[CSSearchableItemActivityIdentifier] as? String,
                  let docId = UUID(uuidString: identifier) else {
                return
            }
            selectedSidebarItem = .allDocuments
            selectedCollectionId = nil
            entityFilter = nil
            selectedDocumentId = docId
        }
        .task {
            await checkHealth()
            await loadCollections()
            await loadAvailableTags()
            if !didConnectWebSocket {
                didConnectWebSocket = true
                await root.webSocketClient.connect { event in
                    Task {
                        await root.ingestionService.handle(event: event)
                    }
                }
            }
            await loadAvailableEntityTypes()
            await checkHealth()
            if !didStartSpotlightIndex {
                didStartSpotlightIndex = true
                Task(priority: .background) {
                    await indexAllDocumentsInSpotlight()
                }
            }
        }
        .onChange(of: scenePhase) { _, newValue in
            guard newValue == .active else { return }
            Task {
                await checkHealth()
            }
        }
        .onDisappear {
            didConnectWebSocket = false
            Task { await root.webSocketClient.disconnect() }
        }
        .sheet(isPresented: $showNewCollectionSheet) {
            NewCollectionSheet(
                collectionService: root.collectionService,
                existingCollections: collections,
                onCreated: { _ in
                    showNewCollectionSheet = false
                    Task { await loadCollections() }
                },
                onCancel: { showNewCollectionSheet = false }
            )
        }
        .sheet(isPresented: $showNewSmartCollectionSheet) {
            NewSmartCollectionSheet(
                collectionService: root.collectionService,
                allTags: availableTags,
                onCreated: { _ in
                    showNewSmartCollectionSheet = false
                    Task {
                        await loadCollections()
                        await loadAvailableTags()
                    }
                },
                onCancel: { showNewSmartCollectionSheet = false }
            )
        }
    }

    @ViewBuilder
    private var documentDetailPane: some View {
        if let selectedDocumentId {
            DocumentDetailView(
                documentId: selectedDocumentId,
                documentService: root.documentService,
                entityService: root.entityService,
                collectionService: root.collectionService,
                apiClient: root.apiClient,
                markdownRenderer: root.markdownRenderer,
                anchorId: searchHitAnchorId,
                pageNumber: searchHitPageNumber,
                onSelectEntity: { entityId in
                    Task {
                        await filterLibraryByEntity(entityId)
                    }
                }
            )
        } else {
            VStack(spacing: 16) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.system(size: 48))
                    .foregroundStyle(.secondary)
                Text("Select a document to view")
                    .font(.title2)
                    .foregroundStyle(.secondary)
                Text("or press \(Image(systemName: "command")) K to search")
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    @ViewBuilder
    private var entityDetailPane: some View {
        if let selectedEntityId {
            EntityDetailView(
                entityId: selectedEntityId,
                entityService: root.entityService,
                onSelectDocument: { docId in
                    selectedCollectionId = nil
                    entityFilter = nil
                    selectedDocumentId = docId
                    selectedSidebarItem = .allDocuments
                }
            )
        } else {
            VStack(spacing: 16) {
                Image(systemName: "link")
                    .font(.system(size: 48))
                    .foregroundStyle(.secondary)
                Text("Select an entity to explore")
                    .font(.title2)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    /// Binding that clears search-hit navigation state when the library changes selection.
    private var librarySelectionBinding: Binding<UUID?> {
        Binding(
            get: { selectedDocumentId },
            set: { newValue in
                searchHitAnchorId = nil
                searchHitPageNumber = nil
                selectedDocumentId = newValue
            }
        )
    }

    /// Binding that clears cross-mode state when sidebar selection changes.
    private var sidebarSelectionBinding: Binding<SidebarItem> {
        Binding(
            get: { selectedSidebarItem },
            set: { newValue in
                if newValue.isDocumentFilter && !selectedSidebarItem.isDocumentFilter {
                    selectedEntityId = nil
                } else if !newValue.isDocumentFilter && selectedSidebarItem.isDocumentFilter {
                    selectedDocumentId = nil
                    searchHitAnchorId = nil
                    searchHitPageNumber = nil
                }
                entityFilter = nil
                selectedCollectionId = nil
                selectedSidebarItem = newValue
            }
        )
    }

    /// Binding that clears entity filter when sidebar selection changes away from library.
    private var entityFilterBinding: Binding<EntityFilter?> {
        Binding(
            get: { entityFilter },
            set: { newValue in
                entityFilter = newValue
            }
        )
    }

    private func filterLibraryByEntity(_ entityId: UUID) async {
        do {
            let detail = try await root.entityService.getDetail(id: entityId)
            let docIds = Set(detail.documents.map(\.documentId))
            selectedSidebarItem = .allDocuments
            selectedCollectionId = nil
            selectedDocumentId = nil
            searchHitAnchorId = nil
            searchHitPageNumber = nil
            entityFilter = EntityFilter(
                entityId: detail.entity.id,
                entityName: detail.entity.name,
                entityType: detail.entity.entityType,
                documentIds: docIds
            )
        } catch {
            // If entity detail fails, fall back to entity mode
            selectedEntityId = entityId
            selectedSidebarItem = .entities
        }
    }

    private var selectedSmartFilter: CollectionFilter? {
        guard let selectedCollectionId else { return nil }
        return collections.first(where: { $0.id == selectedCollectionId })?.filterJson
    }

    private var topLevelCollections: [Collection] {
        collections.filter { $0.parentId == nil }
    }

    private func childCollections(of parentId: UUID) -> [Collection] {
        collections.filter { $0.parentId == parentId }
    }

    private func collectionRow(_ collection: Collection, depth: Int) -> AnyView {
        let children = childCollections(of: collection.id)
        if children.isEmpty {
            return AnyView(collectionLabel(collection, depth: depth))
        } else {
            return AnyView(
                DisclosureGroup {
                    ForEach(children) { child in
                        collectionRow(child, depth: depth + 1)
                    }
                } label: {
                    collectionLabel(collection, depth: depth)
                }
            )
        }
    }

    private func collectionLabel(_ collection: Collection, depth: Int) -> some View {
        let icon = collection.isSmart ? (collection.icon ?? "gearshape") : (collection.icon ?? "folder")
        return Button {
            selectedCollectionId = collection.id
            entityFilter = nil
            selectedSidebarItem = .allDocuments
        } label: {
            Label(collection.name, systemImage: icon)
        }
        .foregroundStyle(selectedCollectionId == collection.id ? .primary : .secondary)
        .dropDestination(for: String.self) { items, _ in
            guard !collection.isSmart,
                  let uuidString = items.first,
                  let docId = UUID(uuidString: uuidString) else {
                return false
            }
            Task {
                _ = try? await root.documentService.setCollection(documentId: docId, collectionId: collection.id)
            }
            return true
        }
        .contextMenu {
            Button(role: .destructive) {
                Task { await deleteCollection(collection.id) }
            } label: {
                Label("Delete", systemImage: "trash")
            }
        }
    }

    private func loadCollections() async {
        do {
            let response = try await root.collectionService.list()
            collections = response.collections
        } catch {
            // Collections loading is best-effort
        }
    }

    private func loadAvailableTags() async {
        do {
            availableTags = try await root.collectionService.listTags()
        } catch {
            // Tags are best-effort
        }
    }

    private func loadAvailableEntityTypes() async {
        do {
            availableEntityTypes = try await root.entityService.listEntityTypes()
        } catch {
            // Entity types are best-effort
        }
    }

    private func deleteCollection(_ id: UUID) async {
        try? await root.collectionService.delete(id: id)
        if selectedCollectionId == id {
            selectedCollectionId = nil
        }
        await loadCollections()
    }

    private func toggleSelectedFavorite() async {
        guard let docId = selectedDocumentId else { return }
        do {
            let doc = try await root.documentService.get(id: docId)
            _ = try await root.documentService.toggleFavorite(document: doc)
        } catch {
            // Best effort — favorite toggle is non-critical
        }
    }

    private func checkHealth() async {
        do {
            let status = try await root.healthRepo.checkHealth()
            healthStatus = status.status
        } catch {
            healthStatus = "disconnected"
        }
    }

    /// Background full-corpus Spotlight indexing: paginates through all documents,
    /// fetches entity names per document, and indexes everything.
    private func indexAllDocumentsInSpotlight() async {
        let pageSize = 100
        var offset = 0
        while true {
            let response: DocumentListResponse
            do {
                response = try await root.documentService.list(
                    filters: DocumentFilters(limit: pageSize, offset: offset)
                )
            } catch {
                break
            }
            guard !response.documents.isEmpty else { break }

            // Fetch entity names per document concurrently (best-effort)
            var entityNames: [UUID: [String]] = [:]
            await withTaskGroup(of: (UUID, [String]).self) { group in
                for doc in response.documents where doc.status == .ready {
                    group.addTask {
                        let names = (try? await root.entityService.getDocumentEntities(documentId: doc.id))?.map(\.name) ?? []
                        return (doc.id, names)
                    }
                }
                for await (docId, names) in group {
                    entityNames[docId] = names
                }
            }

            await root.spotlightIndexer.indexDocuments(response.documents, entityNames: entityNames)

            offset += response.documents.count
            if offset >= response.total { break }
        }
    }
}

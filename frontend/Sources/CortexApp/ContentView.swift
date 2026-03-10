import SwiftUI
import Bootstrap
import Domain

struct ContentView: View {
    let root: CompositionRoot
    @State private var healthStatus: String = "Checking..."
    @State private var selectedSidebarItem: SidebarItem = .allDocuments
    @State private var selectedDocumentId: UUID?
    @State private var searchHitAnchorId: String?
    @State private var searchHitPageNumber: Int?
    @State private var showSearchOverlay = false

    enum SidebarItem: String, CaseIterable {
        case allDocuments = "All Documents"
        case favorites = "Favorites"
        case pdfs = "PDFs"
        case markdown = "Markdown"
        case documents = "Word"
        case spreadsheets = "Excel"

        var iconName: String {
            switch self {
            case .allDocuments: "doc.on.doc"
            case .favorites: "star"
            case .pdfs: "doc.richtext"
            case .markdown: "doc.text"
            case .documents: "doc.fill"
            case .spreadsheets: "tablecells"
            }
        }
    }

    var body: some View {
        NavigationSplitView {
            List(SidebarItem.allCases, id: \.self, selection: $selectedSidebarItem) { item in
                Label(item.rawValue, systemImage: item.iconName)
            }
            .navigationTitle("Cortex")
            .listStyle(.sidebar)
        } content: {
            DocumentLibraryView(
                documentService: root.documentService,
                ingestionService: root.ingestionService,
                thumbnailLoader: root.thumbnailLoader,
                sidebarSelection: selectedSidebarItem,
                selectedDocumentId: librarySelectionBinding
            )
        } detail: {
            if let selectedDocumentId {
                DocumentDetailView(
                    documentId: selectedDocumentId,
                    documentService: root.documentService,
                    apiClient: root.apiClient,
                    markdownRenderer: root.markdownRenderer,
                    anchorId: searchHitAnchorId,
                    pageNumber: searchHitPageNumber
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
                        onSelectResult: { item in
                            searchHitAnchorId = item.anchorId
                            searchHitPageNumber = item.pageNumber
                            selectedDocumentId = item.documentId
                        },
                        onSelectDocument: { item in
                            searchHitAnchorId = item.bestChunkAnchorId
                            searchHitPageNumber = item.bestChunkPage
                            selectedDocumentId = item.documentId
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
        .task {
            await checkHealth()
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

    private func checkHealth() async {
        do {
            let status = try await root.healthRepo.checkHealth()
            healthStatus = status.status
        } catch {
            healthStatus = "disconnected"
        }
    }
}

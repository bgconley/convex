import SwiftUI
import Domain
import AppCore

struct SearchOverlayView: View {
    let searchService: SearchService
    let onSelectResult: (SearchResultItem) -> Void
    let onSelectDocument: (DocumentSearchResultItem) -> Void
    let onDismiss: () -> Void

    @State private var query = ""
    @State private var passageResults: [SearchResultItem] = []
    @State private var documentResults: [DocumentSearchResultItem] = []
    @State private var selectedIndex: Int = 0
    @State private var isSearching = false
    @State private var searchTimeMs: Double?
    @State private var totalCandidates: Int?
    @State private var searchMode: SearchMode = .passages
    @State private var fileTypeFilter: String?
    @State private var dateFrom: Date?
    @State private var dateTo: Date?
    @State private var collectionId: UUID?
    @State private var expandedDocIds: Set<UUID> = []
    @FocusState private var isFieldFocused: Bool

    private var resultCount: Int {
        searchMode == .passages ? groupedPassageResults.count : documentResults.count
    }

    /// Group passage results by document for "More from this document" expansion.
    private var groupedPassageResults: [PassageGroup] {
        var groups: [UUID: PassageGroup] = [:]
        var order: [UUID] = []
        for item in passageResults {
            if groups[item.documentId] == nil {
                groups[item.documentId] = PassageGroup(documentId: item.documentId, items: [])
                order.append(item.documentId)
            }
            groups[item.documentId]?.items.append(item)
        }
        return order.compactMap { groups[$0] }
    }

    var body: some View {
        VStack(spacing: 0) {
            searchField
            Divider()
            SearchFiltersView(
                searchMode: $searchMode,
                fileTypeFilter: $fileTypeFilter,
                dateFrom: $dateFrom,
                dateTo: $dateTo,
                collectionId: $collectionId
            )
            Divider()
            resultsList
            if resultCount > 0 || isSearching {
                Divider()
                statusBar
            }
        }
        .frame(width: 640)
        .frame(maxHeight: 520)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.3), radius: 20, y: 10)
        .padding(.top, 60)
        .onAppear {
            isFieldFocused = true
        }
        .onChange(of: searchMode) { _, _ in
            if query.count >= 2 { performSearch(query) }
        }
        .onChange(of: fileTypeFilter) { _, _ in
            if query.count >= 2 { performSearch(query) }
        }
        .onChange(of: dateFrom) { _, _ in
            if query.count >= 2 { performSearch(query) }
        }
        .onChange(of: dateTo) { _, _ in
            if query.count >= 2 { performSearch(query) }
        }
    }

    private var searchField: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)

            TextField("Search documents...", text: $query)
                .textFieldStyle(.plain)
                .font(.title3)
                .focused($isFieldFocused)
                .onSubmit { selectCurrentResult() }
                .onChange(of: query) { _, newValue in
                    performSearch(newValue)
                }

            if isSearching {
                ProgressView()
                    .controlSize(.small)
            }

            if !query.isEmpty {
                Button {
                    query = ""
                    passageResults = []
                    documentResults = []
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }

            Button("", action: onDismiss)
                .keyboardShortcut(.escape, modifiers: [])
                .hidden()
                .frame(width: 0, height: 0)
        }
        .padding(12)
    }

    private var resultsList: some View {
        Group {
            if resultCount == 0 && !query.isEmpty && !isSearching {
                VStack(spacing: 8) {
                    Image(systemName: "magnifyingglass")
                        .font(.title)
                        .foregroundStyle(.tertiary)
                    Text("No results found")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 24)
            } else if resultCount > 0 {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            switch searchMode {
                            case .passages:
                                passageResultsList
                            case .documents:
                                documentResultsList
                            }
                        }
                    }
                    .onKeyPress(.upArrow) {
                        if selectedIndex > 0 {
                            selectedIndex -= 1
                            proxy.scrollTo(selectedIndex)
                        }
                        return .handled
                    }
                    .onKeyPress(.downArrow) {
                        if selectedIndex < resultCount - 1 {
                            selectedIndex += 1
                            proxy.scrollTo(selectedIndex)
                        }
                        return .handled
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var passageResultsList: some View {
        ForEach(Array(groupedPassageResults.enumerated()), id: \.element.documentId) { groupIndex, group in
            // First result always shown
            SearchResultRow(item: group.items[0], isSelected: groupIndex == selectedIndex)
                .id(groupIndex)
                .onTapGesture {
                    onSelectResult(group.items[0])
                    onDismiss()
                }

            // "More from this document" toggle if multiple chunks
            if group.items.count > 1 {
                Button {
                    if expandedDocIds.contains(group.documentId) {
                        expandedDocIds.remove(group.documentId)
                    } else {
                        expandedDocIds.insert(group.documentId)
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: expandedDocIds.contains(group.documentId)
                              ? "chevron.down" : "chevron.right")
                            .font(.caption2)
                        Text("\(group.items.count - 1) more from this document")
                            .font(.caption)
                    }
                    .foregroundStyle(.secondary)
                    .padding(.leading, 48)
                    .padding(.vertical, 4)
                }
                .buttonStyle(.plain)

                if expandedDocIds.contains(group.documentId) {
                    ForEach(group.items.dropFirst(), id: \.id) { item in
                        SearchResultRow(item: item, isSelected: false)
                            .onTapGesture {
                                onSelectResult(item)
                                onDismiss()
                            }
                            .padding(.leading, 12)
                    }
                }
            }

            if groupIndex < groupedPassageResults.count - 1 {
                Divider().padding(.leading, 48)
            }
        }
    }

    @ViewBuilder
    private var documentResultsList: some View {
        ForEach(Array(documentResults.enumerated()), id: \.element.id) { index, item in
            DocumentSearchResultRow(item: item, isSelected: index == selectedIndex)
                .id(index)
                .onTapGesture {
                    onSelectDocument(item)
                    onDismiss()
                }
            if index < documentResults.count - 1 {
                Divider().padding(.leading, 48)
            }
        }
    }

    private var statusBar: some View {
        HStack {
            if let total = totalCandidates {
                let label = searchMode == .passages ? "passages" : "documents"
                Text("\(resultCount) of \(total) \(label)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if let time = searchTimeMs {
                Text(String(format: "%.0f ms", time))
                    .font(.caption)
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            HStack(spacing: 4) {
                Image(systemName: "arrow.up")
                Image(systemName: "arrow.down")
                Text("navigate")
                Image(systemName: "return")
                Text("open")
                Image(systemName: "escape")
                Text("close")
            }
            .font(.caption2)
            .foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
    }

    private func buildFilters() -> SearchFilters? {
        let hasFileType = fileTypeFilter != nil
        let hasDate = dateFrom != nil || dateTo != nil
        let hasCollection = collectionId != nil
        guard hasFileType || hasDate || hasCollection else { return nil }
        return SearchFilters(
            fileTypes: fileTypeFilter.map { [$0] },
            collectionIds: collectionId.map { [$0] },
            dateFrom: dateFrom,
            dateTo: dateTo
        )
    }

    private func performSearch(_ query: String) {
        guard query.count >= 2 else {
            passageResults = []
            documentResults = []
            searchTimeMs = nil
            totalCandidates = nil
            isSearching = false
            expandedDocIds = []
            Task { await searchService.cancelPendingSearch() }
            return
        }

        isSearching = true
        let filters = buildFilters()

        switch searchMode {
        case .passages:
            Task {
                await searchService.debouncedSearch(query: query, filters: filters) { @Sendable result in
                    Task { @MainActor in
                        isSearching = false
                        switch result {
                        case .success(let response):
                            passageResults = response.results
                            searchTimeMs = response.searchTimeMs
                            totalCandidates = response.totalCandidates
                            selectedIndex = 0
                            expandedDocIds = []
                        case .failure:
                            passageResults = []
                        }
                    }
                }
            }
        case .documents:
            Task {
                await searchService.debouncedSearchDocuments(query: query, filters: filters) { @Sendable result in
                    Task { @MainActor in
                        isSearching = false
                        switch result {
                        case .success(let response):
                            documentResults = response.results
                            searchTimeMs = response.searchTimeMs
                            totalCandidates = response.totalDocuments
                            selectedIndex = 0
                        case .failure:
                            documentResults = []
                        }
                    }
                }
            }
        }
    }

    private func selectCurrentResult() {
        switch searchMode {
        case .passages:
            let groups = groupedPassageResults
            guard !groups.isEmpty, selectedIndex < groups.count else { return }
            onSelectResult(groups[selectedIndex].items[0])
        case .documents:
            guard !documentResults.isEmpty, selectedIndex < documentResults.count else { return }
            onSelectDocument(documentResults[selectedIndex])
        }
        onDismiss()
    }
}

private struct PassageGroup {
    let documentId: UUID
    var items: [SearchResultItem]
}

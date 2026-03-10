import SwiftUI
import Domain
import AppCore

struct SearchOverlayView: View {
    let searchService: SearchService
    let onSelectResult: (SearchResultItem) -> Void
    let onDismiss: () -> Void

    @State private var query = ""
    @State private var results: [SearchResultItem] = []
    @State private var selectedIndex: Int = 0
    @State private var isSearching = false
    @State private var searchTimeMs: Double?
    @State private var totalCandidates: Int?
    @FocusState private var isFieldFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            searchField
            Divider()
            resultsList
            if !results.isEmpty || isSearching {
                Divider()
                statusBar
            }
        }
        .frame(width: 600)
        .frame(maxHeight: 500)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.3), radius: 20, y: 10)
        .padding(.top, 60)
        .onAppear {
            isFieldFocused = true
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
                .onSubmit {
                    selectCurrentResult()
                }
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
                    results = []
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
            if results.isEmpty && !query.isEmpty && !isSearching {
                VStack(spacing: 8) {
                    Image(systemName: "magnifyingglass")
                        .font(.title)
                        .foregroundStyle(.tertiary)
                    Text("No results found")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 24)
            } else if !results.isEmpty {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(Array(results.enumerated()), id: \.element.id) { index, item in
                                SearchResultRow(item: item, isSelected: index == selectedIndex)
                                    .id(index)
                                    .onTapGesture {
                                        onSelectResult(item)
                                        onDismiss()
                                    }
                                if index < results.count - 1 {
                                    Divider().padding(.leading, 48)
                                }
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
                        if selectedIndex < results.count - 1 {
                            selectedIndex += 1
                            proxy.scrollTo(selectedIndex)
                        }
                        return .handled
                    }
                }
            }
        }
    }

    private var statusBar: some View {
        HStack {
            if let total = totalCandidates {
                Text("\(results.count) of \(total) results")
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

    private func performSearch(_ query: String) {
        guard query.count >= 2 else {
            results = []
            searchTimeMs = nil
            totalCandidates = nil
            isSearching = false
            Task { await searchService.cancelPendingSearch() }
            return
        }
        isSearching = true
        Task {
            await searchService.debouncedSearch(query: query) { @Sendable result in
                Task { @MainActor in
                    isSearching = false
                    switch result {
                    case .success(let response):
                        results = response.results
                        searchTimeMs = response.searchTimeMs
                        totalCandidates = response.totalCandidates
                        selectedIndex = 0
                    case .failure:
                        results = []
                    }
                }
            }
        }
    }

    private func selectCurrentResult() {
        guard !results.isEmpty, selectedIndex < results.count else { return }
        onSelectResult(results[selectedIndex])
        onDismiss()
    }
}

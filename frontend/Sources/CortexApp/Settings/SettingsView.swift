import SwiftUI
import Bootstrap
import Domain

struct SettingsView: View {
    let healthRepo: any HealthPort

    @State private var backendURLString: String
    @State private var defaultTopK: Int
    @State private var defaultRerank: Bool
    @State private var defaultIncludeGraph: Bool
    @State private var stats: SystemStats?
    @State private var statsError: String?
    @State private var isLoadingStats = false
    @State private var saveConfirmation = false

    init(settings: Bootstrap.Settings, healthRepo: any HealthPort) {
        self.healthRepo = healthRepo
        _backendURLString = State(initialValue: settings.backendURL.absoluteString)
        _defaultTopK = State(initialValue: settings.defaultTopK)
        _defaultRerank = State(initialValue: settings.defaultRerank)
        _defaultIncludeGraph = State(initialValue: settings.defaultIncludeGraph)
    }

    var body: some View {
        TabView {
            generalTab
                .tabItem {
                    Label("General", systemImage: "gear")
                }
            searchTab
                .tabItem {
                    Label("Search", systemImage: "magnifyingglass")
                }
            storageTab
                .tabItem {
                    Label("Storage", systemImage: "externaldrive")
                }
        }
        .frame(width: 480, height: 320)
    }

    // MARK: - General Tab

    private var generalTab: some View {
        Form {
            Section("Backend Connection") {
                TextField("Backend URL", text: $backendURLString)
                    .textFieldStyle(.roundedBorder)
                    .help("URL of the Cortex API server (e.g. http://10.25.0.50:8090/api/v1)")

                HStack {
                    Spacer()
                    Button("Save & Reconnect") {
                        persistSettings()
                    }
                    .disabled(!isURLValid)
                }
            }

            if saveConfirmation {
                Section {
                    Label("Settings saved. Restart the app to apply changes.", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                }
            }

            Section("Keyboard Shortcuts") {
                VStack(alignment: .leading, spacing: 6) {
                    shortcutRow("Search", shortcut: "\u{2318}K")
                    shortcutRow("Import", shortcut: "\u{2318}I")
                    shortcutRow("Library", shortcut: "\u{2318}1")
                    shortcutRow("Collections", shortcut: "\u{2318}2")
                    shortcutRow("Knowledge Graph", shortcut: "\u{2318}3")
                    shortcutRow("Toggle Favorite", shortcut: "\u{2318}D")
                }
                .font(.callout)
            }
        }
        .formStyle(.grouped)
        .padding()
    }

    // MARK: - Search Tab

    private var searchTab: some View {
        Form {
            Section("Search Defaults") {
                Stepper("Results per search: \(defaultTopK)", value: $defaultTopK, in: 5...50, step: 5)
                Toggle("Neural reranking", isOn: $defaultRerank)
                    .help("Use mxbai-rerank-large-v2 to reorder results by relevance")
                Toggle("Knowledge graph expansion", isOn: $defaultIncludeGraph)
                    .help("Expand search queries through entity co-occurrence graph")
            }

            Section {
                HStack {
                    Spacer()
                    Button("Save") {
                        persistSettings()
                    }
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }

    // MARK: - Storage Tab

    private var storageTab: some View {
        Form {
            Section("Corpus Statistics") {
                if isLoadingStats {
                    ProgressView("Loading statistics...")
                } else if let stats {
                    LabeledContent("Documents", value: "\(stats.documentCount)")
                    LabeledContent("Chunks", value: "\(stats.chunkCount)")
                    LabeledContent("Entities", value: "\(stats.entityCount)")
                    LabeledContent("Total File Size", value: stats.formattedFileSize)
                } else if let error = statsError {
                    Label(error, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.red)
                } else {
                    Text("No data loaded")
                        .foregroundStyle(.secondary)
                }
            }
            Section {
                HStack {
                    Spacer()
                    Button("Refresh") {
                        Task { await loadStats() }
                    }
                    .disabled(isLoadingStats)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
        .task {
            await loadStats()
        }
    }

    // MARK: - Helpers

    private var isURLValid: Bool {
        URL(string: backendURLString) != nil && !backendURLString.isEmpty
    }

    private func persistSettings() {
        guard let url = URL(string: backendURLString) else { return }
        let settings = Bootstrap.Settings(
            backendURL: url,
            defaultTopK: defaultTopK,
            defaultRerank: defaultRerank,
            defaultIncludeGraph: defaultIncludeGraph
        )
        settings.save()
        saveConfirmation = true
        Task {
            try? await Task.sleep(for: .seconds(3))
            saveConfirmation = false
        }
    }

    private func loadStats() async {
        isLoadingStats = true
        defer { isLoadingStats = false }
        do {
            stats = try await healthRepo.fetchStats()
            statsError = nil
        } catch {
            statsError = error.localizedDescription
        }
    }

    private func shortcutRow(_ label: String, shortcut: String) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(shortcut)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 4))
        }
    }
}

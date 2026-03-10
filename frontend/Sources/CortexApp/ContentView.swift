import SwiftUI
import Bootstrap
import Domain

struct ContentView: View {
    let root: CompositionRoot
    @State private var healthStatus: String = "Checking..."
    @State private var selectedSidebarItem: SidebarItem = .allDocuments

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
            VStack {
                Text(selectedSidebarItem.rawValue)
                    .font(.title2)
                    .foregroundColor(.secondary)
                Text("Document library will be added in Step 1.10")
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .navigationTitle(selectedSidebarItem.rawValue)
        } detail: {
            VStack(spacing: 16) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.system(size: 48))
                    .foregroundColor(.secondary)
                Text("Select a document to view")
                    .font(.title2)
                    .foregroundColor(.secondary)
                Text("or press \(Image(systemName: "command")) K to search")
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .toolbar {
            ToolbarItem(placement: .status) {
                HStack(spacing: 4) {
                    Circle()
                        .fill(healthStatus == "healthy" ? .green : .orange)
                        .frame(width: 8, height: 8)
                    Text(healthStatus)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .task {
            await checkHealth()
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
}

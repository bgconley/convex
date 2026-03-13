import SwiftUI
import Domain
import AppCore

struct EntityBrowserView: View {
    let entityService: EntityService
    @Binding var selectedEntityId: UUID?

    @State private var entities: [Entity] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    /// Entities grouped by type, sorted by total mention count per group.
    private var groupedEntities: [(type: String, entities: [Entity])] {
        let grouped = Dictionary(grouping: entities, by: \.entityType)
        return grouped
            .map { (type: $0.key, entities: $0.value) }
            .sorted { $0.entities.reduce(0, { $0 + $1.mentionCount }) > $1.entities.reduce(0, { $0 + $1.mentionCount }) }
    }

    var body: some View {
        Group {
            if isLoading && entities.isEmpty {
                ProgressView("Loading entities...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let errorMessage {
                ContentUnavailableView {
                    Label("Error", systemImage: "exclamationmark.triangle")
                } description: {
                    Text(errorMessage)
                }
            } else if entities.isEmpty {
                ContentUnavailableView {
                    Label("No Entities", systemImage: "tag.slash")
                } description: {
                    Text("No entities have been extracted yet.")
                }
            } else {
                List(selection: $selectedEntityId) {
                    ForEach(groupedEntities, id: \.type) { group in
                        DisclosureGroup {
                            ForEach(group.entities) { entity in
                                EntityRowView(entity: entity)
                                    .tag(entity.id)
                            }
                        } label: {
                            HStack {
                                EntityChipView(name: group.type.capitalized, entityType: group.type)
                                Spacer()
                                Text("\(group.entities.count)")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(Color.gray.opacity(0.15))
                                    .clipShape(Capsule())
                            }
                        }
                    }
                }
                .listStyle(.sidebar)
            }
        }
        .navigationTitle("Entities")
        .task {
            await loadEntities()
        }
    }

    private func loadEntities() async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await entityService.list(limit: 500)
            entities = response.entities
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

private struct EntityRowView: View {
    let entity: Entity

    var body: some View {
        HStack {
            Text(entity.name)
                .lineLimit(1)
            Spacer()
            Text("\(entity.mentionCount)")
                .font(.caption2)
                .monospacedDigit()
                .foregroundStyle(.secondary)
                .padding(.horizontal, 5)
                .padding(.vertical, 1)
                .background(Color.gray.opacity(0.1))
                .clipShape(Capsule())
        }
        .padding(.vertical, 1)
    }
}

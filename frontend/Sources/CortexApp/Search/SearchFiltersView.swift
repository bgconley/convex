import SwiftUI
import Domain

enum SearchMode: String, CaseIterable {
    case passages = "Passages"
    case documents = "Documents"
}

struct SearchFiltersView: View {
    @Binding var searchMode: SearchMode
    @Binding var fileTypeFilter: String?
    @Binding var dateFrom: Date?
    @Binding var dateTo: Date?
    @Binding var collectionId: UUID?
    @Binding var selectedTags: Set<String>
    @Binding var selectedEntityTypes: Set<String>
    let collections: [Collection]
    let availableTags: [String]
    let availableEntityTypes: [String]

    private let fileTypeOptions: [(label: String, value: String?)] = [
        ("All Types", nil),
        ("PDF", "pdf"),
        ("Markdown", "markdown"),
        ("Word", "docx"),
        ("Excel", "xlsx"),
        ("Text", "txt"),
        ("PNG", "png"),
        ("JPEG", "jpg"),
        ("TIFF", "tiff"),
    ]

    var body: some View {
        HStack(spacing: 8) {
            Picker("Mode", selection: $searchMode) {
                ForEach(SearchMode.allCases, id: \.self) { mode in
                    Text(mode.rawValue).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 180)

            Picker("Type", selection: $fileTypeFilter) {
                ForEach(fileTypeOptions, id: \.label) { option in
                    Text(option.label).tag(option.value)
                }
            }
            .frame(width: 110)

            dateFilterButton(label: "From", date: $dateFrom)
            dateFilterButton(label: "To", date: $dateTo)

            // Collection filter — enabled when collections exist (Phase 4)
            Menu {
                Button("All Collections") { collectionId = nil }
                if collections.isEmpty {
                    Divider()
                    Text("No collections yet")
                        .foregroundStyle(.tertiary)
                } else {
                    Divider()
                    ForEach(collections) { collection in
                        Button(collection.name) {
                            collectionId = collection.id
                        }
                    }
                }
            } label: {
                HStack(spacing: 2) {
                    Image(systemName: "folder")
                    Text(selectedCollectionName)
                }
                .font(.caption)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
            }
            .menuStyle(.borderlessButton)
            .help("Filter by collection")

            multiSelectMenu(
                title: selectedTags.isEmpty ? "Tags" : "\(selectedTags.count) tag\(selectedTags.count == 1 ? "" : "s")",
                systemImage: "tag",
                options: availableTags,
                selection: $selectedTags,
                emptyLabel: "No tags yet"
            )
            .help("Filter by tags")

            multiSelectMenu(
                title: selectedEntityTypes.isEmpty ? "Entities" : "\(selectedEntityTypes.count) entity type\(selectedEntityTypes.count == 1 ? "" : "s")",
                systemImage: "link",
                options: availableEntityTypes,
                selection: $selectedEntityTypes,
                emptyLabel: "No entity types"
            )
            .help("Filter by entity type")

            if fileTypeFilter != nil || collectionId != nil || dateFrom != nil || dateTo != nil || !selectedTags.isEmpty || !selectedEntityTypes.isEmpty {
                Button {
                    fileTypeFilter = nil
                    collectionId = nil
                    dateFrom = nil
                    dateTo = nil
                    selectedTags = Set<String>()
                    selectedEntityTypes = Set<String>()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .help("Clear active filters")
            }

            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
    }

    private func dateFilterButton(label: String, date: Binding<Date?>) -> some View {
        Menu {
            if date.wrappedValue != nil {
                Button("Clear") { date.wrappedValue = nil }
                Divider()
            }
            Button("Today") { date.wrappedValue = Calendar.current.startOfDay(for: Date()) }
            Button("Past Week") { date.wrappedValue = Calendar.current.date(byAdding: .day, value: -7, to: Date()) }
            Button("Past Month") { date.wrappedValue = Calendar.current.date(byAdding: .month, value: -1, to: Date()) }
            Button("Past Year") { date.wrappedValue = Calendar.current.date(byAdding: .year, value: -1, to: Date()) }
        } label: {
            HStack(spacing: 2) {
                Text(label)
                    .font(.caption)
                if let d = date.wrappedValue {
                    Text(d, style: .date)
                        .font(.caption)
                        .foregroundStyle(.primary)
                }
            }
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(date.wrappedValue != nil ? Color.accentColor.opacity(0.1) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 4))
        }
        .menuStyle(.borderlessButton)
        .frame(width: date.wrappedValue != nil ? 110 : 50)
    }

    private var selectedCollectionName: String {
        guard let collectionId else { return "All Collections" }
        return collections.first(where: { $0.id == collectionId })?.name ?? "Collection"
    }

    private func multiSelectMenu(
        title: String,
        systemImage: String,
        options: [String],
        selection: Binding<Set<String>>,
        emptyLabel: String
    ) -> some View {
        Menu {
            Button("Clear") {
                selection.wrappedValue = Set<String>()
            }
            .disabled(selection.wrappedValue.isEmpty)

            Divider()

            if options.isEmpty {
                Text(emptyLabel)
                    .foregroundStyle(.tertiary)
            } else {
                ForEach(options, id: \.self) { option in
                    Button {
                        var values = selection.wrappedValue
                        if values.contains(option) {
                            values.remove(option)
                        } else {
                            values.insert(option)
                        }
                        selection.wrappedValue = values
                    } label: {
                        HStack {
                            Text(option)
                            if selection.wrappedValue.contains(option) {
                                Spacer()
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                }
            }
        } label: {
            HStack(spacing: 2) {
                Image(systemName: systemImage)
                Text(title)
            }
            .font(.caption)
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(selection.wrappedValue.isEmpty ? Color.clear : Color.accentColor.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 4))
        }
        .menuStyle(.borderlessButton)
    }
}

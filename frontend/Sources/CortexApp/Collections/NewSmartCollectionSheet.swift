import SwiftUI
import AppCore
import Domain

struct NewSmartCollectionSheet: View {
    let collectionService: CollectionService
    let allTags: [String]
    let onCreated: (Collection) -> Void
    let onCancel: () -> Void

    @State private var name = ""
    @State private var searchQuery = ""
    @State private var fileType = ""
    @State private var selectedTags: Set<String> = []
    @State private var isCreating = false
    @State private var errorMessage: String?

    private static let fileTypeOptions = [
        ("", "Any"),
        ("pdf", "PDF"),
        ("docx", "Word"),
        ("xlsx", "Excel"),
        ("markdown", "Markdown"),
        ("txt", "Plain Text"),
    ]

    var body: some View {
        VStack(spacing: 16) {
            Text("New Smart Collection")
                .font(.headline)

            TextField("Collection name", text: $name)
                .textFieldStyle(.roundedBorder)

            TextField("Search query (optional)", text: $searchQuery)
                .textFieldStyle(.roundedBorder)

            Picker("File Type", selection: $fileType) {
                ForEach(Self.fileTypeOptions, id: \.0) { value, label in
                    Text(label).tag(value)
                }
            }

            if !allTags.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Tags")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    ScrollView {
                        FlowLayout(spacing: 4) {
                            ForEach(allTags, id: \.self) { tag in
                                Button {
                                    if selectedTags.contains(tag) {
                                        selectedTags.remove(tag)
                                    } else {
                                        selectedTags.insert(tag)
                                    }
                                } label: {
                                    Text(tag)
                                        .font(.caption)
                                        .padding(.horizontal, 8)
                                        .padding(.vertical, 4)
                                        .background(selectedTags.contains(tag) ? Color.accentColor.opacity(0.3) : Color.gray.opacity(0.15))
                                        .clipShape(Capsule())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .frame(maxHeight: 100)
                }
            }

            if let errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundStyle(.red)
            }

            HStack {
                Button("Cancel", action: onCancel)
                    .keyboardShortcut(.cancelAction)
                Spacer()
                Button("Create") {
                    Task { await createSmartCollection() }
                }
                .keyboardShortcut(.defaultAction)
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isCreating || !hasFilter)
            }
        }
        .padding(20)
        .frame(width: 340)
    }

    private var hasFilter: Bool {
        !searchQuery.trimmingCharacters(in: .whitespaces).isEmpty || !fileType.isEmpty || !selectedTags.isEmpty
    }

    private func createSmartCollection() async {
        isCreating = true
        errorMessage = nil

        let trimmedQuery = searchQuery.trimmingCharacters(in: .whitespaces)
        let filter = CollectionFilter(
            query: trimmedQuery.isEmpty ? nil : trimmedQuery,
            fileType: fileType.isEmpty ? nil : fileType,
            tags: selectedTags.isEmpty ? nil : Array(selectedTags)
        )

        do {
            let collection = try await collectionService.create(
                name: name.trimmingCharacters(in: .whitespaces),
                icon: "gearshape",
                filterJson: filter
            )
            onCreated(collection)
        } catch {
            errorMessage = error.localizedDescription
        }
        isCreating = false
    }
}

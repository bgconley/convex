import SwiftUI
import AppCore
import Domain

struct NewCollectionSheet: View {
    let collectionService: CollectionService
    let existingCollections: [Collection]
    let onCreated: (Collection) -> Void
    let onCancel: () -> Void

    @State private var name = ""
    @State private var description = ""
    @State private var icon = "folder"
    @State private var selectedParentId: UUID?
    @State private var isCreating = false
    @State private var errorMessage: String?

    private static let iconOptions = [
        "folder", "folder.fill", "tray.full", "archivebox",
        "book.closed", "bookmark", "tag", "star",
        "heart", "flag", "briefcase", "graduationcap",
    ]

    var body: some View {
        VStack(spacing: 16) {
            Text("New Collection")
                .font(.headline)

            TextField("Collection name", text: $name)
                .textFieldStyle(.roundedBorder)

            TextField("Description (optional)", text: $description)
                .textFieldStyle(.roundedBorder)

            Picker("Icon", selection: $icon) {
                ForEach(Self.iconOptions, id: \.self) { iconName in
                    Label(iconName, systemImage: iconName)
                        .tag(iconName)
                }
            }

            if !existingCollections.isEmpty {
                Picker("Parent Collection", selection: $selectedParentId) {
                    Text("None (top-level)")
                        .tag(nil as UUID?)
                    ForEach(existingCollections) { collection in
                        Label(collection.name, systemImage: collection.icon ?? "folder")
                            .tag(collection.id as UUID?)
                    }
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
                    Task { await createCollection() }
                }
                .keyboardShortcut(.defaultAction)
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isCreating)
            }
        }
        .padding(20)
        .frame(width: 320)
    }

    private func createCollection() async {
        isCreating = true
        errorMessage = nil
        do {
            let collection = try await collectionService.create(
                name: name.trimmingCharacters(in: .whitespaces),
                description: description.isEmpty ? nil : description,
                icon: icon,
                parentId: selectedParentId
            )
            onCreated(collection)
        } catch {
            errorMessage = error.localizedDescription
        }
        isCreating = false
    }
}

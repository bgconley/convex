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

    @State private var showDateFrom = false
    @State private var showDateTo = false

    private let fileTypeOptions: [(label: String, value: String?)] = [
        ("All Types", nil),
        ("PDF", "pdf"),
        ("Markdown", "markdown"),
        ("Word", "docx"),
        ("Excel", "xlsx"),
        ("Text", "txt"),
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

            dateFilterButton(label: "From", date: $dateFrom, showPicker: $showDateFrom)
            dateFilterButton(label: "To", date: $dateTo, showPicker: $showDateTo)

            // Collection filter — enabled when collections exist (Phase 4)
            Menu {
                Button("All Collections") { collectionId = nil }
                Divider()
                Text("No collections yet")
                    .foregroundStyle(.tertiary)
            } label: {
                HStack(spacing: 2) {
                    Image(systemName: "folder")
                    Text(collectionId == nil ? "All" : "Collection")
                }
                .font(.caption)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
            }
            .menuStyle(.borderlessButton)
            .disabled(true)
            .help("Collection filter (available after collections are created)")

            if dateFrom != nil || dateTo != nil {
                Button {
                    dateFrom = nil
                    dateTo = nil
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .help("Clear date filters")
            }

            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
    }

    private func dateFilterButton(label: String, date: Binding<Date?>, showPicker: Binding<Bool>) -> some View {
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
}

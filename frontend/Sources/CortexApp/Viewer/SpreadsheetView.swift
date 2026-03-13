import SwiftUI

struct SpreadsheetView: View {
    let spreadsheetJSON: String
    let originalURL: URL?
    let anchorId: String?
    var searchQuery: String = ""

    @State private var viewMode: ViewRepresentation = .structured

    private var workbook: SpreadsheetWorkbook? {
        guard let data = spreadsheetJSON.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(SpreadsheetWorkbook.self, from: data)
    }

    enum ViewRepresentation: String, CaseIterable {
        case structured = "Structured"
        case original = "Original"
    }

    var body: some View {
        Group {
            switch viewMode {
            case .structured:
                if let workbook, !workbook.sheets.isEmpty {
                    SpreadsheetStructuredView(
                        workbook: workbook,
                        anchorId: anchorId,
                        searchQuery: searchQuery
                    )
                } else {
                    ContentUnavailableView(
                        "Spreadsheet content unavailable",
                        systemImage: "tablecells.badge.ellipsis",
                        description: Text("Structured spreadsheet data was not returned by the backend.")
                    )
                }
            case .original:
                if let originalURL {
                    QuickLookView(url: originalURL)
                } else {
                    ContentUnavailableView(
                        "Original file unavailable",
                        systemImage: "tablecells.badge.exclamationmark",
                        description: Text("Structured view is still available.")
                    )
                }
            }
        }
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Picker("View", selection: $viewMode) {
                    ForEach(ViewRepresentation.allCases, id: \.self) { mode in
                        Text(mode.rawValue).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .help("Toggle Structured / Original view")
            }
        }
    }
}

private struct SpreadsheetStructuredView: View {
    let workbook: SpreadsheetWorkbook
    let anchorId: String?
    let searchQuery: String

    @State private var selectedSheetName: String?

    private var currentSheet: SpreadsheetSheet? {
        if let selectedSheetName,
           let selected = workbook.sheets.first(where: { $0.name == selectedSheetName }) {
            return selected
        }
        return workbook.sheets.first
    }

    var body: some View {
        VStack(spacing: 0) {
            if workbook.sheets.count > 1 {
                sheetTabs
                Divider()
            }

            if let sheet = currentSheet {
                ScrollView([.horizontal, .vertical]) {
                    ScrollViewReader { proxy in
                        Grid(alignment: .topLeading, horizontalSpacing: 12, verticalSpacing: 8) {
                            ForEach(Array(sheet.rows.enumerated()), id: \.element.id) { index, row in
                                GridRow {
                                    ForEach(Array(row.cells.enumerated()), id: \.offset) { _, cell in
                                        Text(cell.isEmpty ? " " : cell)
                                            .font(index == 0 ? .headline : .body)
                                            .textSelection(.enabled)
                                            .lineLimit(nil)
                                            .frame(minWidth: 140, alignment: .leading)
                                            .padding(.horizontal, 10)
                                            .padding(.vertical, 8)
                                            .background(cellBackground(for: cell, rowIndex: index))
                                            .clipShape(RoundedRectangle(cornerRadius: 6))
                                    }
                                }
                                .id(row.id)
                                .background(rowBackground(for: row))
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                        }
                        .padding(16)
                        .task(id: scrollTargetKey) {
                            selectBestSheet()
                            guard let target = activeScrollTarget(in: currentSheet) else { return }
                            withAnimation(.easeInOut(duration: 0.2)) {
                                proxy.scrollTo(target, anchor: .top)
                            }
                        }
                    }
                }
                .background(Color(nsColor: .textBackgroundColor))
            }
        }
        .onAppear {
            selectBestSheet()
        }
        .onChange(of: anchorId) { _, _ in
            selectBestSheet()
        }
        .onChange(of: searchQuery) { _, _ in
            selectBestSheet()
        }
    }

    private var sheetTabs: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(workbook.sheets) { sheet in
                    Button(sheet.name) {
                        selectedSheetName = sheet.name
                    }
                    .buttonStyle(.plain)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(selectedSheetName == sheet.name ? Color.accentColor.opacity(0.15) : Color.clear)
                    .clipShape(Capsule())
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
        }
        .background(.bar)
    }

    private var scrollTargetKey: String {
        "\(workbookIdentity)|\(selectedSheetName ?? "")|\(anchorId ?? "")|\(searchQuery)"
    }

    private var workbookIdentity: String {
        workbook.sheets
            .map { sheet in
                let rowIdentity = sheet.rows
                    .map { row in
                        let anchors = row.anchorIds.joined(separator: ",")
                        let cells = row.cells.joined(separator: "\u{1F}")
                        return "\(row.id)#\(anchors)#\(cells)"
                    }
                    .joined(separator: "\u{1E}")
                return "\(sheet.name)#\(rowIdentity)"
            }
            .joined(separator: "\u{1D}")
    }

    private func selectBestSheet() {
        if let anchorId,
           let sheet = workbook.sheets.first(where: { sheet in
               sheet.rows.contains(where: { $0.anchorIds.contains(anchorId) })
           }) {
            selectedSheetName = sheet.name
            return
        }

        let trimmedQuery = searchQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedQuery.isEmpty,
           let sheet = workbook.sheets.first(where: { sheet in
               sheet.rows.contains(where: { row in
                   row.cells.joined(separator: " ").localizedCaseInsensitiveContains(trimmedQuery)
               })
           }) {
            selectedSheetName = sheet.name
            return
        }

        if selectedSheetName == nil {
            selectedSheetName = workbook.sheets.first?.name
        }
    }

    private func activeScrollTarget(in sheet: SpreadsheetSheet?) -> String? {
        guard let sheet else { return nil }

        if let anchorId,
           let row = sheet.rows.first(where: { $0.anchorIds.contains(anchorId) }) {
            return row.id
        }

        let trimmedQuery = searchQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedQuery.isEmpty,
           let row = sheet.rows.first(where: { row in
               row.cells.joined(separator: " ").localizedCaseInsensitiveContains(trimmedQuery)
           }) {
            return row.id
        }

        return nil
    }

    private func rowBackground(for row: SpreadsheetRow) -> Color {
        if let anchorId, row.anchorIds.contains(anchorId) {
            return Color.accentColor.opacity(0.12)
        }

        let trimmedQuery = searchQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedQuery.isEmpty,
           row.cells.joined(separator: " ").localizedCaseInsensitiveContains(trimmedQuery) {
            return Color.yellow.opacity(0.1)
        }

        return Color.clear
    }

    private func cellBackground(for cell: String, rowIndex: Int) -> Color {
        if !searchQuery.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
           cell.localizedCaseInsensitiveContains(searchQuery) {
            return Color.yellow.opacity(0.22)
        }
        return rowIndex == 0 ? Color.secondary.opacity(0.08) : Color.secondary.opacity(0.03)
    }
}

private struct SpreadsheetWorkbook: Decodable {
    let sheets: [SpreadsheetSheet]
}

private struct SpreadsheetSheet: Decodable, Identifiable {
    let name: String
    let rows: [SpreadsheetRow]

    var id: String { name }
}

private struct SpreadsheetRow: Decodable {
    let id: String
    let cells: [String]
    let anchorIds: [String]

    enum CodingKeys: String, CodingKey {
        case id, cells
        case anchorIds = "anchor_ids"
    }
}

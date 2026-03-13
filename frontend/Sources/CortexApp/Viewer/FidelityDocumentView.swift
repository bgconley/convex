import SwiftUI

struct FidelityDocumentView<StructuredView: View>: View {
    let originalURL: URL?
    let defaultViewMode: ViewRepresentation
    private let structuredView: StructuredView

    @State private var viewMode: ViewRepresentation

    enum ViewRepresentation: String, CaseIterable {
        case original = "Original"
        case structured = "Structured"
    }

    init(
        originalURL: URL?,
        defaultViewMode: ViewRepresentation = .original,
        @ViewBuilder structuredView: () -> StructuredView
    ) {
        self.originalURL = originalURL
        self.defaultViewMode = defaultViewMode
        self.structuredView = structuredView()
        _viewMode = State(initialValue: defaultViewMode)
    }

    var body: some View {
        Group {
            switch viewMode {
            case .original:
                if let originalURL {
                    QuickLookView(url: originalURL)
                } else {
                    fallbackView
                }
            case .structured:
                structuredView
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
                .help("Toggle Original / Structured view")
            }
        }
    }

    private var fallbackView: some View {
        ContentUnavailableView(
            "Original file unavailable",
            systemImage: "doc.badge.exclamationmark",
            description: Text("Structured view is still available.")
        )
    }
}

import SwiftUI
import Domain

struct SearchSuggestionsView: View {
    let suggestions: SearchSuggestionsResponse
    let onSelect: (SuggestionItem) -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                if !suggestions.recentSearches.isEmpty {
                    suggestionSection(title: "Recent", icon: "clock", items: suggestions.recentSearches)
                }
                if !suggestions.entities.isEmpty {
                    suggestionSection(title: "Entities", icon: "tag", items: suggestions.entities)
                }
                if !suggestions.documents.isEmpty {
                    suggestionSection(title: "Documents", icon: "doc", items: suggestions.documents)
                }
            }
        }
        .frame(maxHeight: 200)
    }

    private func suggestionSection(title: String, icon: String, items: [SuggestionItem]) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.caption2)
                Text(title)
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .foregroundStyle(.tertiary)
            .padding(.horizontal, 12)
            .padding(.vertical, 4)

            ForEach(items) { item in
                Button {
                    onSelect(item)
                } label: {
                    HStack(spacing: 8) {
                        if item.type == "entity", let entityType = item.entityType {
                            EntityChipView(name: item.label, entityType: entityType) {
                                onSelect(item)
                            }
                        } else {
                            Text(item.label)
                                .font(.subheadline)
                                .lineLimit(1)
                        }
                        Spacer()
                        Text(item.type)
                            .font(.caption2)
                            .foregroundStyle(.quaternary)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
    }
}

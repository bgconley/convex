import SwiftUI
import Domain
import AppCore

struct EntityDetailView: View {
    let entityId: UUID
    let entityService: EntityService
    var onSelectDocument: ((UUID) -> Void)?

    @State private var detail: EntityDetailResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if isLoading {
                ProgressView("Loading entity...")
            } else if let errorMessage {
                ContentUnavailableView {
                    Label("Error", systemImage: "exclamationmark.triangle")
                } description: {
                    Text(errorMessage)
                }
            } else if let detail {
                entityContent(detail)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .task(id: entityId) {
            await loadDetail()
        }
    }

    private func entityContent(_ detail: EntityDetailResponse) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header(detail.entity)

                if !detail.documents.isEmpty {
                    documentsSection(detail.documents)
                }

                if !detail.relatedEntities.isEmpty {
                    relatedSection(detail.relatedEntities)
                }
            }
            .padding(20)
        }
    }

    private func header(_ entity: Entity) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                EntityChipView(name: entity.entityType.capitalized, entityType: entity.entityType)
                Spacer()
            }
            Text(entity.name)
                .font(.title)
                .fontWeight(.semibold)
            HStack(spacing: 16) {
                Label("\(entity.mentionCount) mentions", systemImage: "text.quote")
                Label("\(entity.documentCount) documents", systemImage: "doc.on.doc")
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
    }

    private func documentsSection(_ documents: [EntityDocument]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Documents")
                .font(.headline)
            ForEach(documents) { doc in
                Button {
                    onSelectDocument?(doc.documentId)
                } label: {
                    HStack {
                        Image(systemName: "doc.text")
                            .foregroundStyle(.secondary)
                        Text(doc.title)
                            .lineLimit(1)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }
                    .padding(.vertical, 6)
                    .padding(.horizontal, 10)
                    .background(Color.gray.opacity(0.06))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func relatedSection(_ related: [RelatedEntity]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Related Entities")
                .font(.headline)
            FlowLayout(spacing: 6) {
                ForEach(related) { entity in
                    EntityChipView(name: entity.name, entityType: entity.entityType)
                }
            }
        }
    }

    private func loadDetail() async {
        isLoading = true
        errorMessage = nil
        do {
            detail = try await entityService.getDetail(id: entityId)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

/// Simple flow layout that wraps chips to the next line.
struct FlowLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrange(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrange(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(
                at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y),
                proposal: ProposedViewSize(subviews[index].sizeThatFits(.unspecified))
            )
        }
    }

    private struct ArrangeResult {
        var size: CGSize
        var positions: [CGPoint]
    }

    private func arrange(proposal: ProposedViewSize, subviews: Subviews) -> ArrangeResult {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        var totalHeight: CGFloat = 0
        var totalWidth: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > maxWidth && x > 0 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            positions.append(CGPoint(x: x, y: y))
            rowHeight = max(rowHeight, size.height)
            x += size.width + spacing
            totalWidth = max(totalWidth, x - spacing)
            totalHeight = y + rowHeight
        }

        return ArrangeResult(
            size: CGSize(width: totalWidth, height: totalHeight),
            positions: positions
        )
    }
}

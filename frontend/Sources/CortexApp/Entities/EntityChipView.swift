import SwiftUI
import Domain

struct EntityChipView: View {
    let name: String
    let entityType: String
    var action: (() -> Void)?

    var body: some View {
        Group {
            if let action {
                Button(action: action) {
                    chipLabel
                }
                .buttonStyle(.plain)
            } else {
                chipLabel
            }
        }
        .help(Text(verbatim: "\(entityType): \(name)"))
    }

    private var chipLabel: some View {
        HStack(spacing: 4) {
            Image(systemName: iconName)
                .font(.caption2)
            Text(name)
                .font(.caption)
                .lineLimit(1)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(chipColor.opacity(0.15))
        .foregroundStyle(chipColor)
        .clipShape(Capsule())
    }

    private var chipColor: Color {
        switch entityType {
        case "person": .blue
        case "organization", "company": .green
        case "technology", "software", "programming language", "software framework", "database": .purple
        case "location", "country", "city": .orange
        case "product": .teal
        case "event", "conference": .pink
        case "date": .gray
        case "medical condition", "medication", "medical procedure": .red
        case "law", "regulation", "contract term": .brown
        case "vehicle": .indigo
        default: .secondary
        }
    }

    private var iconName: String {
        switch entityType {
        case "person": "person.fill"
        case "organization", "company": "building.2.fill"
        case "technology", "software", "programming language", "software framework", "database": "cpu"
        case "location", "country", "city": "mappin"
        case "product": "shippingbox.fill"
        case "event", "conference": "calendar"
        case "date": "clock"
        case "medical condition", "medication", "medical procedure": "cross.case.fill"
        case "law", "regulation", "contract term": "book.closed.fill"
        case "vehicle": "car.fill"
        default: "tag.fill"
        }
    }
}

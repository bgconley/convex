import SwiftUI

struct PlainTextView: View {
    let content: String

    var body: some View {
        ScrollView([.horizontal, .vertical]) {
            Text(content)
                .font(.system(.body, design: .monospaced))
                .textSelection(.enabled)
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

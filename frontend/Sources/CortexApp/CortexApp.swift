import SwiftUI
import Bootstrap

@main
struct CortexApp: App {
    private let root = CompositionRoot()

    var body: some Scene {
        WindowGroup {
            ContentView(root: root)
        }
    }
}

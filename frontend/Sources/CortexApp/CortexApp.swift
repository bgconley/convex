import SwiftUI
import Bootstrap
import Domain

@main
struct CortexApp: App {
    @State private var root: CompositionRoot?
    @State private var showOnboarding = false

    var body: some Scene {
        WindowGroup {
            Group {
                if let root {
                    ContentView(root: root)
                } else {
                    ProgressView("Loading...")
                }
            }
            .sheet(isPresented: $showOnboarding) {
                OnboardingView(
                    onComplete: { url in
                        let settings = Bootstrap.Settings(backendURL: url)
                        settings.save()
                        root = CompositionRoot(settings: settings)
                        showOnboarding = false
                    },
                    onSkip: {
                        Bootstrap.Settings().save()
                        showOnboarding = false
                    }
                )
                .interactiveDismissDisabled()
            }
            .onAppear {
                if !Bootstrap.Settings.hasBeenConfigured {
                    root = CompositionRoot()
                    showOnboarding = true
                } else {
                    root = CompositionRoot()
                }
            }
        }
        .commands {
            CommandGroup(replacing: .appSettings) {
                Button("Settings...") {
                    NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                }
                .keyboardShortcut(",", modifiers: .command)
            }
        }

        SwiftUI.Settings {
            if let root {
                SettingsView(settings: root.settings, healthRepo: root.healthRepo)
            } else {
                SettingsView(settings: .load(), healthRepo: APIHealthPlaceholder())
            }
        }
    }
}

/// Placeholder health port used before the composition root is initialized.
private struct APIHealthPlaceholder: HealthPort {
    func checkHealth() async throws -> HealthStatus {
        HealthStatus(status: "unknown", checks: [:])
    }
    func fetchStats() async throws -> SystemStats {
        throw URLError(.notConnectedToInternet)
    }
}

# Frontend Launch

Use the real macOS app host for Xcode runs and debugging:

- Open [Cortex.xcodeproj](/Users/brennanconley/vibecode/convex/frontend/Cortex.xcodeproj)
- Select the `CortexMac` scheme
- Run the app from Xcode

`Package.swift` is still the source of the reusable frontend modules and test targets, but it is no longer the correct entry point for launching/debugging the app itself.

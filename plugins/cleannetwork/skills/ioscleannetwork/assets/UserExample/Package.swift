// swift-tools-version: 6.2

import Foundation
import PackageDescription

let sdkDependency: Package.Dependency
if let localPath = ProcessInfo.processInfo.environment["IOS_CLEAN_NETWORK_PATH"],
   !localPath.isEmpty {
    sdkDependency = .package(name: "ioscleannetwork", path: localPath)
} else {
    sdkDependency = .package(
        url: "https://github.com/alegelos/iOSCleanNetwork",
        from: "1.0.4"
    )
}

let package = Package(
    name: "UserExample",
    platforms: [
        .iOS(.v15),
        .macOS(.v14)
    ],
    products: [
        .library(name: "UserExample", targets: ["UserDomain", "UserData"])
    ],
    dependencies: [sdkDependency],
    targets: [
        .target(
            name: "UserDomain",
            path: "Sources/UserExample/Domain"
        ),
        .target(
            name: "UserData",
            dependencies: [
                "UserDomain",
                .product(name: "iOSCleanNetwork", package: "ioscleannetwork")
            ],
            path: "Sources/UserExample/Data"
        ),
        .testTarget(
            name: "UserExampleTests",
            dependencies: [
                "UserDomain",
                "UserData",
                .product(name: "iOSCleanNetwork", package: "ioscleannetwork"),
                .product(name: "iOSCleanNetworkTesting", package: "ioscleannetwork")
            ],
            resources: [.process("Resources")]
        )
    ]
)

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "UserExample"
include(":user-domain", ":user-data")

val sdkPath = providers.environmentVariable("ANDROID_CLEAN_NETWORK_PATH")
    .orNull
    ?.takeIf { it.isNotBlank() }
    ?: error(
        "Set ANDROID_CLEAN_NETWORK_PATH to an AndroidCleanNetwork SDK checkout, " +
            "for example: export ANDROID_CLEAN_NETWORK_PATH=/absolute/path/to/AndroidCleanNetwork. " +
            "This example uses a local composite build; no published SDK artifact is required.",
    )
val sdkDirectory = file(sdkPath)
require(
    sdkDirectory.resolve("settings.gradle.kts").isFile &&
        sdkDirectory.resolve("android-clean-network/build.gradle.kts").isFile &&
        sdkDirectory.resolve("android-clean-network-testing/build.gradle.kts").isFile,
) {
    "ANDROID_CLEAN_NETWORK_PATH must point to the AndroidCleanNetwork SDK checkout " +
        "containing both SDK modules. Received: $sdkDirectory"
}

includeBuild(sdkDirectory) {
    dependencySubstitution {
        substitute(module("com.alegelos:android-clean-network"))
            .using(project(":android-clean-network"))
        substitute(module("com.alegelos:android-clean-network-testing"))
            .using(project(":android-clean-network-testing"))
    }
}

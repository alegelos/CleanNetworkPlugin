---
name: cleannetwork
description: Choose the iOSCleanNetwork or AndroidCleanNetwork integration workflow for a consuming app or SDK. Use when setting up the CleanNetwork plugin, when the platform is unclear, or when a task spans both SDKs. Platform-specific endpoint work should use its matching bundled skill.
---

# Choose a CleanNetwork integration

Inspect the current consumer project and the requested scope before choosing a
platform. This plugin supplies instructions and examples; installing it does not
add a SwiftPM or Gradle dependency to the consumer.

1. Identify the relevant feature, language, SDK dependency and resolved version
   from its package/build files and existing providers. A repository can contain
   both platforms; an unrelated build file elsewhere is not enough to choose.
   If the task does not establish a target platform, ask that one question.
2. For Swift, read the bundled [iOS skill](../ioscleannetwork/SKILL.md), then its
   relevant guide/example. For Kotlin/Android, read the bundled
   [Android skill](../androidcleannetwork/SKILL.md). For a task that explicitly
   spans both platforms, apply each guide to its own consumer. These relative
   links resolve within the installed plugin; no SDK repository checkout is
   needed just to read them.
3. Keep the host's architecture, naming and dependency injection. Domain and Data
   describe responsibilities: they can be folders/packages in one target/module
   or separate targets/modules. Do not add modules merely to copy the example.
   Presentation belongs to the host's feature: use its Presenter, ViewModel or
   equivalent when the task needs it. An SDK without UI can expose Domain and
   implement Data without adding a presentation layer. A UI SDK may already have
   presentation; preserve it. Add only the layers and files the task needs.
4. Follow the chosen guide's actual platform contracts. Domain inputs and outputs
   remain independent of transport DTOs/responses. Preserve the consumer's
   established use cases/repositories when present instead of adding a parallel
   architecture. Request missing endpoint/authentication facts only when needed
   to implement the requested behavior.

For an installation/setup question, report the selected SDK, its resolved
version (or that it is not installed), the guide selected and how it fits the
consumer. For an implementation request, continue with that skill and the
requested code/tests; do not stop at a setup report. Do not rewrite consumer
instruction files or install an SDK dependency solely because this skill loaded.

The bundled baselines are iOS **1.0.4** and Android **1.0.1**. Compare them with the
consumer's actual dependency. The source releases, commits and file checksums
are recorded in [the source lock](../../sources.lock.json). Plugin updates and
SDK dependency updates are separate operations.

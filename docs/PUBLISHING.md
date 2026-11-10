# Directory submission

GitHub is the public distribution source. A GitHub release does not mean the
plugin has been approved or listed in OpenAI's or Anthropic's directory. Keep
portal receipts outside this repository and update the README with a listing
link only after the listing is live.

## Shared listing

| Field | Value |
| --- | --- |
| Name | CleanNetwork |
| Identifier | cleannetwork |
| Publisher handle | alegelos |
| Short description | Swift and Android SDK guides |
| Source | https://github.com/alegelos/CleanNetworkPlugin |
| Plugin folder | plugins/cleannetwork |
| Support | https://github.com/alegelos/CleanNetworkPlugin/issues |
| License | MIT |
| Components | Three skills, guides and runnable examples; no MCP servers, hooks or agents |

The manifests contain the descriptions and icon paths. The platform skills use
Swift SDK 1.0.4 and Android SDK 1.0.1 as their baselines. A plugin update does not
change a consumer's SwiftPM or Gradle dependencies.

## OpenAI

Use the [OpenAI submission portal linked from its guide](https://developers.openai.com/plugins/deploy/submission).
Select the intended organization/project and a verified individual or business
identity. The publisher displayed in the directory comes from that identity.

1. Upload the release's `cleannetwork-<version>.zip`, the plugin-root archive.
   Do not upload the marketplace or the Claude account archive.
2. Review Metadata & Skills and resolve portal validation/scanning findings.
3. Complete the publisher's policy attestations and submit for review.
4. Publish the approved version and record its directory URL.

This is a skills-only submission. It has no MCP authentication or server setup.
MCP test credentials, MCP review cases and an MCP demo video are not applicable.
The icon and listing limits are checked locally; portal scans, eligibility and
publisher verification still apply. Local validation does not establish approval.

## Anthropic

Open [the developer portal](https://claude.ai/directory/manage), choose **Submit
new → Plugin bundle**, and use:

- Repository: `alegelos/CleanNetworkPlugin`
- Plugin path: `plugins/cleannetwork`
- Branch: `main`

The account must have an eligible plan/role and a connected GitHub identity with
push access. Validate the source, review the generated listing and answer the
data-handling questions. The publisher must review the contact email and required
acknowledgements before submission. After the checks/review pass, request
publication according to the portal's current publish setting.

The plugin includes the Gradle wrapper JAR so its Android example is runnable.
It is pinned to the upstream skill's Git commit and SHA-256 inventory, and carries
its embedded license. Anthropic's checklist flags binary files for reviewer
inspection; this can cause a policy hold. Do not remove the wrapper merely to
conceal that dependency. The portal decides whether the package can be listed.

References: [submission workflow](https://claude.com/docs/plugins/submit),
[pre-submission checks](https://claude.com/docs/plugins/pre-submission-checklist).
The directory and the `claude-plugins-official` marketplace have different
submission paths; this package targets the public directory and its own GitHub
marketplace.

## Data handling facts for the publisher

- The plugin publisher operates no backend and receives no project files,
  credentials, prompts or telemetry from this package.
- The host AI application can read project files and supplied API contracts when
  executing the user's task, subject to that application's permissions and data
  policies. Do not describe the entire AI session as collecting no data.
- Installation fetches plugin files. Explicitly building an example fetches its
  public development dependencies from the sources declared in its build files.
- Fixtures contain fictional User/Item data and example.com URLs. The bundled
  tests do not contact a production API. Real integration work uses the endpoint
  contract and authentication supplied by the consuming project.
- The publisher does not retain session data. The host application's own
  retention policy is separate.
- Intended audience: developers integrating the Swift or Android SDK. This is
  not a product specifically directed at children.

These facts support the publisher's answers; they are not a substitute for
reviewing the portals' exact questions or accepting terms on the publisher's
behalf.

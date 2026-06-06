# Data Source Setup and Scope

## SharePoint

Accept SharePoint site URLs and folder/share links.

Example site URL:

```text
https://hedrickbrotherscom.sharepoint.com/sites/HilltopGardens/SitePages/ProjectHome.aspx
```

Interpret as all directories/libraries in the site, subject to policy and admin first-sync approval.

Example folder link:

```text
https://hedrickbrotherscom.sharepoint.com/:f:/s/HilltopGardens/IgDfplnmGaUIQoNWNaupmVH9AcrLxSg7g9vJ1JLTleZYan8?e=mIgEN5
```

Interpret as selected folder/directory scope only.

## Procore

Accept project homepage URLs and extract project ID.

Examples:

```text
https://app.procore.com/2982068/project/home
https://app.procore.com/2525840/project/home
https://app.procore.com/2091445/project/home
```

Extract numeric project IDs: `2982068`, `2525840`, `2091445`.

## OneDrive

Allow:

- all folders;
- selected folders;
- excluded folders.

Default should not silently sync all OneDrive folders unless the user explicitly chooses that scope.

## Outlook

Allow selected mailbox folders/lookback windows. “Project matching only” is available but not default. Default: safely index selected mailbox scope and classify/project-match relevance after ingestion.

## Calendar

Allow selected calendar/window. “Project matching only” is available but not default. Default: safely index selected calendar scope and classify/project-match relevance after ingestion.

## Scope Preview

Before first sync, show a friendly preview:

- source type;
- detected scope;
- project association;
- access validation;
- estimated size where available;
- admin first-sync requirement.

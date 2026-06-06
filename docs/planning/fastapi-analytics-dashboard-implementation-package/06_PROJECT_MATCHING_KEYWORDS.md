# Project Matching Keywords

## Rule: Do Not Use Folder Names by Default

Do not use folder names for project keyword generation. Projects use the same template folders and only deep nested unique names may occasionally be useful. Standard folder names create false positives.

Excluded by default:

- Drawings
- Specifications
- Submittals
- RFIs
- Photos
- Contracts
- Correspondence
- Change Orders
- Financials
- Meeting Minutes
- Closeout
- any standard template folder naming pattern

Deep nested folder names may only become low-confidence candidate terms requiring user confirmation.

## Allowed Keyword Signals

Use project-specific signals from:

- Procore project name, number, and ID;
- SharePoint site identity;
- project homepage metadata;
- safe document/file titles;
- redacted email subjects and thread summaries;
- calendar subjects;
- known owner/design/vendor names where project-specific;
- confirmed matches;
- user-entered aliases.

## User Controls

Users can add, edit, disable, delete, and exclude keywords. Users can mark a keyword strong/normal/weak. UI should explain why an item matched a project.

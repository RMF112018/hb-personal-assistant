# Chrome Header Page Title Addendum Package

This addendum updates the frontend UI/UX shell implementation package with one required scope correction:

- page titles must render in the chrome header;
- static `Personal Assistant` / `HB Analytics` must not be the routed-page header title;
- page bodies must not render duplicate top-level titles.

Use `prompts/ADDENDUM_CHROME_HEADER_PAGE_TITLE_PROMPT.md` as an additional local-agent prompt, ideally folded into P01/P02 before refactoring the individual pages.


## Second addendum: My Dashboard navigation model

This updated package also adds the required navigation correction:

- `My Items` must be retitled `My Dashboard`.
- `My Dashboard` must be the first item in the primary nav.
- The `Today` view must be nested under `My Dashboard`.
- `Today` remains the primary landing view.
- Existing deep links should be preserved with redirects where practical.

Use `prompts/ADDENDUM_MY_DASHBOARD_NAVIGATION_PROMPT.md` with the chrome-header title prompt. Prefer implementing both together because route-title metadata, active-nav state, breadcrumbs/subtitles, and body-title removal are coupled.

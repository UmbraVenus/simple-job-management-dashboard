# Job Management Dashboard mockup


## You  <sub>2026-10-11 22:38</sub>

@"/Users/REDACTED_USER/Downloads/Job Management Dashboard.pdf"
dont do any code changes, there is no code changes needed, for now, lok at phase 5, frontend design, can you create me a mock up first


## Claude  <sub>2026-10-11 22:38</sub>

> *Tool:* `mcp__visualize__read_me`
> *Tool:* `mcp__visualize__show_widget`

The mockup is above and no project files were touched. Use the state buttons along the top to jump to each Phase 5 state. The page is also live: you can create, change status, delete, and page through the sample data.

Where the mockup differs from the real page:
- **Page size:** it shows 5 rows per page so it fits in chat; the real page is 20.
- **Styling:** it uses the chat's own colours and fonts so it reads in light and dark mode. Layout and components follow AntD, but the exact blue and spacing will differ.
- **Loading:** it shows skeleton rows. AntD's default `Table loading` is a spinner over the previous rows instead.
- **Extra state:** I added "Duplicate name" (the 409) beside "Name required", since both show on the name field.

Decisions for you before sign-off:
1. **Status control:** I drew a native `<select>` per row. It is the simplest for Playwright's `selectOption` and for screen readers, but it will look slightly off next to AntD buttons. The alternative is AntD `Select` (consistent look, but fiddlier in E2E tests).
2. **Created column:** I left it out to keep the table at Name, Status, Actions. Adding it costs nothing on the API side, since `created_at` is already returned.
3. **Status change feedback:** every create, status change and delete shows a toast. Say if you'd rather the status change be silent, since the tag already updates.
4. **Error copy:** the wording is "Enter a job name", "Job names can be up to 255 characters", "That name's already taken. Try another." and "Couldn't load jobs. Check your connection and try again." These become the Phase 6 JSON file keyed by error `code`, so change them now if you want different text.

Tell me what to change and I'll revise the mockup.

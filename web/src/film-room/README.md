# Film Room posts

Each `.md` file in `posts/` is one post on the site's **Film Room** page
(`/film-room`). The file name, without `.md`, is the post's address:
`posts/2026-11-12-why-timeouts-didnt-matter.md` → `/film-room/2026-11-12-why-timeouts-didnt-matter`.

Start every post with this block:

```markdown
---
title: Why timeouts didn't matter
date: 2026-11-12
summary: One or two sentences for the list page.
draft: true
---
```

* `draft: true`: shows when you run the site locally (`make web`), marked as a draft;
  never on the deployed site. Set it to `false` to publish.
* Write the rest in Markdown: `## headings`, **bold**, lists, links, tables, `code`.
  Raw HTML is ignored, on purpose.
* Images: put them in `web/public/film-room/` and write `![What it shows](/film-room/name.png)`.
  `docs/evidence/charts/` has charts you can copy over.
* Publishing: commit and push; Render rebuilds the site.

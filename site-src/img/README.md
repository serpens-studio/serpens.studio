Image assets. Everything here is copied to `dist/img/` and served with a 30-day
cache. Markdown and dotfiles are skipped.

Expected filenames:

| file            | content                                     |
|-----------------|---------------------------------------------|
| `econ-site.jpg` | econwindows.com homepage screenshot         |
| `econ-job.jpg`  | install photo, arched windows, Cave Creek   |

~1600px wide, progressive JPEG, under ~250 KB. `main.js` swaps in a labelled
placeholder for any file that 404s, so a missing image won't break the layout.

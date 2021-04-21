# aws-orbit-workbench
Tying up all components around to deliver a solid and integrated data environment powered by AWS services.

### This branch hosts [Orbit GitHub Pages](https://awslabs.github.io/aws-orbit-workbench/)

### To modify the landing page
edit [index.markdown](./index.markdown)

### To add a blog post
- Add the post as a markdown file in `_posts` folder. 
- Follow required name convetion:
`YYYY-MM-DD-title.markdown`
- Include necessary front matter:
```markdown
---
layout: post
---
```

### To add a tutorial page
- Add the page as a markdown file in `tutorials` folder
- Include necessary front matter:
```markdown
---
layout: tutorial
title: your title
permalink: your-link
---
```
- Add page title and url to `navigation.yml` file under `_data` folder
- Add new entry to proper group, or create a new group if necessary

### To add a page to top menu bar
- Add the page as a markdown file in root folder
- Include necessary front matter:
```markdown
---
layout: default
title: about
---
```
layout and title are must-have.

### check [here](https://awslabs.github.io/aws-orbit-workbench/examples) for Markdown examples

---
name: fetch-snowplow-docs
description: Fetches current Snowplow tracker documentation via the docs sitemap. Use whenever you need accurate, up-to-date tracker API examples — initialisation, tracking calls, plugins — for any platform (web, iOS, Android, server-side). Do not rely on built-in knowledge; tracker APIs change with each release.
---

# Fetch Snowplow Documentation

Do NOT rely on built-in knowledge for tracker APIs — they change with each release. Instead:

1. Use `WebFetch` to fetch `https://docs.snowplow.io/llms.txt` to get the Snowplow documentation sitemap
2. Find the relevant tracker documentation page(s) for the user's platform
3. Extract the path from the URL and use `WebFetch` to fetch those pages and get accurate, up-to-date initialisation and tracking call examples

## Platforms to Look For in llms.txt

- **Web**: JavaScript / Browser tracker
- **iOS**: Swift / iOS tracker
- **Android**: Kotlin / Android tracker
- **Server-side**: Node.js tracker, Python tracker, Go tracker, Java tracker, .NET tracker

Always fetch the docs rather than generating tracker code from memory.

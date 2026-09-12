---
name: install-snowplow-tracking
description: "Install and configure Snowplow tracking from scratch in web, iOS, Android, or server-side (Node, Python, Java, other backend) applications — tracker initialisation, out-of-the-box event tracking, user identification, and stitching server-side events to the client session. Use when an application has no Snowplow tracker yet. For guidance on individual tracking calls in an already-instrumented app, the official snowplow plugin's implementation-guidance skill also applies. Triggers: install Snowplow, add tracker, tracker setup, initialise tracker, out-of-the-box events, server-side tracking, backend tracking, Node tracker, Python tracker, Java tracker."
---

# Install Snowplow Tracking

Install and configure Snowplow tracking with out-of-the-box events, user identification, and local testing setup. Client-side (web, iOS, Android) and server-side (Node, Python, Java, or any other Snowplow server tracker) take different branches through the steps below — the branch is chosen in step 2.1.

## When To Use This Skill

Use this skill when:

- Installing Snowplow tracking in a new application from scratch
- Setting up out-of-the-box event tracking (page views, clicks, forms, etc.)
- Configuring user identification
- Adding server-side tracking to a backend service that has no tracker yet, including stitching its events to the browser session that triggered them
- Need to set up local testing environment (Micro) alongside implementation

Don't use this skill when:

- Application already has Snowplow tracking installed (use the official snowplow plugin's implementation-guidance skill instead)
- Only need to add custom events to existing tracking (use `implement-custom-events`, or the official snowplow plugin's implementation-guidance skill)
- Need to troubleshoot existing tracking implementation (use the official snowplow plugin's troubleshooting skill instead)

## Prerequisites

- Application codebase is accessible for scanning and modification
- User has decided to implement Snowplow tracking
- Package manager available (npm/yarn for JavaScript and Node, CocoaPods/SPM for iOS, Gradle for Android, pip/Poetry for Python, Gradle/Maven for Java), or a plain-HTML site that loads `sp.js` via a tag
- Docker installed (for Micro setup)

## Instructions

### 1. Gather Configuration Requirements

Ask the user for required configuration:

**1.1 Collector Selection**

Ask: "Which Snowplow collector endpoint would you like to use?"

Options:
- Start with Micro for local testing (recommended for new implementations)
- Use an existing DEV pipeline collector
- Use an existing PROD pipeline collector

If they're unsure, recommend starting with Micro for local testing, then moving to DEV, then PROD.

**1.2 Application ID**

Ask: "What application_id value would you like to use?"

This identifies the application in your Snowplow data. Recommend format: `com.company.app-name` or `app-name-platform` (e.g., `my-app-web`, `my-app-ios`, `my-app-api`).

### 2. Detect Platform and Fetch Documentation

**2.1 Scan Codebase**

Examine the codebase to determine the platform:
- **JavaScript/Web**: Look for package.json, React/Vue/Angular files, HTML
- **iOS**: Look for .swift files, Podfile, Package.swift, Xcode project
- **Android**: Look for .kt/.java files, build.gradle, AndroidManifest.xml
- **Server-side**: a tracker-bearing manifest — `package.json` (Node), `requirements.txt`/`pyproject.toml` (Python), `build.gradle`/`pom.xml` (Java) — and **no UI**: no HTML served to a browser, no front-end framework or bundler, no mobile project files. `package.json` alone is ambiguous: Express/Fastify/Koa/NestJS with no front-end build is server-side; a bundler and components is web; both together (Next.js, Remix, SvelteKit) is web here, with the server tracker installed as a second pass through the server-side branch.

**Server-side branch.** Read `reference/server-side-gotchas.md` now, before fetching docs — it holds the failure modes the docs undercover and the checklist for trackers this skill has no per-language content for. On this branch step 3 is skipped (server trackers have no out-of-the-box events) and step 4 is replaced by step 4S.

**2.2 Fetch Current Tracker Documentation**

Do NOT use built-in knowledge for tracker APIs — they change with each release. Call the `fetch-snowplow-docs` skill to fetch current docs. See **Tracker Reference** section below for the exact workflow.

**2.3 Server trackers other than Node, Python or Java**

If the user asks for any other server tracker (Go, .NET, Ruby, PHP, Scala, Rust, Lua, Unity, C++), refer to the Snowplow docs site via `fetch-snowplow-docs` and, where the docs are thin, the tracker's source code — every Snowplow tracker is open source on GitHub under the `snowplow` organisation — to understand that tracker's specific behaviour. Check the tracker's maintenance badge (Actively Maintained / Maintained / Early Release / Unsupported) and tell the user what it means before installing. Then verify that tracker against the cross-tracker checklist in `reference/server-side-gotchas.md#any-other-server-tracker` (buffering and flush, retry codes, buffer capacity, identity scope, default platform) and continue with steps 4S–7.

### 3. Configure Out-of-the-Box Events

**Client-side only.** Server trackers have no out-of-the-box events or plugins — on the server-side branch go straight to step 4S.

Ask the user which OOTB events they want to track. Present platform-specific options:

**For Web/JavaScript:**
- Page views (trackPageView)
- Page activity/engagement (enableActivityTracking)
- Link clicks (LinkClickTrackingPlugin)
- Button clicks (ButtonClickTrackingPlugin)
- Form tracking (FormTrackingPlugin)

**For iOS:**
- Screen views (trackScreenView)
- Lifecycle events (LifecycleAutotracking)
- Screen context (ScreenContextPlugin)
- Deep link received events

**For Android:**
- Screen views (trackScreenView)
- Lifecycle events (LifecycleAutotracking)
- Screen context (ScreenContextPlugin)
- Install tracking

Recommend enabling the most common ones by default (page/screen views, activity tracking, clicks for web).

### 4. Configure User Identification (client-side)

Ask: "Do you want to configure user identification?"

Explain:
- Snowplow automatically tracks `domain_userid` (client cookie) and `network_userid` (server cookie)
- They can optionally set a `user_id` with their own identifier (e.g., from login system)
- This requires calling `setUserId()` when the user identifier becomes available

If yes, include `setUserId()` configuration in the implementation with a comment explaining when to call it.

### 4S. Stitch Server-Side Events to the Client Session (server-side)

The common production pattern: the user's browser sends a request to the backend (a purchase POST, a form submit, an API call) and the backend tracks a Snowplow event about it. That request already carries the client-side values the server event needs. The tracker must **set them from the incoming request** — otherwise the server event describes the server, not the user, and never joins the client-side events for the same session.

Per request, set on the tracker (Node) or on a per-event Subject (Python, Java):

- **`domain_userid`, `domain_sessionid`, `domain_sessionidx`** — read from the JavaScript tracker's first-party `_sp_id.*` cookie on the request (or from values the client sends explicitly in the body or a header) and set via the tracker's domain-user-id / session-id / session-index setters.
- **`network_userid`** — read from the collector's `sp` cookie on the request when the collector and site share a domain; otherwise set it explicitly from a value the client sends. Unset, the collector issues a fresh cookie to every server request and each server event gets a different `network_userid`.
- **`user_ipaddress`** and **`useragent`** — from the request: `X-Forwarded-For` / `X-Real-IP` behind a proxy or load balancer, otherwise the socket address; the `User-Agent` header. The defaults are the server's own IP and HTTP-client UA, which poison the IP-lookup, YAUAA and UA-parser enrichments.
- **`user_id`** — from the authenticated session on the request (session store, JWT claim), never from a tracker-level default.

Find the request-handling layer (Express/Fastify middleware or route handler, Django/Flask request object, Spring `HttpServletRequest`) and wire these there, per request. In Node the identity setters are tracker-global: set the fields and call `track()` in the same synchronous block, with no `await` between them (`reference/server-side-gotchas.md#cross-tracker`, "Identity is per request").

Confirm with the user which of these values the request already carries. If it carries none — a backend called by another service, a cron job, a queue consumer — the event cannot be stitched to a browser session; say so, set what is genuinely known (`user_id`, the caller's IP), and leave the rest unset. The cookie's field layout and the exact setter names come from the fetched docs, never from memory.

### 5. Implement Tracker Initialization

**5.1 Determine Implementation Location**

Scan the codebase to find the best location:
- **Web/JavaScript**: App entry point (index.js, App.js, _app.js for Next.js)
- **iOS**: AppDelegate.swift or main App struct
- **Android**: Application class or MainActivity
- **Server-side**: one tracker instance created in a module loaded at process start (alongside the database client or logger), imported by the request handlers; the per-request identity wiring from step 4S lives in the handler or a middleware, not in the bootstrap module.

**5.2 Generate Implementation Code**

Using the fetched documentation, generate complete implementation code including:

1. **Package installation / tracker loading**
   - **JavaScript with a bundler** (`package.json` present): install `@snowplow/browser-tracker` via npm/yarn.
   - **JavaScript on a plain-HTML site** (no bundler): ask once how the tracker should load, and let the user decide — **CDN** (zero maintenance, but blockable and a third-party request) or **self-hosted** (first-party and ad-blocker resilient, but you vendor an ~84KB `sp.js` into the repo and own updating it on every tracker release). Both are valid; the trade-off is theirs to make, so surface it rather than picking for them.
   - CocoaPods/SPM for iOS
   - Gradle dependency for Android
   - **Node**: `@snowplow/node-tracker` via npm/yarn — check `node --version` is 18 or later first (v4 uses native `fetch`).
   - **Python**: `snowplow-tracker` via pip/Poetry — tell the user it is badged Early Release and not supported by Snowtype.
   - **Java**: `snowplow-java-tracker` via Gradle/Maven **plus** an HTTP-client capability (OkHttp or Apache) — the core artifact alone has no HTTP client.

2. **Import statements**
   - Base tracker package
   - Any plugins needed for OOTB events

3. **Tracker initialization**
   - Namespace/tracker ID
   - Collector endpoint (from step 1.1)
   - Application ID (from step 1.2)
   - Configuration options based on choices in steps 3-4 (client-side)
   - **Server-side:** an asynchronous emitter (Python's default emitter blocks the request thread); `platform` set to `srv` explicitly (Python defaults to `pc`); and a decided **flush point** — long-running server: flush and close on the shutdown signal; per-request, cron or serverless: flush before returning. `reference/server-side-gotchas.md#cross-tracker`, "Buffered emitters".

4. **OOTB event configuration** (client-side)
   - Enable selected tracking features
   - Include any required plugin initialization

5. **Comments explaining**
   - When to call setUserId (if configured)
   - How to update collector endpoint for DEV/PROD
   - Any platform-specific notes from the docs
   - **Server-side:** where the identity fields come from and where the flush happens

**5.3 Insert Code**

Write the implementation to the appropriate file location identified in 5.1.

### 6. Setup Local Testing Environment

The implementation is now complete. Next, set up a local testing environment using Snowplow Micro.

Call the `setup-micro` skill to:
- Install and configure Micro using Docker
- Mount any custom schemas if needed
- Configure Micro to validate events

The user will need Micro running to test the implementation in the next step.

### 7. Test and Validate Implementation

Once Micro is set up, call the `validate-snowplow-implementation` skill to:
- Verify the tracker is sending events
- Check events are valid (appearing in /good endpoint)
- Identify any validation errors (events in /bad endpoint)
- Provide feedback on common issues

**Server-side:** exercise the backend with a request that carries the client values (a browser session against the real front end, or a `curl` with the `_sp_id.*` and `sp` cookies, a browser `User-Agent` and an `X-Forwarded-For`). In `/good`, the event's `domain_userid`, `domain_sessionid`, `network_userid`, `user_id`, `user_ipaddress` and `useragent` must equal the client's values and `platform` must be `srv`. The server's own IP or UA, or identifiers that change on every event, mean step 4S is not wired. Nothing in `/good` at all after the process exited means the emitter was never flushed.

## Tracker Reference

Do not rely on built-in knowledge for tracker APIs — they change with each release. Call the `fetch-snowplow-docs` skill to fetch current documentation. This applies to:
- Tracker initialisation options (step 5.2)
- OOTB event configuration and plugin setup (step 3)
- `setUserId` and user identification API (step 4)
- Subject / identity setters, emitter and flush configuration for server trackers (steps 4S, 5.2) — `reference/server-side-gotchas.md` ends with the pages to fetch

## Platform-Specific Notes

**Web/JavaScript:**
- Some OOTB events require installing additional plugins
- Activity tracking must be enabled before trackPageView
- Form tracking excludes password fields by default

**iOS:**
- Tracker must be initialized before application finishes launching
- Screen view tracking can be automatic with ScreenContextPlugin
- Consider using TrackerConfiguration for centralized settings

**Android:**
- Tracker initialization should happen in Application class
- Screen view tracking can be automatic with ScreenContextPlugin
- Lifecycle events require ProcessLifecycleOwner dependency

**Server-side (Node, Python, Java, others):**
- Everything is in `reference/server-side-gotchas.md`, read at step 2.1 — cross-tracker failure modes first, then one section per tracker, then the checklist for any other tracker

## Common Issues

- **Collector endpoint unreachable**: Ensure Micro is running (step 7) or DEV/PROD endpoint is accessible
- **Events not appearing**: Check network requests in browser/device debugger
- **Events from a script, job or serverless function never appear**: the emitter buffer was not flushed before the process returned (`reference/server-side-gotchas.md#cross-tracker`)
- **Server-side events don't join the client's sessions**: identifiers were not set from the incoming request, or were set on the tracker in a different request (step 4S)
- **TypeScript errors**: May need to install @types packages for JavaScript tracker
- **Build errors**: Verify package versions are compatible with project dependencies

For detailed troubleshooting after implementation, use the official snowplow plugin's troubleshooting skill or the validate-snowplow-implementation skill.

## Reference Documentation

- `reference/server-side-gotchas.md` — sourced failure modes for the Node, Python and Java trackers, the checklist for any other server tracker, and the docs pages to fetch live. Read before writing any server-side tracker code.

## Limits and Next Steps

This skill sets up basic Snowplow tracking with OOTB events. After installation:

- **For custom events/entities**: Use `implement-custom-events`, or the official snowplow plugin's implementation-guidance skill, to add self-describing events with your schemas
- **For typed tracking code** (Node and Java server trackers included; Python is unsupported): use the `setup-snowtype` skill
- **For schema design**: Use the design-tracking-plan skill to design and publish data structures
- **For production deployment**: Update collector endpoint to DEV, validate, then update to PROD endpoint
- **For advanced configuration**: Consult the fetched tracker documentation for platform-specific features (session configuration, global contexts, etc.)

This skill does not cover:
- Creating or deploying schemas (use design-tracking-plan skill)
- Advanced tracker configuration beyond OOTB events
- Custom emitters or anonymous tracking on server trackers
- Troubleshooting complex tracking issues (use the official snowplow plugin's troubleshooting skill)

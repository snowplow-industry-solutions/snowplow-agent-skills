---
name: install-snowplow-tracking
description: Install and configure Snowplow tracking in web, iOS, or Android applications with out-of-the-box event tracking and user identification. Use when a developer needs to instrument Snowplow tracking from scratch in their application.
---

# Install Snowplow Tracking

Install and configure Snowplow tracking with out-of-the-box events, user identification, and local testing setup.

## When To Use This Skill

Use this skill when:

- Installing Snowplow tracking in a new application from scratch
- Setting up out-of-the-box event tracking (page views, clicks, forms, etc.)
- Configuring user identification
- Need to set up local testing environment (Micro) alongside implementation

Don't use this skill when:

- Application already has Snowplow tracking installed (use implementation-guidance instead)
- Only need to add custom events to existing tracking (use implementation-guidance instead)
- Need to troubleshoot existing tracking implementation (use troubleshooting skill instead)

## Prerequisites

- Application codebase is accessible for scanning and modification
- User has decided to implement Snowplow tracking
- Package manager available (npm/yarn for JavaScript, CocoaPods/SPM for iOS, Gradle for Android)
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

This identifies the application in your Snowplow data. Recommend format: `com.company.app-name` or `app-name-platform` (e.g., `my-app-web`, `my-app-ios`).

### 2. Detect Platform and Fetch Documentation

**2.1 Scan Codebase**

Examine the codebase to determine the platform:
- **JavaScript/Web**: Look for package.json, React/Vue/Angular files, HTML
- **iOS**: Look for .swift files, Podfile, Package.swift, Xcode project
- **Android**: Look for .kt/.java files, build.gradle, AndroidManifest.xml

**2.2 Fetch Current Tracker Documentation**

Do NOT use built-in knowledge for tracker APIs — they change with each release. Call the `fetch-snowplow-docs` skill to fetch current docs. See **Tracker Reference** section below for the exact workflow.

### 3. Configure Out-of-the-Box Events

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

### 4. Configure User Identification

Ask: "Do you want to configure user identification?"

Explain:
- Snowplow automatically tracks `domain_userid` (client cookie) and `network_userid` (server cookie)
- They can optionally set a `user_id` with their own identifier (e.g., from login system)
- This requires calling `setUserId()` when the user identifier becomes available

If yes, include `setUserId()` configuration in the implementation with a comment explaining when to call it.

### 5. Implement Tracker Initialization

**5.1 Determine Implementation Location**

Scan the codebase to find the best location:
- **Web/JavaScript**: App entry point (index.js, App.js, _app.js for Next.js)
- **iOS**: AppDelegate.swift or main App struct
- **Android**: Application class or MainActivity

**5.2 Generate Implementation Code**

Using the fetched documentation, generate complete implementation code including:

1. **Package installation command**
   - npm/yarn for JavaScript
   - CocoaPods/SPM for iOS
   - Gradle dependency for Android

2. **Import statements**
   - Base tracker package
   - Any plugins needed for OOTB events

3. **Tracker initialization**
   - Namespace/tracker ID
   - Collector endpoint (from step 1.1)
   - Application ID (from step 1.2)
   - Configuration options based on choices in steps 3-4

4. **OOTB event configuration**
   - Enable selected tracking features
   - Include any required plugin initialization

5. **Comments explaining**
   - When to call setUserId (if configured)
   - How to update collector endpoint for DEV/PROD
   - Any platform-specific notes from the docs

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

## Tracker Reference

Do not rely on built-in knowledge for tracker APIs — they change with each release. Call the `fetch-snowplow-docs` skill to fetch current documentation. This applies to:
- Tracker initialisation options (step 5.2)
- OOTB event configuration and plugin setup (step 3)
- `setUserId` and user identification API (step 4)

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

## Common Issues

- **Collector endpoint unreachable**: Ensure Micro is running (step 7) or DEV/PROD endpoint is accessible
- **Events not appearing**: Check network requests in browser/device debugger
- **TypeScript errors**: May need to install @types packages for JavaScript tracker
- **Build errors**: Verify package versions are compatible with project dependencies

For detailed troubleshooting after implementation, use the troubleshooting skill or validate-snowplow-implementation skill.

## Limits and Next Steps

This skill sets up basic Snowplow tracking with OOTB events. After installation:

- **For custom events/entities**: Use the implementation-guidance skill to add self-describing events with your schemas
- **For schema design**: Use the tracking-design skill to design and publish data structures
- **For production deployment**: Update collector endpoint to DEV, validate, then update to PROD endpoint
- **For advanced configuration**: Consult the fetched tracker documentation for platform-specific features (session configuration, global contexts, etc.)

This skill does not cover:
- Creating or deploying schemas (use tracking-design skill)
- Advanced tracker configuration beyond OOTB events
- Server-side tracking (Node.js, Python, etc.) - use implementation-guidance skill
- Troubleshooting complex tracking issues (use troubleshooting skill)

# Implementation Issues Troubleshooting

Common Snowplow tracker implementation problems and how to diagnose and fix them.

## Issue: Events Not Reaching Micro

**Symptoms:**
- Both /micro/good and /micro/bad return empty arrays
- No network requests visible in debugger
- Tracker appears to initialize but sends nothing

**Diagnosis:**

1. **Check tracker initialization**
   - Verify tracker is initialized before tracking calls
   - Ensure initialization completes (async operations)

2. **Check collector endpoint configuration**
   - Verify endpoint points to Micro (e.g., `http://localhost:9090`)
   - Ensure no typos in URL
   - Check port number matches Micro configuration

3. **Check network connectivity**
   - Ensure Micro is running: `docker ps | grep micro`
   - Verify port is accessible from application
   - Check firewall/security settings

**Fixes:**

**Web/JavaScript:**
```javascript
// Wrong: missing protocol
newTracker('sp', 'localhost:9090', { appId: 'my-app' });

// Correct: include http://
newTracker('sp', 'http://localhost:9090', { appId: 'my-app' });
```

**iOS:**
```swift
// Wrong: HTTPS for local Micro
let networkConfig = NetworkConfiguration(
    endpoint: "https://localhost:9090"
)

// Correct: HTTP for local Micro
let networkConfig = NetworkConfiguration(
    endpoint: "http://localhost:9090"
)
```

**Android:**
```kotlin
// Wrong: missing scheme
val networkConfig = NetworkConfiguration(
    endpoint = "localhost:9090"
)

// Correct: include http://
val networkConfig = NetworkConfiguration(
    endpoint = "http://localhost:9090"
)
```

## Issue: Tracker Not Initialized

**Symptoms:**
- Tracking calls fail silently
- Console errors: "Tracker not found" or "undefined tracker"
- Events don't appear in Micro

**Diagnosis:**

1. **Check initialization order**
   - Ensure tracker initialization happens before tracking calls
   - For web, check initialization runs before app renders

2. **Check namespace/ID**
   - Verify namespace used in initialization matches tracking calls
   - Ensure tracker ID is unique

**Fixes:**

**Web/JavaScript:**
```javascript
// Wrong: tracking call before initialization
trackPageView();
newTracker('sp', 'http://localhost:9090', { appId: 'my-app' });

// Correct: initialize first
newTracker('sp', 'http://localhost:9090', { appId: 'my-app' });
trackPageView();
```

**iOS:**
```swift
// Wrong: tracking before tracker is created
Snowplow.defaultTracker()?.track(ScreenView(name: "Home"))

// Correct: create tracker first
let tracker = Snowplow.createTracker(...)
tracker.track(ScreenView(name: "Home"))
```

## Issue: OOTB Events Not Working

**Symptoms:**
- Manual tracking calls work, but auto-tracking doesn't
- Page views work, but clicks/forms don't track
- Some OOTB events missing in Micro

**Diagnosis:**

1. **Check plugin installation**
   - Verify required plugins are installed (web only)
   - Check plugin initialization happens before enablement

2. **Check plugin enablement**
   - Ensure plugin-specific enable methods are called
   - Verify enablement happens after tracker initialization

3. **Check configuration order**
   - Some features must be enabled before trackPageView (e.g., activity tracking)

**Fixes:**

**Web/JavaScript - Link Click Tracking:**
```javascript
// Wrong: plugin not installed
import { newTracker, enableLinkClickTracking } from '@snowplow/browser-tracker';
newTracker('sp', endpoint, { appId: 'my-app' });
enableLinkClickTracking(); // Fails: plugin not loaded

// Correct: install and load plugin
import { newTracker, enableLinkClickTracking } from '@snowplow/browser-tracker';
import { LinkClickTrackingPlugin } from '@snowplow/browser-plugin-link-click-tracking';

newTracker('sp', endpoint, {
  appId: 'my-app',
  plugins: [LinkClickTrackingPlugin()]
});
enableLinkClickTracking(); // Works: plugin loaded
```

**Web/JavaScript - Activity Tracking:**
```javascript
// Wrong: order matters
trackPageView();
enableActivityTracking({ minimumVisitLength: 10, heartbeatDelay: 10 });

// Correct: enable before trackPageView
enableActivityTracking({ minimumVisitLength: 10, heartbeatDelay: 10 });
trackPageView();
```

## Issue: Context Entities Not Attached

**Symptoms:**
- Event validates in Micro but context is missing
- Expected context entities don't appear in event payload

**Diagnosis:**

1. **Check context attachment**
   - Verify contexts parameter is provided
   - Ensure context is properly formatted

2. **Check global contexts**
   - Verify global contexts are registered before events are sent

**Fixes:**

**Web/JavaScript:**
```javascript
// Wrong: context not attached
trackSelfDescribingEvent({
  schema: 'iglu:com.example/button_click/jsonschema/1-0-0',
  data: { label: 'Sign Up' }
});

// Correct: attach context
trackSelfDescribingEvent({
  schema: 'iglu:com.example/button_click/jsonschema/1-0-0',
  data: { label: 'Sign Up' },
  context: [
    {
      schema: 'iglu:com.example/user_context/jsonschema/1-0-0',
      data: { user_tier: 'premium' }
    }
  ]
});
```

**iOS:**
```swift
// Wrong: entity not attached
let event = SelfDescribing(
    schema: "iglu:com.example/button_click/jsonschema/1-0-0",
    payload: ["label": "Sign Up"]
)
tracker.track(event)

// Correct: attach entity
let entity = SelfDescribingJson(
    schema: "iglu:com.example/user_context/jsonschema/1-0-0",
    andData: ["user_tier": "premium"]
)
let event = SelfDescribing(
    schema: "iglu:com.example/button_click/jsonschema/1-0-0",
    payload: ["label": "Sign Up"]
)
event.entities.append(entity)
tracker.track(event)
```

## Issue: Build/Compilation Errors

**Symptoms:**
- TypeScript errors for tracker methods
- Import errors for plugins
- Version compatibility issues

**Diagnosis:**

1. **Check package versions**
   - Verify tracker version compatibility
   - Check plugin versions match tracker version

2. **Check imports**
   - Ensure correct import paths
   - Verify package is installed

**Fixes:**

**Web/JavaScript - TypeScript:**
```bash
# Install type definitions
npm install --save-dev @types/snowplow-tracker
```

**Web/JavaScript - Version Mismatch:**
```bash
# Check installed versions
npm list @snowplow/browser-tracker
npm list @snowplow/browser-plugin-*

# Update to matching versions
npm install @snowplow/browser-tracker@latest
npm install @snowplow/browser-plugin-link-click-tracking@latest
```

## Issue: Platform-Specific Problems

### iOS: App Transport Security

**Symptom:** Network requests to Micro fail with ATS error

**Fix:** Add exception for localhost in Info.plist:
```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
</dict>
```

### Android: Network on Main Thread

**Symptom:** Events don't send, crash on tracking call

**Fix:** Ensure tracker uses background threads (default behavior). If custom executor, verify it's not main thread.

### Web: CORS Issues

**Symptom:** Browser console shows CORS error when sending to Micro

**Fix:** Micro allows all origins by default. Check browser console for actual error. May need to configure Micro's CORS settings in docker-compose.yml.

## Debugging Tools

### Browser DevTools (Web)

1. Open browser DevTools (F12)
2. Go to Network tab
3. Trigger tracking event
4. Look for request to collector endpoint
5. Check request payload and response

### iOS Debugger

Enable tracker logging:
```swift
let trackerConfig = TrackerConfiguration()
    .logLevel(.verbose)
```

### Android Debugger

Enable tracker logging:
```kotlin
val trackerConfig = TrackerConfiguration("my-app")
    .logLevel(LogLevel.VERBOSE)
```

## Getting Help

If issues persist:
1. Check validation errors in Micro /bad endpoint
2. Review tracker documentation for platform-specific details
3. Verify schemas are deployed to DEV
4. Test with simple events first (page view, screen view)
5. Check implementation code against fetched documentation examples

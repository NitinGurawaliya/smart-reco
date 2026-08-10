Build a complete production-ready React + TypeScript + Vite single-page app called **SmartReco** — an agentic free-alternative recommender for a hackathon demo.

CRITICAL: This frontend must plug into an EXISTING FastAPI backend with ZERO invented endpoints and ZERO renamed fields. Match the API contract below exactly. Do not add auth providers, GraphQL, Supabase, Firebase, or fake recommendation generators. All AI recommendations come from the backend.

============================================================
STACK & PROJECT SHAPE
============================================================
- React 18+ with TypeScript
- Vite
- React Router v6
- Plain CSS modules or a single global CSS file with CSS variables (no Tailwind unless already default; prefer clean custom CSS)
- fetch API only (no axios required)
- Env var: `import.meta.env.VITE_API_URL` defaulting to `http://localhost:8000`
- Output a full runnable Vite app structure:
  src/
    api/client.ts
    api/auth.ts
    api/events.ts
    api/recommendations.ts
    api/catalog.ts
    lib/authStorage.ts
    lib/eventTracker.ts
    data/mockCourses.ts
    types/api.ts
    components/...
    pages/...
    App.tsx
    main.tsx
    styles.css
  .env.example with VITE_API_URL=http://localhost:8000

============================================================
PRODUCT CONCEPT (MUST REFLECT IN UX COPY)
============================================================
SmartReco watches how a user browses paid Udemy-style courses (behavioral SIGNAL only) and recommends FREE resources from an admin-managed catalog (YouTube/docs).
- Udemy courses are NEVER products in the database and NEVER recommended.
- Free catalog resources are the ONLY recommendable items.
- Recommendations are cached on the backend; page load must NOT pretend to call an LLM.
- Show this mental model lightly in the dashboard copy.

============================================================
VISUAL DESIGN DIRECTION
============================================================
Brand: SmartReco
Look: crisp edtech marketplace — deep ink navy (#0B1F33), warm paper background (#F7F4EF), electric teal accent (#0F8B8D), charcoal text (#1A1A1A). Avoid purple gradients, avoid cream+terracotta serif cliché, avoid dark-neon glow, avoid emoji spam, avoid generic Inter-only look.
Typography: distinctive pairing — e.g. "Fraunces" or "Newsreader" for brand/display + "Source Sans 3" or "IBM Plex Sans" for UI (Google Fonts).
Layout: one clear composition per viewport; brand name is hero-level on marketing/login; no card-heavy dashboard clutter; course browse can use simple list/grid without nested shadow stacks.
Motion: subtle page fade + course hover lift + recommendation appear transition (2–3 intentional motions only).
Responsive: desktop + mobile.

============================================================
AUTH & APP SHELL
============================================================
Roles: `user` | `admin`
Store in localStorage:
- `smartreco_token` = access_token string
- `smartreco_user` = JSON user object `{id,email,role,created_at}`

Routes:
- `/` public landing (brand SmartReco, 1 headline, 1 sentence, CTA Login + Sign up). No stats strip.
- `/login`
- `/signup`
- `/app` protected user home/dashboard
- `/browse` protected Udemy-style course marketplace (signal surface)
- `/browse/:courseId` course detail
- `/admin` admin-only free catalog manager
- Redirect unauthenticated users to `/login`
- If role !== admin, hide Admin nav and block `/admin`

Top nav (authenticated): SmartReco | Browse | Dashboard | Admin(if admin) | email + Logout

============================================================
EXACT BACKEND API CONTRACT (DO NOT CHANGE)
============================================================
Base URL: `${VITE_API_URL}`
All JSON.
Auth header on protected routes:
  Authorization: Bearer <access_token>

--- AUTH ---
POST /auth/signup
Body: { "email": string, "password": string }  // password min 6
201 Response:
{
  "access_token": string,
  "token_type": "bearer",
  "user": { "id": number, "email": string, "role": "user"|"admin", "created_at": string }
}

POST /auth/login
Body: { "email": string, "password": string }
200: same TokenResponse shape as signup

GET /auth/me
200: { "id", "email", "role", "created_at" }

Errors: show `detail` string or validation array message from FastAPI.

--- EVENTS (behavioral signal; never embed on client) ---
POST /events
Body:
{
  "events": [
    {
      "event_type": "view" | "search" | "click" | "time_spent",
      "source": "udemy",
      "raw_metadata": { ...object }
    }
  ]
}
Constraints: 1–500 events per request.
200 Response:
{
  "inserted": number,
  "triggered": boolean,
  "trigger_reason": string | null,
  "recommendation": RecommendationOut | null
}

GET /events?limit=50
200: EventOut[]
EventOut = {
  id, user_id, event_type, source, raw_metadata, created_at
}

--- RECOMMENDATIONS (cached; instant; no loading skeleton that implies AI call) ---
GET /recommendations/latest
200:
{
  "recommendation": null | {
    "id": number,
    "user_id": number,
    "narrative": string,
    "resource_ids": number[],
    "trigger_reason": string,
    "generated_at": string,
    "expires_at": string,
    "resources": FreeResourceOut[]
  }
}

FreeResourceOut = {
  id, title, description, topic_tags: string[], youtube_url, level, category,
  sync_status, created_at, updated_at
}

--- CATALOG (free resources; admin writes) ---
GET /catalog
Auth required (any logged-in user)
200: FreeResourceOut[]

GET /catalog/{id}
200: FreeResourceOut

POST /catalog   // ADMIN ONLY
Body:
{
  "title": string,
  "description": string,
  "topic_tags": string[],
  "youtube_url": string,
  "level": string,      // e.g. beginner|intermediate|advanced
  "category": string    // e.g. programming|web-development|backend|data|machine-learning|computer-science|devops|tools|general
}
201: FreeResourceOut (includes sync_status: pending|synced|failed)

PUT /catalog/{id}  // ADMIN ONLY
Body: any subset of create fields
200: FreeResourceOut

DELETE /catalog/{id}  // ADMIN ONLY
204 empty

POST /catalog/{id}/resync  // ADMIN ONLY
200: FreeResourceOut

============================================================
API CLIENT REQUIREMENTS
============================================================
Implement `api/client.ts`:
- `apiFetch(path, options)` prepends VITE_API_URL
- Always set Content-Type application/json when body present
- Attach Bearer token if present
- On 401: clear auth storage and redirect to /login
- Parse FastAPI errors (`detail` string or array) into readable toast/banner text
- Never call Mesh/OpenAI from the frontend

============================================================
MOCK UDEMY COURSE MARKETPLACE (FRONTEND-ONLY DATA)
============================================================
There is NO backend courses endpoint. Create `src/data/mockCourses.ts` with ~12 realistic paid courses:
Fields per course:
{
  id: string,
  title: string,
  instructor: string,
  price: number,
  rating: number,
  students: number,
  category: string,
  level: string,
  shortDescription: string,
  topics: string[]
}
Categories should overlap free catalog themes: Python, FastAPI, JavaScript, React, SQL, ML, DSA, Docker, Git, CS50-style CS.

Browse page:
- Search box
- Category filter chips
- Course grid/list
- Clicking a course goes to detail

============================================================
EVENT TRACKER (CRITICAL EFFICIENCY FEATURE)
============================================================
Implement `lib/eventTracker.ts` as a singleton buffer:

API:
- track(event_type, raw_metadata)
- flush()
- start() / stop()

Behavior:
1. Buffer events in memory
2. Auto-flush when buffer length >= 5
3. Auto-flush on interval every 10 seconds if buffer non-empty
4. On `visibilitychange` hidden / `pagehide` / `beforeunload`: flush remaining via `navigator.sendBeacon` when possible
   - sendBeacon URL: `${VITE_API_URL}/events`
   - body must be JSON string of `{ events: [...] }`
   - IMPORTANT: sendBeacon cannot set Authorization headers. Therefore ALSO keep a normal fetch flush with auth for interval/threshold. For unload, use fetch with `keepalive: true` + Authorization header (preferred over beacon if auth required). Implement keepalive fetch flush for unload.
5. Tracking must never block UI (fire-and-forget; catch errors quietly; optional small console debug)
6. Every event includes `source: "udemy"`

When to track:
- view: course card enters viewport OR course detail mounts → raw_metadata: { courseId, title, category, level }
- search: debounced 400ms on browse search submit/change → { query }
- click: course card click / CTA click → { courseId, title }
- time_spent: on course detail unmount or every 30s while open → { courseId, title, seconds }

After successful POST /events:
- if response.triggered === true and recommendation present, update recommendation context/state so Dashboard can show it immediately
- else do nothing heavy

============================================================
PAGES — DETAILED UX
============================================================

1) Landing `/`
- Brand name SmartReco large
- Headline: free alternatives for what you’re browsing
- One supporting sentence about behavioral AI + grounded free catalog
- CTA: Get started / Log in
- No fake metrics, no feature card wall in first viewport

2) Signup `/signup` & Login `/login`
- Email + password forms
- Password min 6
- On success store token+user and route to `/browse`
- Demo hint text (small): Admin demo login `admin@smartreco.dev` / `admin123`

3) Browse `/browse`
- Marketplace feel titled like “Explore courses” (signal surface)
- Subtle note: “Browsing here trains SmartReco — we recommend free alternatives, not these paid listings.”
- Search + filters + course cards
- Wire eventTracker for search/view/click

4) Course detail `/browse/:courseId`
- Paid course presentation (price, instructor, topics)
- Primary button “View syllabus” / “I’m interested” triggers click event
- Track time_spent
- Side note CTA: “See free alternatives on your Dashboard”

5) Dashboard `/app`
Sections (one job each):
A. For You — recommendation panel
   - Fetch GET /recommendations/latest on load (instant)
   - If null: empty state “Browse a few courses to unlock free alternatives” + link to /browse
   - If present: show narrative prominently; list recommended free resources with title, description snippet, category/level, Open YouTube button (youtube_url new tab)
   - Show meta: trigger_reason, generated_at, expires_at (small)
B. Recent activity — GET /events?limit=20 as a simple feed (type + metadata summary + time)
C. Optional tiny status chip if last event batch triggered agent

Do NOT show a “Generate recommendation” button. Backend trigger is automatic.

6) Admin `/admin` (role=admin only)
- Table/list of GET /catalog
- Columns: title, category, level, sync_status badge (synced green / failed red / pending amber), actions
- Create form modal/panel: title, description, topic_tags (comma-separated → string[]), youtube_url, level select, category select
- Edit + Delete + Resync actions
- After create/update, show returned sync_status
- If sync_status=failed, emphasize Resync button
- Confirmation on delete

============================================================
STATE / CONTEXT
============================================================
- AuthContext: user, token, login, signup, logout, refreshMe
- RecommendationContext or simple SWR-like state: latest recommendation, setFromEventBatch, reloadLatest
- Event tracker starts on authenticated app mount and stops on logout

============================================================
EMPTY / ERROR / LOADING STATES
============================================================
- Skeleton only for network waits on dashboard/admin lists
- Friendly empty states
- Inline error banners with backend `detail`
- Never crash on recommendation=null

============================================================
SEED / DEMO HELPERS (UI ONLY)
============================================================
On dashboard empty state, include helper text:
“Tip: open 5 courses or search a few times — recommendations refresh after enough activity (backend threshold).”

Do not hardcode fake recommendations in UI.

============================================================
QUALITY BAR
============================================================
- TypeScript types matching API exactly in `types/api.ts`
- No unused placeholder pages
- Accessible forms (labels, button types)
- Mobile nav works
- Code is clean and ready to drop into an existing `frontend/` Vite React TS repo
- Include a short README section in a comment at top of api/client.ts listing endpoints used

============================================================
OUT OF SCOPE (DO NOT BUILD)
============================================================
- Real Udemy scraping/extension
- Email digest UI
- LangSmith UI
- Payments/social login
- Inventing backend routes
- Client-side LLM calls
- Recommending paid courses

Build the full app end-to-end now with all pages, API modules, mock courses, and the event buffer wired exactly as specified.
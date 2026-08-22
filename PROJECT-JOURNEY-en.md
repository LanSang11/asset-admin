# From Runnable to Deliverable: Project Journey and Engineering Retrospective

[简体中文](./PROJECT-JOURNEY.md) · [Product README](./README-en.md)

This is not a day-by-day activity log. It is an evidence-based account of how requirements became features, how failures were traced to mechanisms, how fixes were verified, and how each lesson became a reusable guardrail.

## What the 42 records mean

- Before this public documentation pass, the internal engineering notebook contained **42 real records**: 32 focused fixes, 6 issue discoveries, and 4 phase retrospectives.
- “42 records” does not mean exactly 42 independent bugs. Several retrospectives cover groups of problems with a shared root cause.
- The documentation and feature pass added three fixes—business query bars, test-state pollution, and the publish script help path—bringing that stage to **45 records**.
- GitHub rendering QA added one record, bringing the notebook to 46. The final public-history audit adds another, bringing the completed release to **47 records**.
- The challenge map remains a snapshot of the 45-record stage. The sanitized index at the end deliberately preserves the original 42-record baseline.
- Twelve representative cases are explained in depth. Internal logs, accounts, addresses, credentials, and runtime data are excluded.

## Four stages from requirements to the current system

| Stage | Training capability | Concrete result in this project | Verifiable entry point |
|---|---|---|---|
| Stage 1: project foundation | Development environment, coding tools, FastAPI fundamentals | Python service, Vue frontend, SQLite models, unified settings, and a sign-in security baseline | `app/`, `web/`, `run.py` |
| Stage 2: API contracts | Unified responses, exceptions, validation, database queries, and API debugging | CRUD, pagination, filters, Pydantic validation, CSV import/export, and API contract tests | `app/api/v1/`, `app/schemas/`, `deploy/tests/test_business_api.py` |
| Stage 3: access and workflows | Authentication, RBAC, frontend/backend integration, domain flows, and AI work records | Four-role model, row-level scope, field masking, checkout/return, two-level approval, notifications, and role-specific portals | `app/core/dependency.py`, `app/controllers/`, `web/src/views/business/` |
| Stage 4: integrated delivery | Advanced workflows, AI, testing, deployment, and troubleshooting | Transfer, repair, inventory, attachments, AI/RAG, security operations, backups, native deployment, and release gates | `app/services/`, `deploy/native/`, `deploy/tests/` |

These stages were not isolated assignments. Each later stage exposed boundaries left implicit by the previous one: a rendered page did not prove a correct API contract, an HTTP 200 did not prove data isolation, and a successful local run did not prove a reliable production release.

## A development timeline shaped by evidence

![Project challenge map](deploy/sample-picture/project-challenge-map.png)

The work clustered into six recurring engineering challenges:

1. **Frontend/backend contracts:** component slots, query parameters, pagination responses, and export filters had to agree.
2. **State machines and transactions:** applications, asset state, history, and notifications had to commit or roll back together.
3. **Authorization and isolation:** hidden menus were only presentation; server-side role, row, and field rules remained authoritative.
4. **Security and credentials:** sign-in, password rotation, TOTP, single-use tokens, audit, and release artifacts had to be designed for failure paths.
5. **AI and RAG:** provider failures needed explicit degradation, and retrieved answers needed traceable citations rather than plausible-looking fabricated output.
6. **Deployment and operations:** migrations, static files, certificate paths, probes, backups, and service restarts jointly determined release stability.

## Twelve representative cases

Each case follows the same reasoning chain: **business context → observed behavior → wrong direction → root cause → human correction → verification → prevention**.

### 1. Seven pages declared filters, but the browser showed none

- **Business context:** employees, assets, approvals, transfers, repairs, checkout, and inventory all need filters.
- **Observed behavior:** `QueryBarItem` existed in source, yet only the table appeared.
- **Wrong direction:** add more backend parameters or force the controls visible with CSS.
- **Root cause:** `CrudTable` renders only the named `#queryBar` slot; seven pages placed their controls in the default slot.
- **Human correction:** move 8 tables across 7 pages to the correct slot; add employee status and safe sorting; share one query helper between list and CSV export.
- **Verification:** static contracts inspect slot placement, real local requests carry all five filter/sort fields, and before/after screenshots show the change.
- **Prevention:** tests assert where a component is mounted and what it binds—not merely whether its name appears in source.

| Before | After |
|---|---|
| ![Employee page before the fix](deploy/sample-picture/screenshots/employees-before-filter-fix.png) | ![Employee page after the fix](deploy/sample-picture/screenshots/employees-filter-and-sort.png) |

### 2. A paginated endpoint returned data while the table remained wrong

- **Business context:** the shared table depends on stable `page`, `page_size`, `list`, and `total` semantics.
- **Observed behavior:** direct API calls returned rows, but totals or page two were incorrect in the UI.
- **Wrong direction:** teach each page to adapt a different response shape.
- **Root cause:** backend pagination fields and the frontend table contract had drifted; old tests asserted only the status code.
- **Human correction:** standardize request and response fields and keep page-size limits on the server.
- **Verification:** create more than 15 rows in an in-memory SQLite database and assert totals plus first- and second-page contents.
- **Prevention:** every list test checks rows, totals, and boundaries; HTTP 200 alone is never the acceptance criterion.

### 3. Return and repair both select an asset, but mean different things

- **Business context:** a return can select only the current employee’s in-use assets, while an administrator may register an idle asset for repair.
- **Observed behavior:** return choices included invalid states, or idle repair registration lacked the required person semantics.
- **Wrong direction:** reuse an “all assets” endpoint and let the frontend infer state.
- **Root cause:** similar controls concealed different domain constraints and field meanings.
- **Human correction:** split the server queries by workflow, define the registrant rule for idle repairs, and revalidate asset state on the server.
- **Verification:** cover in-use, idle, another employee’s asset, and resigned-employee scenarios.
- **Prevention:** UI components may be shared; domain queries and state validation remain workflow-specific.

### 4. Approval is more than changing one status number

- **Business context:** manager and administrator approval must update the request, asset, history, and notifications.
- **Observed behavior:** an intermediate failure could leave an approved request with stale asset or history state.
- **Wrong direction:** write several tables in screen order without rollback.
- **Root cause:** one state transition crossed multiple models without an atomic transaction or centralized constants.
- **Human correction:** wrap the writes in a transaction, centralize states, and emit notifications only after the transition is settled.
- **Verification:** assert approval stage, assignment, history entries, and blocked out-of-order approval.
- **Prevention:** define prerequisites, write set, rollback behavior, and allowed roles for every transition.

### 5. A route-prefix collision sent employees into an empty admin shell

- **Business context:** administrators enter the admin console; employees and managers enter the work portal.
- **Observed behavior:** a successful employee sign-in opened a blank management shell or the wrong home page.
- **Wrong direction:** add management menus to ordinary users to fill the shell.
- **Root cause:** a root/dynamic route matched too early and overrode the post-login destination decision.
- **Human correction:** return a stable `portal` value from the backend, compute home in one guard, and separate shell/permission sources.
- **Verification:** administrator, manager, and employee tests assert landing page, visible entries, and forbidden access.
- **Prevention:** portal selection has one source of truth; redirects do not independently guess the role.

### 6. Correct menu permissions did not guarantee safe data

- **Business context:** managers see their department, employees see themselves, and administrators see the organization.
- **Observed behavior:** a hidden button did not stop a direct list request from returning extra rows or contact fields.
- **Wrong direction:** treat frontend `v-permission` as complete authorization.
- **Root cause:** menu/API permissions, row scope, and field masking are separate layers.
- **Human correction:** recompute scope on the server, mask non-owner fields, and reuse the same scope for dashboards and exports.
- **Verification:** the role matrix asserts row count, row identity, and masked fields.
- **Prevention:** every list endpoint documents role, row, field, and export scopes before release.

### 7. First-time password rotation returned 500 and exposed extra fields

- **Business context:** a new installation requires rotation of its random initial credential.
- **Observed behavior:** serialization failed during rotation, and user responses risked including password-hash or internal fields.
- **Wrong direction:** hide fields only in the frontend or return the original stack trace.
- **Root cause:** update arguments, model serialization, and response schemas lacked one minimal contract.
- **Human correction:** fix the update call, exclude sensitive fields at the model layer, and keep detailed errors in internal logs only.
- **Verification:** rotation succeeds, the old token becomes invalid, user responses omit sensitive fields, and security headers remain present.
- **Prevention:** models exclude sensitive fields by default; endpoints may narrow further but never widen them.

### 8. Step-up tokens were reusable until bound to the operation

- **Business context:** deletion, import, export, and policy changes require recent verification.
- **Observed behavior:** an early draft proved only that the user had verified recently, not what operation or method was approved.
- **Wrong direction:** share one long-lived “verified” state across every high-risk button.
- **Root cause:** the token lacked user, operation key, verification mode, expiry, and single-consumption bindings.
- **Human correction:** bind all five conditions, consume once, reject mismatched keys/modes, and write an audit event.
- **Verification:** focused tests cover wrong operation, wrong mode, expiry, and a second use.
- **Prevention:** a security token must answer who, what, how, until when, and how many times.

### 9. A fake embedding fallback was more dangerous than an explicit failure

- **Business context:** knowledge retrieval should keep working when an external embedding provider is temporarily unavailable.
- **Observed behavior:** the old fallback silently stored hash arrays as if they were semantic vectors.
- **Wrong direction:** make the endpoint look successful at any cost.
- **Root cause:** availability was confused with “any output counts as success.”
- **Human correction:** record the degradation reason, fall back to lexical retrieval, cite the matched section, and rebuild embeddings after recovery.
- **Verification:** network errors, timeouts, and malformed responses never store fake vectors; lexical search still finds the correct section.
- **Prevention:** AI degradation must be observable, explainable, and recoverable.

### 10. Secret scanning blocked ordinary training text

- **Business context:** knowledge ingestion should reject real credentials while allowing security guidance and examples.
- **Observed behavior:** educational phrases containing terms such as “API key” or “password example” were rejected.
- **Wrong direction:** expand a keyword blacklist.
- **Root cause:** the scanner ignored structure, placeholders, context, and credential-like entropy.
- **Human correction:** separate high-confidence credential shapes from ordinary instructional language and return an explainable reason.
- **Verification:** credential-like fixtures fail, placeholders pass, and boundary-length plus mixed-text cases are covered.
- **Prevention:** structure and entropy are strong signals; keywords remain weak signals.

### 11. A migration passed locally but failed at SQLite’s capability boundary

- **Business context:** release new fields and frontend assets while preserving the production business database.
- **Observed behavior:** a column-comment migration failed at startup; on another release, static cleanup touched a certificate-validation file and produced a 403 home page.
- **Wrong direction:** copy development migration and static replacement behavior directly into production.
- **Root cause:** database-dialect capability, certificate paths, and deployment file boundaries were not modeled separately.
- **Human correction:** skip unsupported SQLite comment changes explicitly, publish code/dist only, and exclude certificate paths from cleanup.
- **Verification:** check the pre-release snapshot, service state, home page, static assets, and rollback artifact independently.
- **Prevention:** release tooling states exactly what it replaces, what it preserves, where it stops, and how it rolls back.

### 12. Probes, bans, and backup automation could harm one another

- **Business context:** releases run automatic probes, the gateway rate-limits traffic, and nightly jobs back up the databases.
- **Observed behavior:** a probe banned the shared egress used for acceptance; a backup job existed but did not run because the script lacked execution permission.
- **Wrong direction:** repeat the probe or inspect only whether the scheduled task exists.
- **Root cause:** automation modeled the success path but not identity/IP semantics, permissions, output, or repeatability.
- **Human correction:** separate authenticated and anonymous buckets, clear only automatic bans after successful sign-in, exclude documentation networks, and invoke backups through an explicit shell with artifact checks.
- **Verification:** repeated probes do not self-lock, the service remains active, and backup files open and pass integrity checks.
- **Prevention:** automation acceptance checks exit codes, side effects, artifacts, and whether the next run still works.

## Where tools and AI helped—and where human judgment remained essential

Tools and AI were useful for scaffolding, draft tests, repetitive code, and documentation structure. Delivery still required human judgment to:

1. define business roles, state machines, and data boundaries;
2. verify behavior through logs, requests, database state, and screenshots;
3. remove generic suggestions that contradicted the current system;
4. add positive, negative, and repeat-run tests;
5. inspect release artifacts, running services, backups, and rollback evidence; and
6. convert incidents into reusable rules.

## Verified engineering evidence

| Gate | Verified result |
|---|---|
| Internal Python suite | 150 tests passed |
| Public Python suite after this documentation change | 150 tests total, with 2 optional-dependency skips |
| Node UI/security contracts | 60 tests passed |
| Vite production build | 2,825 modules transformed |
| Query-filter screenshots | Synthetic local data through the real Vue pages and FastAPI endpoints; requests carry status and sort fields |
| Cloud release boundary | Earlier business fix used code-only deployment with a pre-release snapshot; the local database did not replace production data |

## Sanitized index of the original 42 records

> The sequence is preserved from the original notebook. Its status distribution remains 32 fixed, 6 discovered, and 4 retrospective records.

| # | Status | Area | Sanitized symptom | Resolution / conclusion |
|---:|---|---|---|---|
| 01 | Retrospective | Security baseline | Stage one proved startup but left security boundaries incomplete | Established sign-in, input, configuration, and test baselines |
| 02 | Retrospective | Integrated fixes | Gateway, state, frontend, and deployment issues shared roots | Split by layer and created a regression checklist |
| 03 | Discovered | Sign-in risk | Image sliders still have machine-recognition and new-egress limits | Recorded the accepted boundary and retained layered controls |
| 04 | Discovered | Data isolation | Notification audiences, read models, and field scopes were incomplete | Created an isolation-hardening checklist |
| 05 | Discovered | Information exposure | Demo content, API definitions, and debug text could enter releases | Added a pre-release disclosure check |
| 06 | Fixed | Notification audience | Workflow stages did not distinguish recipients | Unified notification types and stage-based delivery |
| 07 | Fixed | Data isolation | Manager/employee lists and dashboards were too broad | Narrowed row scopes and masked fields |
| 08 | Fixed | Identity model | Account roles and employee-manager identity diverged | Unified role resolution and matrix tests |
| 09 | Fixed | Portal experience | Admin and work portals lacked stable routing | Added separate shells and localized forbidden responses |
| 10 | Fixed | Sensitive responses | Forced rotation failed and internal fields/security headers leaked | Minimized responses, excluded fields, and added headers |
| 11 | Fixed | Menu permissions | Ordinary users saw excessive admin entries | Narrowed menus and added role-scoped dashboards |
| 12 | Fixed | Information exposure | Schemas, docs, JWT settings, and anonymous text exposed internals | Applied tiered cleanup and release checks |
| 13 | Fixed | Sign-in controls | Sign-in lacked a mandatory slider and failure lock | Added slider, rate limits, and failure counters |
| 14 | Retrospective | Execution debugging | Command variants, wrong methods, and token lifetime caused false conclusions | Standardized repeatable commands and evidence order |
| 15 | Retrospective | Historical archive | Fixes were scattered across handoffs and test reports | Consolidated a searchable engineering notebook |
| 16 | Fixed | Session security | Access-token lifetime was too long | Shortened the default and verified old sessions |
| 17 | Fixed | Security operations | Events, bans, TOTP, and audit lacked one control surface | Built a zero-cost security operations package |
| 18 | Fixed | Sign-in UI | Sign-in lacked polish and state feedback | Rebuilt visual and interaction feedback |
| 19 | Discovered | Routing | Every role could land in an empty admin shell | Isolated the prefix collision and portal truth |
| 20 | Fixed | Routing | Root routing overrode the work portal destination | Unified portal and guard logic |
| 21 | Fixed | Repair | Idle-asset repair registration lacked person semantics | Added field contracts and state validation |
| 22 | Fixed | Loading UI | Logo, animation, and text used different axes | Unified layout and responsive sizes |
| 23 | Discovered | Credentials | Historical packages and scripts could retain old credentials | Defined rotation and artifact-cleanup scope |
| 24 | Discovered | Security search | Frontend and backend filters were disconnected | Defined a composable filter contract |
| 25 | Fixed | AI frontend | The assistant drawer referenced an undefined session variable | Corrected state ownership and added a contract test |
| 26 | Fixed | Sensitive fields | User lists returned model-provider configuration | Minimized schemas and excluded sensitive fields |
| 27 | Fixed | AI routing | Missing assistant route metadata broke startup | Completed the route contract and startup test |
| 28 | Fixed | Release gate | Credential material had entered a release package | Rotated, cleaned history, and added secret scanning |
| 29 | Fixed | Database | Notification-table indexes initialized incompletely | Added structural repair and repeat-run checks |
| 30 | Fixed | Security search | Success, time, and region exclusions could not combine | Unified `FilterSpec` and drill-down behavior |
| 31 | Fixed | Slider feedback | A wrong slider position could look successful | Drove visual state from the server result |
| 32 | Fixed | Step-up verification | High-risk verification, self-lock, and recovery were incomplete | Added operation binding, one-time tokens, and audit |
| 33 | Fixed | Static release | Certificate validation blocked static replacement and caused 403 | Isolated certificate paths and verified rollback |
| 34 | Fixed | Knowledge base | Secret scanning rejected ordinary instructional text | Distinguished credential shapes from placeholders |
| 35 | Fixed | Migration | Unsupported SQLite comments prevented startup | Added dialect checks and explicit skips |
| 36 | Fixed | Public demo script | Demo credentials had an inappropriate fallback | Required environment input and suppressed output |
| 37 | Fixed | Second-step sign-in | Download guidance displaced the verification action | Reordered information and responsive layout |
| 38 | Fixed | Backup | Scheduled backup script lacked execution permission | Used an explicit shell and checked artifacts |
| 39 | Fixed | Gateway | Release probes banned the operator’s shared egress | Split authenticated/anonymous buckets and auto-unban boundaries |
| 40 | Fixed | AI/RAG | Embedding failure silently generated fake vectors | Degraded explicitly to lexical retrieval |
| 41 | Fixed | AI errors | Chat failures exposed exception types to the browser | Returned localized generic text and kept internal logs |
| 42 | Fixed | Public release gate | The public tree missed files, contracts, and lock consistency | Added public regression and dependency gates |

## Recommended review order

1. Start with the product positioning and six-layer architecture in the README.
2. Open employee management and use keyword, department, status, and safe sorting.
3. Compare the employee page screenshots and explain the named-slot root cause.
4. Demonstrate one complete approval, transfer, or repair workflow.
5. Compare menu, row, and field scopes across roles.
6. Show cited knowledge retrieval and explicit degradation—not merely a chatbot response.
7. Close with the challenge map, verified gates, and the original 42-record index.

## Closing summary

The project’s value is not just its feature count. It is the ability to preserve evidence, identify a mechanism-level cause, apply the smallest correct change, rerun automated gates, release predictably, and turn the result into a rule the next iteration can reuse.

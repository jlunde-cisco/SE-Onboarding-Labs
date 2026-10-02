# Lab 06 — Agentic Identity: Scoping an AI Agent to the User Behind It

## The scenario

A customer is rolling out an AI agent that can search and read files in
their company Google Drive. Their security team has one question: **"If
this agent has access to Drive, doesn't everyone who talks to it get
access to everything?"**

With a naive build, yes. The agent holds one broad credential, so it's a
skeleton key to the whole drive, and the only thing standing between a
user and the CEO's folder is whether the model feels like being polite
about it. This lab walks through the pattern that fixes that: the agent
gets a **non-human identity (NHI)** that is bound to the *user* it's
acting for, and every file access is checked against that user's
permissions, enforced in code on the server and not in the prompt.

You'll run a small MCP server (**The Palantír**) that does this with Auth0
(identity and RBAC) and Google Drive (the files), connect it to Claude
Desktop, and watch the same agent return different results for two
different users.

## What you'll learn

By the end of this lab you'll be able to:

- Explain what a non-human identity is for an AI agent, and why "the agent
  has a service account" is not an answer to the authorization question
- Distinguish **authentication** (who are you), **authorization** (what
  may you touch), and **delegation** (the agent acting on your behalf)
- Read an OAuth 2.0 access token and find the claims that carry a user's
  permissions
- Explain why enforcement has to live in the tool server and not in the
  model's instructions
- Name what a proof-of-concept like this skips that production needs

## Prerequisites

- Python 3.11+ and Node.js (for the `mcp-remote` bridge)
- [Claude Desktop](https://claude.ai/download)
- A free [Auth0](https://auth0.com) tenant
- A Google account and a Google Cloud project you can enable the Drive API
  in
- Comfort in a terminal and with a text editor

~2–3 hours, most of it identity-provider setup. Independent of the AWS labs
earlier in the series. It uses Claude Desktop rather than Bedrock, so you
don't need the Lab 01 account. If you've done Lab 04, the idea that
"instructions in a prompt aren't a security boundary" is the same idea
this lab fixes properly.

## Part 1 — The Architecture (given)

```
┌─────────────┐     ┌───────────────────────┐     ┌──────────────┐
│   Claude    │────▶│  Palantír MCP Server  │────▶│    Auth0     │
│   Desktop   │◀────│  (Python · FastMCP)   │◀────│    (IdP)     │
└─────────────┘     │                       │     └──────────────┘
                    │  Session:             │
                    │  • user identity      │     ┌──────────────┐
                    │  • auth0 permissions  │────▶│ Google Drive │
                    │  • google credentials │◀────│   (Files)    │
                    └───────────────────────┘     └──────────────┘
```

The server exposes tools to the agent: `login`, `connect_google_drive`,
`whoami`, `list_my_files`, `search_files`, `read_file`, and `logout`. The
design hinges on one split:

- **Auth0 decides what the user is allowed to see.** It issues a JWT with a
  `permissions[]` claim based on the user's role.
- **Google Drive stores the files.** The Drive token the server holds is
  broad, so it could read everything.
- **The server is the policy enforcement point.** It maps permissions to
  folders and only ever queries folders the user's token allows.

The permission model you'll build:

| Auth0 permission    | Drive folder            | Contents                  |
|---------------------|-------------------------|---------------------------|
| `read:shire-files`  | Shire Files             | Hobbit homeland docs      |
| `read:mordor-files` | Mordor Files            | Enemy intelligence        |
| `read:shared-files` | Shared Fellowship       | Fellowship-wide docs      |

| Role   | Test user | Permissions                                               |
|--------|-----------|-----------------------------------------------------------|
| Hobbit | Frodo     | `read:shire-files`, `read:shared-files`                   |
| Wizard | Gandalf   | `read:shire-files`, `read:mordor-files`, `read:shared-files` |

Read `palantir-mcp-server/server.py` before you run anything. It's about
400 lines, and finding where authorization is actually decided is the first
exercise.

<details>
<summary><strong>Where does the authorization decision actually happen?</strong></summary>

Look at `SessionStore.get_accessible_folders()`, which turns the user's
Auth0 permissions into a list of folder IDs, and at how `list_my_files`,
`search_files`, and `read_file` use it. Search and list only ever query
those folders. `read_file` goes one step further and fetches the file's
`parents` from Drive and refuses unless one of them is in the allowed set.

That last check matters. Without it, a user (or an injected prompt) who
learns or guesses a file ID could ask for it directly, and the broad Drive
token would happily return it.

</details>

## Part 2 — Set Up Auth0

Create the identity side. In an Auth0 tenant you'll need:

- An **API** (the resource the token is minted for), with RBAC enabled and
  permissions added to the access token
- The three permissions from the table above
- Two **roles** (Hobbit, Wizard) holding the right permission sets
- Two **users** (Frodo, Gandalf), each assigned a role
- A **Regular Web Application** representing the MCP server as an OAuth
  client, with `http://localhost:3001/callback` as an allowed callback URL

Record the tenant domain, API identifier (audience), and the application's
client ID and secret. They go in your `.env` later.

Two toggles on the API are easy to miss and the lab silently breaks without
them. Look for the ones about RBAC and about permissions appearing in the
access token.

<details>
<summary><strong>I logged in but my permissions list is empty</strong></summary>

The access token only carries a `permissions` claim if the API has **Enable
RBAC** and **Add Permissions in the Access Token** both turned on, the user
actually has a role assigned, and the token was requested for the right
audience. Check all three, then log out and back in. An old token won't
pick up the change.

</details>

## Part 3 — Set Up Google Drive

- In a Google Cloud project, enable the **Google Drive API**
- Create **OAuth 2.0 credentials** of type Web application, with
  `http://localhost:3002/callback` as an authorized redirect URI
- Create three Drive folders matching the table in Part 1 and put a few
  small text files in each. Make the contents recognizable per folder, so
  you can tell at a glance whether a leak happened.
- Note each folder's ID (it's in the folder's URL)

If Google makes you configure an OAuth consent screen, add your own account
as a test user.

## Part 4 — Run the Server and Connect Claude Desktop

Work in `palantir-mcp-server/`. Make a virtual environment, install
`requirements.txt`, copy `.env.example` to `.env`, and fill in everything
you collected in Parts 2 and 3. Then start `server.py`.

Claude Desktop reaches the server over SSE through the `mcp-remote` bridge.
Add a server entry to `claude_desktop_config.json` that runs
`npx -y mcp-remote http://localhost:3000/sse`, then restart Claude Desktop.
Confirm the Palantír's tools show up.

<details>
<summary><strong>Claude Desktop doesn't show the tools</strong></summary>

Check, in order: the server is still running and printed its startup
banner, the URL in the config ends in `/sse`, and the JSON is valid. Fully
quit Claude Desktop (not just close the window) and reopen it. If the
bridge itself errors, `npx` needs Node on your `PATH`.

</details>

## Part 5 — Same Agent, Different Users

Now the payoff. In Claude Desktop:

1. Ask it to log in to the Palantír and sign in as **Frodo**
2. Connect Google Drive when prompted
3. Run `whoami`, then list your files, then search for something that lives
   in the Mordor folder
4. Log out, sign in as **Gandalf**, and repeat

Record what each user sees. Frodo should see 5 files across two folders;
Gandalf 8 across three.

Then try to break it as Frodo:

- Ask the agent directly to read a Mordor file. If you can't get the ID
  from a listing, find it in the Drive UI.
- Tell the agent you're an administrator and it should make an exception.
- Ask for the contents of "every folder," or phrase the request so the
  model is tempted to do the server's job for it.

<details>
<summary><strong>What should happen, and why can't the model talk its way past it?</strong></summary>

Every attempt should come back as an access denied from the *server*,
because the decision isn't made by the model. The model never sees the
Mordor folder ID or has a way to widen the folder list. That list is
computed from the JWT's permissions, which the user can't edit. Compare
this to Lab 04, where the restriction lived in a system prompt and the
model was the only thing enforcing it.

If you did manage to read something you shouldn't have, you've found a bug
worth understanding. Trace it through `read_file`.

</details>

## Part 6 — Look Inside the Token

The server decodes the Auth0 access token to get permissions. Take one
issued for Frodo and one for Gandalf and decode them (jwt.io works, or a
few lines of Python), and compare the claims.

Answer for yourself:

- Which claim carries the permissions? What are `aud`, `sub`, and `exp`
  telling you?
- Who is the "subject" of the token, the human or the agent? What does that
  mean for audit logs?
- How long does the token live, and what does that imply if it leaks?

<details>
<summary><strong>Delegation vs. impersonation</strong></summary>

The agent isn't logging in as Frodo. It holds a token that says *Frodo
authorized this client to act for him, with these permissions*. The user's
identity is preserved through the chain, so a log entry can say "agent X
read file Y on behalf of Frodo." Impersonation, where the agent just uses
Frodo's password or a shared service account, loses that chain, and you
can no longer tell what the agent did from what the human did.

</details>

## Part 7 — Find the Gaps

This is a proof of concept, and the code says so in several comments. Audit
it as a security engineer would, then compare your list to the one in the
wrap-up. Start with these questions:

- What does `decode_auth0_token` verify? What could an attacker do with
  that?
- What happens if two people use the server at once?
- What's the search path doing with the user-supplied `query` string?
- What happens when a token expires?
- What would an audit trail need that this doesn't produce?

<details>
<summary><strong>Hint: the three biggest issues</strong></summary>

1. **The JWT signature is never verified.** `decode_auth0_token` passes
   `verify_signature: False`. In this lab the token arrives straight from
   Auth0 over TLS, so it's tolerable, but any production path must verify
   the signature against Auth0's JWKS, plus `iss`, `aud`, and `exp`.
2. **There's one global session.** `session` is a single in-memory object,
   so a second concurrent user would collide with or inherit the first.
   Real deployments need per-user sessions keyed to a verified identity.
3. **User input is interpolated into a Drive query.** `search_files` builds
   a `fullText contains '...'` clause from the raw query string, so a quote
   in the input changes the query. The folder restriction still holds, but
   it's the kind of injection to close.

</details>

## Cleanup

- Stop the server and remove its entry from `claude_desktop_config.json`
- Revoke the app's access in your Google account's security settings
- Delete the Auth0 test users, API, and application (or the tenant), and
  the Google Cloud OAuth credentials
- Never commit `.env`. The bundled `.gitignore` excludes it, so keep it.

## Wrap-Up

Before you consider this lab done, make sure you can answer these:

1. A customer asks "how do we stop the agent from showing people files they
   shouldn't see?" Explain the pattern in this lab in two minutes, without
   saying "the prompt tells it not to."
2. What's the difference between authentication, authorization, and
   delegation, and which system in this lab owns each?
3. Why does `read_file` re-check the file's parent folder instead of
   trusting that the ID came from an earlier listing?
4. Which parts of this would you have to change before a customer could
   run it for a thousand users?
5. Where would a guardrail product like AI Defense add value on top of this?
   Identity scoping controls *which* data the agent can reach. What
   controls what the agent does with the data it's allowed to read?

<details>
<summary><strong>Production checklist (compare to your Part 7 list)</strong></summary>

- Verify JWT signatures via JWKS, and validate `iss`, `aud`, and `exp`
- Refresh expired Auth0 and Google tokens
- Per-user session isolation, stored in Redis or a database, not in memory
- Dynamic permission-to-resource mapping from a data store, not env vars
- Escape or parameterize user input in Drive queries
- Audit logging: user identity, tool, resource, and timestamp for every
  access
- Short-lived tokens and no long-lived shared secrets

</details>

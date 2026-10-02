# 🔮 The Palantír

**Non-Human Identity with Per-User Permission Scoping for AI Agents**

A proof-of-concept MCP server demonstrating how to scope an AI agent's file access to a user's permission boundaries using OAuth 2.0 delegated authorization, Auth0 RBAC, and Google Drive.

> *The Palantír sees only what its user is permitted to see.*

---

## The Problem

When an AI agent acts on behalf of a user, it needs a **non-human identity (NHI)** that is constrained to that user's permissions. Without proper scoping, a single agent becomes a skeleton key to all organizational data.

This lab demonstrates the correct pattern: **the agent authenticates users through an identity provider, receives a token containing only that user's permissions, and uses those permissions to constrain which resources it can access.**

## Architecture

```
┌─────────────┐     ┌───────────────────────┐     ┌──────────────┐
│   Claude     │────▶│  Palantír MCP Server   │────▶│    Auth0     │
│   Desktop    │◀────│  (Python · FastMCP)    │◀────│    (IdP)     │
└─────────────┘     │                       │     └──────────────┘
                    │  Session:             │
                    │  • user identity      │     ┌──────────────┐
                    │  • auth0 permissions  │────▶│ Google Drive  │
                    │  • google credentials │◀────│    (Files)    │
                    └───────────────────────┘     └──────────────┘
```

**The key insight:** Authorization comes from Auth0 (what can this user access?), not from Google Drive. The agent's Drive token is broad, but the MCP server only queries folders the user's Auth0 permissions allow.

## Demo: Same Agent, Different Users, Different Access

### Frodo (Hobbit Role) → 5 files
```
📂 Shire Files (read:shire-files)
  📄 shire-map.txt
  📄 ring-bearer-journal.txt
  📄 second-breakfast.txt
📂 Shared Fellowship (read:shared-files)
  📄 council-of-elrond.txt
  📄 fellowship-roster.txt
❌ Mordor Files → INVISIBLE
```

### Gandalf (Wizard Role) → 8 files
```
📂 Shire Files (read:shire-files)
  📄 shire-map.txt
  📄 ring-bearer-journal.txt
  📄 second-breakfast.txt
📂 Mordor Files (read:mordor-files)
  📄 mordor-intel.txt
  📄 orc-deployments.txt
  📄 mount-doom-route.txt
📂 Shared Fellowship (read:shared-files)
  📄 council-of-elrond.txt
  📄 fellowship-roster.txt
```

Same agent. Same Google Drive. **Auth0 JWT permissions determine what the agent can see.**

## How It Works

1. **User calls `login`** → MCP server opens browser for Auth0 authentication
2. **Auth0 returns a JWT** with a `permissions[]` claim based on the user's role
3. **User calls `connect_google_drive`** → OAuth consent for Drive read access
4. **User calls `search_files` or `list_my_files`** → MCP server maps Auth0 permissions to folder IDs and only queries authorized folders
5. **User calls `read_file`** → MCP server verifies the file's parent folder is in the user's authorized set before returning content

## Permission Model

| Auth0 Permission    | Google Drive Folder     | Description              |
|---------------------|-------------------------|--------------------------|
| `read:shire-files`  | Shire Files folder      | Hobbit homeland docs     |
| `read:mordor-files` | Mordor Files folder     | Enemy intelligence       |
| `read:shared-files` | Shared Fellowship folder| Fellowship-wide docs     |

| Role   | User    | Permissions                                              |
|--------|---------|----------------------------------------------------------|
| Hobbit | Frodo   | `read:shire-files`, `read:shared-files`                  |
| Wizard | Gandalf | `read:shire-files`, `read:mordor-files`, `read:shared-files` |

## Setup

### Prerequisites

- Python 3.11+
- Node.js (for `mcp-remote` bridge)
- [Auth0 account](https://auth0.com) (free tier)
- [Google Cloud project](https://console.cloud.google.com) with Drive API enabled
- [Claude Desktop](https://claude.ai/download)

### 1. Clone and install

```bash
git clone https://github.com/jlunde-cisco/SE-Onboarding-Labs.git
cd SE-Onboarding-Labs/lab-06-agentic-identity/palantir-mcp-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Auth0 Setup

1. Create an Auth0 tenant
2. **Create an API** called "The Palantir" with identifier `https://palantir.middle-earth.local`
   - Enable RBAC
   - Enable "Add Permissions in the Access Token"
3. **Add permissions** to the API: `read:shire-files`, `read:mordor-files`, `read:shared-files`
4. **Create roles:**
   - Hobbit → `read:shire-files`, `read:shared-files`
   - Wizard → all three permissions
5. **Create users** and assign roles (e.g., Frodo → Hobbit, Gandalf → Wizard)
6. **Create a Regular Web Application** ("Palantír MCP Agent")
   - Note the Client ID and Client Secret
   - Set Allowed Callback URLs: `http://localhost:3001/callback`

### 3. Google Drive Setup

1. Create a Google Cloud project and enable the **Google Drive API**
2. Create **OAuth 2.0 credentials** (Web application)
   - Authorized redirect URI: `http://localhost:3002/callback`
3. Create three folders in Google Drive with test files:
   - `Shire Files/` — hobbit-related documents
   - `Mordor Files/` — enemy intelligence
   - `Shared Fellowship/` — fellowship-wide documents
4. Note each folder's ID from the Drive URL

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret
AUTH0_AUDIENCE=https://palantir.middle-earth.local

GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

GDRIVE_SHIRE_FOLDER_ID=your_folder_id
GDRIVE_MORDOR_FOLDER_ID=your_folder_id
GDRIVE_SHARED_FOLDER_ID=your_folder_id
```

### 5. Run the server

```bash
python server.py
```

### 6. Configure Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "palantir": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:3000/sse"]
    }
  }
}
```

Restart Claude Desktop.

### 7. Test it

In Claude Desktop:
1. "Log in to the Palantír" → authenticate as Frodo or Gandalf
2. "Connect my Google Drive" → authorize Drive access
3. "List my files" → see only what your role permits
4. "Search for ring" → scoped search across authorized folders
5. Log out, switch users, and see different results

## MCP Tools

| Tool                  | Description                                        |
|-----------------------|----------------------------------------------------|
| `login`               | Authenticate via Auth0 (opens browser)             |
| `connect_google_drive`| Link Google Drive (opens browser for OAuth consent)|
| `whoami`              | Show current user, permissions, and session status |
| `list_my_files`       | List all files in authorized folders               |
| `search_files`        | Search across authorized folders                   |
| `read_file`           | Read a specific file (with authorization check)    |
| `logout`              | Clear session and tokens                           |

## Key Architectural Principles

- **Least privilege by default** — the agent has zero standing permissions; all access derives from the user's token
- **Delegation, not impersonation** — the identity chain is preserved (agent acting on behalf of user)
- **Authorization ≠ authentication** — Auth0 handles what you can access; Google handles file storage access
- **Short-lived, scoped tokens** — no long-lived API keys or shared secrets
- **Defense in depth** — `read_file` verifies parent folder authorization even if a file ID is guessed

## Anti-Patterns This Avoids

- ❌ God-mode service accounts with app-layer filtering
- ❌ Shared API keys across all users
- ❌ Client-side only permission enforcement
- ❌ Long-lived credentials or hardcoded secrets

## Production Considerations

This is a lab/POC. For production, you would want:

- **Token refresh** — handle expired Google and Auth0 tokens
- **Proper JWT verification** — validate Auth0 token signatures using JWKS
- **Persistent session store** — Redis or database instead of in-memory
- **Multi-user concurrency** — session isolation per concurrent user
- **Dynamic permission mapping** — lookup folder mappings from a database instead of static config
- **Audit logging** — log every file access with user identity and timestamp

## Tech Stack

| Component         | Technology              | Cost                  |
|-------------------|-------------------------|-----------------------|
| Identity Provider | Auth0 (free tier)       | Free (7,500 users)    |
| File Storage      | Google Drive API        | Free (15 GB)          |
| Agent Runtime     | Python + MCP SDK        | Free (open source)    |
| AI Client         | Claude Desktop          | Free (with Claude plan)|

## License

MIT

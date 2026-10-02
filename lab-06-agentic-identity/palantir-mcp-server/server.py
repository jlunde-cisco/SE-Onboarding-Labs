"""
🔮 The Palantír — MCP Server with OAuth-Scoped Google Drive Access

Demonstrates non-human identity with per-user permission boundaries.
Users authenticate via Auth0, and file access is scoped to their permissions.
"""

import os
import json
import secrets
import webbrowser
import threading
import time
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

import httpx
import jwt
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# ─── Configuration ───────────────────────────────────────────────────────────

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Map Auth0 permissions to Google Drive folder IDs
PERMISSION_FOLDER_MAP = {
    "read:shire-files": os.getenv("GDRIVE_SHIRE_FOLDER_ID"),
    "read:mordor-files": os.getenv("GDRIVE_MORDOR_FOLDER_ID"),
    "read:shared-files": os.getenv("GDRIVE_SHARED_FOLDER_ID"),
}

SERVER_PORT = int(os.getenv("SERVER_PORT", "3000"))
AUTH0_CALLBACK_PORT = 3001  # Separate port for OAuth callbacks
GOOGLE_CALLBACK_PORT = 3002

# ─── In-Memory Session Store ─────────────────────────────────────────────────
# In production, use Redis or a database.

class SessionStore:
    """Stores authenticated user sessions and tokens."""

    def __init__(self):
        self.current_user = None  # Current Auth0 user info
        self.auth0_access_token = None  # Auth0 access token (with permissions)
        self.auth0_permissions = []  # Extracted permissions list
        self.google_credentials = None  # Google OAuth tokens
        self._pending_auth0_state = None
        self._pending_google_state = None
        self._auth0_code = None
        self._google_code = None

    def clear(self):
        self.__init__()

    @property
    def is_authenticated(self):
        return self.current_user is not None

    @property
    def has_google_drive(self):
        return self.google_credentials is not None

    def get_accessible_folders(self):
        """Return list of Google Drive folder IDs this user can access."""
        folders = []
        for perm in self.auth0_permissions:
            folder_id = PERMISSION_FOLDER_MAP.get(perm)
            if folder_id:
                folders.append((perm, folder_id))
        return folders


session = SessionStore()

# ─── OAuth Callback Handler ──────────────────────────────────────────────────

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles OAuth callback redirects from Auth0 and Google."""

    callback_type = None  # Set by the factory

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/callback":
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]

            if self.callback_type == "auth0":
                if state == session._pending_auth0_state and code:
                    session._auth0_code = code
                    self._respond("🧙 The Palantír recognizes you! You may close this window and return to Claude.")
                else:
                    self._respond("❌ Authentication failed — the seeing stone rejects this request.")
            elif self.callback_type == "google":
                if state == session._pending_google_state and code:
                    session._google_code = code
                    self._respond("📁 Google Drive connected! You may close this window and return to Claude.")
                else:
                    self._respond("❌ Google Drive connection failed.")
        else:
            self._respond("Unknown path", 404)

    def _respond(self, message, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        html = f"""
        <html><body style="font-family: sans-serif; text-align: center; padding: 60px;">
        <h1>{'🔮' if status == 200 else '❌'}</h1>
        <h2>{message}</h2>
        </body></html>
        """
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass  # Suppress noisy HTTP logs


def run_callback_server(port, callback_type, timeout=120):
    """Run a temporary HTTP server to catch the OAuth callback."""

    class Handler(OAuthCallbackHandler):
        pass
    Handler.callback_type = callback_type

    server = HTTPServer(("localhost", port), Handler)
    server.timeout = timeout
    server.handle_request()  # Handle exactly one request
    server.server_close()


# ─── Auth0 Functions ─────────────────────────────────────────────────────────

def build_auth0_login_url():
    """Build the Auth0 authorization URL."""
    state = secrets.token_urlsafe(32)
    session._pending_auth0_state = state

    params = {
        "response_type": "code",
        "client_id": AUTH0_CLIENT_ID,
        "redirect_uri": f"http://localhost:{AUTH0_CALLBACK_PORT}/callback",
        "scope": "openid profile email",
        "audience": AUTH0_AUDIENCE,
        "state": state,
    }
    return f"https://{AUTH0_DOMAIN}/authorize?{urlencode(params)}"


def exchange_auth0_code(code):
    """Exchange authorization code for tokens."""
    response = httpx.post(
        f"https://{AUTH0_DOMAIN}/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": AUTH0_CLIENT_ID,
            "client_secret": AUTH0_CLIENT_SECRET,
            "code": code,
            "redirect_uri": f"http://localhost:{AUTH0_CALLBACK_PORT}/callback",
        },
    )
    response.raise_for_status()
    return response.json()


def decode_auth0_token(access_token):
    """Decode the Auth0 access token to extract permissions.

    For a lab, we decode without full verification. In production,
    you'd verify the signature using Auth0's JWKS endpoint.
    """
    # Decode without verification for lab purposes
    decoded = jwt.decode(
        access_token,
        options={"verify_signature": False},
        algorithms=["RS256"],
    )
    return decoded


# ─── Google Drive Functions ──────────────────────────────────────────────────

def build_google_auth_url():
    """Build the Google OAuth authorization URL."""
    state = secrets.token_urlsafe(32)
    session._pending_google_state = state

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": f"http://localhost:{GOOGLE_CALLBACK_PORT}/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/drive.readonly",
        "access_type": "offline",
        "state": state,
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_google_code(code):
    """Exchange Google authorization code for tokens."""
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"http://localhost:{GOOGLE_CALLBACK_PORT}/callback",
        },
    )
    response.raise_for_status()
    return response.json()


def list_files_in_folder(folder_id, google_access_token, query=None):
    """List files in a specific Google Drive folder."""
    q = f"'{folder_id}' in parents and trashed = false"
    if query:
        q += f" and fullText contains '{query}'"

    response = httpx.get(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {google_access_token}"},
        params={
            "q": q,
            "fields": "files(id, name, mimeType, modifiedTime, size)",
            "pageSize": 20,
        },
    )
    response.raise_for_status()
    return response.json().get("files", [])


def get_file_content(file_id, google_access_token):
    """Download a file's text content from Google Drive.
    
    Handles both native Google Docs (which need export) and
    regular files (which can be downloaded directly).
    """
    # First, check the file's MIME type
    meta_response = httpx.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers={"Authorization": f"Bearer {google_access_token}"},
        params={"fields": "mimeType, name"},
    )
    meta_response.raise_for_status()
    mime_type = meta_response.json().get("mimeType", "")

    # Google Workspace files need to be exported, not downloaded
    google_docs_types = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }

    if mime_type in google_docs_types:
        export_mime = google_docs_types[mime_type]
        response = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
            headers={"Authorization": f"Bearer {google_access_token}"},
            params={"mimeType": export_mime},
        )
    else:
        response = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers={"Authorization": f"Bearer {google_access_token}"},
            params={"alt": "media"},
        )

    response.raise_for_status()
    return response.text


# ─── MCP Server ──────────────────────────────────────────────────────────────

mcp = FastMCP(
    "The Palantír",
    host="127.0.0.1",
    port=SERVER_PORT,
    instructions="""You are connected to The Palantír, a seeing stone that provides access
    to Middle-earth's archives. Users must first authenticate (login) to prove their identity,
    then connect their Google Drive. The Palantír will only show files the user is authorized
    to see based on their role (Hobbit or Wizard).

    Typical workflow:
    1. Call `login` to authenticate the user
    2. Call `connect_google_drive` to link their file storage
    3. Call `whoami` to see their identity and permissions
    4. Call `search_files` or `list_my_files` to access authorized files
    5. Call `read_file` to read a specific file's contents
    """,
)


@mcp.tool()
def login() -> str:
    """Authenticate with Auth0. Opens a browser window for the user to log in.
    This must be called before accessing any files."""

    if session.is_authenticated:
        return f"✅ Already authenticated as {session.current_user['name']} ({session.current_user['email']}). Permissions: {', '.join(session.auth0_permissions)}"

    # Start callback server in background thread
    callback_thread = threading.Thread(
        target=run_callback_server,
        args=(AUTH0_CALLBACK_PORT, "auth0"),
        daemon=True,
    )
    callback_thread.start()

    # Open browser for login
    login_url = build_auth0_login_url()
    webbrowser.open(login_url)

    # Wait for callback
    callback_thread.join(timeout=120)

    if not session._auth0_code:
        return "❌ Authentication timed out. Please try again."

    # Exchange code for tokens
    try:
        token_response = exchange_auth0_code(session._auth0_code)
        access_token = token_response["access_token"]

        # Decode the access token to get permissions
        decoded = decode_auth0_token(access_token)

        # Extract user info
        session.auth0_access_token = access_token
        session.auth0_permissions = decoded.get("permissions", [])

        # Get user profile from Auth0
        userinfo_response = httpx.get(
            f"https://{AUTH0_DOMAIN}/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_response.raise_for_status()
        session.current_user = userinfo_response.json()

        perm_list = ", ".join(session.auth0_permissions) or "none"
        return (
            f"🧙 The Palantír recognizes you!\n\n"
            f"**Identity:** {session.current_user.get('name', 'Unknown')}\n"
            f"**Email:** {session.current_user.get('email', 'Unknown')}\n"
            f"**Permissions:** {perm_list}\n\n"
            f"Next step: Call `connect_google_drive` to link your file storage."
        )

    except Exception as e:
        session.clear()
        return f"❌ Authentication failed: {str(e)}"


@mcp.tool()
def connect_google_drive() -> str:
    """Connect Google Drive for file access. Must be authenticated first.
    Opens a browser window to authorize Google Drive access."""

    if not session.is_authenticated:
        return "❌ You must `login` first before connecting Google Drive."

    if session.has_google_drive:
        return "✅ Google Drive is already connected."

    # Start callback server in background thread
    callback_thread = threading.Thread(
        target=run_callback_server,
        args=(GOOGLE_CALLBACK_PORT, "google"),
        daemon=True,
    )
    callback_thread.start()

    # Open browser for Google auth
    google_url = build_google_auth_url()
    webbrowser.open(google_url)

    # Wait for callback
    callback_thread.join(timeout=120)

    if not session._google_code:
        return "❌ Google Drive connection timed out. Please try again."

    try:
        token_response = exchange_google_code(session._google_code)
        session.google_credentials = token_response

        return (
            "📁 Google Drive connected successfully!\n\n"
            "You can now use `list_my_files` to see your authorized files, "
            "`search_files` to search, or `read_file` to read a specific file."
        )

    except Exception as e:
        return f"❌ Google Drive connection failed: {str(e)}"


@mcp.tool()
def whoami() -> str:
    """Show the current user's identity, role, and what files they can access."""

    if not session.is_authenticated:
        return "❌ Not authenticated. Please call `login` first."

    accessible = session.get_accessible_folders()
    folder_list = "\n".join(
        f"  - **{perm}** → folder `{fid[:12]}...`"
        for perm, fid in accessible
    )

    return (
        f"🔮 **Palantír Session**\n\n"
        f"**User:** {session.current_user.get('name', 'Unknown')}\n"
        f"**Email:** {session.current_user.get('email', 'Unknown')}\n"
        f"**Permissions:** {', '.join(session.auth0_permissions)}\n"
        f"**Google Drive:** {'Connected ✅' if session.has_google_drive else 'Not connected ❌'}\n\n"
        f"**Accessible folders:**\n{folder_list or '  None'}"
    )


@mcp.tool()
def list_my_files() -> str:
    """List all files the current user is authorized to access.
    Requires both Auth0 login and Google Drive connection."""

    if not session.is_authenticated:
        return "❌ Not authenticated. Please call `login` first."
    if not session.has_google_drive:
        return "❌ Google Drive not connected. Please call `connect_google_drive` first."

    accessible_folders = session.get_accessible_folders()
    if not accessible_folders:
        return "🚫 You don't have permission to access any files."

    google_token = session.google_credentials["access_token"]
    all_results = []

    for perm, folder_id in accessible_folders:
        try:
            files = list_files_in_folder(folder_id, google_token)
            folder_label = perm.replace("read:", "").replace("-", " ").title()
            all_results.append(f"\n📂 **{folder_label}** (`{perm}`):")
            if files:
                for f in files:
                    all_results.append(f"  - 📄 {f['name']} (id: `{f['id']}`)")
            else:
                all_results.append("  - (empty)")
        except Exception as e:
            all_results.append(f"  - ⚠️ Error reading folder: {str(e)}")

    return (
        f"🔮 **Files visible to {session.current_user.get('name', 'you')}:**\n"
        + "\n".join(all_results)
    )


@mcp.tool()
def search_files(query: str) -> str:
    """Search for files across all folders the user has permission to access.

    Args:
        query: Search term to look for in file names and contents.
    """

    if not session.is_authenticated:
        return "❌ Not authenticated. Please call `login` first."
    if not session.has_google_drive:
        return "❌ Google Drive not connected. Please call `connect_google_drive` first."

    accessible_folders = session.get_accessible_folders()
    if not accessible_folders:
        return "🚫 You don't have permission to access any files."

    google_token = session.google_credentials["access_token"]
    all_results = []

    for perm, folder_id in accessible_folders:
        try:
            files = list_files_in_folder(folder_id, google_token, query=query)
            if files:
                folder_label = perm.replace("read:", "").replace("-", " ").title()
                all_results.append(f"\n📂 **{folder_label}** (`{perm}`):")
                for f in files:
                    all_results.append(f"  - 📄 {f['name']} (id: `{f['id']}`)")
        except Exception as e:
            all_results.append(f"  - ⚠️ Error searching: {str(e)}")

    if not all_results:
        # Show which folders were searched for transparency
        searched = ", ".join(p for p, _ in accessible_folders)
        return f"🔍 No results for '{query}' in your authorized folders ({searched})."

    return (
        f"🔍 **Search results for '{query}'** "
        f"(as {session.current_user.get('name', 'you')}):\n"
        + "\n".join(all_results)
    )


@mcp.tool()
def read_file(file_id: str) -> str:
    """Read the contents of a specific file by its Google Drive file ID.

    Args:
        file_id: The Google Drive file ID (shown in list_my_files or search_files results).
    """

    if not session.is_authenticated:
        return "❌ Not authenticated. Please call `login` first."
    if not session.has_google_drive:
        return "❌ Google Drive not connected. Please call `connect_google_drive` first."

    # Security check: verify the file is in an authorized folder
    google_token = session.google_credentials["access_token"]
    accessible_folders = session.get_accessible_folders()

    # Get the file's parent folder to check authorization
    try:
        file_meta = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers={"Authorization": f"Bearer {google_token}"},
            params={"fields": "id, name, parents"},
        )
        file_meta.raise_for_status()
        meta = file_meta.json()

        parents = meta.get("parents", [])
        allowed_folder_ids = [fid for _, fid in accessible_folders]

        if not any(p in allowed_folder_ids for p in parents):
            return (
                f"🚫 Access denied. The file '{meta.get('name', file_id)}' "
                f"is not in a folder you have permission to access."
            )

        # File is authorized — read it
        content = get_file_content(file_id, google_token)
        return (
            f"📄 **{meta.get('name', 'Unknown')}**\n\n"
            f"---\n{content}\n---"
        )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"❌ File not found: `{file_id}`"
        return f"❌ Error reading file: {str(e)}"
    except Exception as e:
        return f"❌ Error reading file: {str(e)}"


@mcp.tool()
def logout() -> str:
    """Log out and clear the current session."""
    if not session.is_authenticated:
        return "ℹ️ No active session."

    name = session.current_user.get("name", "Unknown")
    session.clear()
    return f"👋 {name} has been logged out. The Palantír grows dark."


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🔮 The Palantír MCP Server starting...")
    print(f"   Auth0 Domain: {AUTH0_DOMAIN}")
    print(f"   API Audience: {AUTH0_AUDIENCE}")
    print(f"   Folder mappings:")
    for perm, fid in PERMISSION_FOLDER_MAP.items():
        print(f"     {perm} → {fid or '(not set)'}")
    print(f"\n   Starting SSE transport on http://localhost:{SERVER_PORT}/sse")
    print(f"   Auth0 callback on http://localhost:{AUTH0_CALLBACK_PORT}/callback")
    print(f"   Google callback on http://localhost:{GOOGLE_CALLBACK_PORT}/callback")

    mcp.run(transport="sse")
# Process Lifecycle

Backend startup writes runtime state to the user data directory:

- `%LOCALAPPDATA%\SNInsightTerminal\runtime\server.pid`
- `%LOCALAPPDATA%\SNInsightTerminal\runtime\server_port.json`
- `%LOCALAPPDATA%\SNInsightTerminal\runtime\server_session.json`

APIs:

- `GET /api/terminal/system/process-status`
- `POST /api/terminal/system/shutdown`

Shutdown stops new task acceptance, marks runtime state as closed, removes the pid file, and asks the HTTP server to exit gracefully. It must not kill unrelated user Python or browser processes.

The default product policy is to stop the local backend when the terminal exits unless the user explicitly chooses to keep it running.

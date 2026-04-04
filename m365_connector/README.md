# Microsoft 365 Connector Agent for Copilot (MCP)

This agent provides integration with Microsoft 365 services (Outlook, Teams, OneDrive, Access, OneNote) for Copilot and other agents using the Model Context Protocol (MCP).

## Table of Contents

- [Features](#features)
- [Setup](#setup)
- [Services Supported](#services-supported)
- [Extending](#extending)
- [License](#license)

## Features
- OAuth2 authentication for M365 APIs
- Declarative actions for Copilot (read/send mail, list files, post Teams message, etc.)
- Extensible for additional M365 services
- Python-based MCP server logic

## Setup
1. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
2. Configure Azure AD app registration for M365 API access (see docs/setup.md).
3. Run the agent:
   ```sh
   python mcp_server.py
   ```

## Services Supported
- Outlook (Mail, Calendar)
- Teams (Messages, Channels)
- OneDrive (Files)
- Access (Database API)
- OneNote (Notebooks, Pages)

## Extending
- Add new action handlers in `actions/`
- Update `mcp_server.py` to register new actions

## License
MIT

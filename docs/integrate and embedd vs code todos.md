# Open Todos

## Plan: Integrate Embedded VS Code Editor (Controllable via Extension)

This plan details actionable steps to embed VS Code as an editor within BossForgeOS, controllable via a custom extension, and to connect it to the agent/bus system for automation and workflows.

---

### 1. Research and Feasibility
- **Goal:** Determine the best approach for embedding VS Code as an editor (webview, electron, or remote control).
- **TODOs:**
  - Research VS Code Web (vscode.dev) and open-source Monaco Editor for embedding.
  - Evaluate options: embedding full VS Code (electron/webview) vs. Monaco Editor with extension API bridge.
  - Assess licensing, security, and technical constraints.
  - Document findings and select approach.
- **Verification:** Chosen approach is feasible, legal, and aligns with BossForgeOS architecture.

---

### 2. Extension/Bridge Design
- **Goal:** Design a VS Code extension (or bridge) that exposes editor control APIs to BossForgeOS agents.
- **TODOs:**
  - Define extension API for agent-initiated actions (open file, edit, highlight, run command, etc.).
  - Design message protocol (bus, websocket, or local RPC) for agent-extension communication.
  - Plan for authentication/authorization of agent commands.
  - Document extension API and integration points.
- **Verification:** Extension API spec and message protocol documented.

---

### 3. Implementation: Embedded Editor
- **Goal:** Integrate the chosen editor (VS Code Web/Monaco) into BossForgeOS UI (Control Hall or standalone window).
- **TODOs:**
  - Add embedded editor panel to Control Hall Flask app or as a new Electron window.
  - Wire up file open/save to Rune Bus and agent commands.
  - Enable extension loading and agent control hooks.
  - Implement basic editor actions (open, edit, save, highlight, run command).
- **Verification:** Editor loads in Control Hall or window, can open/save files via bus/agent.

---

### 4. Implementation: Extension/Bridge
- **Goal:** Implement the VS Code extension/bridge for agent control.
- **TODOs:**
  - Scaffold extension with commands for agent-initiated actions.
  - Implement message handler for bus/websocket/RPC events.
  - Add security/auth checks for incoming commands.
  - Test agent-initiated editor actions (open file, edit, highlight, etc.).
- **Verification:** Extension responds to agent commands and updates editor as expected.

---

### 5. Integration and Automation
- **Goal:** Enable BossForgeOS agents to automate editor workflows (e.g., code review, refactor, highlight issues).
- **TODOs:**
  - Add agent-side logic for sending editor control commands.
  - Implement sample automation (e.g., auto-fix, highlight TODOs, run tests from agent).
  - Document automation flows and user override options.
- **Verification:** Agents can trigger editor actions and automation flows are documented.

---

### 6. Documentation and UX
- **Goal:** Ensure users understand how to use the embedded editor and agent automation.
- **TODOs:**
  - Update README and docs with setup, usage, and troubleshooting.
  - Add screenshots and usage examples.
  - Gather user feedback and iterate on UX.
- **Verification:** Docs are complete, and users can follow setup and usage instructions.

---

Each phase can be tracked as a separate epic or milestone, with progress visible in todos.md and Control Hall.

Would you like to prioritize a specific phase or begin with research and feasibility?
Outstanding work and delegated actions are tracked here.

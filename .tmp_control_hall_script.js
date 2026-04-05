
        let currentView = 'view_status';
        let chatHistory = [];
        let pinnedOverlayViewId = '';
        let soundEvents = [];
        let soundScheme = {};

        async function refreshDiagnostics() {
            const el = document.getElementById('diagnostics_output');
            if (!el) return;
            el.textContent = 'Loading...';

            const statusData = await fetchJsonWithTimeout('/api/status');
            const eventsData = await fetchJsonWithTimeout('/api/events?limit=20');
            const lines = [];

            const agentState = (statusData && statusData.agent_state && typeof statusData.agent_state === 'object')
                ? statusData.agent_state
                : {};
            const names = Object.keys(agentState);
            lines.push('Agent Health:');
            if (names.length) {
                for (const name of names) {
                    const info = agentState[name] || {};
                    lines.push('- ' + name + ': ' + (info.health || 'unknown') + ' (last seen: ' + (info.last_seen || 'never') + ')');
                }
            } else {
                lines.push('- No agent health data available.');
            }

            lines.push('');
            lines.push('Recent Events:');
            const events = (eventsData && Array.isArray(eventsData.items)) ? eventsData.items : [];
            if (events.length) {
                for (const item of events.slice(0, 10)) {
                    const stamp = item && item.timestamp ? String(item.timestamp) : 'unknown-time';
                    const evt = item && (item.event || item.type) ? String(item.event || item.type) : 'event';
                    lines.push('- ' + stamp + ' :: ' + evt);
                }
            } else {
                lines.push('- No events available.');
            }

            el.textContent = lines.join('\n');
        }

        function renderSoundEvents() {
            const root = document.getElementById('sound_events');
            if (!root) return;
            root.textContent = JSON.stringify({ events: soundEvents, scheme: soundScheme }, null, 2);
        }

        async function fetchSoundEvents() {
            const data = await fetchJsonWithTimeout('/api/soundstage/list_schemes');
            if (data && data.ok) {
                soundEvents = [];
                soundScheme = { available_schemes: data.schemes || [] };
                setSoundSchemeStatus('Sound schemes loaded.');
            } else {
                setSoundSchemeStatus('Unable to load sound schemes.');
            }
            renderSoundEvents();
        }

        function switchView(viewId) {
            currentView = viewId;
            document.querySelectorAll('.view-panel').forEach((el) => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach((el) => el.classList.remove('active'));
            const panel = document.getElementById(viewId);
            if (panel) panel.classList.add('active');
            const btn = document.querySelector(`.nav-btn[data-view="${viewId}"]`);
            if (btn) btn.classList.add('active');
            syncPinControls();
            if (viewId === 'view_diagnostics') refreshDiagnostics();
            if (viewId === 'view_sounds') fetchSoundEvents();
        }

        async function fetchJsonWithTimeout(url, timeoutMs = 4000) {
            const ctl = new AbortController();
            const timer = setTimeout(() => ctl.abort(), timeoutMs);
            try {
                const res = await fetch(url, { signal: ctl.signal });
                if (!res.ok) return { ok: false, error: 'HTTP ' + res.status };
                return await res.json();
            } catch (err) {
                return { ok: false, error: String(err) };
            } finally {
                clearTimeout(timer);
            }
        }

        function syncPinControls() {
            const note = document.getElementById('pin_note');
            const toggle = document.getElementById('pin_toggle');
            if (!note || !toggle) return;
            if (!pinnedOverlayViewId) {
                note.textContent = 'No desktop pin active';
                toggle.textContent = 'Pin Current View';
                return;
            }
            const pinnedNav = document.querySelector(`.nav-btn[data-view="${pinnedOverlayViewId}"]`);
            const pinnedTitle = pinnedNav ? pinnedNav.textContent.trim() : pinnedOverlayViewId;
            note.textContent = 'Pinned (always-on-top desktop): ' + pinnedTitle;
            toggle.textContent = pinnedOverlayViewId === currentView ? 'Unpin Current View' : 'Pin Current View';
        }

        async function refreshPinState() {
            const data = await fetchJsonWithTimeout('/api/pin/state');
            pinnedOverlayViewId = (data && data.running) ? (data.view || '') : '';
            syncPinControls();
        }

        async function launchPinnedOverlay(viewId) {
            const res = await fetch('/api/pin/launch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ view: viewId, alpha: 0.95 })
            });
            const data = await res.json();
            if (!data.ok) {
                alert(data.message || 'Failed to pin view');
                return;
            }
            pinnedOverlayViewId = data.view || '';
            syncPinControls();
        }

        async function clearPinnedView() {
            await fetch('/api/pin/close', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
            pinnedOverlayViewId = '';
            syncPinControls();
        }

        async function togglePinCurrentView() {
            if (pinnedOverlayViewId === currentView) {
                await clearPinnedView();
                return;
            }
            await launchPinnedOverlay(currentView);
        }

        async function sendCmd(target, command, args) {
            const res = await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target, command, args })
            });
            const data = await res.json();
            document.getElementById('toast').textContent = data.ok ? ('Command queued: ' + command) : ('Command failed: ' + (data.message || 'unknown error'));
            refresh();
        }

        function refreshTargetDropdown(agents) {
            const target = document.getElementById('target');
            if (!target) return;
            const current = target.value;
            target.innerHTML = '';
            const keys = Object.keys(agents || {});
            for (const key of keys) {
                const op = document.createElement('option');
                op.value = key;
                op.textContent = key;
                target.appendChild(op);
            }
            if (current && keys.includes(current)) target.value = current;
        }

        async function refreshChatEndpoints() {
            const data = await fetchJsonWithTimeout('/api/model/endpoints');
            const endpoints = (data && data.endpoints && typeof data.endpoints === 'object') ? Object.keys(data.endpoints) : [];
            const chat = document.getElementById('chat_endpoint');
            const maker = document.getElementById('maker_endpoint');
            const override = document.getElementById('maker_override_endpoint');
            if (chat) {
                const selected = chat.value;
                chat.innerHTML = endpoints.map((e) => `<option value="${e}">${e}</option>`).join('');
                if (selected && endpoints.includes(selected)) chat.value = selected;
            }
            if (maker) {
                const selected = maker.value;
                maker.innerHTML = endpoints.map((e) => `<option value="${e}">${e}</option>`).join('');
                if (selected && endpoints.includes(selected)) maker.value = selected;
            }
            if (override) {
                const selected = override.value;
                override.innerHTML = '<option value="">(agent default)</option>' + endpoints.map((e) => `<option value="${e}">${e}</option>`).join('');
                if (selected && endpoints.includes(selected)) override.value = selected;
            }
        }

        function renderChat() {
            const root = document.getElementById('chat_log');
            if (!root) return;
            if (!chatHistory.length) {
                root.textContent = 'No messages yet.';
                return;
            }
            root.textContent = chatHistory.map((m) => `${m.role.toUpperCase()} (${m.endpoint}): ${m.content}`).join('\n\n');
        }

        async function sendChat() {
            const endpoint = (document.getElementById('chat_endpoint').value || '').trim();
            const system = (document.getElementById('chat_system').value || '').trim();
            const prompt = (document.getElementById('chat_prompt').value || '').trim();
            if (!endpoint || !prompt) {
                alert('endpoint and prompt are required');
                return;
            }
            chatHistory.push({ role: 'user', endpoint, content: prompt });
            renderChat();
            document.getElementById('chat_prompt').value = '';
            const res = await fetch('/api/model/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ endpoint, system, prompt })
            });
            const data = await res.json();
            chatHistory.push({ role: 'assistant', endpoint, content: data.text || data.message || JSON.stringify(data) });
            renderChat();
        }

        async function refreshAgentMaker() {
            const data = await fetchJsonWithTimeout('/api/model/agents');
            const agents = (data && data.agents && typeof data.agents === 'object') ? data.agents : {};
            const names = Object.keys(agents);
            document.getElementById('maker_agents').textContent = names.length ? JSON.stringify(agents, null, 2) : 'No agents defined.';
            const sel = document.getElementById('maker_agent_select');
            if (sel) {
                const current = sel.value;
                sel.innerHTML = names.map((n) => `<option value="${n}">${n}</option>`).join('');
                if (current && names.includes(current)) sel.value = current;
            }
        }

        async function createAgentProfile() {
            const payload = {
                name: (document.getElementById('maker_name').value || '').trim(),
                endpoint: (document.getElementById('maker_endpoint').value || '').trim(),
                system: (document.getElementById('maker_system').value || '').trim(),
            };
            if (!payload.name || !payload.endpoint) {
                alert('name and endpoint are required');
                return;
            }
            const res = await fetch('/api/model/agents/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const data = await res.json();
            document.getElementById('maker_result').textContent = JSON.stringify(data, null, 2);
            await refreshAgentMaker();
        }

        async function runAgentProfile() {
            const payload = {
                name: (document.getElementById('maker_agent_select').value || '').trim(),
                task: (document.getElementById('maker_task').value || '').trim(),
                endpoint: (document.getElementById('maker_override_endpoint').value || '').trim(),
            };
            if (!payload.name || !payload.task) {
                alert('name and task are required');
                return;
            }
            const res = await fetch('/api/model/agents/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const data = await res.json();
            document.getElementById('maker_result').textContent = JSON.stringify(data, null, 2);
        }

        async function deleteAgentProfile() {
            const payload = { name: (document.getElementById('maker_agent_select').value || '').trim() };
            if (!payload.name) {
                alert('select an agent first');
                return;
            }
            const res = await fetch('/api/model/agents/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const data = await res.json();
            document.getElementById('maker_result').textContent = JSON.stringify(data, null, 2);
            await refreshAgentMaker();
        }

        async function refreshSecurityState() {
            const data = await fetchJsonWithTimeout('/api/security/state');
            document.getElementById('security_findings').textContent = JSON.stringify(data, null, 2);
        }

        async function runSecurityScan() {
            const path = (document.getElementById('security_scan_path').value || '').trim();
            const res = await fetch('/api/security/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) });
            const data = await res.json();
            document.getElementById('security_findings').textContent = JSON.stringify(data, null, 2);
        }

        async function refreshSecretsList() {
            const data = await fetchJsonWithTimeout('/api/security/secrets');
            document.getElementById('security_secrets').textContent = JSON.stringify(data, null, 2);
        }

        function sendManual() {
            const target = (document.getElementById('target').value || '').trim();
            const command = (document.getElementById('command').value || '').trim();
            if (!target || !command) {
                alert('target and command are required');
                return;
            }
            let args = {};
            try {
                args = JSON.parse(document.getElementById('args').value || '{}');
            } catch {
                alert('args must be valid JSON');
                return;
            }
            sendCmd(target, command, args);
        }

        function renderAgents(agentState) {
            const root = document.getElementById('agents');
            if (!root) return;
            const entries = Object.entries(agentState || {}).map(([name, info]) => {
                const klass = (info && info.health) || 'offline';
                const seen = (info && info.last_seen) || 'never';
                return '<div class="agent-item"><strong>' + name + '</strong><span class="pill ' + klass + '">' + klass + '</span><div class="muted">' + seen + '</div></div>';
            }).join('');
            root.innerHTML = entries || '<div class="muted">No agents found.</div>';
        }

        async function refresh() {
            document.getElementById('toast').textContent = 'Refreshing...';

            const statusData = await fetchJsonWithTimeout('/api/status');
            const eventsData = await fetchJsonWithTimeout('/api/events?limit=40');
            const snapData = await fetchJsonWithTimeout('/api/snapshot');
            const sealData = await fetchJsonWithTimeout('/api/archivist/seal');

            if (statusData && statusData.agent_state) {
                renderAgents(statusData.agent_state);
                refreshTargetDropdown(statusData.agent_state);
            } else {
                document.getElementById('agents').innerHTML = '<div class="muted">Status unavailable.</div>';
            }

            document.getElementById('events').textContent = JSON.stringify((eventsData && eventsData.items) ? eventsData.items : eventsData, null, 2);
            document.getElementById('snapshot').textContent = JSON.stringify(snapData, null, 2);
            document.getElementById('seal').textContent = JSON.stringify(sealData, null, 2);

            const failed = [statusData, eventsData, snapData, sealData].filter(x => x && x.ok === false).length;
            document.getElementById('toast').textContent = failed ? ('Loaded with ' + failed + ' endpoint issue(s).') : 'Loaded successfully.';
        }

        // === SoundStage Bundle UI Logic ===
        async function exportSoundstageBundle() {
            const btn = event && event.target;
            if (btn) btn.disabled = true;
            try {
                const res = await fetch('/api/soundstage/export_bundle', { method: 'POST' });
                if (!res.ok) throw new Error('Export failed');
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'exported.B4Gsoundstage';
                document.body.appendChild(a);
                a.click();
                setTimeout(() => { document.body.removeChild(a); window.URL.revokeObjectURL(url); }, 100);
                setSoundSchemeStatus('Exported bundle downloaded.');
            } catch (e) {
                setSoundSchemeStatus('Export failed: ' + e);
            } finally {
                if (btn) btn.disabled = false;
            }
        }

        function showImportBundleDialog() {
            document.getElementById('soundstage_bundle_file').click();
        }

        async function handleImportBundle(event) {
            const file = event.target.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('bundle', file);
            formData.append('scheme_name', file.name.replace(/\\.B4Gsoundstage$/i, ''));
            setSoundSchemeStatus('Importing bundle...');
            try {
                const res = await fetch('/api/soundstage/import_bundle', { method: 'POST', body: formData });
                const data = await res.json();
                if (!data.ok) throw new Error(data.message || 'Import failed');
                setSoundSchemeStatus('Imported: ' + data.message);
                await listSoundstageSchemes();
            } catch (e) {
                setSoundSchemeStatus('Import failed: ' + e);
            }
        }

        async function listSoundstageSchemes() {
            try {
                const res = await fetch('/api/soundstage/list_schemes');
                const data = await res.json();
                if (!data.ok) throw new Error('Failed to list schemes');
                const el = document.getElementById('soundstage_schemes_list');
                if (el) {
                    el.innerHTML = 'Available Schemes: ' + (data.schemes && data.schemes.length ? data.schemes.map(s => `<span class="pill">${s}</span>`).join(' ') : 'None');
                }
            } catch (e) {
                setSoundSchemeStatus('Failed to list schemes: ' + e);
            }
        }

        function setSoundSchemeStatus(msg) {
            const el = document.getElementById('sound_scheme_status');
            if (el) el.textContent = msg;
        }

        function saveSoundScheme() {
            setSoundSchemeStatus('Save Scheme is not yet wired in this build.');
        }

        function loadSoundScheme() {
            document.getElementById('sound_scheme_file').click();
        }

        function createNewScheme() {
            soundScheme = { name: 'new-scheme', created_at: new Date().toISOString() };
            renderSoundEvents();
            setSoundSchemeStatus('Created in-memory scheme draft.');
        }

        async function handleSchemeFile(event) {
            const file = event.target.files[0];
            if (!file) return;
            try {
                const text = await file.text();
                soundScheme = JSON.parse(text);
                renderSoundEvents();
                setSoundSchemeStatus('Loaded scheme from file: ' + file.name);
            } catch (e) {
                setSoundSchemeStatus('Failed to load scheme file: ' + e);
            }
        }

        // Call on load
        switchView(currentView);
        refreshPinState();
        refreshChatEndpoints();
        refreshAgentMaker();
        refreshSecurityState();
        refreshSecretsList();
        refresh();
        listSoundstageSchemes();
        setInterval(refresh, 4000);
        setInterval(refreshPinState, 3000);
    

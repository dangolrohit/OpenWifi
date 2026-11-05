'use strict';
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const message = document.getElementById('message');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const bytes = n => { if (n < 1024) return n + ' B'; let i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), 4); return (n / 1024 ** i).toFixed(2) + ' ' + ['B', 'KB', 'MB', 'GB', 'TB'][i]; };
async function api(path, data) { const opts = { cache: 'no-store' }; if (data !== undefined) Object.assign(opts, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(data) }); const r = await fetch(path, opts); const d = await r.json(); if (r.status === 401 && path != '/api/login') { location.replace('/login'); throw Error('Session ended'); } if (!r.ok) throw Error(d.error || 'Request failed'); return d; }
function error(e) { message.textContent = e.message; message.className = 'status error'; }
const login = document.getElementById('login-form');
if (login) { login.onsubmit = async e => { e.preventDefault(); const b = login.querySelector('button'); b.disabled = true; message.textContent = 'Signing in…'; try { await api('/api/login', { username: login.username.value, password: login.password.value }); location.replace('/dashboard'); } catch (e) { error(e); b.disabled = false; } }; }
else {
    const pages = {
        dashboard: ['Dashboard', 'A clear view of your network, family devices, and customer isolation.'],
        wifi: ['Wifi Settings', 'Manage the access point and wireless configuration.'],
        devices: ['Connected Device', 'Review devices, assign nicknames, set speed limits, and manage curfews.'],
        filtering: ['Device Filtering', 'Control IPv4 internet access by device address.'],
        usages: ['Usages', 'Network traffic measured on the access-point interface.'],
        activity: ['Activity Logs', 'Monitor website and domain requests from connected devices.'],
        plans: ['Plans & Hotspot', 'Configure guest captive portal plans, vouchers, and active hotspot sessions.'],
        logs: ['User Logs', 'Review administrator activity in this portal.'],
        settings: ['Settings', 'Portal preferences and connection details.']
    };
    const key = location.pathname.split('/')[1] || 'dashboard'; const [title, subtitle] = pages[key] || pages.dashboard;
    document.title = title + ' · OshinWiFi'; document.getElementById('title').textContent = title; document.getElementById('crumb').textContent = title; document.getElementById('subtitle').textContent = subtitle;
    const activeNav = document.querySelector(`nav a[href="/${pages[key] ? key : 'dashboard'}"]`);
    if (activeNav) activeNav.classList.add('active');
    const menu = document.getElementById('menu'); menu.onclick = () => { const open = document.getElementById('sidebar').classList.toggle('open'); menu.setAttribute('aria-expanded', String(open)); };
    document.getElementById('logout').onclick = async () => { try { await api('/api/logout', {}); location.replace('/login'); } catch (e) { error(e); } };
    const page = document.getElementById('page'); let loading = false, previousUsage = null, timer = null, currentDevices = [];
    const detail = (name, value) => `<div class="detail"><span>${esc(name)}</span><strong>${esc(value)}</strong></div>`;
    const card = (label, value, foot) => `<div class="card"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(foot)}</small></div>`;

    function groupBadge(group) {
        if (group === 'family') return '<span class="badge group-family">Family</span>';
        if (group === 'customer') return '<span class="badge group-customer" title="Isolated from LAN, Admin portal locked">Customer 🔒</span>';
        if (group === 'staff') return '<span class="badge group-staff">Staff</span>';
        return '<span class="badge group-default">Unassigned</span>';
    }

    function statusBadge(dev) {
        if (dev.blocked) return '<span class="badge off">Blocked</span>';
        if (dev.scheduled) return '<span class="badge off" title="Curfew active">🌙 Curfew Active</span>';
        if (dev.guest_session) {
            const rem = Math.max(0, Math.floor(dev.guest_session.expires_at - (Date.now() / 1000)));
            const m = Math.floor(rem / 60);
            return `<span class="badge on" title="Guest session active">🎟 ${m}m left</span>`;
        }
        if (dev.schedule && dev.schedule.enabled) return `<span class="badge" title="Schedule active between ${dev.schedule.start} and ${dev.schedule.end}">⏱ ${dev.schedule.start}-${dev.schedule.end}</span>`;
        return '<span class="badge">Active</span>';
    }

    function openEditModal(dev) {
        const existing = document.getElementById('edit-modal');
        if (existing) existing.remove();
        const sched = dev.schedule || { enabled: false, start: '22:00', end: '06:00' };
        const modalHtml = `
        <div class="modal-backdrop" id="edit-modal">
            <div class="modal">
                <h3>Configure Device: ${esc(dev.name || dev.ip)}</h3>
                <p class="muted" style="margin-top:-8px; margin-bottom:16px;">IP: ${esc(dev.ip)} ${dev.mac ? '· MAC: ' + esc(dev.mac) : ''}</p>
                <form id="device-edit-form">
                    <div class="form-row">
                        <label for="edit-name">Device Nickname</label>
                        <input id="edit-name" value="${esc(dev.name || '')}" placeholder="e.g. Dad's iPhone, Living Room TV, Table 4 Customer">
                    </div>
                    <div class="form-row">
                        <label for="edit-group">Network Group</label>
                        <select id="edit-group">
                            <option value="family" ${dev.group === 'family' ? 'selected' : ''}>Family (Bypasses captive portal, full LAN access)</option>
                            <option value="customer" ${dev.group === 'customer' ? 'selected' : ''}>Customer / Guest (Isolated from LAN, Admin portal locked)</option>
                            <option value="staff" ${dev.group === 'staff' ? 'selected' : ''}>Staff / Business</option>
                            <option value="default" ${dev.group === 'default' ? 'selected' : ''}>Default / Unassigned</option>
                        </select>
                    </div>
                    <div class="form-row">
                        <label for="edit-speed">Bandwidth Speed Limit (QoS)</label>
                        <select id="edit-speed">
                            <option value="0" ${dev.speed_limit === 0 ? 'selected' : ''}>Unlimited (Full gateway speed)</option>
                            <option value="2" ${dev.speed_limit === 2 ? 'selected' : ''}>2 Mbps (Light browsing)</option>
                            <option value="5" ${dev.speed_limit === 5 ? 'selected' : ''}>5 Mbps (Recommended for customers)</option>
                            <option value="10" ${dev.speed_limit === 10 ? 'selected' : ''}>10 Mbps (Fast streaming)</option>
                            <option value="20" ${dev.speed_limit === 20 ? 'selected' : ''}>20 Mbps (High bandwidth)</option>
                        </select>
                    </div>
                    <div class="form-row">
                        <label class="checkbox-label">
                            <input type="checkbox" id="edit-sched-enabled" ${sched.enabled ? 'checked' : ''}>
                            Enable Access Schedule (Bedtime / Curfew)
                        </label>
                        <div id="sched-box" style="margin-top:10px; ${sched.enabled ? '' : 'display:none;'}">
                            <label>Block internet between:</label>
                            <div class="time-inputs">
                                <input type="time" id="edit-sched-start" value="${esc(sched.start || '22:00')}">
                                <span>to</span>
                                <input type="time" id="edit-sched-end" value="${esc(sched.end || '06:00')}">
                            </div>
                            <small class="muted">Internet access for this device will be automatically blocked during this window.</small>
                        </div>
                    </div>
                    <div class="modal-actions">
                        <button type="button" class="secondary" id="modal-cancel">Cancel</button>
                        <button type="submit" id="modal-save">Save Settings</button>
                    </div>
                </form>
            </div>
        </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = document.getElementById('edit-modal');
        const form = document.getElementById('device-edit-form');
        const schedCheck = document.getElementById('edit-sched-enabled');
        const schedBox = document.getElementById('sched-box');
        schedCheck.onchange = () => { schedBox.style.display = schedCheck.checked ? 'block' : 'none'; };
        document.getElementById('modal-cancel').onclick = () => { modal.remove(); };
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
        form.onsubmit = async (e) => {
            e.preventDefault();
            const saveBtn = document.getElementById('modal-save');
            saveBtn.disabled = true;
            try {
                await api('/api/device/update', {
                    ip: dev.ip,
                    name: document.getElementById('edit-name').value.trim(),
                    group: document.getElementById('edit-group').value,
                    speed_limit: Number(document.getElementById('edit-speed').value),
                    schedule: {
                        enabled: schedCheck.checked,
                        start: document.getElementById('edit-sched-start').value || '22:00',
                        end: document.getElementById('edit-sched-end').value || '06:00'
                    }
                });
                modal.remove();
                await load();
            } catch (err) {
                error(err);
                saveBtn.disabled = false;
            }
        };
    }

    function deviceTable(data, filtered = false) {
        currentDevices = data.devices;
        const rows = filtered ? data.devices.filter(x => x.blocked || x.scheduled) : data.devices;
        return `<div class="tablewrap"><table><thead><tr><th>Device & Identity</th><th>MAC address</th><th>Group</th><th>Speed limit</th><th>Access status</th><th>Action</th></tr></thead><tbody>${rows.map(x => `<tr data-search="${esc((x.name || '') + ' ' + x.ip + ' ' + x.mac + ' ' + x.group)}"><td><strong>${esc(x.name || x.ip)}</strong>${x.name ? `<br><small class="muted">${esc(x.ip)}</small>` : ''}${x.ip === data.client ? ' <span class="muted">(you)</span>' : ''}</td><td>${esc(x.mac || 'Unknown')}</td><td>${groupBadge(x.group)}</td><td>${x.speed_limit ? esc(x.speed_limit) + ' Mbps' : '<span class="muted">Unlimited</span>'}</td><td>${statusBadge(x)}</td><td><div class="row-actions"><button class="secondary small" data-edit="${esc(x.ip)}" title="Configure nickname, speed limit, and schedule">⚙ Edit</button><a class="button secondary small" href="/activity?ip=${esc(x.ip)}" title="View activity for ${esc(x.ip)}">Activity</a><button class="${x.blocked ? '' : 'danger'} small" data-action="${x.blocked ? 'unblock' : 'block'}" data-ip="${esc(x.ip)}" ${x.ip === data.client && !x.blocked ? 'disabled' : ''}>${x.blocked ? 'Unblock' : 'Block'}</button></div></td></tr>`).join('')}</tbody></table>${rows.length ? '' : '<div class="empty">' + (filtered ? 'No blocked addresses.' : 'No devices discovered yet. Connect a device and browse, then refresh.') + '</div>'}</div>`;
    }

    function wireActions() {
        page.querySelectorAll('[data-action]').forEach(b => {
            b.onclick = async () => {
                if (!confirm(`${b.dataset.action === 'block' ? 'Block' : 'Unblock'} IPv4 internet access for ${b.dataset.ip}?`)) return;
                b.disabled = true;
                try { await api('/api/action', { action: b.dataset.action, ip: b.dataset.ip }); await load(); } catch (e) { error(e); b.disabled = false; }
            };
        });
        page.querySelectorAll('[data-edit]').forEach(b => {
            b.onclick = () => {
                const dev = currentDevices.find(d => d.ip === b.dataset.edit);
                if (dev) openEditModal(dev);
            };
        });
        const search = document.getElementById('search');
        if (search) search.oninput = () => {
            page.querySelectorAll('tr[data-search]').forEach(row => {
                row.hidden = !row.dataset.search.toLowerCase().includes(search.value.toLowerCase());
            });
        };
    }

    async function load() {
        if (loading) return; loading = true; message.className = 'status'; message.textContent = 'Updating…'; try {
            if (['dashboard', 'devices', 'filtering'].includes(key)) {
                const data = await api('/api/devices');
                currentDevices = data.devices;
                const blocked = data.devices.filter(x => x.blocked || x.scheduled).length;
                const familyCount = data.devices.filter(x => x.group === 'family').length;
                const customerCount = data.devices.filter(x => x.group === 'customer').length;
                if (key === 'dashboard') {
                    page.innerHTML = `
                    <div class="cards">
                        ${card('Total devices', data.devices.length, 'Discovered on Wi-Fi')}
                        ${card('Family devices', familyCount, 'Bypasses captive portal')}
                        ${card('Customers (Isolated)', customerCount, 'Portal locked · QoS capped')}
                    </div>
                    <div class="notice"><strong>Network Security Active:</strong> Devices marked as <em>Customer</em> are blocked from opening the administrator portal (port 8090) and isolated from accessing family devices. Speed limits (QoS) and access curfews apply automatically.</div>
                    <div class="split">
                        <section class="panel">
                            <h2>Network configuration</h2>
                            ${detail('Wireless network', 'OshinWiFi (configured name)')}
                            ${detail('Gateway', '192.168.16.2 · Ubuntu')}
                            ${detail('Access point', '192.168.16.1 · AP mode')}
                            ${detail('Captive Hotspot', 'Port 8088 · Active')}
                        </section>
                        <section class="panel">
                            <h2>Access & QoS controls</h2>
                            <p>Assign friendly device nicknames, separate customers from family devices, set bandwidth caps, or configure bedtime curfews.</p>
                            <a class="button" href="/devices">Manage devices & limits →</a>
                        </section>
                    </div>
                    <section class="panel">
                        <h2>Device overview</h2>
                        ${deviceTable(data)}
                    </section>`;
                } else {
                    page.innerHTML = `
                    <div class="notice">${key === 'filtering' ? 'Blocks apply to routed IPv4 traffic. Wi-Fi association and local communication remain available. A changed IP can bypass a rule.' : 'Assign friendly names, categorize devices into Family vs. Customer, enforce speed limits, and set automatic access curfews.'}</div>
                    <section class="panel">
                        <h2>${key === 'filtering' ? 'Blocked addresses' : 'Discovered devices'}</h2>
                        <input class="search" id="search" placeholder="Search by name, IP, MAC address, or group" aria-label="Search devices">
                        ${deviceTable(data, key === 'filtering')}
                        ${key === 'filtering' ? '<p class="muted">To edit device groups or speed limits, open <a href="/devices">Connected Device</a>.</p>' : ''}
                    </section>`;
                }
                wireActions();
            } else if (key === 'wifi') {
                page.innerHTML = `<section class="panel"><h2>Wireless access point</h2>${detail('Router', 'LB-Link BL-WR450H')}${detail('Mode', 'AP mode — configured during setup')}${detail('Wi-Fi name', 'OshinWiFi — configured during setup')}${detail('Management address', '192.168.16.1')}<div class="notice">Direct router integration is not configured. Change the Wi-Fi name, password, channel, and guest settings in the router’s own admin page.</div><a class="button" href="http://192.168.16.1" target="_blank" rel="noopener noreferrer">Open router settings ↗</a></section>`;
            } else if (key === 'usages') {
                const u = await api('/api/usage'); let speed = 'Collecting'; if (previousUsage && u.at > previousUsage.at && u.upload >= previousUsage.upload && u.download >= previousUsage.download) speed = bytes((u.upload + u.download - previousUsage.upload - previousUsage.download) / (u.at - previousUsage.at)) + '/s'; previousUsage = u;
                page.innerHTML = `<div class="cards">${card('Received from Wi-Fi side', bytes(u.upload), 'Interface RX total')}${card('Sent to Wi-Fi side', bytes(u.download), 'Interface TX total')}${card('Combined traffic rate', speed, 'Average between refreshes')}</div><section class="panel"><h2>What these totals measure</h2><p>These are real aggregate Ethernet-interface counters. They include local traffic and dashboard requests, and reset when the interface counters reset. They are not per-device or monthly internet totals.</p><div class="notice">Per-device usage history has not been enabled. No fabricated traffic charts or usage records are shown.</div></section>`;
            } else if (key === 'activity') {
                const urlParams = new URLSearchParams(location.search);
                const filterIp = urlParams.get('ip') || '';
                const d = await api('/api/activity' + (filterIp ? `?ip=${encodeURIComponent(filterIp)}` : ''));
                const total = d.queries ? d.queries.length : 0;
                const uniqueClients = d.queries ? new Set(d.queries.map(q => q.client)).size : 0;
                page.innerHTML = `
                <div class="cards">
                    ${card('Recorded queries', total, filterIp ? 'Filtered for ' + filterIp : 'All client devices')}
                    ${card('Active querying devices', uniqueClients, 'Devices seen in DNS log')}
                    ${card('DNS logger status', d.log_exists ? 'Active' : 'Standby', d.log_exists ? '/var/log/dnsmasq.log' : 'Awaiting DNS lookups')}
                </div>
                <div class="notice">DNS query logs record domain name lookups (e.g. youtube.com, instagram.com) routed through your gateway. Modern web connections use TLS/HTTPS encryption, so webpage contents, search queries, passwords, and chat messages remain encrypted. Devices with 'Private DNS' (DoH / DoT) enabled bypass local DNS logging.</div>
                <section class="panel">
                    <h2>Device browsing activity</h2>
                    <div class="activity-toolbar">
                        <select id="activity-device" aria-label="Select device">
                            <option value="">All Connected Devices (${(d.devices || []).length})</option>
                            ${(d.devices || []).map(dev => `<option value="${esc(dev.ip)}" ${filterIp === dev.ip ? 'selected' : ''}>${esc(dev.name ? dev.name + ' (' + dev.ip + ')' : dev.ip)}${dev.ip === d.client ? ' (you)' : ''}</option>`).join('')}
                        </select>
                        <input class="search" id="activity-search" placeholder="Filter by domain or IP (e.g. youtube, google)" aria-label="Search activity">
                        <button class="secondary" id="clear-activity">Clear activity history</button>
                    </div>
                    <div class="tablewrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Client Device</th>
                                    <th>Domain / Website</th>
                                    <th>Query Type</th>
                                </tr>
                            </thead>
                            <tbody id="activity-rows">
                                ${(d.queries || []).map(q => `<tr data-search="${esc(q.domain + ' ' + q.client)}"><td>${esc(q.time || 'Recent')}</td><td><strong>${esc(q.client)}</strong>${q.client === d.client ? ' <span class="muted">(you)</span>' : ''}</td><td><span class="domain-pill">${esc(q.domain)}</span></td><td><span class="badge">${esc(q.type)}</span></td></tr>`).join('')}
                            </tbody>
                        </table>
                        ${total ? '' : '<div class="empty">No domain lookups recorded yet. Connect a device to Wi-Fi and browse websites, then refresh.</div>'}
                    </div>
                </section>`;
                const devSelect = document.getElementById('activity-device');
                if (devSelect) devSelect.onchange = () => {
                    const val = devSelect.value;
                    const newUrl = val ? `/activity?ip=${encodeURIComponent(val)}` : '/activity';
                    history.pushState(null, '', newUrl);
                    load();
                };
                const actSearch = document.getElementById('activity-search');
                if (actSearch) actSearch.oninput = () => {
                    const term = actSearch.value.toLowerCase();
                    document.querySelectorAll('#activity-rows tr[data-search]').forEach(row => {
                        row.hidden = !row.dataset.search.toLowerCase().includes(term);
                    });
                };
                const clearBtn = document.getElementById('clear-activity');
                if (clearBtn) clearBtn.onclick = async () => {
                    if (!confirm('Clear all recorded DNS activity logs?')) return;
                    clearBtn.disabled = true;
                    try { await api('/api/activity/clear', {}); await load(); } catch (e) { error(e); clearBtn.disabled = false; }
                };
            } else if (key === 'plans') {
                const data = await api('/api/plans');
                const guests = Object.values(data.guests || {});
                const now = Date.now() / 1000;
                const activeGuests = guests.filter(g => g.expires_at > now);
                const vouchers = Object.values(data.vouchers || {});
                const unusedVouchers = vouchers.filter(v => !v.used);
                const plans = data.plans || [];

                page.innerHTML = `
                <div class="cards">
                    ${card('Hotspot Barrier', data.captive_enabled ? 'Active' : 'Disabled', data.captive_enabled ? 'Enforcing login portal' : 'Open access for all')}
                    ${card('Active Guests', activeGuests.length, 'Currently connected')}
                    ${card('Unused Vouchers', unusedVouchers.length, 'Available for customers')}
                </div>
                <div class="notice">
                    <strong>Captive Hotspot Portal:</strong> Customer devices connecting to Wi-Fi are redirected to the guest login page until authorized. Devices tagged as <em>Family</em> automatically bypass the portal.
                    <button class="secondary small" id="toggle-captive-btn" style="margin-left:12px;">${data.captive_enabled ? 'Disable Hotspot Barrier' : 'Enable Hotspot Barrier'}</button>
                </div>

                <!-- Active Guest Sessions -->
                <section class="panel">
                    <h2>Active Customer Hotspot Sessions</h2>
                    <div class="tablewrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Client IP</th>
                                    <th>Plan</th>
                                    <th>Time Remaining</th>
                                    <th>Speed Limit</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${activeGuests.map(g => {
                                    const rem = Math.max(0, Math.floor(g.expires_at - now));
                                    const m = Math.floor(rem / 60);
                                    const s = rem % 60;
                                    return `<tr>
                                        <td><strong>${esc(g.ip)}</strong></td>
                                        <td>${esc(g.plan_id)}</td>
                                        <td><span class="badge ${rem < 300 ? 'off' : ''}">⏱ ${m}m ${s < 10 ? '0' : ''}${s}s</span></td>
                                        <td>${g.speed_limit ? g.speed_limit + ' Mbps' : 'Unlimited'}</td>
                                        <td>
                                            <div class="row-actions">
                                                <button class="secondary small" data-extend="${esc(g.ip)}" title="Add 30 minutes">+30m</button>
                                                <button class="danger small" data-revoke="${esc(g.ip)}">Disconnect</button>
                                            </div>
                                        </td>
                                    </tr>`;
                                }).join('')}
                            </tbody>
                        </table>
                        ${activeGuests.length ? '' : '<div class="empty">No active guest sessions. When customers connect and accept a plan, their sessions appear here.</div>'}
                    </div>
                </section>

                <!-- 5 Customizable Access Plans -->
                <section class="panel">
                    <h2>Hotspot Access Plans (5 Configurable Plans)</h2>
                    <p class="muted">Adjust the duration, bandwidth speed limit, and authorization mode for each plan.</p>
                    <form id="plans-form">
                        <div class="plans-grid">
                            ${plans.map((p, idx) => `
                            <div class="plan-card ${p.active ? 'active-plan' : ''}">
                                <h3>
                                    <span>Plan ${idx + 1}: ${esc(p.name)}</span>
                                    <label class="checkbox-label" style="font-size:12px;">
                                        <input type="checkbox" name="active_${p.id}" ${p.active ? 'checked' : ''}> Active
                                    </label>
                                </h3>
                                <label>Plan Name</label>
                                <input name="name_${p.id}" value="${esc(p.name)}" required>
                                <label>Access Mode</label>
                                <select name="type_${p.id}">
                                    <option value="click" ${p.type === 'click' ? 'selected' : ''}>One-Click Agreement (Free)</option>
                                    <option value="voucher" ${p.type === 'voucher' ? 'selected' : ''}>Voucher Code Required</option>
                                </select>
                                <div style="display:flex; gap:10px;">
                                    <div style="flex:1;">
                                        <label>Duration (mins)</label>
                                        <input type="number" name="duration_${p.id}" value="${p.duration_minutes}" min="1" max="43200" required>
                                    </div>
                                    <div style="flex:1;">
                                        <label>Speed (Mbps)</label>
                                        <input type="number" name="speed_${p.id}" value="${p.speed_limit}" min="0" max="1000" required>
                                    </div>
                                </div>
                            </div>
                            `).join('')}
                        </div>
                        <div style="margin-top:20px; text-align:right;">
                            <button type="submit" id="save-plans-btn">Save All Plans</button>
                        </div>
                    </form>
                </section>

                <!-- Voucher Management -->
                <section class="panel">
                    <h2>Customer Vouchers</h2>
                    <p class="muted">Generate single-use access PINs for customers using your paid or extended plans.</p>
                    <div class="activity-toolbar">
                        <select id="voucher-plan-select" aria-label="Select Plan">
                            ${plans.filter(p => p.type === 'voucher').map(p => `<option value="${esc(p.id)}">${esc(p.name)} (${p.duration_minutes}m · ${p.speed_limit ? p.speed_limit + ' Mbps' : 'Unlimited'})</option>`).join('')}
                        </select>
                        <button id="gen-voucher-btn" class="button" style="width:auto;">+ Generate Voucher PIN</button>
                    </div>
                    <div class="tablewrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Voucher PIN</th>
                                    <th>Assigned Plan</th>
                                    <th>Created Date</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${vouchers.map(v => `
                                <tr>
                                    <td><span class="voucher-pill">${esc(v.code)}</span></td>
                                    <td>${esc(v.plan_id)}</td>
                                    <td>${esc(new Date(v.created_at * 1000).toLocaleString())}</td>
                                    <td>${v.used ? `<span class="badge off">Used by ${esc(v.used_by || 'Guest')}</span>` : '<span class="badge on">Available</span>'}</td>
                                    <td><button class="secondary small" data-del-voucher="${esc(v.code)}">Delete</button></td>
                                </tr>
                                `).join('')}
                            </tbody>
                        </table>
                        ${vouchers.length ? '' : '<div class="empty">No vouchers generated yet. Click "Generate Voucher PIN" to create one.</div>'}
                    </div>
                </section>
                `;

                document.getElementById('toggle-captive-btn').onclick = async () => {
                    await api('/api/plans/toggle', { enabled: !data.captive_enabled });
                    await load();
                };

                document.querySelectorAll('[data-extend]').forEach(b => {
                    b.onclick = async () => {
                        await api('/api/guest/extend', { ip: b.dataset.extend, minutes: 30 });
                        await load();
                    };
                });

                document.querySelectorAll('[data-revoke]').forEach(b => {
                    b.onclick = async () => {
                        if (!confirm(`Revoke internet access for guest ${b.dataset.revoke}?`)) return;
                        await api('/api/guest/revoke', { ip: b.dataset.revoke });
                        await load();
                    };
                });

                document.getElementById('gen-voucher-btn').onclick = async () => {
                    const planSelect = document.getElementById('voucher-plan-select');
                    if (!planSelect || !planSelect.value) {
                        alert('No voucher plan configured.');
                        return;
                    }
                    await api('/api/vouchers/create', { plan_id: planSelect.value });
                    await load();
                };

                document.querySelectorAll('[data-del-voucher]').forEach(b => {
                    b.onclick = async () => {
                        await api('/api/vouchers/delete', { code: b.dataset.delVoucher });
                        await load();
                    };
                });

                document.getElementById('plans-form').onsubmit = async (e) => {
                    e.preventDefault();
                    const form = e.target;
                    const saveBtn = document.getElementById('save-plans-btn');
                    saveBtn.disabled = true;
                    try {
                        const updatedPlans = plans.map(p => {
                            return {
                                id: p.id,
                                name: form[`name_${p.id}`].value.trim(),
                                type: form[`type_${p.id}`].value,
                                duration_minutes: Number(form[`duration_${p.id}`].value) || 30,
                                speed_limit: Number(form[`speed_${p.id}`].value) || 0,
                                active: form[`active_${p.id}`].checked,
                                description: p.description || ''
                            };
                        });
                        await api('/api/plans/update', { plans: updatedPlans });
                        message.textContent = 'Plans saved successfully!';
                        message.className = 'status success';
                        await load();
                    } catch (err) {
                        error(err);
                        saveBtn.disabled = false;
                    }
                };
            } else if (key === 'logs') {
                const d = await api('/api/logs'); page.innerHTML = `<div class="notice">Administrator sign-ins, sign-outs, and filtering actions only. To view website domains looked up by Wi-Fi clients, see <a href="/activity">Activity Logs</a>. The latest 300 events are kept in memory and reset when the service restarts.</div><section class="panel"><h2>Recent administrator activity</h2><div class="tablewrap"><table><thead><tr><th>Time</th><th>Activity</th><th>Admin address</th><th>Target</th></tr></thead><tbody>${d.events.map(e => `<tr><td>${esc(new Date(e.time * 1000).toLocaleString())}</td><td>${esc(e.action)}</td><td>${esc(e.client)}</td><td>${esc(e.target || '—')}</td></tr>`).join('')}</tbody></table>${d.events.length ? '' : '<div class="empty">No events in this service session.</div>'}</div></section>`;
            } else if (key === 'settings') {
                page.innerHTML = `<div class="split"><section class="panel"><h2>Display preferences</h2><label for="interval">Automatic refresh</label><select id="interval" class="settings-select"><option value="0">Off — refresh manually</option><option value="10">Every 10 seconds</option><option value="30">Every 30 seconds</option><option value="60">Every minute</option></select><p class="muted">Saved in this browser. Applies to devices, usage, activity, plans, and logs.</p></section><section class="panel"><h2>Administrator session</h2>${detail('Username', 'admin')}${detail('Idle timeout', '30 minutes')}${detail('Maximum session', '8 hours')}${detail('Authentication', 'Login page + secure session cookie')}</section></div><section class="panel"><h2>Network configuration</h2>${detail('Gateway', '192.168.16.2/24')}${detail('Downstream interface', 'enp1s0')}${detail('Router', '192.168.16.1')}${detail('Portal version', '2.3')}<p class="muted">Network configuration is shown for reference; editing it here is not enabled.</p></section>`; let value = '0'; try { value = localStorage.getItem('oshin-refresh') || '0'; } catch { } const select = document.getElementById('interval'); select.value = value; select.onchange = () => { try { localStorage.setItem('oshin-refresh', select.value); } catch { } schedule(); };
            }
            message.textContent = 'Updated ' + new Date().toLocaleTimeString();
        } catch (e) { error(e); } finally { loading = false; }
    }
    function schedule() { clearInterval(timer); let seconds = 0; try { seconds = Number(localStorage.getItem('oshin-refresh')); } catch { } if ([10, 30, 60].includes(seconds) && !['settings', 'wifi'].includes(key)) timer = setInterval(() => { if (!document.hidden) load(); }, seconds * 1000); }
    document.getElementById('refresh').onclick = load; window.addEventListener('pageshow', e => { if (e.persisted) location.reload(); });
    window.addEventListener('popstate', () => { load(); });
    load(); schedule();
}

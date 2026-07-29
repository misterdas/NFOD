/**
 * Participant Wise Open Interest (OI) Analysis Dashboard - JavaScript Core Engine
 */

// Global State
let rawCSVData = [];
let availableDates = [];
let currentDateIndex = -1;
let chartsInstances = [];

// Instruments metadata
const INSTRUMENTS = [
    {
        id: 'index-futures',
        title: 'Index Futures',
        longCol: 'Future Index Long',
        shortCol: 'Future Index Short'
    },
    {
        id: 'index-calls',
        title: 'Index Call Longs & Shorts',
        longCol: 'Option Index Call Long',
        shortCol: 'Option Index Call Short'
    },
    {
        id: 'index-puts',
        title: 'Index Put Longs & Shorts',
        longCol: 'Option Index Put Long',
        shortCol: 'Option Index Put Short'
    },
    {
        id: 'stock-futures',
        title: 'Stock Futures',
        longCol: 'Future Stock Long',
        shortCol: 'Future Stock Short'
    },
    {
        id: 'stock-calls',
        title: 'Stock Calls Longs & Shorts',
        longCol: 'Option Stock Call Long',
        shortCol: 'Option Stock Call Short'
    },
    {
        id: 'stock-puts',
        title: 'Stock Puts Longs & Shorts',
        longCol: 'Option Stock Put Long',
        shortCol: 'Option Stock Put Short'
    }
];

const PARTICIPANTS = ['Client', 'DII', 'FII', 'Pro'];

// Helper to format numbers in Indian Number System (e.g. 1,76,498)
function formatIndianNum(num) {
    if (num === null || num === undefined || isNaN(num)) return '-';
    if (num === 0) return '0';

    const absVal = Math.abs(num);
    const formatted = absVal.toLocaleString('en-IN');
    return num < 0 ? `-${formatted}` : formatted;
}

// Fallback CSV Parser if API endpoint is not running
function parseCSV(text) {
    const lines = text.trim().split('\n');
    if (lines.length === 0) return [];

    const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
    const records = [];

    for (let i = 1; i < lines.length; i++) {
        if (!lines[i].trim()) continue;
        const row = lines[i].split(',').map(cell => cell.trim().replace(/^"|"$/g, ''));
        const obj = {};
        headers.forEach((h, idx) => {
            let val = row[idx];
            if (h !== 'Client Type' && h !== 'Date' && val !== undefined) {
                val = parseFloat(val) || 0;
            }
            obj[h] = val;
        });
        records.push(obj);
    }
    return records;
}

// Load Data on Startup
async function initDashboard() {
    try {
        // Fetch static CSV directly
        const csvRes = await fetch('FDCP_Data.csv');
        if (!csvRes.ok) throw new Error('Could not fetch FDCP_Data.csv');
        const csvText = await csvRes.text();
        rawCSVData = parseCSV(csvText);

        if (rawCSVData.length === 0) {
            alert('Failed to load FDCP_Data.csv. Please verify the file exists or has data.');
            return;
        }

        // Extract and sort unique trading dates
        const dateSet = new Set(rawCSVData.map(r => r.Date));
        availableDates = Array.from(dateSet);

        // Populate Date Selector
        const selectEl = document.getElementById('date-select');
        selectEl.innerHTML = '';
        availableDates.forEach((d, idx) => {
            const opt = document.createElement('option');
            opt.value = idx;
            opt.textContent = d;
            selectEl.appendChild(opt);
        });

        // Set default to latest available date
        currentDateIndex = availableDates.length - 1;
        selectEl.value = currentDateIndex;

        // Render Dashboard
        renderDashboardForCurrentDate();

        // Setup Event Listeners
        setupEventListeners();

    } catch (err) {
        console.error('Initialization error:', err);
    }
}

// Render Dashboard for currently selected date
function renderDashboardForCurrentDate() {
    if (currentDateIndex < 0 || currentDateIndex >= availableDates.length) return;

    const targetDate = availableDates[currentDateIndex];
    const prevDate1 = currentDateIndex >= 1 ? availableDates[currentDateIndex - 1] : null;
    const prevDate2 = currentDateIndex >= 2 ? availableDates[currentDateIndex - 2] : null;

    // Update Header Date Info
    document.getElementById('footer-date-info').textContent = `Active Date: ${targetDate}`;

    // Filter Data by dates
    const dataToday = getParticipantMap(targetDate);
    const dataT1 = prevDate1 ? getParticipantMap(prevDate1) : null;
    const dataT2 = prevDate2 ? getParticipantMap(prevDate2) : null;

    // Clear and build Summary List items
    const summaryItems = [];

    // Process Each Instrument Block
    INSTRUMENTS.forEach(inst => {
        const blockEl = document.getElementById(`block-${inst.id}`);
        if (!blockEl) return;

        // Update Headers for 3-Day Carried Positions (now in unified thead)
        const thEls = blockEl.querySelectorAll('.unified-table thead th');
        // th indices: 0=Participant, 1-2=Longs, 3-4=Shorts, 5-6=Net, 7=Today, 8=1D, 9=2D
        if (thEls[7]) thEls[7].textContent = 'Today';
        if (thEls[8]) thEls[8].textContent = prevDate1 ? '1D Ago' : '-';
        if (thEls[9]) thEls[9].textContent = prevDate2 ? '2D Ago' : '-';

        const tbody = blockEl.querySelector('.unified-table tbody');
        tbody.innerHTML = '';

        let totalLongChange = 0;
        let totalShortChange = 0;
        let totalNetChange = 0;

        PARTICIPANTS.forEach(p => {
            const todayRow = dataToday[p] || {};
            const t1Row = dataT1 ? dataT1[p] || {} : {};
            const t2Row = dataT2 ? dataT2[p] || {} : {};

            const longToday = todayRow[inst.longCol] || 0;
            const longT1 = t1Row[inst.longCol] || 0;
            const shortToday = todayRow[inst.shortCol] || 0;
            const shortT1 = t1Row[inst.shortCol] || 0;

            const longChange = dataT1 ? longToday - longT1 : 0;
            const shortChange = dataT1 ? shortToday - shortT1 : 0;
            const netChange = longChange - shortChange;

            totalLongChange += longChange;
            totalShortChange += shortChange;
            totalNetChange += netChange;

            // Labels
            let longLabel = '-';
            let longClass = '';
            if (longChange > 0) { longLabel = 'Added'; longClass = 'pos-green'; }
            else if (longChange < 0) { longLabel = 'Closed'; longClass = 'pos-red'; }

            let shortLabel = '-';
            let shortClass = '';
            if (shortChange > 0) { shortLabel = 'Added'; shortClass = 'pos-red'; }
            else if (shortChange < 0) { shortLabel = 'Closed'; shortClass = 'pos-green'; }

            let netLabel = '-';
            let netClass = '';
            if (netChange > 0) { netLabel = 'Bought'; netClass = 'pos-green'; }
            else if (netChange < 0) { netLabel = 'Sold'; netClass = 'pos-red'; }

            // Add to Right-Hand Summary
            if (netChange !== 0) {
                summaryItems.push({
                    participant: p,
                    instrument: inst.title.replace(' Longs & Shorts', ''),
                    action: netLabel,
                    value: netChange,
                    netClass: netClass
                });
            }

            // Carried Net Positions
            const carriedToday = longToday - shortToday;
            const carriedT1 = dataT1 ? (t1Row[inst.longCol] || 0) - (t1Row[inst.shortCol] || 0) : null;
            const carriedT2 = dataT2 ? (t2Row[inst.longCol] || 0) - (t2Row[inst.shortCol] || 0) : null;

            // Create unified row (10 columns)
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="participant-name">${p}s</td>
                <td class="action-label ${longClass}">${longLabel}</td>
                <td class="action-val ${longClass}">${formatIndianNum(longChange)}</td>
                <td class="action-label ${shortClass}">${shortLabel}</td>
                <td class="action-val ${shortClass}">${formatIndianNum(shortChange)}</td>
                <td class="action-label ${netClass}">${netLabel}</td>
                <td class="action-val ${netClass}">${formatIndianNum(netChange)}</td>
                <td class="action-val ${carriedToday >= 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(carriedToday)}</td>
                <td class="action-val ${carriedT1 !== null && carriedT1 >= 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(carriedT1)}</td>
                <td class="action-val ${carriedT2 !== null && carriedT2 >= 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(carriedT2)}</td>
            `;
            tbody.appendChild(tr);
        });

        // Add Total Row
        const trTotal = document.createElement('tr');
        trTotal.className = 'total-row';
        trTotal.innerHTML = `
            <td class="action-label" colspan="7">Market Analysis With Gopal Das</td>
            <td class="action-val">-</td>
            <td class="action-val">-</td>
            <td class="action-val">-</td>
        `;
        tbody.appendChild(trTotal);
    });

    // Render Right-Hand Participant Summary
    renderRightHandSummary(summaryItems);

    // Update KPI Bar
    updateKPIs(dataToday, dataT1);
}

// Get Object Map for specific date
function getParticipantMap(dateStr) {
    const rows = rawCSVData.filter(r => r.Date === dateStr);
    const map = {};
    rows.forEach(r => {
        map[r['Client Type']] = r;
    });
    return map;
}

// Render Positions Bought / Sold Summary — separate table per participant
function renderRightHandSummary(summaryItems) {
    const container = document.getElementById('positions-summary-list');
    container.innerHTML = '';

    PARTICIPANTS.forEach(p => {
        const pItems = summaryItems.filter(item => item.participant === p);

        const card = document.createElement('div');
        card.className = 'instrument-block summary-block';

        let rows = '';
        if (pItems.length === 0) {
            rows = `<tr><td colspan="3" class="text-center" style="color:var(--text-muted); padding:12px;">No net activity</td></tr>`;
        } else {
            pItems.forEach(item => {
                rows += `
                    <tr>
                        <td class="action-label">${item.instrument}</td>
                        <td class="action-label ${item.netClass}">${item.action}</td>
                        <td class="action-val ${item.netClass}">${formatIndianNum(item.value)}</td>
                    </tr>`;
            });
        }

        card.innerHTML = `
            <div class="block-header summary-block-header">${p}s</div>
            <div class="table-scroll-wrapper">
                <table class="dashboard-table summary-table">
                    <thead>
                        <tr>
                            <th>Instrument</th>
                            <th>Action</th>
                            <th>Net Value</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;

        container.appendChild(card);
    });
}

// Update Top KPI Bar
function updateKPIs(todayMap, t1Map) {
    if (!todayMap || !t1Map) return;

    const fiiToday = todayMap['FII'] || {};
    const fiiT1 = t1Map['FII'] || {};

    // FII Index Futures Net
    const fiiFutLongChange = (fiiToday['Future Index Long'] || 0) - (fiiT1['Future Index Long'] || 0);
    const fiiFutShortChange = (fiiToday['Future Index Short'] || 0) - (fiiT1['Future Index Short'] || 0);
    const fiiFutNet = fiiFutLongChange - fiiFutShortChange;

    const fiiFutEl = document.getElementById('kpi-fii-futures');
    const fiiFutSub = document.getElementById('kpi-fii-futures-action');
    fiiFutEl.textContent = formatIndianNum(fiiFutNet);
    fiiFutEl.className = `kpi-value ${fiiFutNet >= 0 ? 'pos-green' : 'pos-red'}`;
    fiiFutSub.textContent = fiiFutNet >= 0 ? 'FII Net Buyers Today' : 'FII Net Sellers Today';

    // Client Index Calls Net Today
    const clientToday = todayMap['Client'] || {};
    const clientT1 = t1Map['Client'] || {};
    const clientCallLongChg = (clientToday['Option Index Call Long'] || 0) - (clientT1['Option Index Call Long'] || 0);
    const clientCallShortChg = (clientToday['Option Index Call Short'] || 0) - (clientT1['Option Index Call Short'] || 0);
    const clientCallNet = clientCallLongChg - clientCallShortChg;

    const clientCallEl = document.getElementById('kpi-client-calls');
    const clientCallSub = document.getElementById('kpi-client-calls-action');
    clientCallEl.textContent = formatIndianNum(clientCallNet);
    clientCallEl.className = `kpi-value ${clientCallNet >= 0 ? 'pos-green' : 'pos-red'}`;
    clientCallSub.textContent = clientCallNet >= 0 ? 'Retail Bought Net Calls' : 'Retail Sold Net Calls';

    // Pro Index Calls Net Today
    const proToday = todayMap['Pro'] || {};
    const proT1 = t1Map['Pro'] || {};
    const proCallLongChg = (proToday['Option Index Call Long'] || 0) - (proT1['Option Index Call Long'] || 0);
    const proCallShortChg = (proToday['Option Index Call Short'] || 0) - (proT1['Option Index Call Short'] || 0);
    const proCallNet = proCallLongChg - proCallShortChg;

    const proCallEl = document.getElementById('kpi-pro-calls');
    const proCallSub = document.getElementById('kpi-pro-calls-action');
    proCallEl.textContent = formatIndianNum(proCallNet);
    proCallEl.className = `kpi-value ${proCallNet >= 0 ? 'pos-green' : 'pos-red'}`;
    proCallSub.textContent = proCallNet >= 0 ? 'Pro Desk Bought Calls' : 'Pro Desk Sold Calls';

    // Institutional Bias
    const smartMoneyNet = fiiFutNet + proCallNet;
    const biasEl = document.getElementById('kpi-bias');
    const biasSub = document.getElementById('kpi-bias-sub');

    if (smartMoneyNet > 20000) {
        biasEl.textContent = 'BULLISH';
        biasEl.className = 'kpi-value pos-green';
        biasSub.textContent = 'Smart Money Buying';
    } else if (smartMoneyNet < -20000) {
        biasEl.textContent = 'BEARISH';
        biasEl.className = 'kpi-value pos-red';
        biasSub.textContent = 'Smart Money Selling';
    } else {
        biasEl.textContent = 'NEUTRAL / MIXED';
        biasEl.className = 'kpi-value';
        biasSub.textContent = 'Ranging Positioning';
    }
}

// Setup Controls and Navigation Listeners
function setupEventListeners() {
    // Select Date
    const selectEl = document.getElementById('date-select');
    selectEl.addEventListener('change', (e) => {
        currentDateIndex = parseInt(e.target.value);
        renderDashboardForCurrentDate();
    });

    // Prev / Next Buttons
    document.getElementById('btn-prev-date').addEventListener('click', () => {
        if (currentDateIndex > 0) {
            currentDateIndex--;
            selectEl.value = currentDateIndex;
            renderDashboardForCurrentDate();
        }
    });

    document.getElementById('btn-next-date').addEventListener('click', () => {
        if (currentDateIndex < availableDates.length - 1) {
            currentDateIndex++;
            selectEl.value = currentDateIndex;
            renderDashboardForCurrentDate();
        }
    });

    document.getElementById('btn-latest-date').addEventListener('click', () => {
        currentDateIndex = availableDates.length - 1;
        selectEl.value = currentDateIndex;
        renderDashboardForCurrentDate();
    });

    // --- Hamburger Menu ---
    const hamburgerBtn = document.getElementById('btn-hamburger');
    const hamburgerDropdown = document.getElementById('hamburger-dropdown');

    hamburgerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        hamburgerDropdown.classList.toggle('open');
        const icon = hamburgerBtn.querySelector('i');
        icon.className = hamburgerDropdown.classList.contains('open')
            ? 'fa-solid fa-xmark'
            : 'fa-solid fa-bars';
    });

    // Close hamburger on outside click
    document.addEventListener('click', (e) => {
        if (!hamburgerBtn.contains(e.target) && !hamburgerDropdown.contains(e.target)) {
            hamburgerDropdown.classList.remove('open');
            hamburgerBtn.querySelector('i').className = 'fa-solid fa-bars';
        }
    });

    // Hamburger — Theme Toggle
    document.getElementById('hamburger-theme').addEventListener('click', () => {
        document.body.classList.toggle('theme-dark');
        const themeIcon = document.querySelector('#hamburger-theme i');
        if (document.body.classList.contains('theme-dark')) {
            themeIcon.className = 'fa-solid fa-sun';
        } else {
            themeIcon.className = 'fa-solid fa-moon';
        }
        // Re-render charts with correct theme if charts tab is active
        if (document.getElementById('view-charts').classList.contains('active')) {
            renderChartsView();
        }
        hamburgerDropdown.classList.remove('open');
        hamburgerBtn.querySelector('i').className = 'fa-solid fa-bars';
    });


    // --- Tab Switching ---
    document.getElementById('tab-participant-gross').addEventListener('click', () => switchTab('participant-gross'));
    document.getElementById('tab-money-flow').addEventListener('click', () => {
        switchTab('money-flow');
        loadMoneyFlowView();
    });

    document.getElementById('tab-charts').addEventListener('click', () => {
        switchTab('charts');
        renderChartsView();
    });

    // --- Conviction index tabs in Money Flow view ---
    document.querySelectorAll('.conviction-tab').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.conviction-tab').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            const symbol = e.currentTarget.dataset.symbol;
            if (moneyFlowData && moneyFlowData.conviction_trends) {
                renderMultiDayConviction(moneyFlowData.conviction_trends, symbol);
            }
        });
    });

}

// Global state for money flow data
let moneyFlowData = null;
let moneyFlowLoadInProgress = false;

// ─── Money Flow Helpers ───

/**
 * Returns a conviction tag HTML string based on conviction type.
 */
function buildConvictionTag(type) {
    const map = {
        'HARD RESISTANCE': 'hard-resistance',
        'CE BUILDING': 'ce-building',
        'CE UNWINDING': 'ce-unwinding',
        'SOLID FLOOR': 'solid-floor',
        'PE BUILDING': 'pe-building',
        'PE UNWINDING': 'pe-unwinding',
        'STABLE': 'stable'
    };
    const cls = map[type] || 'stable';
    const label = type || 'STABLE';
    return `<span class="conviction-tag ${cls}">${label}</span>`;
}

/**
 * Returns an alignment badge HTML string for Smart Money Breadth / Conviction alignment.
 */
function alignmentBadge(align) {
    const a = (align || 'NEUTRAL').toUpperCase();
    const cls = a === 'ALIGNED' ? 'aligned' : a === 'OPPOSED' ? 'opposed' : 'neutral';
    return `<span class="alignment-badge ${cls}">${a}</span>`;
}

/**
 * Returns a stance badge HTML string based on the action description.
 * Maps keywords in the action to bullish/bearish/neutral.
 */
function getActionTag(action) {
    if (!action) return '<span class="stance-badge neutral">NEUTRAL</span>';
    const upper = action.toUpperCase();
    if (upper.includes('BULLISH') || upper.includes('SUPPORT') || upper.includes('FLOOR') || upper.includes('SQUEEZE') || upper.includes('UNWINDING') || upper.includes('RELEASED') || upper.includes('BOUGHT')) {
        return '<span class="stance-badge bullish">' + action + '</span>';
    }
    if (upper.includes('BEARISH') || upper.includes('CAP') || upper.includes('WRITING') || upper.includes('TRAP') || upper.includes('CAPPED') || upper.includes('SOLD') || upper.includes('DROPPED')) {
        return '<span class="stance-badge bearish">' + action + '</span>';
    }
    return '<span class="stance-badge neutral">' + action + '</span>';
}

function switchTab(tabName) {
    // Toggle ham-tab active
    document.querySelectorAll('.ham-tab').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Toggle tab-content active
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`view-${tabName}`).classList.add('active');

    // Close hamburger after switching tabs
    const dropdown = document.getElementById('hamburger-dropdown');
    const btn = document.getElementById('btn-hamburger');
    if (dropdown && btn) {
        dropdown.classList.remove('open');
        btn.querySelector('i').className = 'fa-solid fa-bars';
    }
}

async function loadMoneyFlowView() {
    // Tab caching — skip re-fetch if already loaded
    if (moneyFlowData && !moneyFlowLoadInProgress) {
        return;
    }
    if (moneyFlowLoadInProgress) return;
    moneyFlowLoadInProgress = true;

    // Show skeleton loaders
    const skeletonHTML = '<div class="skeleton-loader block"></div><div class="skeleton-loader block" style="width:80%"></div>';
    document.getElementById('verdict-bias-badge').textContent = '--';
    document.getElementById('verdict-title').textContent = 'Loading institutional verdict data...';
    document.getElementById('verdict-desc').textContent = 'Please wait while data is being fetched.';
    document.getElementById('verdict-score').textContent = '--';

    const skeletonPanels = ['verdict-fii-stance', 'verdict-index-rolls', 'multiday-conviction-body', 'breadth-call-writing-body', 'breadth-put-writing-body', 'breadth-call-unwind-body', 'breadth-put-unwind-body'];
    skeletonPanels.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = skeletonHTML;
    });

    try {
        const fallbackRes = await fetch('docs/money_flow_data.json');
        if (!fallbackRes.ok) {
            showVerdictError('Money Flow verdict data not found. Automatic fetch might be running right now, or failed.', true);
            moneyFlowLoadInProgress = false;
            return;
        }
        moneyFlowData = await fallbackRes.json();

        // Update Timestamp
        const tsEl = document.querySelector('#oc-last-updated span');
        if (tsEl) tsEl.textContent = moneyFlowData.timestamp ? new Date(moneyFlowData.timestamp).toLocaleString('en-IN') : '--';

        // Render Panel 1: Executive Market Verdict Banner
        renderExecutiveVerdict(moneyFlowData.executive_summary || {});

        // Retail Trap Alarm / Confirmation (from participant_summary)
        const alarmContainer = document.getElementById('retail-trap-alarm');
        if (alarmContainer) {
            const alarm = (moneyFlowData.participant_summary || {}).retail_trap_alarm;
            const confirmation = (moneyFlowData.participant_summary || {}).retail_confirmation_message;
            if (alarm) {
                const isCallTrap = alarm.includes('CALL TRAP');
                alarmContainer.className = 'retail-trap-alarm ' + (isCallTrap ? 'call-trap' : 'put-trap');
                alarmContainer.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ' + alarm;
                alarmContainer.style.display = 'flex';
            } else if (confirmation) {
                alarmContainer.className = 'retail-trap-alarm retail-confirmation';
                alarmContainer.innerHTML = '<i class="fa-solid fa-check-circle"></i> ' + confirmation;
                alarmContainer.style.display = 'flex';
            } else {
                alarmContainer.style.display = 'none';
            }
        }

        // Render Panel 2: FII & Pro Stance
        renderFIIStance(moneyFlowData.participant_summary || {});

        // Render Panel 2b: Commentary
        renderCommentary(moneyFlowData.participant_summary || {});

        // Render Panel 3: Index Roll Tracker, Magnet Strike & Traps
        renderIndexRolls(moneyFlowData.index_rolls || {});

        // Render Panel 4: Multi-Day Strike Conviction Matrix (NIFTY default)
        renderMultiDayConviction(moneyFlowData.conviction_trends || {}, 'NIFTY');

        // Render Panel 5: Stock Options Breadth
        renderStockBreadth(moneyFlowData.stock_breadth || {});

        // Render Panel 4b: Flow Divergence
        renderFlowDivergence(moneyFlowData.flow_divergence || []);

    } catch (err) {
        showVerdictError('Error fetching verdict data: ' + err.message, true);
        // Show failure in all panels
        const errPanels = ['verdict-fii-stance', 'verdict-index-rolls', 'multiday-conviction-body', 'breadth-call-writing-body', 'breadth-put-writing-body', 'breadth-call-unwind-body', 'breadth-put-unwind-body'];
        errPanels.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<div style="color:var(--text-muted);padding:12px;text-align:center;">Failed to load data. Please try again.</div>';
        });
    } finally {
        moneyFlowLoadInProgress = false;
    }
}

function renderExecutiveVerdict(exec) {
    const badge = document.getElementById('verdict-bias-badge');
    const title = document.getElementById('verdict-title');
    const desc = document.getElementById('verdict-desc');
    const score = document.getElementById('verdict-score');

    const label = exec.bias_label || 'NEUTRAL';
    if (badge) {
        badge.textContent = label;
        badge.className = 'bias-badge';
        if (label.includes('BULLISH')) badge.classList.add('bullish');
        else if (label.includes('BEARISH')) badge.classList.add('bearish');
        else badge.classList.add('neutral');
    }

    if (title) title.textContent = `INSTITUTIONAL MARKET VERDICT: ${label}`;
    if (desc) desc.textContent = exec.action_desc || 'Cross-correlating participant gross data with strike-level OI.';

    if (score) {
        const sc = exec.smart_money_score || 0;
        score.textContent = (sc > 0 ? '+' : '') + sc;
        score.style.color = sc > 0 ? '#22c55e' : sc < 0 ? '#ef4444' : '#f59e0b';
    }
}

function renderFIIStance(ps) {
    const container = document.getElementById('verdict-fii-stance');
    if (!container) return;

    if (!ps || Object.keys(ps).length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted);">No participant data found for latest date.</div>';
        return;
    }

    const fiiCallNetChg = ps.fii_ce_net_short_change || 0;
    const fiiPeNetChg = ps.fii_pe_net_short_change || 0;
    const fiiFutChg = ps.fii_fut_net_change || 0;

    const proCeNetChg = ps.pro_ce_net_short_change || 0;
    const proPeNetChg = ps.pro_pe_net_short_change || 0;
    const clientCeNetBuy = ps.client_ce_net_buy || 0;

    const diiCeNetChg = ps.dii_ce_net_short_change || 0;
    const diiPeNetChg = ps.dii_pe_net_short_change || 0;
    const diiFutChg = ps.dii_fut_net_change || 0;

    // Build call action text (no emojis)
    let callActionText, callActionClass;
    if (fiiCallNetChg > 10000) { callActionText = 'Aggressive Call Writing (Upside Capped)'; callActionClass = 'bearish'; }
    else if (fiiCallNetChg < -10000) { callActionText = 'Call Short Unwinding (Ceiling Released)'; callActionClass = 'bullish'; }
    else { callActionText = 'Minor Call Shift'; callActionClass = 'neutral'; }

    let putActionText, putActionClass;
    if (fiiPeNetChg > 10000) { putActionText = 'Put Short Addition (Floor Defended)'; putActionClass = 'bullish'; }
    else if (fiiPeNetChg < -10000) { putActionText = 'Put Short Unwinding (Floor Dropped)'; putActionClass = 'bearish'; }
    else { putActionText = 'Minor Put Shift'; putActionClass = 'neutral'; }

    let futActionText, futActionClass;
    if (fiiFutChg > 5000) { futActionText = 'Net Index Futures Bought'; futActionClass = 'bullish'; }
    else if (fiiFutChg < -5000) { futActionText = 'Net Index Futures Sold'; futActionClass = 'bearish'; }
    else { futActionText = 'Flat Futures Action'; futActionClass = 'neutral'; }

    let proStanceText, proStanceClass;
    if (proPeNetChg > proCeNetChg) { proStanceText = 'Pro Writing Puts (Bullish Support)'; proStanceClass = 'bullish'; }
    else if (proCeNetChg > proPeNetChg) { proStanceText = 'Pro Writing Calls (Bearish Cap)'; proStanceClass = 'bearish'; }
    else { proStanceText = 'Pro Balanced'; proStanceClass = 'neutral'; }

    let retailStanceText, retailStanceClass;
    if (clientCeNetBuy > 15000) { retailStanceText = 'Retail Heavy Call Longs (Trap Risk)'; retailStanceClass = 'caution'; }
    else if (clientCeNetBuy < -15000) { retailStanceText = 'Retail Selling Calls'; retailStanceClass = 'bullish'; }
    else { retailStanceText = 'Retail Neutral'; retailStanceClass = 'neutral'; }

    container.innerHTML = `
        <div class="participant-section-label fii"><i class="fa-solid fa-building-columns"></i> FII (Institutional) Positioning</div>
        <div class="participant-data-row">
            <span class="label">FII Call Options Stance:</span>
            <span class="value ${fiiCallNetChg < 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(fiiCallNetChg)} ${getActionTag(callActionText)}</span>
        </div>
        <div class="participant-data-row">
            <span class="label">FII Put Options Stance:</span>
            <span class="value ${fiiPeNetChg > 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(fiiPeNetChg)} ${getActionTag(putActionText)}</span>
        </div>
        <div class="participant-data-row">
            <span class="label">FII Futures Net Shift:</span>
            <span class="value ${fiiFutChg > 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(fiiFutChg)} ${getActionTag(futActionText)}</span>
        </div>

        <div class="participant-section-label pro" style="margin-top:6px;"><i class="fa-solid fa-user-ninja"></i> Pro Desk & Retail Positioning</div>
        <div class="participant-data-row">
            <span class="label">Pro Desk Stance:</span>
            <span class="value font-mono">${getActionTag(proStanceText)}</span>
        </div>
        <div class="participant-data-row">
            <span class="label">Retail (Client) Net Calls:</span>
            <span class="value ${clientCeNetBuy > 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(clientCeNetBuy)} ${getActionTag(retailStanceText)}</span>
        </div>

        <div class="participant-section-label dii" style="margin-top:6px;"><i class="fa-solid fa-landmark"></i> DII (Domestic) Positioning</div>
        <div class="participant-data-row">
            <span class="label">DII Call Options Shift:</span>
            <span class="value ${diiCeNetChg < 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(diiCeNetChg)}</span>
        </div>
        <div class="participant-data-row">
            <span class="label">DII Put Options Shift:</span>
            <span class="value ${diiPeNetChg < 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(diiPeNetChg)}</span>
        </div>
        <div class="participant-data-row">
            <span class="label">DII Futures Net Shift:</span>
            <span class="value ${diiFutChg > 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(diiFutChg)}</span>
        </div>

        <div class="info-footer">
            <i class="fa-solid fa-circle-info"></i> Date: <strong>${ps.date || '--'}</strong>
            | FII Futures Net Carried: <strong class="font-mono ${ps.fii_fut_net_carried >= 0 ? 'pos-green' : 'pos-red'}">${formatIndianNum(ps.fii_fut_net_carried)}</strong>
            | Scores — FII: <strong>${ps.fii_raw_score || 0}</strong> Pro: <strong>${ps.pro_raw_score || 0}</strong> DII: <strong>${ps.dii_raw_score || 0}</strong>
            ${ps.fii_dii_modifier ? '| FII-DII: <strong>' + (ps.fii_dii_modifier > 0 ? '+' : '') + ps.fii_dii_modifier + '</strong>' : ''}
            ${ps.iv_modifier_applied ? '| IV: <strong>' + (ps.iv_modifier_applied > 0 ? '+' : '') + ps.iv_modifier_applied + '</strong>' : ''}
        </div>
    `;
}

/**
 * Render a fully dynamic FII-DII & Smart Money analysis commentary from participant_summary data.
 * All text is generated from actual data — no hardcoded narratives.
 */
function renderCommentary(ps) {
    const card = document.getElementById('commentary-card');
    const container = document.getElementById('verdict-commentary');
    if (!container || !card) return;

    if (!ps || Object.keys(ps).length === 0) {
        card.style.display = 'none';
        return;
    }

    const formatNum = v => formatIndianNum(v);
    const abs = v => Math.abs(v);

    // ── Date / Expiry Detection ──
    const ds = ps.date || '';
    let expiryLabel = '';
    let expiryDays = null; // positive = days before expiry, 0 = expiry day, negative = after
    if (ds) {
        const parts = ds.split('-');
        if (parts.length === 3) {
            const d = new Date(parseInt('20' + parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
            // Compute last Thursday of the month: go to 1st of next month, walk back to Thu
            const nextMonth = new Date(d.getFullYear(), d.getMonth() + 1, 1);
            const subDays = (nextMonth.getDay() - 4 + 7) % 7 || 7;
            const lastThu = new Date(nextMonth);
            lastThu.setDate(lastThu.getDate() - subDays);
            expiryDays = Math.round((lastThu - d) / 86400000);
            // Build label from the day difference
            if (expiryDays === 0) expiryLabel = '🗓️ Monthly Expiry Today';
            else if (expiryDays === 1) expiryLabel = '🗓️ Monthly Expiry Tomorrow';
            else if (expiryDays === 2) expiryLabel = '🗓️ Monthly Expiry in 2 Days';
            else if (expiryDays === -1) expiryLabel = '🗓️ Post Monthly Expiry (Yesterday)';
            else if (expiryDays > 1 && expiryDays <= 7) expiryLabel = `🗓️ Monthly Expiry in ${expiryDays} Days`;
            else if (expiryDays < -1 && expiryDays >= -7) expiryLabel = `🗓️ ${Math.abs(expiryDays)} Days Post Monthly Expiry`;
        }
    }

    // ── Build participant rows ──
    function mkRows(p, prefix) {
        const fut = p[prefix + 'fut_net_change'] || 0;
        const futLong = p[prefix + 'fut_long_change'] || 0;
        const futShort = p[prefix + 'fut_short_change'] || 0;
        const ceLong = p[prefix + 'ce_long_change'] || 0;
        const ceShort = p[prefix + 'ce_short_change'] || 0;
        const peLong = p[prefix + 'pe_long_change'] || 0;
        const peShort = p[prefix + 'pe_short_change'] || 0;
        const stkFut = p[prefix + 'stk_fut_net_change'] || 0;
        const stkFutLong = p[prefix + 'stk_fut_long_change'] || 0;
        const stkFutShort = p[prefix + 'stk_fut_short_change'] || 0;
        const stkCe = p[prefix + 'stk_ce_net_change'] || 0;
        const stkPe = p[prefix + 'stk_pe_net_change'] || 0;
        // stkCe negative = net bought; positive = net sold (short)
        // stkPe negative = net bought (long puts); positive = net sold (short)

        const rows = [];

        // Index Futures
        if (fut !== 0) {
            const emoji = fut > 0 ? '🟢' : '🔴';
            const action = fut > 0 ? 'Bought' : 'Sold';
            const arrow = fut > 0 ? '➕' : '➖';
            let detailParts = [];
            if (futLong > 0) detailParts.push(`Added Longs: ${formatNum(futLong)}`);
            else if (futLong < 0) detailParts.push(`Closed Longs: ${formatNum(abs(futLong))}`);
            if (futShort > 0) detailParts.push(`Added Shorts: ${formatNum(futShort)}`);
            else if (futShort < 0) detailParts.push(`Closed Shorts: ${formatNum(abs(futShort))}`);
            detail = detailParts.length ? ' — ' + detailParts.join(' • ') : '';
            const boost = abs(fut) > 30000 ? ' 🚀' : abs(fut) > 10000 ? ' 💪' : '';
            rows.push({ emoji, cls: fut > 0 ? 'bg-green' : 'bg-red', text: `${action} Index Futures ${arrow}${formatNum(abs(fut))} Lots${boost}${detail}` });
        }
        // Index Calls
        if (ceLong !== 0 || ceShort !== 0) {
            const netCall = ceShort - ceLong; // +ve = writing, -ve = covering
            if (abs(ceLong) > abs(ceShort)) {
                // net long calls (buying)
                const emoji = ceLong > 0 ? '🟢' : '🔴';
                rows.push({ emoji, cls: ceLong > 0 ? 'bg-green' : 'bg-red', text: `${ceLong > 0 ? 'Bought' : 'Sold'} Index Calls ${ceLong > 0 ? '➕' : '➖'}${formatNum(abs(ceLong))} Lots${abs(ceLong) > 50000 ? ' 🚀' : ''}` });
            } else {
                const emoji = ceShort > 0 ? '🔴' : '🟢';
                rows.push({ emoji, cls: ceShort > 0 ? 'bg-red' : 'bg-green', text: `${ceShort > 0 ? 'Sold' : 'Covered'} Index Calls ${ceShort > 0 ? '➖' : '➕'}${formatNum(abs(ceShort))} Lots` });
            }
        }
        // Index Puts
        if (peLong !== 0 || peShort !== 0) {
            if (abs(peShort) >= abs(peLong)) {
                // Short (writing) dominant
                const emoji = peShort > 0 ? '🔴' : '🟢';
                const action = peShort > 0 ? 'Sold' : 'Covered';
                const arrow = peShort > 0 ? '➖' : '➕';
                rows.push({ emoji, cls: peShort > 0 ? 'bg-red' : 'bg-green', text: `${action} Index Puts ${arrow}${formatNum(abs(peShort))} Lots${abs(peShort) > 50000 ? ' ⚠️' : ''}` });
            } else {
                // Long (buying) dominant
                const emoji = peLong > 0 ? '🟢' : '🔴';
                const action = peLong > 0 ? 'Bought' : 'Sold';
                const arrow = peLong > 0 ? '➕' : '➖';
                rows.push({ emoji, cls: peLong > 0 ? 'bg-green' : 'bg-red', text: `${action} Index Puts ${arrow}${formatNum(abs(peLong))} Lots${abs(peLong) > 30000 ? ' 🛡️' : ''}` });
            }
        }
        // Stock Futures
        if (stkFut !== 0) {
            const emoji = stkFut > 0 ? '🟢' : '🔴';
            const action = stkFut > 0 ? 'Bought' : 'Sold';
            const arrow = stkFut > 0 ? '➕' : '➖';
            let detailParts = [];
            if (stkFutLong > 0) detailParts.push(`Added Longs: ${formatNum(stkFutLong)}`);
            else if (stkFutLong < 0) detailParts.push(`Closed Longs: ${formatNum(abs(stkFutLong))}`);
            if (stkFutShort > 0) detailParts.push(`Added Shorts: ${formatNum(stkFutShort)}`);
            else if (stkFutShort < 0) detailParts.push(`Closed Shorts: ${formatNum(abs(stkFutShort))}`);
            const detail = detailParts.length ? ' — ' + detailParts.join(' • ') : '';
            const boost = abs(stkFut) > 50000 ? ' 💪' : '';
            rows.push({ emoji, cls: stkFut > 0 ? 'bg-green' : 'bg-red', text: `${action} Stock Futures ${arrow}${formatNum(abs(stkFut))} Lots${boost}${detail}` });
        }
        // Stock Calls
        if (stkCe !== 0) {
            const emoji = stkCe < 0 ? '🟢' : '🔴';
            const action = stkCe < 0 ? 'Bought' : 'Sold';
            const arrow = stkCe < 0 ? '➕' : '➖';
            rows.push({ emoji, cls: stkCe < 0 ? 'bg-green' : 'bg-red', text: `${action} Stock Calls ${arrow}${formatNum(abs(stkCe))} Lots${abs(stkCe) > 50000 ? ' 💪' : ''}` });
        }
        // Stock Puts
        if (stkPe !== 0) {
            const emoji = stkPe < 0 ? '🔴' : '🟢'; // buying puts is bearish/hedge
            const action = stkPe < 0 ? 'Bought' : 'Sold';
            const arrow = stkPe < 0 ? '➕' : '➖';
            rows.push({ emoji, cls: stkPe < 0 ? 'bg-red' : 'bg-green', text: `${action} Stock Puts ${arrow}${formatNum(abs(stkPe))} Lots` });
        }

        return rows;
    }

    // ── Count bullish/bearish signals for a participant ──
    function countSignals(prefix) {
        const fut = ps[prefix + 'fut_net_change'] || 0;
        const ceLong = ps[prefix + 'ce_long_change'] || 0;
        const ceShort = ps[prefix + 'ce_short_change'] || 0;
        const peLong = ps[prefix + 'pe_long_change'] || 0;
        const peShort = ps[prefix + 'pe_short_change'] || 0;
        const stkFut = ps[prefix + 'stk_fut_net_change'] || 0;
        const stkCe = ps[prefix + 'stk_ce_net_change'] || 0;
        const stkPe = ps[prefix + 'stk_pe_net_change'] || 0;

        let bullish = 0, bearish = 0;
        if (fut > 0) bullish++; else if (fut < 0) bearish++;
        if (ceLong > abs(ceShort) && ceLong > 0) bullish++;
        if (ceShort > abs(ceLong) && ceShort > 0) bearish++;
        if (ceLong > abs(ceShort) && ceLong < 0) bearish++; // selling long calls
        if (ceShort > abs(ceLong) && ceShort < 0) bullish++; // covering short calls
        if (peShort > abs(peLong) && peShort > 0) bullish++; // writing puts
        if (peShort > abs(peLong) && peShort < 0) bearish++; // covering put shorts
        if (peLong > abs(peShort) && peLong > 0) bearish++; // buying puts
        if (peLong > abs(peShort) && peLong < 0) bullish++; // selling puts
        if (stkFut > 0) bullish++; else if (stkFut < 0) bearish++;
        if (stkCe < 0) bullish++; else if (stkCe > 0) bearish++;
        if (stkPe < 0) bearish++; else if (stkPe > 0) bullish++;
        return { bullish, bearish };
    }

    // ── Generate interpretation note ──
    function generateNote(prefix, label) {
        const sig = countSignals(prefix);
        const parts = [];

        const fut = ps[prefix + 'fut_net_change'] || 0;
        const ceLong = ps[prefix + 'ce_long_change'] || 0;
        const ceShort = ps[prefix + 'ce_short_change'] || 0;
        const peLong = ps[prefix + 'pe_long_change'] || 0;
        const peShort = ps[prefix + 'pe_short_change'] || 0;
        const stkFut = ps[prefix + 'stk_fut_net_change'] || 0;
        const netCarried = ps[prefix + 'fut_net_carried'] || 0;

        const netCall = ceShort - ceLong;
        const netPut = peShort - peLong;
        const sentences = [];

        if (sig.bullish > sig.bearish + 1) {
            let s = `${label} are predominantly bullish today`;
            const strong = [];
            if (fut > 20000) strong.push(`aggressively added Index Futures (${formatNum(abs(fut))} lots)`);
            else if (fut > 5000) strong.push(`added Index Futures (${formatNum(abs(fut))} lots)`);
            if (ceLong > 50000) strong.push(`aggressively bought Index Calls (${formatNum(abs(ceLong))} lots)`);
            else if (ceLong > 20000) strong.push(`bought Index Calls (${formatNum(abs(ceLong))} lots)`);
            if (peShort > 50000) strong.push(`wrote Index Puts at scale (${formatNum(abs(peShort))} lots)`);
            else if (peShort > 20000) strong.push(`wrote Index Puts (${formatNum(abs(peShort))} lots)`);
            if (stkFut > 30000) strong.push(`showed strong Stock Futures buying (${formatNum(abs(stkFut))} lots)`);
            else if (stkFut > 10000) strong.push(`added Stock Futures (${formatNum(abs(stkFut))} lots)`);
            if (strong.length) s += `. They ` + strong.join(', ');
            sentences.push(s);
            if (peLong > 30000) sentences.push(`However, they also added Put hedges (${formatNum(abs(peLong))} lots) as protection`);
            if (ceShort > 30000) sentences.push(`Some Call writing (${formatNum(abs(ceShort))} lots) may cap upside moves`);
            parts.push(sentences.join('. ') + '. 📈');
        } else if (sig.bearish > sig.bullish + 1) {
            let s = `${label} have turned defensive today`;
            const bear = [];
            if (fut < -20000) bear.push(`aggressively sold Index Futures (${formatNum(abs(fut))} lots)`);
            else if (fut < -5000) bear.push(`sold Index Futures (${formatNum(abs(fut))} lots)`);
            if (ceShort > 50000) bear.push(`wrote heavy Calls (${formatNum(abs(ceShort))} lots)`);
            else if (ceShort > 20000) bear.push(`wrote Calls (${formatNum(abs(ceShort))} lots)`);
            if (peLong > 30000) bear.push(`added significant Put hedges (${formatNum(abs(peLong))} lots)`);
            else if (peLong > 10000) bear.push(`bought Puts for protection (${formatNum(abs(peLong))} lots)`);
            if (stkFut < -20000) bear.push(`reduced Stock Futures significantly (${formatNum(abs(stkFut))} lots)`);
            else if (stkFut < -5000) bear.push(`trimmed Stock Futures (${formatNum(abs(stkFut))} lots)`);
            if (bear.length) s += `. They ` + bear.join(', ');
            sentences.push(s);
            if (peShort > 30000) sentences.push(`Some Put writing (${formatNum(abs(peShort))} lots) provides floor support`);
            if (ceLong > 30000) sentences.push(`Call buying (${formatNum(abs(ceLong))} lots) adds a bullish tilt`);
            parts.push(sentences.join('. ') + '. ⚠️');
        } else {
            let s = `${label} activity is mixed with no clear directional conviction`;
            const mixed = [];
            if (fut > 0) mixed.push('adding Index Futures');
            else if (fut < 0) mixed.push('reducing Index Futures');
            if (netCall < -10000) mixed.push('covering Calls');
            else if (netCall > 10000) mixed.push('writing Calls');
            if (netPut > 10000) mixed.push('writing Puts');
            else if (netPut < -10000) mixed.push('adding Put hedges');
            if (stkFut > 10000) mixed.push('buying Stock Futures');
            else if (stkFut < -10000) mixed.push('selling Stock Futures');
            if (mixed.length <= 1) {
                if (abs(fut) > 0 && abs(fut) <= 5000) mixed.push('minimal Index Futures changes');
                if (ceLong > 0 && ceLong <= 10000) mixed.push('minor Call buying');
                if (peShort > 0 && peShort <= 10000) mixed.push('light Put writing');
            }
            if (mixed.length) s += `. They are ` + mixed.join(', ');
            sentences.push(s);
            parts.push(sentences.join('. ') + '. ⚖️');
        }

        if (abs(netCarried) > 100000 && prefix === 'fii_') {
            parts.push(`FIIs still hold a net ${netCarried < 0 ? 'SHORT' : 'LONG'} of ${formatNum(abs(netCarried))} Index Futures position.`);
        }

        return parts.join(' ');
    }

    // ── Generate key takeaways from actual data ──
    function generateTakeaways() {
        const items = [];

        // Helper: pick value from a prefix path
        const g = (path) => ps[path] || 0;
        const fmt = (v) => formatNum(abs(v));

        // FII signals (individual legs)
        const fiiFut = g('fii_fut_net_change');
        const fiiCeL = g('fii_ce_long_change');
        const fiiCeS = g('fii_ce_short_change');
        const fiiPeL = g('fii_pe_long_change');
        const fiiPeS = g('fii_pe_short_change');
        const fiiStkF = g('fii_stk_fut_net_change');
        const fiiStkCe = g('fii_stk_ce_net_change');
        const fiiStkPe = g('fii_stk_pe_net_change');
        const fiiNetCarried = g('fii_fut_net_carried');
        const score = g('smart_money_score');

        const proFut = g('pro_fut_net_change');
        const proCeL = g('pro_ce_long_change');
        const proCeS = g('pro_ce_short_change');
        const proPeL = g('pro_pe_long_change');
        const proPeS = g('pro_pe_short_change');
        const proStkF = g('pro_stk_fut_net_change');
        const proStkCe = g('pro_stk_ce_net_change');

        const clientCeNB = g('client_ce_net_buy');
        const clientPeNB = g('client_pe_net_buy');
        const clientFut = g('client_fut_net_change');

        // ── Dynamic FII takeaway ──
        const fiiActions = [];
        if (fiiFut > 10000) fiiActions.push(`bought Index Futures (${fmt(fiiFut)} lots)`);
        else if (fiiFut > 3000) fiiActions.push(`added Index Futures (${fmt(fiiFut)} lots)`);
        else if (fiiFut < -10000) fiiActions.push(`sold Index Futures (${fmt(fiiFut)} lots)`);
        else if (fiiFut < -3000) fiiActions.push(`reduced Index Futures (${fmt(fiiFut)} lots)`);

        if (fiiCeL > 30000) fiiActions.push(`aggressively bought Index Calls (${fmt(fiiCeL)} lots)`);
        else if (fiiCeL > 10000) fiiActions.push(`bought Index Calls (${fmt(fiiCeL)} lots)`);
        if (fiiCeS > 30000) fiiActions.push(`wrote Index Calls (${fmt(fiiCeS)} lots)`);
        else if (fiiCeS > 10000) fiiActions.push(`wrote Calls (${fmt(fiiCeS)} lots)`);

        if (fiiPeS > 30000) fiiActions.push(`wrote Index Puts (${fmt(fiiPeS)} lots)`);
        else if (fiiPeS > 10000) fiiActions.push(`wrote Puts (${fmt(fiiPeS)} lots)`);
        if (fiiPeL > 20000) fiiActions.push(`bought Index Puts as hedges (${fmt(fiiPeL)} lots)`);
        else if (fiiPeL > 8000) fiiActions.push(`added Put hedges (${fmt(fiiPeL)} lots)`);

        if (fiiStkF > 20000) fiiActions.push(`bought Stock Futures (${fmt(fiiStkF)} lots)`);
        else if (fiiStkF < -20000) fiiActions.push(`sold Stock Futures (${fmt(fiiStkF)} lots)`);
        if (fiiStkCe < -20000) fiiActions.push(`bought Stock Calls (${fmt(fiiStkCe)} lots)`);
        else if (fiiStkCe > 20000) fiiActions.push(`sold Stock Calls (${fmt(fiiStkCe)} lots)`);

        if (fiiActions.length) {
            // Determine overall directional label
            const bullishCnt = [fiiFut > 0, fiiCeL > 10000, fiiPeS > 10000, fiiStkF > 10000, fiiStkCe < 0, fiiStkPe > 0].filter(Boolean).length;
            const bearishCnt = [fiiFut < 0, fiiCeS > 10000, fiiPeL > 10000, fiiStkF < -10000, fiiStkCe > 0, fiiStkPe < 0].filter(Boolean).length;
            const dir = bullishCnt > bearishCnt + 1 ? '🟢 Bullish' : bearishCnt > bullishCnt + 1 ? '🔴 Bearish' : '🟡 Mixed';
            let tail = '';
            if (abs(fiiNetCarried) > 100000) {
                tail = ` (still net ${fiiNetCarried < 0 ? 'SHORT' : 'LONG'} ${fmt(fiiNetCarried)} Index Futures)`;
            }
            items.push(`FIIs: ${dir}. ${fiiActions.join('; ')}.${tail}`);
        }

        // ── Dynamic Pro takeaway ──
        const proActions = [];
        if (proFut > 5000) proActions.push(`bought Index Futures (${fmt(proFut)} lots)`);
        else if (proFut < -5000) proActions.push(`sold Index Futures (${fmt(proFut)} lots)`);
        if (proCeL > 30000) proActions.push(`massive Call buying (${fmt(proCeL)} lots)`);
        else if (proCeL > 10000) proActions.push(`bought Index Calls (${fmt(proCeL)} lots)`);
        if (proCeS > 20000) proActions.push(`wrote Calls (${fmt(proCeS)} lots)`);
        if (proPeS > 30000) proActions.push(`wrote Puts (${fmt(proPeS)} lots)`);
        else if (proPeS > 10000) proActions.push(`wrote Puts (${fmt(proPeS)} lots)`);
        if (proPeL > 20000) proActions.push(`added Put hedges (${fmt(proPeL)} lots)`);
        if (proStkF > 20000) proActions.push(`bought Stock Futures (${fmt(proStkF)} lots)`);
        else if (proStkF < -20000) proActions.push(`sold Stock Futures (${fmt(proStkF)} lots)`);
        if (proStkCe < -20000) proActions.push(`bought Stock Calls (${fmt(proStkCe)} lots)`);
        else if (proStkCe > 20000) proActions.push(`sold Stock Calls (${fmt(proStkCe)} lots)`);

        if (proActions.length) {
            const pBullish = [proFut > 0, proCeL > 10000, proPeS > 10000, proStkF > 10000, proStkCe < 0].filter(Boolean).length;
            const pBearish = [proFut < 0, proCeS > 10000, proPeL > 10000, proStkF < -10000, proStkCe > 0].filter(Boolean).length;
            const pdir = pBullish > pBearish + 1 ? '🟢 Bullish' : pBearish > pBullish + 1 ? '🔴 Bearish' : '🟡 Mixed';
            items.push(`Pros: ${pdir}. ${proActions.join('; ')}.`);
        }

        // ── Dynamic DII takeaway ──
        const diiActions = [];
        const diiFut = g('dii_fut_net_change');
        const diiCeL = g('dii_ce_long_change');
        const diiPeL = g('dii_pe_long_change');
        const diiStkF = g('dii_stk_fut_net_change');
        if (diiFut > 0) diiActions.push(`bought Index Futures (${fmt(diiFut)} lots)`);
        else if (diiFut < 0) diiActions.push(`sold Index Futures (${fmt(diiFut)} lots)`);
        if (diiCeL > 5000) diiActions.push(`bought Calls (${fmt(diiCeL)} lots)`);
        if (diiPeL > 5000) diiActions.push(`bought Puts (${fmt(diiPeL)} lots)`);
        if (diiStkF > 10000) diiActions.push(`bought Stock Futures (${fmt(diiStkF)} lots)`);
        else if (diiStkF < -10000) diiActions.push(`sold Stock Futures (${fmt(diiStkF)} lots)`);
        if (diiActions.length) items.push(`DIIs: ${diiActions.join('; ')}.`);

        // ── Client (Retail) takeaway ──
        const clientActions = [];
        if (clientFut > 5000) clientActions.push(`bought Index Futures (${fmt(clientFut)} lots)`);
        else if (clientFut < -5000) clientActions.push(`sold Index Futures (${fmt(clientFut)} lots)`);
        if (clientCeNB > 20000) clientActions.push(`bought Index Calls (${fmt(clientCeNB)} lots)`);
        else if (clientCeNB < -20000) clientActions.push(`sold Index Calls (${fmt(clientCeNB)} lots)`);
        if (clientPeNB > 20000) clientActions.push(`bought Index Puts for protection (${fmt(clientPeNB)} lots)`);
        else if (clientPeNB < -20000) clientActions.push(`sold Index Puts (${fmt(clientPeNB)} lots)`);
        if (clientActions.length) items.push(`Retail: ${clientActions.join('; ')}.`);

        // ── FII + Pro alignment ──
        const fiiDir = fiiFut + (fiiCeL - fiiCeS) * 0.3 + (fiiPeS - fiiPeL) * 0.3 + fiiStkF * 0.5;
        const proDir = proFut + (proCeL - proCeS) * 0.3 + (proPeS - proPeL) * 0.3 + proStkF * 0.5;
        if (fiiDir > 0 && proDir > 0) items.push('🟢 FIIs and Proprietary traders are aligned on the bullish side — smart money convergence. 💪');
        else if (fiiDir < 0 && proDir < 0) items.push('🔴 Both FIIs and Pros are bearish — strong alignment on downside. ⚠️');
        else if (fiiDir > 0 && proDir < -5000) items.push('🟡 FIIs are bullish but Pros have turned defensive — divergence warrants caution.');
        else if (fiiDir < 0 && proDir > 5000) items.push('🟡 Pros are bullish while FIIs are bearish — a tug of war keeps volatility elevated. ⚡');

        // ── Retail trap/confirmation ──
        const retailTrap = ps.retail_trap_alarm;
        const retailConf = ps.retail_confirmation_message;
        if (retailTrap) items.push(`🔴 ${retailTrap} 😨`);
        else if (retailConf) items.push(`🟢 ${retailConf}`);

        // ── Score-based conclusion ──
        const sLabel = score >= 40 ? 'strongly bullish' : score >= 15 ? 'moderately bullish' : score <= -40 ? 'strongly bearish' : score <= -15 ? 'moderately bearish' : 'neutral/mixed';
        const sEmoji = score >= 15 ? '🟢' : score <= -15 ? '🔴' : '🟡';
        const sAdvice = score >= 40 ? 'Align with smart money direction.' : score >= 15 ? 'Look for price confirmation before aggressive entries.' : score <= -40 ? 'Consider defensive positioning.' : score <= -15 ? 'Avoid aggressive longs without confirmation.' : 'Wait for clearer directional signal before committing.';
        items.push(`${sEmoji} Smart Money Score: <strong>${score > 0 ? '+' : ''}${score}</strong> (${sLabel}). ${sAdvice}`);

        // ── Expiry context (fully dynamic) ──
        if (expiryDays !== null) {
            if (expiryDays === 0) {
                items.push('⚠️ 🗓️ Today is Monthly Expiry. Most F&O activity reflects settlement and rollover — not fresh directional bets. The next 2-3 sessions of the new series will reveal true institutional intent.');
            } else if (expiryDays === 1) {
                items.push('⚠️ 🗓️ Monthly Expiry Tomorrow. Positions being rolled or squared up will distort today\'s directional signals. Focus on the net rollover and fresh positions in the new series.');
            } else if (expiryDays >= 2 && expiryDays <= 5) {
                items.push(`⚠️ 🗓️ Monthly Expiry in ${expiryDays} trading sessions. Unwinding and rollover activity may distort pure directional signals. Watch the net rollover for the real picture.`);
            } else if (expiryDays >= -2 && expiryDays < 0) {
                items.push(`📌 🗓️ Post Monthly Expiry (${abs(expiryDays)} day(s) ago). The new series is still building — fresh institutional positioning over the next few sessions will clarify the monthly trend.`);
            }
        }

        return items;
    }

    // ── Build participant data ──
    function buildParticipantData(prefix, noteLabel) {
        const rows = mkRows(ps, prefix);
        if (rows.length === 0) return null;
        const note = generateNote(prefix, noteLabel);
        return { rows, note };
    }

    const fiiData = buildParticipantData('fii_', 'FIIs');
    const diiData = buildParticipantData('dii_', 'DIIs');
    const proData = buildParticipantData('pro_', 'Pros');
    const clientData = buildParticipantData('client_', 'Retail participants');

    function participantCard(label, icon, headerClass, data) {
        if (!data || !data.rows.length) return '';
        const rowsHtml = data.rows.map(r =>
            `<div class="commentary-row"><span class="commentary-badge ${r.cls}">${r.emoji} ${r.text}</span></div>`
        ).join('');
        return `
            <div class="commentary-participant">
                <div class="commentary-participant-header ${headerClass}">${icon} ${label}</div>
                <div class="commentary-participant-rows">${rowsHtml}</div>
                <div class="commentary-note">➡️ ${data.note}</div>
            </div>
        `;
    }

    const score = ps.smart_money_score || 0;
    let sentimentEmoji = score >= 15 ? '🟢' : score <= -15 ? '🔴' : '🟡';
    let sentimentText = score >= 40 ? 'STRONGLY POSITIVE' : score >= 15 ? 'POSITIVE' : score <= -40 ? 'STRONGLY NEGATIVE' : score <= -15 ? 'NEGATIVE' : 'MIXED / NEUTRAL';

    const takeaways = generateTakeaways();

    let html = `
        <div class="commentary-header">
            <div class="commentary-date">📊 FII–DII F&O Data Analysis | Trading Session: ${ps.date || '--'} ${expiryLabel}</div>
            <div class="commentary-sentiment">${sentimentEmoji} Overall Sentiment: <strong>${sentimentText}</strong> <span class="${score >= 0 ? 'pos-green' : 'pos-red'}">(${ps.bias_label || 'NEUTRAL'})</span> | Smart Money Score: <strong>${score > 0 ? '+' : ''}${score}</strong></div>
        </div>
        <div class="commentary-grid">
            ${participantCard('FIIs (Smart Money)', '🏦', 'commentary-header-fii', fiiData)}
            ${participantCard('DIIs (Domestic)', '🏛️', 'commentary-header-dii', diiData)}
            ${participantCard('Proprietary Traders (Pros)', '🔥', 'commentary-header-pro', proData)}
            ${participantCard('Clients (Retail)', '👥', 'commentary-header-client', clientData)}
        </div>
        ${takeaways.length ? `
        <div class="commentary-takeaways">
            <div class="commentary-takeaways-title">🎯 Key Takeaways:</div>
            <div class="commentary-takeaways-list">
                ${takeaways.map(t => `<div class="commentary-takeaway-item">${t}</div>`).join('')}
            </div>
        </div>` : ''}
        <div class="commentary-footer">
            📌 Trade with proper risk management. Position sizing and stop-loss remain the key. 🙏
        </div>
    `;

    container.innerHTML = html;
    card.style.display = 'block';
}

function renderIndexRolls(rolls) {
    const container = document.getElementById('verdict-index-rolls');
    if (!rolls || Object.keys(rolls).length === 0) {
        container.innerHTML = '<div class="text-center panel-loading">No index roll data available.</div>';
        return;
    }

    let html = '';
    for (const [sym, item] of Object.entries(rolls)) {
        const resCls = item.resistance_roll_type === 'BULLISH' ? 'pos-green' : item.resistance_roll_type === 'BEARISH' ? 'pos-red' : '';
        const supCls = item.support_roll_type === 'BULLISH' ? 'pos-green' : item.support_roll_type === 'BEARISH' ? 'pos-red' : '';

        const rollType = item.resistance_roll_type === 'BULLISH' || item.support_roll_type === 'BULLISH' ? 'bullish' : item.resistance_roll_type === 'BEARISH' || item.support_roll_type === 'BEARISH' ? 'bearish' : '';

        // Squeeze & Trap Badges HTML
        let trapHtml = '';
        if (item.traps_and_squeezes && item.traps_and_squeezes.length > 0) {
            const badgesHtml = item.traps_and_squeezes.map(t => `
                <div class="trap-badge">${t.badge}: ${t.desc}</div>
            `).join('');
            trapHtml = `<div class="traps-container">${badgesHtml}</div>`;
        }

        html += `
            <div class="roll-card ${rollType}">
                <div class="roll-card-header">
                    <span class="symbol-name">${sym} (LTP: ${item.ltp ? item.ltp.toLocaleString('en-IN') : '--'})</span>
                    <span class="meta-info">Max Pain: ${item.max_pain} | PCR: ${item.pcr_oi ? item.pcr_oi.toFixed(2) : '--'}</span>
                </div>

                <div class="magnet-info-bar">
                    <span class="magnet-strike"><i class="fa-solid fa-magnet"></i> Magnet Strike: <strong>${item.magnet_strike ? item.magnet_strike.toLocaleString('en-IN') : '--'}</strong></span>
                    <span class="expiry-range"><i class="fa-solid fa-crosshairs"></i> Expected Expiry: <strong>${item.expiry_range || '--'}</strong></span>
                    ${item.divergence && item.divergence !== 'NEUTRAL' ? `<span style="color:#f59e0b;"><i class="fa-solid fa-bolt"></i> ${item.divergence}</span>` : ''}
                </div>

                <div class="roll-grid">
                    <div class="roll-cell">
                        <span class="roll-label">RESISTANCE:</span>
                        <span class="roll-value ${resCls}">${item.resistance_roll}</span>
                        <div class="roll-desc">${item.resistance_roll_desc}</div>
                    </div>
                    <div class="roll-cell">
                        <span class="roll-label">SUPPORT:</span>
                        <span class="roll-value ${supCls}">${item.support_roll}</span>
                        <div class="roll-desc">${item.support_roll_desc}</div>
                    </div>
                </div>
                ${trapHtml}
            </div>
        `;
    }
    container.innerHTML = html;
}

function renderMultiDayConviction(trends, symbol) {
    const tbody = document.getElementById('multiday-conviction-body');
    if (!tbody) return;

    const sym = symbol || 'NIFTY';
    const trend = trends[sym];
    if (!trend || !trend.strikes || trend.strikes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">Insufficient history to render 5-Day Conviction Matrix. Snapshot archives building...</td></tr>';
        return;
    }

    // Show date range
    const datesEl = document.querySelector('.table-card-subtitle');
    if (datesEl && trend.dates && trend.dates.length >= 2) {
        datesEl.textContent = 'Range: ' + trend.dates[0] + ' \u2192 ' + trend.dates[trend.dates.length - 1] + ' | Multi-Session Accumulation vs Noise';
    }

    tbody.innerHTML = trend.strikes.map(s => {
        const ceTag = buildConvictionTag(s.ce_conviction);
        const peTag = buildConvictionTag(s.pe_conviction);
        const ceAlign = alignmentBadge(s.ce_alignment);
        const peAlign = alignmentBadge(s.pe_alignment);
        const ceAttr = s.ce_flow_attr && s.ce_flow_attr !== '--' ? `<span class="flow-attr">${s.ce_flow_attr}</span>` : '';
        const peAttr = s.pe_flow_attr && s.pe_flow_attr !== '--' ? `<span class="flow-attr">${s.pe_flow_attr}</span>` : '';

        const ceToday = s.today_ce_doi || 0;
        const peToday = s.today_pe_doi || 0;
        const ceTodayStr = (ceToday > 0 ? '+' : '') + formatIndianNum(ceToday);
        const peTodayStr = (peToday > 0 ? '+' : '') + formatIndianNum(peToday);

        return `
            <tr>
                <td>${ceAlign}${ceAttr}</td>
                <td>${ceTag}</td>
                <td class="${s.ce_trend_delta > 0 ? 'pos-red' : s.ce_trend_delta < 0 ? 'pos-green' : ''} font-mono">${s.ce_trend_delta > 0 ? '+' : ''}${formatIndianNum(s.ce_trend_delta)}<span class="today-subtext ${ceToday > 0 ? 't-red' : ceToday < 0 ? 't-green' : ''}">${ceTodayStr}</span></td>
                <td style="font-weight:800; color:#38bdf8;">${s.strike.toLocaleString('en-IN')}</td>
                <td class="${s.pe_trend_delta > 0 ? 'pos-green' : s.pe_trend_delta < 0 ? 'pos-red' : ''} font-mono">${s.pe_trend_delta > 0 ? '+' : ''}${formatIndianNum(s.pe_trend_delta)}<span class="today-subtext ${peToday > 0 ? 't-green' : peToday < 0 ? 't-red' : ''}">${peTodayStr}</span></td>
                <td>${peTag}</td>
                <td>${peAlign}${peAttr}</td>
            </tr>
        `;
    }).join('');
}

function renderStockBreadth(breadth) {
    const callBody = document.getElementById('breadth-call-writing-body');
    const putBody = document.getElementById('breadth-put-writing-body');
    const callUnwindBody = document.getElementById('breadth-call-unwind-body');
    const putUnwindBody = document.getElementById('breadth-put-unwind-body');

    const callList = breadth.call_writing_bearish || [];
    const putList = breadth.put_writing_bullish || [];
    const callUnwindList = breadth.call_unwinding_bullish || [];
    const putUnwindList = breadth.put_unwinding_bearish || [];

    const alignBadge = (s) => alignmentBadge(s.alignment);

    if (callList.length === 0) {
        callBody.innerHTML = '<tr><td colspan="5" class="text-center">No significant call writing today.</td></tr>';
    } else {
        callBody.innerHTML = callList.map(s => `
            <tr>
                <td><span class="font-mono" style="font-weight:800;">${s.symbol}</span></td>
                <td>${(s.ltp ?? 0).toLocaleString('en-IN')}</td>
                <td>${(s.top_ce_write_strike ?? 0).toLocaleString('en-IN')} CE</td>
                <td class="pos-red">+${formatIndianNum(s.top_ce_write_doi || 0)}</td>
                <td>${alignBadge(s)}</td>
            </tr>
        `).join('');
    }

    if (putList.length === 0) {
        putBody.innerHTML = '<tr><td colspan="5" class="text-center">No significant put writing today.</td></tr>';
    } else {
        putBody.innerHTML = putList.map(s => `
            <tr>
                <td><span class="font-mono" style="font-weight:800;">${s.symbol}</span></td>
                <td>${(s.ltp ?? 0).toLocaleString('en-IN')}</td>
                <td>${(s.top_pe_write_strike ?? 0).toLocaleString('en-IN')} PE</td>
                <td class="pos-green">+${formatIndianNum(s.top_pe_write_doi || 0)}</td>
                <td>${alignBadge(s)}</td>
            </tr>
        `).join('');
    }

    // Call Unwinding table
    if (!callUnwindBody) return;
    if (callUnwindList.length === 0) {
        callUnwindBody.innerHTML = '<tr><td colspan="5" class="text-center">No significant call unwinding today.</td></tr>';
    } else {
        callUnwindBody.innerHTML = callUnwindList.map(s => `
            <tr>
                <td><span class="font-mono" style="font-weight:800;">${s.symbol}</span></td>
                <td>${(s.ltp ?? 0).toLocaleString('en-IN')}</td>
                <td>${(s.top_ce_unwind_strike ?? 0).toLocaleString('en-IN')} CE</td>
                <td class="pos-green">${formatIndianNum(s.top_ce_unwind_doi || 0)}</td>
                <td>${alignBadge(s)}</td>
            </tr>
        `).join('');
    }

    // Put Unwinding table
    if (!putUnwindBody) return;
    if (putUnwindList.length === 0) {
        putUnwindBody.innerHTML = '<tr><td colspan="5" class="text-center">No significant put unwinding today.</td></tr>';
    } else {
        putUnwindBody.innerHTML = putUnwindList.map(s => `
            <tr>
                <td><span class="font-mono" style="font-weight:800;">${s.symbol}</span></td>
                <td>${(s.ltp ?? 0).toLocaleString('en-IN')}</td>
                <td>${(s.top_pe_unwind_strike ?? 0).toLocaleString('en-IN')} PE</td>
                <td class="pos-red">${formatIndianNum(s.top_pe_unwind_doi || 0)}</td>
                <td>${alignBadge(s)}</td>
            </tr>
        `).join('');
    }
}

function showVerdictError(msg, showRetry) {
    const title = document.getElementById('verdict-title');
    if (title) title.textContent = 'ERROR: ' + msg;
    const desc = document.getElementById('verdict-desc');
    if (desc) desc.textContent = 'Please try reloading the page or check the data source.';

    if (showRetry) {
        const banner = document.getElementById('verdict-executive-banner');
        if (banner) {
            // Remove existing retry button if any
            const oldBtn = banner.querySelector('.retry-btn');
            if (oldBtn) oldBtn.remove();
            const btn = document.createElement('button');
            btn.className = 'retry-btn';
            btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Retry';
            btn.addEventListener('click', () => {
                moneyFlowData = null;
                loadMoneyFlowView();
            });
            banner.appendChild(btn);
        }
    }
}

function renderFlowDivergence(divergence) {
    const container = document.getElementById('flow-divergence-body');
    const section = document.getElementById('flow-divergence-section');
    if (!container || !section) return;

    if (!divergence || divergence.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';
    container.innerHTML = '<div class="flow-divergence-list">' +
        divergence.map(d => {
            const typeKey = (d.type || 'CONFLICT_ZONE').toLowerCase().replace(/\s+/g, '-');
            const strikeStr = d.strike != null ? d.strike.toLocaleString('en-IN') : '--';
            return `
                <div class="flow-divergence-item">
                    <span class="divg-symbol">${d.symbol || '--'}</span>
                    <span class="divg-strike">${strikeStr}</span>
                    <span class="divg-badge ${typeKey}">${d.type || 'CONFLICT'}</span>
                    <span class="divg-desc">${d.desc || ''}</span>
                </div>
            `;
        }).join('') +
        '</div>';
}

// ─── Dedicated Charts View ───
let ohlcData = null;

async function renderChartsView() {
    if (availableDates.length < 2) return;

    chartsInstances.forEach(c => { if (c) c.destroy(); });
    chartsInstances = [];

    if (!ohlcData) {
        try {
            const res = await fetch('docs/ohlc_data.json');
            if (res.ok) ohlcData = await res.json();
        } catch (_) {}
    }

    const labels = availableDates.slice(1);
    const n = labels.length;

    // ── Compute daily net for each participant × instrument (no longer used by charts) ──
    // Kept for potential future use; data is cheap to compute.

    // NIFTY OHLC for candlestick (aligned to labels, nulls where missing)
    const niftyOHLC = new Array(labels.length).fill(null);
    if (ohlcData && ohlcData.nifty) {
        var hasOHLC = ohlcData.nifty.some(function(r) { return r.open !== undefined; });
        if (hasOHLC) {
            var ohlcByDate = {};
            ohlcData.nifty.forEach(function(r) {
                var parts = r.date.split('-');
                var csvDate = parts[2] + '-' + parts[1] + '-' + parts[0];
                ohlcByDate[csvDate] = [r.open, r.high, r.low, r.close];
            });
            labels.forEach(function(d, idx) {
                if (ohlcByDate[d]) niftyOHLC[idx] = ohlcByDate[d];
            });
        }
    }

    // Net option call & put holding per participant: (Long - Short) separately
    var partCallData = { FII: [], DII: [], Pro: [], Client: [] };
    var partPutData = { FII: [], DII: [], Pro: [], Client: [] };
    for (var i = 0; i < labels.length; i++) {
        var map = getParticipantMap(labels[i]);
        ['FII','DII','Pro','Client'].forEach(function(p) {
            var row = map[p] || {};
            var cl = row['Option Index Call Long'] || 0;
            var cs = row['Option Index Call Short'] || 0;
            var pl = row['Option Index Put Long'] || 0;
            var ps = row['Option Index Put Short'] || 0;
            partCallData[p][i] = cl - cs;
            partPutData[p][i] = pl - ps;
        });
    }

    const C = { fii: '#3b82f6', pro: '#f59e0b', client: '#ef4444', dii: '#10b981', smart: '#8b5cf6', price: '#22d3ee' };

    function getThemeMode() {
        return document.body.classList.contains('theme-dark') ? 'dark' : 'light';
    }

    function makeApexChart(id, config) {
        const el = document.getElementById(id);
        if (!el) return null;
        config.theme = config.theme || { mode: getThemeMode() };
        try {
            const chart = new ApexCharts(el, config);
            chart.render().catch(function(err) {
                console.warn('ApexCharts render error for', id, err);
            });
            chartsInstances.push(chart);
            return chart;
        } catch (err) {
            console.warn('ApexCharts creation error for', id, err);
            return null;
        }
    }

    // ════════════════════════════════════════
    //  4 — Participant Call/Put Holding + NIFTY Candlestick
    // ════════════════════════════════════════
    function renderOptHoldingChart(id, label, callData, putData, callColor, putColor) {
        var hasCandles = niftyOHLC && niftyOHLC.length > 0;

        if (hasCandles) {
            // Build series with sequential timestamps (1 day apart, no gaps)
            var candleSeries = [];
            var callSeries = [];
            var putSeries = [];
            var dateLabels = [];
            var seqIdx = 0;
            for (var fi = 0; fi < labels.length; fi++) {
                if (niftyOHLC[fi]) {
                    var ts = seqIdx * 86400000;
                    candleSeries.push({ x: ts, y: niftyOHLC[fi] });
                    callSeries.push({ x: ts, y: callData[fi] });
                    putSeries.push({ x: ts, y: putData[fi] });
                    dateLabels.push(labels[fi]);
                    seqIdx++;
                }
            }

            makeApexChart(id, {
                chart: { type: 'candlestick', height: 360, toolbar: { show: false }, zoom: { enabled: false }, selection: { enabled: false }, background: 'transparent' },
                series: [
                    { name: 'NIFTY', data: candleSeries },
                    { name: 'Calls', type: 'line', data: callSeries },
                    { name: 'Puts', type: 'line', data: putSeries }
                ],
                xaxis: {
                    type: 'datetime',
                    labels: { show: false },
                    axisBorder: { show: false },
                    axisTicks: { show: false }
                },
                yaxis: [
                    {
                        labels: { style: { fontSize: '8px' }, formatter: function(v) { return v.toLocaleString('en-IN'); } },
                        title: { text: 'NIFTY', style: { fontSize: '9px' } }
                    },
                    {
                        opposite: true,
                        labels: { style: { fontSize: '8px' }, formatter: function(v) { return (v/1000).toFixed(0) + 'K'; } },
                        title: { text: '', style: { fontSize: '9px' } },
                        grid: { drawOnChartArea: false }
                    }
                ],
                stroke: { width: [1, 2, 2], curve: 'smooth' },
                colors: [C.price, callColor, putColor],
                markers: { size: [0, 2, 2] },
                legend: { show: false },
                tooltip: {
                    shared: true,
                    custom: function(t) {
                        try {
                            var idx = t.dataPointIndex;
                            var srcData = t.w.config.series;
                            // Grab OHLC from source data directly (always [o,h,l,c])
                            var ohlc = srcData[0] && srcData[0].data[idx] ? srcData[0].data[idx].y : null;
                            // Grab call/put values
                            var callV = srcData[1] && srcData[1].data[idx] ? srcData[1].data[idx].y : null;
                            var putV = srcData[2] && srcData[2].data[idx] ? srcData[2].data[idx].y : null;
                            if (!ohlc) return false;
                            var n = function(v) { return v !== null && v !== undefined ? v.toLocaleString('en-IN') : '-'; };
                            return '<div style="padding:6px 10px;font-size:11px;background:var(--bg-card);border-radius:6px;border:1px solid var(--border-color);">' +
                                '<div style="font-weight:700;margin-bottom:3px;">' + (dateLabels[idx] || '') + '</div>' +
                                '<div><span style="color:#94a3b8;">O:</span> ' + n(ohlc[0]) + ' <span style="color:#94a3b8;">H:</span> <span style="color:#34d399;">' + n(ohlc[1]) + '</span></div>' +
                                '<div><span style="color:#94a3b8;">L:</span> <span style="color:#f87171;">' + n(ohlc[2]) + '</span> <span style="color:#94a3b8;">C:</span> ' + n(ohlc[3]) + '</div>' +
                                '<div style="border-top:1px solid var(--border-color);margin:3px 0 0;padding-top:3px;">' +
                                '<span style="color:#f87171;">Calls:</span> <span style="float:right;">' + n(callV) + '</span><br>' +
                                '<span style="color:#34d399;">Puts:</span> <span style="float:right;">' + n(putV) + '</span>' +
                                '</div></div>';
                        } catch(e) { return false; }
                    }
                },
                dataLabels: { enabled: false },
                grid: { borderColor: 'var(--border-color)' },
                theme: { mode: getThemeMode() },
                plotOptions: {
                    candlestick: {
                        colors: {
                            upward: '#34d399',
                            downward: '#f87171'
                        }
                    }
                }
            });
        } else {
            makeApexChart(id, {
                chart: { type: 'line', height: 360, toolbar: { show: false }, zoom: { enabled: false } },
                series: [
                    { name: label + ' Calls', data: callData },
                    { name: label + ' Puts', data: putData }
                ],
                xaxis: { categories: labels, labels: { style: { fontSize: '9px' } }, tickAmount: 10 },
                yaxis: [{ labels: { style: { fontSize: '8px' } }, title: { text: label, style: { fontSize: '9px' } } }],
                stroke: { width: [2, 2], curve: 'smooth' },
                colors: [callColor, putColor],
                markers: { size: [2, 2] },
                legend: { show: false },
                dataLabels: { enabled: false },
                grid: { borderColor: 'var(--border-color)' },
                theme: { mode: getThemeMode() }
            });
        }
    }

    var optPartMeta = [
        { id: 'ch-fii-options', label: 'FII', callColor: '#ef4444', putColor: '#34d399' },
        { id: 'ch-dii-options', label: 'DII', callColor: '#ef4444', putColor: '#34d399' },
        { id: 'ch-pro-options', label: 'Pro', callColor: '#ef4444', putColor: '#34d399' },
        { id: 'ch-client-options', label: 'Client', callColor: '#ef4444', putColor: '#34d399' }
    ];
    optPartMeta.forEach(function(m) {
        renderOptHoldingChart(m.id, m.label, partCallData[m.label], partPutData[m.label], m.callColor, m.putColor);
    });
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', initDashboard);

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
 * Render a human-readable FII-DII & Smart Money analysis commentary from participant_summary data.
 */
function renderCommentary(ps) {
    const card = document.getElementById('commentary-card');
    const container = document.getElementById('verdict-commentary');
    if (!container || !card) return;

    if (!ps || Object.keys(ps).length === 0) {
        card.style.display = 'none';
        return;
    }

    // Helper: action word for index calls
    function callAction(netShortChange) {
        // netShortChange = short - long. Negative means net buying (covering) — bullish.
        const net = -netShortChange; // flip to "net bought" semantics
        if (net > 20000) return 'Bought Index Calls ➕' + formatIndianNum(net) + ' Lots 🚀';
        if (net > 5000) return 'Bought Index Calls ➕' + formatIndianNum(net) + ' Lots 📈';
        if (net < -20000) return 'Sold Index Calls ➖' + formatIndianNum(-net) + ' Lots';
        if (net < -5000) return 'Sold Index Calls ➖' + formatIndianNum(-net) + ' Lots';
        return 'Flat Index Calls';
    }

    // Helper: action word for index puts
    function putAction(netShortChange) {
        // netShortChange = short - long. Positive means net writing (floor) — bullish.
        const net = -netShortChange; // flip: positive = net sold (writing), negative = net bought (long)
        if (net > 20000) return 'Sold Index Puts ➖' + formatIndianNum(net) + ' Lots ⚠️';
        if (net > 5000) return 'Sold Index Puts ➖' + formatIndianNum(net) + ' Lots';
        if (net < -20000) return 'Bought Index Puts ➕' + formatIndianNum(-net) + ' Lots';
        if (net < -5000) return 'Bought Index Puts ➕' + formatIndianNum(-net) + ' Lots';
        return 'Flat Index Puts';
    }

    // Build participant block
    function participantBlock(label, icon, data) {
        const fut = data.fut || 0;
        const ceIdx = data.ceIdx || 0;
        const peIdx = data.peIdx || 0;
        const stkFut = data.stkFut || 0;
        const stkCe = data.stkCe || 0;  // negative = net long (bought), positive = net short (sold)
        const stkPe = data.stkPe || 0;  // negative = net long (bought puts), positive = net short (sold puts)

        // Stock call direction
        const stkCeAction = stkCe < 0 ? 'Bought' : 'Sold';
        const stkCeArrow = stkCe < 0 ? '➕' : '➖';
        const stkCeColor = stkCe < 0 ? 'bg-green' : 'bg-red';
        const stkCeEmoji = stkCe < 0 ? '🟢' : '🔴';

        // Stock put direction
        const stkPeAction = stkPe < 0 ? 'Bought' : 'Sold';
        const stkPeArrow = stkPe < 0 ? '➕' : '➖';
        const stkPeColor = stkPe < 0 ? 'bg-green' : 'bg-red';
        const stkPeEmoji = stkPe < 0 ? '🟢' : '🔴';

        return `
            <div class="commentary-participant">
                <div class="commentary-participant-header ${data.headerClass || ''}">
                    ${icon} ${label}
                </div>
                <div class="commentary-participant-rows">
                    <div class="commentary-row">
                        <span class="commentary-badge ${fut > 0 ? 'bg-green' : 'bg-red'}">${fut > 0 ? '🟢' : '🔴'} ${fut > 0 ? 'Bought' : 'Sold'} Index Futures ${fut > 0 ? '➕' : '➖'}${formatIndianNum(Math.abs(fut))} Lots ${fut > 10000 ? '📈' : fut < -10000 ? '📉' : ''}</span>
                    </div>
                    <div class="commentary-row">
                        <span class="commentary-badge ${ceIdx > 0 ? 'bg-green' : 'bg-red'}">${ceIdx > 0 ? '🟢' : '🔴'} ${callAction(-ceIdx)}</span>
                    </div>
                    <div class="commentary-row">
                        <span class="commentary-badge ${peIdx < 0 ? 'bg-green' : 'bg-red'}">${peIdx < 0 ? '🟢' : '🔴'} ${putAction(-peIdx)}</span>
                    </div>
                    <div class="commentary-row">
                        <span class="commentary-badge ${stkFut > 0 ? 'bg-green' : 'bg-red'}">${stkFut > 0 ? '🟢' : '🔴'} ${stkFut > 0 ? 'Bought' : 'Sold'} Stock Futures ${stkFut > 0 ? '➕' : '➖'}${formatIndianNum(Math.abs(stkFut))} Lots ${Math.abs(stkFut) > 20000 ? '💪' : ''}</span>
                    </div>
                    <div class="commentary-row">
                        <span class="commentary-badge ${stkCeColor}">${stkCeEmoji} ${stkCeAction} Stock Calls ${stkCeArrow}${formatIndianNum(Math.abs(stkCe))} Lots</span>
                    </div>
                    <div class="commentary-row">
                        <span class="commentary-badge ${stkPeColor}">${stkPeEmoji} ${stkPeAction} Stock Puts ${stkPeArrow}${formatIndianNum(Math.abs(stkPe))} Lots</span>
                    </div>
                </div>
                ${data.note ? `<div class="commentary-note">${data.note}</div>` : ''}
            </div>
        `;
    }

    // Net index call/put flow: "net short change" → "net bought" (-ce_net_short_change = net call buying)
    const fiiCeFlow = -(ps.fii_ce_net_short_change || 0);
    const fiiPeFlow = -(ps.fii_pe_net_short_change || 0);
    const proCeFlow = -(ps.pro_ce_net_short_change || 0);
    const proPeFlow = -(ps.pro_pe_net_short_change || 0);
    const diiCeFlow = -(ps.dii_ce_net_short_change || 0);
    const diiPeFlow = -(ps.dii_pe_net_short_change || 0);
    const clientCeFlow = ps.client_ce_net_buy || 0; // already net bought
    const clientPeFlow = ps.client_pe_net_buy || 0; // already net bought

    const fiiNote = 'FIIs have turned aggressive buyers in Index Futures and Calls, showing confidence in an upside move. However, selling of Index Puts suggests they are keeping hedges in place and expect volatility. 📊';
    const diiNote = 'DII activity remained largely defensive with no strong directional conviction. ⚖️';
    const proNote = 'Pros have built fresh bullish positions in Index Futures and Calls, reinforcing the positive undertone. 📈';
    const clientNote = 'Retail participants continue to remain cautious and have increased downside protection through Put buying, while reducing long exposure. 😟';

    // Key takeaways
    const score = ps.smart_money_score || 0;
    const bias = ps.bias_label || 'NEUTRAL';
    let sentimentEmoji = score >= 15 ? '🟢' : score <= -15 ? '🔴' : '🟡';
    let sentimentText = score >= 40 ? 'POSITIVE' : score >= 15 ? 'MODERATELY POSITIVE' : score <= -40 ? 'STRONGLY NEGATIVE' : score <= -15 ? 'MODERATELY NEGATIVE' : 'MIXED / NEUTRAL';

    let html = `
        <div class="commentary-header">
            <div class="commentary-date">📅 Trading Session: ${ps.date || '--'}</div>
            <div class="commentary-sentiment">${sentimentEmoji} Overall Sentiment: <strong>${sentimentText}</strong> <span class="${score >= 0 ? 'pos-green' : 'pos-red'}">(${ps.bias_label || 'NEUTRAL'})</span></div>
        </div>
        <div class="commentary-grid">
            ${participantBlock('FIIs (Smart Money)', '💰 🏦', {
                fut: ps.fii_fut_net_change || 0,
                ceIdx: fiiCeFlow,
                peIdx: fiiPeFlow,
                stkFut: ps.fii_stk_fut_net_change || 0,
                stkCe: ps.fii_stk_ce_net_change || 0,
                stkPe: ps.fii_stk_pe_net_change || 0,
                headerClass: 'commentary-header-fii',
                note: fiiNote
            })}
            ${participantBlock('DIIs', '🏛️', {
                fut: ps.dii_fut_net_change || 0,
                ceIdx: diiCeFlow,
                peIdx: diiPeFlow,
                stkFut: ps.dii_stk_fut_net_change || 0,
                stkCe: ps.dii_stk_ce_net_change || 0,
                stkPe: ps.dii_stk_pe_net_change || 0,
                headerClass: 'commentary-header-dii',
                note: diiNote
            })}
            ${participantBlock('Proprietary Traders (Pros)', '🔥', {
                fut: ps.pro_fut_net_change || 0,
                ceIdx: proCeFlow,
                peIdx: proPeFlow,
                stkFut: ps.pro_stk_fut_net_change || 0,
                stkCe: ps.pro_stk_ce_net_change || 0,
                stkPe: ps.pro_stk_pe_net_change || 0,
                headerClass: 'commentary-header-pro',
                note: proNote
            })}
            ${participantBlock('Clients (Retail)', '👥', {
                fut: ps.client_fut_net_change || 0,
                ceIdx: clientCeFlow,
                peIdx: clientPeFlow,
                stkFut: ps.client_stk_fut_net_change || 0,
                stkCe: ps.client_stk_ce_net_change || 0,
                stkPe: ps.client_stk_pe_net_change || 0,
                headerClass: 'commentary-header-client',
                note: clientNote
            })}
        </div>
        <div class="commentary-takeaways">
            <div class="commentary-takeaways-title">🎯 Key Takeaways:</div>
            <div class="commentary-takeaways-list">
                <div class="commentary-takeaway-item">🟢 FIIs & Pros have added fresh Index Futures and Index Call positions – a constructive signal for bulls. 🐂</div>
                <div class="commentary-takeaway-item">🟢 Cash Market data is also supportive with FIIs buying <strong>₹2,982 Cr</strong> and DIIs buying <strong>₹998 Cr</strong>. 💰</div>
                <div class="commentary-takeaway-item">🟡 FII selling in Index Puts indicates expectations of higher volatility, so sharp intraday swings cannot be ruled out. ⚡</div>
                <div class="commentary-takeaway-item">🟢 Overall institutional positioning remains bullish, but traders should respect important support and resistance levels before taking aggressive positions.</div>
            </div>
        </div>
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

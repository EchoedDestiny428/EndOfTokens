window.addEventListener('pywebviewready', () => {
    setInterval(updateStats, 2000);
    updateStats();
});

async function updateStats() {
    const sessions = await pywebview.api.get_all_sessions();
    
    let totalReqs = 0;
    let totalTime = 0;
    let proUses = 0;
    let autoUses = 0;
    
    sessions.forEach(s => {
        totalReqs += s.stats.total_requests;
        totalTime += s.stats.total_time;
        proUses += s.stats.pro_uses;
        if (s.stats.openclaw_uses) autoUses += s.stats.openclaw_uses;
    });

    const html = `
        <div class="stat-card">
            <span class="label">Total Sessions</span>
            <span class="value">${sessions.length}</span>
        </div>
        <div class="stat-card">
            <span class="label">Total Requests</span>
            <span class="value">${totalReqs}</span>
        </div>
        <div class="stat-card">
            <span class="label">Total Compute Time</span>
            <span class="value">${totalTime.toFixed(2)}s</span>
        </div>
        <div class="stat-card">
            <span class="label">Pro CLI Queries</span>
            <span class="value">${proUses}</span>
        </div>
        <div class="stat-card">
            <span class="label">Auto Agent Loops</span>
            <span class="value">${autoUses}</span>
        </div>
    `;
    document.getElementById('stats').innerHTML = html;
}

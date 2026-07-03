const params = new URLSearchParams(location.search);
const gameId = params.get("g");
const app = document.getElementById("app");

let token = gameId ? getStoredToken(gameId) : null;
let formRoundKey = null;
let pollTimer = null;

function renderJoinForm() {
    app.innerHTML = `<div class="card">
        <h3>Csatlakozás a játékhoz (${gameId})</h3>
        <label>A neved</label>
        <input type="text" id="joinName" placeholder="pl. Béla">
        <button id="joinBtn">Csatlakozás</button>
        <div class="error" id="joinError"></div>
    </div>`;
    document.getElementById("joinBtn").addEventListener("click", async () => {
        const name = document.getElementById("joinName").value.trim();
        const errorBox = document.getElementById("joinError");
        if (!name) {
            errorBox.textContent = "Add meg a neved.";
            return;
        }
        try {
            const res = await api("POST", `/api/games/${gameId}/join`, { name });
            token = res.player_token;
            storeToken(gameId, token);
            startPolling();
        } catch (e) {
            errorBox.textContent = e.message;
        }
    });
}

function renderHeader(state) {
    let html = `<div class="card">
        <div class="row" style="justify-content:space-between;">
            <div><strong>Kör:</strong> ${state.round_index + 1} / ${state.total_rounds}</div>
            <div><strong>Te vagy:</strong> ${state.you.name}${state.you.is_host ? " (házigazda)" : ""}</div>
        </div>
        <p><strong>A betűid:</strong> ${
            state.you.letters.map((l) => `<span class="tile">${l}</span>`).join("") || '<span class="muted">(nincs betűd)</span>'
        }</p>
        <ul class="player-list">`;
    state.players.forEach((p) => {
        html += `<li><span>${p.name}${p.is_host ? " 👑" : ""}</span><span>${p.score} pont | ${p.money} pénz | ${p.letter_count} betű</span></li>`;
    });
    html += `</ul>`;
    if (state.you.is_host) {
        html += `<button id="forceEndBtn" class="secondary">Kör lezárása (lejárt az idő)</button>
        <div class="error" id="forceEndError"></div>`;
    }
    html += `</div>`;
    document.getElementById("header").innerHTML = html;
    if (state.you.is_host) {
        document.getElementById("forceEndBtn").addEventListener("click", async () => {
            try {
                await api("POST", `/api/games/${gameId}/force_end?token=${token}`);
                poll();
            } catch (e) {
                document.getElementById("forceEndError").textContent = e.message;
            }
        });
    }
}

function renderLobby(state) {
    const joinUrl = `${location.origin}/game?g=${gameId}`;
    const canStart = state.you && state.you.is_host;
    let html = `<div class="card">
        <h3>Váróterem</h3>
        <p>Hívd meg a többieket ezzel a linkkel:</p>
        <div class="row"><input type="text" readonly value="${joinUrl}" id="joinLink" style="flex:1;"><button id="copyLinkBtn" class="secondary">Másolás</button></div>
        <h4>Játékosok (${state.players.length})</h4>
        <ul class="player-list">${state.players.map((p) => `<li><span>${p.name}${p.is_host ? " 👑" : ""}</span></li>`).join("")}</ul>
        ${
            canStart
                ? `<button id="startBtn" ${state.players.length < 2 ? "disabled" : ""}>Játék indítása</button>${state.players.length < 2 ? '<p class="muted">Legalább 2 játékos kell az induláshoz.</p>' : ""}`
                : '<p class="muted">Várakozás, hogy a házigazda elindítsa a játékot...</p>'
        }
        <div class="error" id="lobbyError"></div>
    </div>`;
    document.getElementById("roundContent").innerHTML = html;
    document.getElementById("copyLinkBtn").addEventListener("click", () => {
        navigator.clipboard.writeText(joinUrl);
    });
    if (canStart) {
        document.getElementById("startBtn").addEventListener("click", async () => {
            try {
                await api("POST", `/api/games/${gameId}/start?token=${token}`);
            } catch (e) {
                document.getElementById("lobbyError").textContent = e.message;
            }
        });
    }
}

function renderFinished(state) {
    const sorted = [...state.players].sort((a, b) => b.score - a.score);
    let html = `<div class="card"><h3>Vége a játéknak!</h3><table><tr><th>Helyezés</th><th>Játékos</th><th>Pont</th></tr>`;
    sorted.forEach((p, i) => {
        html += `<tr><td>${i + 1}.</td><td>${p.name}</td><td>${p.score}</td></tr>`;
    });
    html += `</table></div>`;
    document.getElementById("roundContent").innerHTML = html;
}

function buildBidForm(state) {
    const round = state.round;
    const money = state.you.money;
    let html = `<div class="card"><h3>Licit kör</h3>
        <p>Pénzed: <strong>${money}</strong></p>`;
    round.auctions.forEach((a, i) => {
        html += `<div class="auction-card">
            <div>${a.letters.map((l) => `<span class="tile">${l}</span>`).join("")}</div>
            <label>Licit összeg erre a betűkészletre</label>
            <input type="number" min="0" value="${a.your_bid ?? 0}" class="bid-input" data-index="${i}">
        </div>`;
    });
    html += `<button id="submitBidsBtn">Licitek beküldése</button>
        <p class="muted" id="bidSubmittedCount"></p>
        <p class="success" id="bidConfirm"></p>
        <div class="error" id="bidError"></div>
    </div>`;
    document.getElementById("roundContent").innerHTML = html;
    document.getElementById("submitBidsBtn").addEventListener("click", async () => {
        const inputs = document.querySelectorAll(".bid-input");
        const bids = {};
        inputs.forEach((inp) => {
            bids[inp.dataset.index] = parseInt(inp.value || "0", 10);
        });
        try {
            await api("POST", `/api/games/${gameId}/bid?token=${token}`, { bids });
            document.getElementById("bidError").textContent = "";
            document.getElementById("bidConfirm").textContent =
                "Beküldve! Amíg a licit le nem zárul, még módosíthatod és újraküldheted.";
        } catch (e) {
            document.getElementById("bidError").textContent = e.message;
        }
    });
}

function patchBidStatus(state) {
    const c = document.getElementById("bidSubmittedCount");
    if (c) c.textContent = `${state.round.submitted_count}/${state.round.total_players} játékos küldött már be licitet.`;
}

function renderBidReveal(state) {
    const round = state.round;
    let html = `<div class="card"><h3>Licit kör – betűválasztás</h3>`;
    round.auctions.forEach((a, i) => {
        const statusBadge = a.done
            ? '<span class="badge done">Kész</span>'
            : a.is_your_turn
            ? '<span class="badge turn">Te vagy soron!</span>'
            : `<span class="badge wait">${a.current_picker ?? "-"} van soron</span>`;
        const remainingHtml =
            a.remaining
                .map((l) => {
                    const clickable = a.is_your_turn;
                    return `<span class="tile ${clickable ? "clickable" : ""}" ${
                        clickable ? `onclick="pickLetter(${i}, '${l}')"` : ""
                    }>${l}</span>`;
                })
                .join("") || "-";
        const bidsHtml = Object.entries(a.bids)
            .map(([n, v]) => `${n}: ${v}`)
            .join(", ");
        const assignedHtml =
            Object.entries(a.assigned)
                .map(([n, l]) => `${n}: ${l}`)
                .join(", ") || "-";
        html += `<div class="auction-card">
            <div class="row" style="justify-content:space-between;">
                <div>Eredeti betűk: ${a.letters.map((l) => `<span class="tile">${l}</span>`).join("")}</div>
                ${statusBadge}
            </div>
            <p class="muted">Licitek: ${bidsHtml}</p>
            <p>Maradék betűk: ${remainingHtml}</p>
            <p class="muted">Kiosztott betűk: ${assignedHtml}</p>
        </div>`;
    });
    html += `<div class="error" id="pickError"></div></div>`;
    document.getElementById("roundContent").innerHTML = html;
}

window.pickLetter = async function (auctionIndex, letter) {
    try {
        await api("POST", `/api/games/${gameId}/pick?token=${token}`, { auction_index: auctionIndex, letter });
        poll();
    } catch (e) {
        const box = document.getElementById("pickError");
        if (box) box.textContent = e.message;
    }
};

function buildWordForm(state) {
    const round = state.round;
    let html = `<div class="card"><h3>Szókirakás</h3>
        <p>Kategória: <strong>${round.category_name}</strong></p>
        <label>A szavad</label>
        <input type="text" id="wordInput" value="${round.your_submission || ""}" placeholder="pl. ALMA">
        <button id="submitWordBtn">Szó beküldése</button>
        <p class="muted" id="wordSubmittedCount"></p>
        <p class="success" id="wordConfirm"></p>
        <div class="error" id="wordError"></div>
    </div>`;
    document.getElementById("roundContent").innerHTML = html;
    document.getElementById("submitWordBtn").addEventListener("click", async () => {
        const word = document.getElementById("wordInput").value.trim();
        if (!word) return;
        try {
            await api("POST", `/api/games/${gameId}/word?token=${token}`, { word });
            document.getElementById("wordError").textContent = "";
            document.getElementById("wordConfirm").textContent =
                "Beküldve! Amíg a kör le nem zárul, még módosíthatod és újraküldheted.";
        } catch (e) {
            document.getElementById("wordError").textContent = e.message;
        }
    });
}

function patchWordStatus(state) {
    const c = document.getElementById("wordSubmittedCount");
    if (c) c.textContent = `${state.round.submitted_count}/${state.round.total_players} játékos küldött már be szót.`;
}

function renderWordResults(state) {
    const round = state.round;
    let html = `<div class="card"><h3>Szókirakás eredménye</h3><p>Kategória: <strong>${round.category_name}</strong></p>
        <table><tr><th>Játékos</th><th>Szó</th><th>Érvényes?</th><th>Pont</th></tr>`;
    Object.entries(round.results).forEach(([name, r]) => {
        html += `<tr><td>${name}</td><td>${r.word || "-"}</td><td>${r.valid ? "✅" : "❌"}</td><td>${r.points}</td></tr>`;
    });
    html += `</table><p class="muted">Hamarosan folytatódik a játék...</p></div>`;
    document.getElementById("roundContent").innerHTML = html;
}

function render(state) {
    if (state.status === "lobby") {
        document.getElementById("header").innerHTML = "";
        renderLobby(state);
        formRoundKey = null;
        return;
    }
    if (state.status === "finished") {
        document.getElementById("header").innerHTML = "";
        renderFinished(state);
        formRoundKey = null;
        return;
    }
    renderHeader(state);
    const round = state.round;
    if (!round) return;
    if (round.type === "bid") {
        if (!round.revealed) {
            const key = `bid-${state.round_index}`;
            if (formRoundKey !== key) {
                buildBidForm(state);
                formRoundKey = key;
            }
            patchBidStatus(state);
        } else {
            formRoundKey = null;
            renderBidReveal(state);
        }
    } else if (round.type === "word") {
        if (!round.resolved) {
            const key = `word-${state.round_index}`;
            if (formRoundKey !== key) {
                buildWordForm(state);
                formRoundKey = key;
            }
            patchWordStatus(state);
        } else {
            formRoundKey = null;
            renderWordResults(state);
        }
    }
}

async function poll() {
    try {
        const state = await api("GET", `/api/games/${gameId}/state?token=${token}`);
        render(state);
    } catch (e) {
        clearInterval(pollTimer);
        app.innerHTML = `<p class="error">${e.message}</p>`;
    }
}

function startPolling() {
    app.innerHTML = '<div id="header"></div><div id="roundContent"></div>';
    poll();
    pollTimer = setInterval(poll, 1000);
}

function init() {
    if (!gameId) {
        app.innerHTML = '<p class="error">Hiányzik a játék azonosítója a linkből.</p>';
        return;
    }
    if (!token) {
        renderJoinForm();
    } else {
        startPolling();
    }
}

init();

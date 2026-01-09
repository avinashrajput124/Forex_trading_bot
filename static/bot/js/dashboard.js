/* ---------- ELEMENTS ---------- */
const balance = document.getElementById("balance");
const equity = document.getElementById("equity");
const freeMargin = document.getElementById("freeMargin");
const openPL = document.getElementById("openPL");
const headerPL = document.getElementById("headerPL");
const account = document.getElementById("account");


const bid = document.getElementById("bid");
const ask = document.getElementById("ask");

const symbol = document.getElementById("symbol");
const tf = document.getElementById("tf");
const lot = document.getElementById("lot");
const strategy = document.getElementById("strategy");

const buyBtn = document.getElementById("buyBtn");
const sellBtn = document.getElementById("sellBtn");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const session = document.getElementById("session");


const tradeMsg = document.getElementById("tradeMsg"); // 👈 KEPT (nothing removed)


/* =========================================================
   API CALL (SAFE + BACKWARD COMPATIBLE)
========================================================= */
function apiCall(url, data = null) {
    let options = {};

    if (data) {
        options = {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        };
    }

    return fetch(url, options)
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        })
        .then(d => {
            if (d?.comment) {
                showMessage(d.comment, d.status !== "error");
            }

            if (d?.status === "error") {
                notify(d.comment || "Action failed", "error");
            }

            return d;
        })
        .catch(err => {
            console.error(err);
            showMessage("Server error", false);
            notify("Server not responding", "error");
        });
}


/* =========================================================
   OLD MESSAGE SYSTEM (KEPT AS-IS)
========================================================= */
function showMessage(msg, success = false) {
    if (!tradeMsg) return;
    tradeMsg.innerText = msg;
    tradeMsg.style.color = success ? "lime" : "red";
    tradeMsg.style.display = "block";
    setTimeout(() => tradeMsg.style.display = "none", 3000);
}
/* ---------- SYMBOLS LOAD ---------- */
apiCall("/symbols/")
    .then(d => {
        if (!d || !d.symbols) return;

        symbol.innerHTML = `<option value="">Select Symbol</option>`;

        d.symbols.forEach(s => {
            let o = document.createElement("option");
            o.value = s;
            o.innerText = s;
            symbol.appendChild(o);
        });
    });


/* =========================================================
   BUTTON LOGIC (UNCHANGED)
========================================================= */
function updateButtons() {
    if (strategy.value === "") {
        buyBtn.style.display = "inline-block";
        sellBtn.style.display = "inline-block";
        startBtn.style.display = "none";
        stopBtn.style.display = "none";
    } else {
        buyBtn.style.display = "none";
        sellBtn.style.display = "none";
        startBtn.style.display = "inline-block";
        stopBtn.style.display = "inline-block";
    }
}
strategy.addEventListener("change", updateButtons);
updateButtons();


/* =========================================================
   GLOBAL CONFIRM MODAL (REUSABLE)
========================================================= */
let confirmCallback = null;

function openConfirmModal({ title, message, onConfirm }) {
    document.getElementById("confirmTitle").innerText = title || "Confirm";
    document.getElementById("confirmMessage").innerText = message || "Are you sure?";
    confirmCallback = onConfirm;
    document.getElementById("globalConfirmModal").style.display = "flex";
}

function closeConfirmModal() {
    confirmCallback = null;
    document.getElementById("globalConfirmModal").style.display = "none";
}

document.getElementById("confirmActionBtn").onclick = function () {
    if (confirmCallback) confirmCallback();
    closeConfirmModal();
};


/* =========================================================
   ACCOUNT SOCKET (UNCHANGED)
========================================================= */
const accountSocket = new WebSocket("ws://127.0.0.1:8000/ws/account-info/");

accountSocket.onmessage = (e) => {
    const d = JSON.parse(e.data);

    balance.innerText = d.balance.toFixed(2);
    equity.innerText = d.equity.toFixed(2);
    freeMargin.innerText = d.free_margin.toFixed(2);
    account.innerText=d.account.toFixed(2);

    const tbody = document.querySelector("#runningStrategies tbody");
    tbody.innerHTML = "";

    if (!d.strategies || d.strategies.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align:center;">
                    No strategy running
                </td>
            </tr>`;
        return;
    }

    d.strategies.forEach((s, i) => {
        tbody.insertAdjacentHTML("beforeend", `
            <tr>
                <td>${i + 1}</td>
                <td>${s.strategy}</td>
                <td>${s.symbol}</td>
                <td>${s.timeframe}</td>
                <td>${s.lot}</td>
                <td>
                    <span class="${s.status === 'Running' ? 'running' : 'stopped'}">
                        ${s.status}
                    </span>
                </td>
                <td>
                    <button class="logout-btn" onclick="stopBot(${s.id})">
                        Stop Bot
                    </button>
                </td>
            </tr>
        `);
    });
};


/* =========================================================
   MANUAL TRADES (UNCHANGED)
========================================================= */
buyBtn.onclick = () =>
    apiCall(`/manual_trade/?symbol=${symbol.value}&lot=${lot.value}&side=BUY&tf=${tf.value}`);

sellBtn.onclick = () =>
    apiCall(`/manual_trade/?symbol=${symbol.value}&lot=${lot.value}&side=SELL&tf=${tf.value}`);


/* =========================================================
   BOT START (UNCHANGED)
========================================================= */
startBtn.onclick = () => {
    apiCall(`/start/?symbol=${symbol.value}&tf=${tf.value}&lot=${lot.value}&strategy=${strategy.value}&session=${session.value}`);
};


/* =========================================================
   BOT STOP (ONLY CONFIRM ADDED)
========================================================= */
function stopBot(botId) {
    openConfirmModal({
        title: "Stop Trading Bot",
        message: "Are you sure you want to stop this strategy?",
        onConfirm: () => {
            apiCall("/stop/", { bot_id: botId });
        }
    });
}


/* =========================================================
   LIVE PRICE (UNCHANGED)
========================================================= */
let priceSocket = new WebSocket("ws://127.0.0.1:8000/ws/live-price/");
priceSocket.onmessage = e => {
    let d = JSON.parse(e.data);
    bid.innerText = d.bid;
    ask.innerText = d.ask;
};
symbol.onchange = () =>
    priceSocket.send(JSON.stringify({ symbol: symbol.value }));


/* =========================================================
   OPEN TRADES (UNCHANGED)
========================================================= */
let openSocket = new WebSocket("ws://127.0.0.1:8000/ws/open-trades/");
openSocket.onmessage = e => {
    let d = JSON.parse(e.data);
    let tb = document.querySelector("#openTrades tbody");
    tb.innerHTML = "";

    let pl = 0;
    d.positions.forEach(p => {
        pl += p.profit;
        tb.innerHTML += `
        <tr>
            <td>${p.ticket}</td>
            <td>${p.symbol}</td>
            <td>${p.timeframe}</td>
            <td>${p.lot}</td>
            <td>${p.type}</td>
            <td>${p.open_time}</td>
            <td>${p.price_open}</td>
            <td>${p.current_price}</td>
            <td style="color:${p.profit >= 0 ? 'lime' : 'red'}">${p.profit}</td>
            <td>${p.sl}</td>


            
            <td>${p.tp}</td>
            <td>${p.strategy || 'Manual'}</td>
            <td>
                <button onclick="openConfirmModal({
                    title:'Close Trade',
                    message:'Close trade #${p.ticket}?',
                    onConfirm:()=>apiCall('/close_trade/?ticket=${p.ticket}')
                })">X</button>
            </td>
        </tr>`;
    });

    openPL.innerText = pl.toFixed(2);
    headerPL.innerText = `P/L: ${pl.toFixed(2)}`;
};


/* =========================================================
   TOAST NOTIFICATION (NEW – SAFE)
========================================================= */
function notify(message, type = "info", timeout = 3000) {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, timeout);
}


/* =========================================================
   TRADE HISTORY (FULL + SAFE)
========================================================= */

let historyPage = 1;
let perPage = 10;
const refreshBtn = document.getElementById("refreshHistory");

function loadHistory(page) {
    if (!refreshBtn) return;

    refreshBtn.classList.add("spin");

    fetch(`/trade_history/?page=${page}&per_page=${perPage}`)
        .then(res => {
            if (!res.ok) throw new Error("History fetch failed");
            return res.json();
        })
        .then(d => {
            const tb = document.querySelector("#tradeHistory tbody");
            if (!tb) return;

            tb.innerHTML = "";

            if (!d.history || d.history.length === 0) {
                tb.innerHTML = `
                    <tr>
                        <td colspan="10" style="text-align:center;">
                            No trade history found
                        </td>
                    </tr>`;
                return;
            }

            d.history.forEach(h => {
                tb.insertAdjacentHTML("beforeend", `
                    <tr>
                        <td>${h.ticket}</td>
                        <td>${h.symbol}</td>
                        <td>${h.lot}</td>
                        <td>${h.type}</td>
                        <td>${h.open_time}</td>
                        <td>${h.close_time}</td>
                        <td>${h.price_open}</td>
                        <td>${h.price_close}</td>
                        <td style="color:${h.profit >= 0 ? 'lime' : 'red'}">
                            ${h.profit}
                        </td>
                        <td>${h.strategy || "-"}</td>
                    </tr>
                `);
            });

            /* ---------- PAGINATION ---------- */
            const pag = document.getElementById("historyPagination");
            if (!pag) return;

            pag.innerHTML = "";

            for (let i = 1; i <= d.total_pages; i++) {
                const btn = document.createElement("button");
                btn.innerText = i;

                if (i === page) {
                    btn.classList.add("active");
                }

                btn.onclick = () => {
                    historyPage = i;
                    loadHistory(i);
                };

                pag.appendChild(btn);
            }
        })
        .catch(err => {
            console.error(err);
            notify("Failed to load trade history", "error");
        })
        .finally(() => {
            refreshBtn.classList.remove("spin");
        });
}

/* ---------- REFRESH BUTTON ---------- */
if (refreshBtn) {
    refreshBtn.onclick = () => loadHistory(historyPage);
}

/* ---------- INITIAL LOAD ---------- */
loadHistory(1);



function confirmLogout(e) {
    e.preventDefault(); // direct logout stop karega

    openConfirmModal({
        title: "Logout Confirmation",
        message: "Are you sure you want to logout from the dashboard?",
        onConfirm: () => {
            window.location.href = e.target.href;
        }
    });
}

console.log("Dashboard JS Loaded ✅");

window.onload = function () {

    const enableBacktest = document.getElementById("enableBacktest");
    const backtestDates = document.getElementById("backtestDates");
    const backtestResult = document.getElementById("backtestResultWrapper");

    // Trading buttons
    const buyBtn = document.getElementById("buyBtn");
    const sellBtn = document.getElementById("sellBtn");
    const startBtn = document.getElementById("startBtn");
    const stopBtn = document.getElementById("stopBtn");

    if (!enableBacktest) {
        console.error("❌ enableBacktest checkbox not found");
        return;
    }

    function disableTradingButtons(disable) {
        buyBtn.style.display = "none";
        sellBtn.style.display = "none";
        startBtn.style.display = "none";
        stopBtn.style.display = "none";

        buyBtn.style.opacity = disable ? "0.4" : "1";
        sellBtn.style.opacity = disable ? "0.4" : "1";
        startBtn.style.opacity = disable ? "0.4" : "1";
        stopBtn.style.opacity = disable ? "0.4" : "1";
    }

    enableBacktest.addEventListener("change", function () {

        console.log("Backtest enabled:", this.checked);

        if (this.checked) {
            // SHOW BACKTEST
            backtestDates.style.display = "block";
            backtestResult.style.display = "block";

            // DISABLE TRADING
            disableTradingButtons(true);

        } else {
            // HIDE BACKTEST
            backtestDates.style.display = "none";
            backtestResult.style.display = "none";
            

            // ENABLE TRADING
            disableTradingButtons(false);
        }
    });

};


document.getElementById("backtestBtn").addEventListener("click", async () => {
    const payload = {
        symbol: document.getElementById("symbol").value,
        timeframe: document.getElementById("tf").value,
        strategy: document.getElementById("strategy").value,
        from_date: document.getElementById("fromDate").value,
        to_date: document.getElementById("toDate").value,
        lot: document.getElementById("lot").value,
        session: document.getElementById("session").value
    };

    const res = await fetch("backtest/", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const data = await res.json();

    document.getElementById("backtestResultWrapper").style.display = "block";
    document.getElementById("btTrades").innerText = data.total_trades;
    document.getElementById("btWins").innerText = data.wins;
    document.getElementById("btLoss").innerText = data.losses;
    document.getElementById("btWinRate").innerText = data.winrate + "%";
    document.getElementById("btProfit").innerText = data.net_pnl;
    document.getElementById("btbalance").innerText = data.final_balance;


});


const sessionRow = document.getElementById("sessionRow");
const enableBacktest = document.getElementById("enableBacktest");
const backtestDates = document.getElementById("backtestDates");

strategy.addEventListener("change", () => {
    sessionRow.style.display = strategy.value ? "flex" : "none";
});

enableBacktest.addEventListener("change", () => {
    backtestDates.style.display = enableBacktest.checked ? "flex" : "none";
});
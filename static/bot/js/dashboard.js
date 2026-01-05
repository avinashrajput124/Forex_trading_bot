/* ---------- ELEMENTS ---------- */
const balance = document.getElementById("balance");
const equity = document.getElementById("equity");
const freeMargin = document.getElementById("freeMargin");
const openPL = document.getElementById("openPL");
const headerPL = document.getElementById("headerPL");

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

const botStatus = document.getElementById("botStatus");
const runningStrategy = document.getElementById("runningStrategy");
const tradeMsg = document.getElementById("tradeMsg");


/* ---------- GLOBAL API CALL HANDLER ---------- */
function apiCall(url) {
    // console.log(url,"myname hsjhdsjhdjshdjshj");

    return fetch(url)
        .then(res => res.json())
        .then(d => {
            if (d.comment) {
                showMessage(d.comment, d.retcode === 0);
            }
            console.error(d)
            return d;
        })
        .catch(err => {
            console.error(err);
            showMessage("Server error", false);
          
        });
}

/* ---------- UI MESSAGE ---------- */
function showMessage(msg, success = false) {
    if (!tradeMsg) return;
    tradeMsg.innerText = msg;
    tradeMsg.style.color = success ? "lime" : "red";
    tradeMsg.style.display = "block";

    setTimeout(() => {
        tradeMsg.style.display = "none";
    }, 3000);
}


/* ---------- BUTTON LOGIC ---------- */
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


/* ---------- ACCOUNT SOCKET ---------- */
/* ---------- ACCOUNT SOCKET ---------- */
const accountSocket = new WebSocket("ws://127.0.0.1:8000/ws/account-info/");

accountSocket.onmessage = (e) => {
    const d = JSON.parse(e.data);
    console.log("WS DATA:", d);

    /* ===== ACCOUNT INFO ===== */
    if (typeof d.balance !== "undefined") {
        balance.innerText = d.balance.toFixed(2);
        equity.innerText = d.equity.toFixed(2);
        freeMargin.innerText = d.free_margin.toFixed(2);
    }

    /* ===== RUNNING STRATEGIES ===== */
    const tbody = document.querySelector("#runningStrategies tbody");
    tbody.innerHTML = "";

    if (!Array.isArray(d.strategies) || d.strategies.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="3" style="text-align:center; color:#999;">
                    No strategy running
                </td>
            </tr>
        `;
        return;
    }

    d.strategies.forEach((strategy, index) => {
        const statusClass =
            strategy.status === "Running" ? "running" : "stopped";

        tbody.insertAdjacentHTML(
            "beforeend",
            `
            <tr>
                <td>${index + 1}</td>
                <td>${strategy.name}</td>
                <td>
                    <span class="${statusClass}">
                        ${strategy.status}
                    </span>
                </td>
            </tr>
            `
        );
    });
};

/* ---------- SOCKET ERROR HANDLING ---------- */
accountSocket.onerror = (err) => {
    console.error("WebSocket error:", err);
};

accountSocket.onclose = () => {
    console.warn("Account socket closed");
};

/* ---------- MANUAL TRADES ---------- */
buyBtn.onclick = () =>
    console.log("my ame is avinash")
    console.log("my ame is avinash")

    apiCall(`/manual_trade/?symbol=${symbol.value}&lot=${lot.value}&side=BUY&tf=${tf.value}`);

sellBtn.onclick = () =>
    apiCall(`/manual_trade/?symbol=${symbol.value}&lot=${lot.value}&side=SELL&tf=${tf.value}`);


/* ---------- BOT START / STOP ---------- */
startBtn.onclick = () => {
    apiCall(`/start/?symbol=${symbol.value}&tf=${tf.value}&lot=${lot.value}&strategy=${strategy.value}`)
        .then(() => {
            botStatus.innerText = "RUNNING";
            botStatus.className = "status running";
            runningStrategy.innerText = strategy.options[strategy.selectedIndex].text;
        });
};

stopBtn.onclick = () => {
    apiCall(`/stop/`)
        .then(() => {
            botStatus.innerText = "STOPPED";
            botStatus.className = "status stopped";
            runningStrategy.innerText = "--";
        });
};


/* ---------- LIVE PRICE ---------- */
let priceSocket = new WebSocket("ws://127.0.0.1:8000/ws/live-price/");
priceSocket.onmessage = e => {
    let d = JSON.parse(e.data);
    bid.innerText = d.bid;
    ask.innerText = d.ask;
};
symbol.onchange = () =>
    priceSocket.send(JSON.stringify({ symbol: symbol.value }));


/* ---------- OPEN TRADES ---------- */
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
                <button onclick="apiCall('/close_trade/?ticket=${p.ticket}')">X</button>
            </td>
        </tr>`;
    });

    openPL.innerText = pl.toFixed(2);
    headerPL.innerText = `P/L: ${pl.toFixed(2)}`;
};


/* ---------- SYMBOLS ---------- */
apiCall("/symbols/")
    .then(d => {
        d.symbols?.forEach(s => {
            let o = document.createElement("option");
            o.value = s;
            o.innerText = s;
            symbol.appendChild(o);
        });
    });


/* ---------- TRADE HISTORY ---------- */
let historyPage = 1;
let perPage = 10;
const refreshBtn = document.getElementById("refreshHistory");

function loadHistory(page) {
    refreshBtn.classList.add("spin");

    fetch(`/trade_history/?page=${page}&per_page=${perPage}`)
        .then(r => r.json())
        .then(d => {
            let tb = document.querySelector("#tradeHistory tbody");
            tb.innerHTML = "";

            d.history.forEach(h => {
                tb.innerHTML += `
                <tr>
                    <td>${h.ticket}</td>
                    <td>${h.symbol}</td>
                    <td>${h.lot}</td>
                    <td>${h.type}</td>
                    <td>${h.open_time}</td>
                    <td>${h.close_time}</td>
                    <td>${h.price_open}</td>
                    <td>${h.price_close}</td>
                    <td style="color:${h.profit >= 0 ? 'lime' : 'red'}">${h.profit}</td>
                    <td>${h.strategy}</td>
                </tr>`;
            });

            let pag = document.getElementById("historyPagination");
            pag.innerHTML = "";
            for (let i = 1; i <= d.total_pages; i++) {
                let b = document.createElement("button");
                b.innerText = i;
                if (i === page) b.style.background = "#555";
                b.onclick = () => {
                    historyPage = i;
                    loadHistory(i);
                };
                pag.appendChild(b);
            }
            refreshBtn.classList.remove("spin");
        })
        .catch(() => refreshBtn.classList.remove("spin"));
}

refreshBtn.onclick = () => loadHistory(historyPage);
loadHistory(1);

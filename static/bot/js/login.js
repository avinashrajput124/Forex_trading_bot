function showMessage(message, color="#fff") {
    const msg = document.getElementById("msg");
    msg.style.color = color;
    msg.innerHTML = message;
}

function connect(){
    const loginField = document.getElementById("login");
    const passwordField = document.getElementById("password");
    const serverField = document.getElementById("server");
    const btn = document.getElementById("btn");

    // Custom validation
    if(!loginField.value){
        showMessage("⚠ Please enter your MT5 Login ID", "#facc15");
        loginField.focus(); return;
    }
    if(!passwordField.value){
        showMessage("⚠ Please enter your MT5 Password", "#facc15");
        passwordField.focus(); return;
    }
    if(!serverField.value){
        showMessage("⚠ Please enter MT5 Server", "#facc15");
        serverField.focus(); return;
    }

    btn.disabled = true;
    showMessage('<span class="spinner"></span>Verifying MT5 connection...', "#94a3b8");

    fetch("/validate-mt5/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({
            login: loginField.value,
            password: passwordField.value,
            server: serverField.value
        })
    })
    .then(res => res.json())
    .then(data => {
        btn.disabled = false;
        if(data.status === "success"){
            showMessage("✔ " + data.message, "#22c55e");
            setTimeout(() => { window.location.href = ""; }, 900);
        } else {
            showMessage("✖ " + data.message, "#ef4444");
        }
    })
    .catch(() => {
        btn.disabled = false;
        showMessage("✖ Server not responding", "#ef4444");
    });
}

function getCookie(name){
    let cookieValue = null;
    if (document.cookie && document.cookie !== ''){
        const cookies = document.cookie.split(';');
        for (let i=0;i<cookies.length;i++){
            const cookie = cookies[i].trim();
            if (cookie.substring(0,name.length+1) === (name + '=')){
                cookieValue = decodeURIComponent(cookie.substring(name.length+1));
                break;
            }
        }
    }
    return cookieValue;
}

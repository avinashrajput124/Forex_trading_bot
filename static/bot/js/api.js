// -------- GLOBAL MESSAGE BOX ----------
function showMessage(msg, type) {
    let box = document.getElementById("uiMessage");

    if (!box) {
        box = document.createElement("div");
        box.id = "uiMessage";
        document.body.prepend(box);
    }

    box.className = `ui-message ${type}`;
    box.innerText = msg;
    box.style.display = "block";

    setTimeout(() => {
        box.style.display = "none";
    }, 4000);
}


// -------- GLOBAL API CALL ----------
function apiCall(url, options = {}) {
    return fetch(url, options)
        .then(res => res.json())
        .then(d =>
          {
            if (!d.success) {
                showMessage(d.message || "Something went wrong", "error");
                console.log(d,"err")

                throw d;
            }

            if (d.message) {
                showMessage(d.message, "success");
            }
            console.log(d,"errrtttt")


            return d;
        })
        .catch(err => {
            if (!err || !err.message) {
                showMessage("Server error / Network issue", "error");
            }
            console.log(err,"err")

            throw err;
        });
}

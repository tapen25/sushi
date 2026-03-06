let total = 0;

function addPlate(price) {
    const userID = document.getElementById("userID").value;
    //合計金額を計算
    total += price;
    //合計金額を書き換え
    document.getElementById("total").innerText = total;

    //DBに送信
    fetch("/plates", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ user_id: parseInt(userID), price: price })
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("order-message").innerText = "へい！まいどあり！";
    });
}

//豆知識を表示する
function showTrivia() {
    fetch("/trivial")
    .then(response => response.json())
    .then(data => {
        const bubble = document.getElementById("trivial-message");
        const text = document.getElementById("bubble-text");
        text.innerText = data.text;
        bubble.style.display = "block";
    })
    .catch(error => {
        console.error("Error fetching trivia:", error);
    });
}

//豆知識のバブルを閉じる
function closeBubble(){
    document.getElementById("trivial-message").style.display="none"
}
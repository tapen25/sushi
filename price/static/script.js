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
        document.getElementById("message").innerText = "へい！まいどあり！";
    });
}
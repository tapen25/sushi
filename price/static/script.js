function addPlate(price) {
    const userID = document.getElementById("userID").value;

    fetch("/plates", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ user_id: parseInt(userID), price: price })
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("message").innerText = "へい！まいどあり！"+price+"円";
    });
}
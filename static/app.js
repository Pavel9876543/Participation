// ==================================================
// SWIPE LOGIC (open / close card)
// ==================================================
document.querySelectorAll(".card").forEach(card => {
    let startX = 0;
    let currentX = 0;
    let dragging = false;

    const content = card.querySelector(".card-content");

    content.addEventListener("touchstart", e => {
        startX = e.touches[0].clientX;
        dragging = true;
    });

    content.addEventListener("touchmove", e => {
        if (!dragging) return;

        currentX = e.touches[0].clientX - startX;

        // двигаем только влево
        if (currentX < 0) {
            content.style.transform =
                `translateX(${Math.max(currentX, -200)}px)`;
        }
    });

    content.addEventListener("touchend", () => {
        dragging = false;

        if (currentX < -60) {
            closeAllCards();
            card.classList.add("open");
        } else {
            card.classList.remove("open");
            content.style.transform = "";
        }

        currentX = 0;
    });
});

// закрыть все карточки
function closeAllCards() {
    document.querySelectorAll(".card.open").forEach(card => {
        card.classList.remove("open");
        const content = card.querySelector(".card-content");
        content.style.transform = "";
    });
}

// закрытие при тапе вне карточек
document.addEventListener("click", e => {
    if (!e.target.closest(".card")) {
        closeAllCards();
    }
});


// ==================================================
// MOVE UP / DOWN (swap neighbors)
// ==================================================
document.querySelectorAll(".move-up").forEach(btn => {
    btn.addEventListener("click", async e => {
        e.stopPropagation();
        const card = btn.closest(".card");
        await move(card.dataset.id, "up");
    });
});

document.querySelectorAll(".move-down").forEach(btn => {
    btn.addEventListener("click", async e => {
        e.stopPropagation();
        const card = btn.closest(".card");
        await move(card.dataset.id, "down");
    });
});

async function move(id, direction) {
    await fetch("/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, direction })
    });
    location.reload();
}


// ==================================================
// DELETE
// ==================================================
document.querySelectorAll(".delete").forEach(btn => {
    btn.addEventListener("click", async e => {
        e.stopPropagation();
        if (!confirm("Удалить запись?")) return;

        const card = btn.closest(".card");

        await fetch("/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: card.dataset.id })
        });

        location.reload();
    });
});


// ==================================================
// EDIT RECORD (ONE ✏️ BUTTON)
// ==================================================
document.querySelectorAll(".edit-record-btn").forEach(btn => {
    btn.addEventListener("click", async e => {
        e.stopPropagation();
        const card = btn.closest(".card");

        // если НЕ в режиме редактирования → войти
        if (!card.classList.contains("editing")) {
            enterEditMode(card);
            return;
        }

        // если уже редактируем → сохранить
        await saveEdit(card);
        location.reload();
    });
});


// ==================================================
// ENTER EDIT MODE
// ==================================================
function enterEditMode(card) {
    const editBtn = card.querySelector(".edit-record-btn");
    editBtn.textContent = "💾";
    editBtn.title = "Сохранить";
    card.classList.add("editing");

    // ФИО
    card.querySelector(".person-text").hidden = true;
    card.querySelector(".person-input").hidden = false;

    // статус
    card.querySelector(".status-text").hidden = true;
    card.querySelector(".status-select").hidden = false;

    // дата
    const status = card.querySelector(".status-select").value;
    const dateText = card.querySelector(".date-text");
    const dateInput = card.querySelector(".date-input");

    dateText.hidden = true;

    if (status === "+") {
        dateInput.hidden = false;
        dateInput.disabled = false;
    } else {
        dateInput.hidden = true;
        dateInput.disabled = true;
    }

    // если пользователь меняет статус → реагируем
    card.querySelector(".status-select").addEventListener("change", e => {
        if (e.target.value === "+") {
            dateInput.hidden = false;
            dateInput.disabled = false;
        } else {
            dateInput.hidden = true;
            dateInput.disabled = true;
        }
    });
}


// ==================================================
// SAVE EDIT
// ==================================================
async function saveEdit(card) {
    const id = card.dataset.id;

    const person = card.querySelector(".person-input").value;
    const status = card.querySelector(".status-select").value || null;

    // сохраняем ФИО
    await fetch("/update-person", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, person })
    });

    // сохраняем статус
    await fetch("/update-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, status })
    });

    // сохраняем дату ТОЛЬКО если +
    if (status === "+") {
        const date = card.querySelector(".date-input").value;
        if (date) {
            await fetch("/update-date", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id, date })
            });

    const editBtn = card.querySelector(".edit-record-btn");
    editBtn.textContent = "✏️";
    editBtn.title = "Редактировать";
        }
    }
}

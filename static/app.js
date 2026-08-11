// ==================================================
// SWIPE LOGIC (open / close card)
// ==================================================
document.querySelectorAll(".card").forEach(card => {

    let startX = 0
    let currentX = 0
    let dragging = false

    const content = card.querySelector(".card-content")

    content.addEventListener("touchstart", e => {

        startX = e.touches[0].clientX
        dragging = true

    })

    content.addEventListener("touchmove", e => {

        if (!dragging) return

        currentX = e.touches[0].clientX - startX

        if (currentX < 0) {

            content.style.transform =
                `translateX(${Math.max(currentX, -200)}px)`

        }

    })

    content.addEventListener("touchend", () => {

        dragging = false

        if (currentX < -60) {

            closeAllCards()
            card.classList.add("open")

        } else {

            card.classList.remove("open")
            content.style.transform = ""

        }

        currentX = 0

    })

})


// ==================================================
// CLOSE CARDS
// ==================================================
function closeAllCards() {

    document.querySelectorAll(".card.open").forEach(card => {

        card.classList.remove("open")

        const content = card.querySelector(".card-content")
        content.style.transform = ""

    })

}


document.addEventListener("click", e => {

    if (!e.target.closest(".card")) {

        closeAllCards()

    }

})


// ==================================================
// REQUEST HELPERS
// ==================================================
async function sendJson(url, payload) {

    const response = await fetch(url, {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify(payload)

    })

    const result = await response.json()

    if (!response.ok || result.success === false) {

        throw new Error(result.error || "Ошибка сохранения. Повторите операцию.")

    }

    return result

}


function showError(error) {

    alert(error.message || "Ошибка сохранения. Повторите операцию.")

}


// ==================================================
// MOVE UP / DOWN
// ==================================================
const LONG_PRESS_DELAY = 650


setupMoveButton(".move-up", "up", "start")
setupMoveButton(".move-down", "down", "end")


function setupMoveButton(selector, direction, target) {

    document.querySelectorAll(selector).forEach(btn => {

        let longPressTimer = null
        let longPressTriggered = false

        btn.addEventListener("pointerdown", e => {

            e.stopPropagation()

            if (btn.dataset.moving === "1") return

            longPressTriggered = false

            longPressTimer = window.setTimeout(async () => {

                longPressTriggered = true
                btn.dataset.moving = "1"

                try {

                    const card = btn.closest(".card")

                    await move(card.dataset.id, direction, target)

                } finally {

                    btn.dataset.moving = ""

                }

            }, LONG_PRESS_DELAY)

        })

        btn.addEventListener("pointerup", clearLongPressTimer)
        btn.addEventListener("pointerleave", clearLongPressTimer)
        btn.addEventListener("pointercancel", clearLongPressTimer)

        btn.addEventListener("click", async e => {

            e.stopPropagation()

            if (longPressTriggered) {

                e.preventDefault()
                longPressTriggered = false
                return

            }

            if (btn.dataset.moving === "1") return

            const card = btn.closest(".card")

            await move(card.dataset.id, direction)

        })

        function clearLongPressTimer() {

            if (longPressTimer) {

                window.clearTimeout(longPressTimer)
                longPressTimer = null

            }

        }

    })

}


async function move(id, direction, target = null) {

    try {

        await sendJson("/move", { id, direction, target })

        location.reload()

    } catch (error) {

        showError(error)

    }

}


// ==================================================
// DELETE
// ==================================================
document.querySelectorAll(".delete").forEach(btn => {

    btn.addEventListener("click", async e => {

        e.stopPropagation()

        if (!confirm("Удалить запись?")) return

        const card = btn.closest(".card")

        try {

            await sendJson("/delete", { id: card.dataset.id })

            location.reload()

        } catch (error) {

            showError(error)

        }

    })

})


// ==================================================
// EDIT RECORD
// ==================================================
document.querySelectorAll(".edit-record-btn").forEach(btn => {

    btn.addEventListener("click", async e => {

        e.stopPropagation()

        const card = btn.closest(".card")

        if (!card.classList.contains("editing")) {

            enterEditMode(card)
            return

        }

        try {

            await saveEdit(card)

            location.reload()

        } catch (error) {

            showError(error)

        }

    })

})


// ==================================================
// ENTER EDIT MODE
// ==================================================
function enterEditMode(card) {

    const editBtn = card.querySelector(".edit-record-btn")

    editBtn.textContent = "💾"
    editBtn.title = "Сохранить"

    card.classList.add("editing")

    // ФИО
    card.querySelector(".person-text").hidden = true
    card.querySelector(".person-input").hidden = false

    // статус
    card.querySelector(".status-text").hidden = true
    card.querySelector(".status-select").hidden = false

    // дата редактируется только у базовой записи без статуса
    const dateText = card.querySelector(".date-text")
    const dateInput = card.querySelector(".date-input")

    const canEditDate = card.dataset.canEditDate === "1"

    dateText.hidden = canEditDate
    dateInput.hidden = !canEditDate
    dateInput.disabled = !canEditDate

}


// ==================================================
// SAVE EDIT
// ==================================================
async function saveEdit(card) {

    const id = card.dataset.id

    const person = card.querySelector(".person-input").value
    const status = card.querySelector(".status-select").value || null
    const date = card.querySelector(".date-input").value

    await sendJson("/update-record", {

        id,
        person,
        status,
        date: card.dataset.canEditDate === "1" ? date : null

    })

}

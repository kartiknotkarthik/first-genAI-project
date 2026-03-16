import { buildRequestPayload, validateFields, mapRestaurantsToCards } from "./uiLogic.js";

const form = document.getElementById("preference-form");
const resetBtn = document.getElementById("reset-btn");
const formErrorEl = document.getElementById("form-error");
const statusPill = document.getElementById("status-pill");
const resultsStatus = document.getElementById("results-status");
const resultsExplanation = document.getElementById("results-explanation");
const resultsList = document.getElementById("results-list");

const slider = document.getElementById("maxPrice");
const budgetValue = document.getElementById("budget-value");
if (slider && budgetValue) {
  slider.addEventListener("input", (e) => {
    budgetValue.textContent = e.target.value;
  });
}

function readFormFields() {
  const data = new FormData(form);
  // Max price slider value
  const maxPriceVal = document.getElementById("maxPrice").value;
  return {
    freeText: data.get("freeText") || "",
    city: data.get("city") || "",
    cuisine: data.get("cuisine") || "",
    minRating: data.get("minRating") || "",
    maxPrice: maxPriceVal || "",
    limit: data.get("limit") || "10",
  };
}

function renderCards(restaurants, explanationText) {
  const cards = mapRestaurantsToCards(restaurants);
  resultsList.innerHTML = "";

  if (!cards.length) {
    resultsStatus.textContent = "No results found.";
    resultsExplanation.textContent =
      explanationText ||
      "No restaurants matched your filters. Try relaxing the rating or budget, or widening the area.";
    return;
  }

  resultsStatus.textContent = `${cards.length} result(s) shown.`;
  if (explanationText) {
    resultsExplanation.textContent = explanationText;
  }

  for (const card of cards) {
    const li = document.createElement("li");
    li.className = "card";
    li.innerHTML = `
      <div>
        <div class="card-title">${card.name}</div>
        <div class="card-meta">${card.subtitle}</div>
        <div class="tag-row">
          ${
            card.price
              ? `<span class="tag">Approx Cost: ${card.price} INR</span>`
              : ""
          }
        </div>
      </div>
      <div class="card-right">
        ${
          card.rating != null
            ? `<div>⭐ ${card.rating.toFixed(1)}</div>`
            : "<div>Rating N/A</div>"
        }
      </div>
    `;
    resultsList.appendChild(li);
  }
}

async function handleSubmit(event) {
  event.preventDefault();
  formErrorEl.textContent = "";
  statusPill.textContent = "Loading...";
  resultsList.innerHTML = "";

  const fields = readFormFields();
  const validation = validateFields(fields);
  if (!validation.valid) {
    formErrorEl.textContent = validation.message;
    statusPill.textContent = "Validation error";
    return;
  }

  const payload = buildRequestPayload(fields);

  try {
    const response = await fetch("http://localhost:8000/api/recommendations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_message: payload.user_message || "Recommend restaurants",
        limit: payload.limit || 10
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend error: ${response.statusText}`);
    }

    const data = await response.json();
    statusPill.textContent = "Results received";
    renderCards(data.restaurants, data.explanation);
    
    // Store session ID for future refinements if provided
    if (data.session_id) {
      window.currentSessionId = data.session_id;
    }
  } catch (error) {
    statusPill.textContent = "Error connecting to backend";
    formErrorEl.textContent = `Could not fetch recommendations: ${error.message}. Is the backend running?`;
    console.error(error);
  }
}

function handleReset() {
  form.reset();
  formErrorEl.textContent = "";
  if (budgetValue) {
    budgetValue.textContent = "2000";
  }
  statusPill.textContent = "Idle";
  resultsStatus.textContent = "No results yet.";
  resultsExplanation.textContent =
    "When you request recommendations, this panel will show Groq’s explanation and a ranked list of restaurants from the Zomato dataset.";
  resultsList.innerHTML = "";
}

async function fetchMetadata() {
  try {
    const res = await fetch("http://localhost:8000/api/metadata");
    if (!res.ok) return;
    const data = await res.json();
    
    const citiesList = document.getElementById("cities");
    if (citiesList && data.cities) {
      data.cities.forEach(city => {
        if (city) {
          const opt = document.createElement("option");
          opt.value = city;
          citiesList.appendChild(opt);
        }
      });
    }

    const cuisinesList = document.getElementById("cuisines");
    if (cuisinesList && data.cuisines) {
      data.cuisines.forEach(c => {
        if (c) {
          const opt = document.createElement("option");
          opt.value = c;
          cuisinesList.appendChild(opt);
        }
      });
    }
  } catch (err) {
    console.error("Could not load metadata", err);
  }
}

if (form) {
  form.addEventListener("submit", handleSubmit);
}
if (resetBtn) {
  resetBtn.addEventListener("click", handleReset);
}

// Fetch metadata on load
fetchMetadata();


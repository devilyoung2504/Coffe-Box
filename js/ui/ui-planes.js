import { estado } from "../state/state.js";

export function initPlanesPage() {
  renderPlanes();
}

function renderPlanes() {
  const row = document.querySelector("#plans-container");
  if (!row || !estado.catalogo) return;

  row.innerHTML = estado.catalogo.plans
    .map((plan) => {
      const destacado = plan.id === "standard" ? "featured" : "";
      const precio = plan.priceMonthly.toLocaleString("es-CO");

      return `
        <div class="col-md-4">
          <div class="plan-card ${destacado}">
            <h3>${plan.name}</h3>
            <p class="plan-price">$${precio} / mes</p>
            <ul class="plan-list">
              ${plan.features.map((f) => `<li>${f}</li>`).join("")}
            </ul>
            <a href="suscribirse.html?plan=${plan.id}" class="plan-button">
              Elegir este plan
            </a>
          </div>
        </div>
      `;
    })
    .join("");
}

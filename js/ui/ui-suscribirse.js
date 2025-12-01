// js/ui/ui-suscribirse.js
import { estado } from "../state/state.js";
import { guardarSuscripcion } from "../services/suscripcionesStorage.js";

export function initSuscribirsePage() {
  const form = document.getElementById("suscripcionForm");
  const planSelect = document.getElementById("planSelect");
  const brandSelect = document.getElementById("brandSelect");
  const grindSelect = document.getElementById("tipoCafeSelect");

  if (!form || !planSelect || !brandSelect || !grindSelect || !estado.catalogo) {
    console.warn("No se encontró el formulario o el catálogo aún no está cargado.");
    return;
  }

  // 1. Poblar select de planes desde el catálogo
  planSelect.innerHTML = estado.catalogo.plans
    .map((plan) => {
      const label = `${plan.name} - $${plan.priceMonthly.toLocaleString("es-CO")}`;
      return `<option value="${plan.id}">${label}</option>`;
    })
    .join("");

  // 2. Poblar select de marcas desde coffeeBrands
  brandSelect.innerHTML = estado.catalogo.coffeeBrands
    .map((brand) => {
      const label = `${brand.name} (${brand.origin})`;
      return `<option value="${brand.id}">${label}</option>`;
    })
    .join("");

  // 3. Preseleccionar plan si viene como query param ?plan=standard
  const url = new URL(window.location.href);
  const planParam = url.searchParams.get("plan");
  if (planParam) {
    planSelect.value = planParam;
  }

  // 4. Actualizar moliendas según la marca seleccionada
  function actualizarGrinds() {
    const brandId = brandSelect.value;
    const brand = estado.catalogo.coffeeBrands.find((b) => b.id === brandId);

    if (!brand) {
      grindSelect.innerHTML = "";
      return;
    }

    grindSelect.innerHTML = brand.grindOptions
      .map((g) => `<option value="${g.id}">${g.label}</option>`)
      .join("");
  }

  // Llenar moliendas la primera vez
  actualizarGrinds();
  // Y cada vez que cambie la marca
  brandSelect.addEventListener("change", actualizarGrinds);

  // 5. Manejar envío del formulario
  form.addEventListener("submit", (e) => {
    e.preventDefault();

    // Datos del cliente
    const nombre = document.getElementById("nombre").value.trim();
    const apellido = document.getElementById("apellido").value.trim();
    const email = document.getElementById("email").value.trim();
    const telefono = document.getElementById("telefono").value.trim();
    const direccion = document.getElementById("direccion").value.trim();

    // Configuración de la suscripción
    const planId = planSelect.value;
    const brandId = brandSelect.value;
    const grindId = grindSelect.value;

    if (
      !nombre ||
      !apellido ||
      !email ||
      !telefono ||
      !direccion ||
      !planId ||
      !brandId ||
      !grindId
    ) {
      alert("Por favor completa todos los campos del formulario.");
      return;
    }

    const suscripcionBase = {
      planId,
      brands: [
        {
          brandId,
          grindId,
        },
      ],
      customer: {
        name: nombre,
        lastname: apellido,
        email,
        phone: telefono,
        address: direccion,
      },
    };

    const guardada = guardarSuscripcion(suscripcionBase);
    console.log("Suscripción guardada:", guardada);
    alert("¡Suscripción creada! ID: " + guardada.id);

    form.reset();
    // Después del reset, volvemos a dejar selects en estado inicial
    planSelect.selectedIndex = 0;
    brandSelect.selectedIndex = 0;
    actualizarGrinds();
  });
}
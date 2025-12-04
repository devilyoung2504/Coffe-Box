const CATALOGO_URL = "js/data/catalogo.json";

// 1. Cargar catálogo desde el JSON
async function cargarCatalogo() {
  const resp = await fetch(CATALOGO_URL);
  if (!resp.ok) {
    throw new Error("No se pudo cargar el catálogo");
  }
  return await resp.json();
}

// 2. Rellenar select de planes
function llenarPlanes(plans, select) {
  select.innerHTML = "";
  plans.forEach((plan) => {
    const option = document.createElement("option");
    option.value = plan.id;
    const precioFormateado = plan.priceMonthly.toLocaleString("es-CO");
    option.textContent = `${plan.name} - $${precioFormateado}`;
    select.appendChild(option);
  });
}

// 3. Rellenar select de marcas
function llenarMarcas(brands, select) {
  select.innerHTML = "";
  brands.forEach((brand) => {
    const option = document.createElement("option");
    option.value = brand.id;
    option.textContent = `${brand.name} (${brand.origin})`;
    select.appendChild(option);
  });
}

// 4. Rellenar select de tipos de molienda en función de la marca
function llenarMoliendas(brands, brandId, select) {
  select.innerHTML = "";

  const brand = brands.find((b) => b.id === brandId);
  if (!brand) return;

  brand.grindOptions.forEach((g) => {
    const option = document.createElement("option");
    option.value = g.id;
    option.textContent = g.label;
    select.appendChild(option);
  });
}

// 5. Inicializar la página de suscripción
async function initSuscribirsePage() {
  const form        = document.getElementById("suscripcionForm");
  const planSelect  = document.getElementById("planSelect");
  const brandSelect = document.getElementById("brandSelect");
  const grindSelect = document.getElementById("tipoCafeSelect");

  if (!form || !planSelect || !brandSelect || !grindSelect) {
    console.warn("No se encontró el formulario o los selects en el DOM.");
    return;
  }

  try {
    // 5.1. Cargar catálogo
    const catalogo = await cargarCatalogo();
    console.log("Catálogo cargado:", catalogo);

    const { plans, coffeeBrands } = catalogo;

    // 5.2. Rellenar selects
    llenarPlanes(plans, planSelect);
    llenarMarcas(coffeeBrands, brandSelect);
    // inicializar molienda con la primera marca
    llenarMoliendas(coffeeBrands, brandSelect.value, grindSelect);

    // Cuando cambie la marca, actualizar tipos de molienda
    brandSelect.addEventListener("change", () => {
      llenarMoliendas(coffeeBrands, brandSelect.value, grindSelect);
    });

    // 5.3. Manejar el envío del formulario
    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const nombre    = document.getElementById("nombre").value;
      const apellido  = document.getElementById("apellido").value;
      const email     = document.getElementById("email").value;
      const telefono  = document.getElementById("telefono").value;
      const direccion = document.getElementById("direccion").value;

      const payload = {
        planId: planSelect.value,
        brands: [
          {
            brandId: brandSelect.value,
            grindId: grindSelect.value,
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

      console.log("Enviando suscripción:", payload);

      try {
        const resp = await fetch("http://localhost:3000/api/suscripciones", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await resp.json();
        console.log("Respuesta backend:", data);

        if (!resp.ok || !data.ok) {
          throw new Error(data.error || "Error al guardar suscripción");
        }

        alert("¡Suscripción creada correctamente!");
        form.reset();

        // volver a rellenar selects después del reset
        llenarPlanes(plans, planSelect);
        llenarMarcas(coffeeBrands, brandSelect);
        llenarMoliendas(coffeeBrands, brandSelect.value, grindSelect);
      } catch (err) {
        console.error("Error al enviar suscripción:", err);
        alert("Ocurrió un error guardando la suscripción.");
      }
    });
  } catch (err) {
    console.error("Error inicializando la página de suscribirse:", err);
  }
}

// 6. Lanzar todo cuando cargue el DOM
document.addEventListener("DOMContentLoaded", initSuscribirsePage);

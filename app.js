import { cargarCatalogo } from "./js/services/catalogoService.js";
import { estado } from "./js/state/state.js";
import { guardarSuscripcion, obtenerSuscripciones } from "./js/services/suscripcionesStorage.js";

document.addEventListener("DOMContentLoaded", async () => {
  try {
    // Cargar catalogo
    const catalogo = await cargarCatalogo();
    estado.catalogo = catalogo;

    console.log("Catálogo cargado:", catalogo);

    // Suscripcion de ejemplo - borrar luego
    const suscripcionDemo = {
      planId: "standard",
      brands: [
        { brandId: "brand_juan_valdez", grindId: "espresso" }
      ],
      customer: {
        name: "Cliente Demo",
        email: "demo@example.com",
        phone: "3000000000",
        address: "Dirección demo 123"
      }
    };

    const guardada = guardarSuscripcion(suscripcionDemo);
    console.log("Suscripción guardada:", guardada);

    console.log("Todas las suscripciones:", obtenerSuscripciones());
  } catch (err) {
    console.error(err);
  }
});

//prueba

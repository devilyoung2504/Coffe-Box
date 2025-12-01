// js/app.js
import { cargarCatalogo } from "./services/catalogoService.js";
import { estado } from "./state/state.js";
import { initPlanesPage } from "./ui/ui-planes.js";
import { initSuscribirsePage } from "./ui/ui-suscribirse.js";

document.addEventListener("DOMContentLoaded", async () => {
  const page = document.body.dataset.page;

  try {
    const catalogo = await cargarCatalogo();
    estado.catalogo = catalogo;

    if (page === "planes") {
      initPlanesPage();
    } else if (page === "suscribirse") {
      initSuscribirsePage();
    } else {
      console.log("Página:", page);
    }
  } catch (err) {
    console.error("Error inicializando la app:", err);
  }
});

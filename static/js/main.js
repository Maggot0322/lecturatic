/* ==========================================================
   LECTURATIC - main.js
   Funciones generales: cronómetro de actividades, selección
   visual de respuestas y animación de celebración (confeti).
   ========================================================== */

// ---------- Cronómetro de actividad ----------
let segundosTranscurridos = 0;
let intervaloCronometro = null;

function iniciarCronometro() {
  const elemento = document.getElementById("cronometro");
  const campoOculto = document.getElementById("tiempo_segundos");
  if (!elemento) return;

  intervaloCronometro = setInterval(function () {
    segundosTranscurridos++;
    const minutos = Math.floor(segundosTranscurridos / 60).toString().padStart(2, "0");
    const segundos = (segundosTranscurridos % 60).toString().padStart(2, "0");
    elemento.textContent = `${minutos}:${segundos}`;
    if (campoOculto) campoOculto.value = segundosTranscurridos;
  }, 1000);
}

document.addEventListener("DOMContentLoaded", iniciarCronometro);

// ---------- Selección visual de opciones (radio buttons estilizados) ----------
document.addEventListener("click", function (e) {
  const opcion = e.target.closest(".opcion-respuesta");
  if (!opcion) return;
  const grupo = opcion.dataset.grupo;
  document.querySelectorAll(`.opcion-respuesta[data-grupo="${grupo}"]`).forEach((el) => {
    el.classList.remove("seleccionada");
  });
  opcion.classList.add("seleccionada");
  const radio = opcion.querySelector('input[type="radio"]');
  if (radio) radio.checked = true;
});

// ---------- Celebración con confeti al aprobar ----------
function lanzarConfeti() {
  const colores = ["#2E7D32", "#1565C0", "#FF9800", "#F44336", "#9C27B0"];
  for (let i = 0; i < 60; i++) {
    const pieza = document.createElement("div");
    pieza.className = "confeti";
    pieza.style.left = Math.random() * 100 + "vw";
    pieza.style.width = pieza.style.height = Math.random() * 8 + 6 + "px";
    pieza.style.backgroundColor = colores[Math.floor(Math.random() * colores.length)];
    pieza.style.animationDuration = 2 + Math.random() * 2 + "s";
    document.body.appendChild(pieza);
    setTimeout(() => pieza.remove(), 4200);
  }
}

// ---------- Confirmaciones de acciones administrativas ----------
function confirmarAccion(mensaje) {
  return confirm(mensaje || "¿Estás seguro de realizar esta acción?");
}

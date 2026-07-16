/* ==========================================================
   LECTURATIC - accesibilidad.js
   Controla: modo oscuro, tamaño de fuente, alto contraste
   y lectura de texto en voz alta (Text-to-Speech).
   ========================================================== */

document.addEventListener("DOMContentLoaded", function () {
  const body = document.body;

  // Cargar preferencias guardadas en localStorage del navegador (solo UI, no datos académicos)
  const prefs = {
    tema: localStorage.getItem("lecturatic_tema") || "claro",
    fuente: localStorage.getItem("lecturatic_fuente") || "normal",
    contraste: localStorage.getItem("lecturatic_contraste") || "normal",
  };
  aplicarPreferencias(prefs);

  function aplicarPreferencias(p) {
    body.classList.toggle("tema-oscuro", p.tema === "oscuro");
    body.classList.toggle("contraste-alto", p.contraste === "alto");
    body.classList.remove("fuente-grande", "fuente-xgrande");
    if (p.fuente === "grande") body.classList.add("fuente-grande");
    if (p.fuente === "xgrande") body.classList.add("fuente-xgrande");
  }

  function guardarPreferencias(p) {
    localStorage.setItem("lecturatic_tema", p.tema);
    localStorage.setItem("lecturatic_fuente", p.fuente);
    localStorage.setItem("lecturatic_contraste", p.contraste);
    fetch("/api/accesibilidad", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p),
    }).catch(() => {});
  }

  // Botón: alternar modo oscuro
  const btnTema = document.getElementById("btnTema");
  if (btnTema) {
    btnTema.addEventListener("click", function () {
      prefs.tema = prefs.tema === "oscuro" ? "claro" : "oscuro";
      aplicarPreferencias(prefs);
      guardarPreferencias(prefs);
    });
  }

  // Botón: aumentar tamaño de letra (cíclico: normal -> grande -> xgrande -> normal)
  const btnFuente = document.getElementById("btnFuente");
  if (btnFuente) {
    btnFuente.addEventListener("click", function () {
      prefs.fuente = prefs.fuente === "normal" ? "grande" :
                      prefs.fuente === "grande" ? "xgrande" : "normal";
      aplicarPreferencias(prefs);
      guardarPreferencias(prefs);
    });
  }

  // Botón: alto contraste
  const btnContraste = document.getElementById("btnContraste");
  if (btnContraste) {
    btnContraste.addEventListener("click", function () {
      prefs.contraste = prefs.contraste === "normal" ? "alto" : "normal";
      aplicarPreferencias(prefs);
      guardarPreferencias(prefs);
    });
  }

  // Botón: lectura por voz (Text-to-Speech) del contenido principal
  const btnVoz = document.getElementById("btnVoz");
  if (btnVoz) {
    let hablando = false;
    btnVoz.addEventListener("click", function () {
      if (!("speechSynthesis" in window)) {
        alert("Tu navegador no soporta lectura por voz.");
        return;
      }
      if (hablando) {
        window.speechSynthesis.cancel();
        hablando = false;
        btnVoz.classList.remove("btn-danger");
        return;
      }
      const contenedor = document.querySelector("[data-lectura-voz]");
      const texto = contenedor ? contenedor.innerText : document.body.innerText;
      const utterance = new SpeechSynthesisUtterance(texto);
      utterance.lang = "es-ES";
      utterance.rate = 0.95;
      utterance.onend = () => {
        hablando = false;
        btnVoz.classList.remove("btn-danger");
      };
      window.speechSynthesis.speak(utterance);
      hablando = true;
      btnVoz.classList.add("btn-danger");
    });
  }
});

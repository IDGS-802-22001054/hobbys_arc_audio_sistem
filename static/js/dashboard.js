document.addEventListener("DOMContentLoaded", () => {

    const tabVentas = document.getElementById("d-tab-ventas");
    const tabDefectos = document.getElementById("d-tab-defectos");

    const panelVentas = document.querySelector(".d-graph-panel--ventas");
    const panelDefectos = document.querySelector(".d-graph-panel--defectos");

    function actualizarVista() {
        if (tabVentas.checked) {
            panelVentas.style.display = "flex";
            panelDefectos.style.display = "none";
        } else {
            panelVentas.style.display = "none";
            panelDefectos.style.display = "flex";
        }
    }

    tabVentas.addEventListener("change", actualizarVista);
    tabDefectos.addEventListener("change", actualizarVista);

    actualizarVista();

    // animación
    const bars = document.querySelectorAll(".d-bar");

    bars.forEach(bar => {
        const finalHeight = bar.style.height;

        bar.style.height = "0%";

        setTimeout(() => {
            bar.style.height = finalHeight;
        }, 200);
    });

});
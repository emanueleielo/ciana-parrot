document.addEventListener("DOMContentLoaded", function () {
  if (typeof mermaid === "undefined") return;

  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    themeVariables: {
      darkMode: true,
      background: "#050510",
      primaryColor: "#0a0a2a",
      primaryTextColor: "#E8DCC8",
      primaryBorderColor: "rgba(0, 240, 255, 0.2)",
      lineColor: "#5A5A6A",
      secondaryColor: "#0a0a2a",
      tertiaryColor: "#0a0a2a",
      noteTextColor: "#E8DCC8",
      noteBkgColor: "rgba(8, 8, 25, 0.85)",
      noteBorderColor: "rgba(0, 240, 255, 0.2)",
      actorTextColor: "#E8DCC8",
      actorBkg: "rgba(8, 8, 25, 0.85)",
      actorBorder: "rgba(0, 240, 255, 0.2)",
      actorLineColor: "#5A5A6A",
      signalColor: "#E8DCC8",
      signalTextColor: "#E8DCC8",
      labelBoxBkgColor: "rgba(8, 8, 25, 0.85)",
      labelBoxBorderColor: "rgba(0, 240, 255, 0.2)",
      labelTextColor: "#E8DCC8",
      loopTextColor: "#00F0FF",
      activationBorderColor: "#00F0FF",
      activationBkgColor: "rgba(0, 240, 255, 0.08)",
      sequenceNumberColor: "#050510",
      edgeLabelBackground: "#050510",
      clusterBkg: "rgba(0, 240, 255, 0.03)",
      clusterBorder: "rgba(0, 240, 255, 0.12)",
      titleColor: "#E8DCC8",
      nodeTextColor: "#E8DCC8",
    },
    flowchart: { curve: "basis", htmlLabels: true },
    sequence: { mirrorActors: false },
  });

  document.querySelectorAll(".mermaid").forEach(function (el) {
    // Read textContent to get un-escaped text
    var text = el.textContent || el.innerText;
    if (!text.trim()) return;
    el.removeAttribute("data-processed");
    el.textContent = text;
  });

  mermaid.run({ querySelector: ".mermaid" });
});

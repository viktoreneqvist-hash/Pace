const tooltip = document.getElementById("tooltip");

document.querySelectorAll(".hover-value").forEach((item) => {
  item.addEventListener("mouseenter", (event) => {
    tooltip.textContent = item.dataset.tooltip;
    tooltip.style.display = "block";
    tooltip.style.left = `${event.clientX + 14}px`;
    tooltip.style.top = `${event.clientY + 14}px`;
  });
  item.addEventListener("mousemove", (event) => {
    tooltip.style.left = `${event.clientX + 14}px`;
    tooltip.style.top = `${event.clientY + 14}px`;
  });
  item.addEventListener("mouseleave", () => {
    tooltip.style.display = "none";
  });
});

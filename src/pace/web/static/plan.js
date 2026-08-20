const revisionButton = document.getElementById("plan-revision-button");
const revisionStatus = document.getElementById("plan-revision-status");

if (revisionButton && revisionStatus) {
  revisionButton.addEventListener("click", async () => {
    const csrf = document.querySelector('meta[name="pace-csrf"]')?.content;
    const planId = Number(revisionButton.dataset.planId);
    const originalLabel = revisionButton.textContent;
    revisionButton.disabled = true;
    revisionButton.textContent = "Skapar nästa 14 dagar…";
    revisionStatus.hidden = true;

    try {
      const response = await fetch("/api/plan/revise/confirm", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Pace-CSRF": csrf || ""},
        body: JSON.stringify({plan_id: planId}),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Revisionen kunde inte skapas.");
      revisionStatus.classList.remove("error");
      revisionStatus.textContent = `Plan ${payload.plan.id} är aktiv. Plan-vyn uppdateras nu.`;
      revisionStatus.hidden = false;
      window.setTimeout(() => window.location.assign("/plan"), 500);
    } catch (error) {
      revisionButton.disabled = false;
      revisionButton.textContent = originalLabel;
      revisionStatus.classList.add("error");
      revisionStatus.textContent = `Kunde inte skapa nästa 14 dagar: ${error.message}`;
      revisionStatus.hidden = false;
    }
  });
}

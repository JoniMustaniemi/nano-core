function formatPlanDate(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function updatePlansBadge(plans) {
  const hasPending = Array.isArray(plans) && plans.some((plan) => plan.status === "pending");
  plansTabBadge.hidden = !hasPending;
}

function closePlanReader() {
  activePlanId = null;
  planReader.hidden = true;
  plansList.hidden = false;
}

function openPlanReader(plan) {
  activePlanId = plan.id;
  planReaderTitle.textContent = plan.title || "Improvement plan";
  planReaderBody.textContent = plan.body || "";
  planProcessButton.hidden = plan.status !== "pending";
  planProcessButton.disabled = plan.status !== "pending";
  plansList.hidden = true;
  planReader.hidden = false;
}

async function openPlanById(planId) {
  const response = await fetch(`/api/improvement-plans/${planId}`);
  if (!response.ok) {
    return;
  }
  const plan = await response.json();
  openPlanReader(plan);
}

function renderPlans(plans) {
  updatePlansBadge(plans);
  plansList.replaceChildren();
  if (!Array.isArray(plans) || plans.length === 0) {
    const empty = document.createElement("p");
    empty.className = "plans-empty";
    empty.textContent = "No improvement plans yet.";
    plansList.appendChild(empty);
    return;
  }

  for (const plan of plans) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "plan-card";
    button.setAttribute("role", "listitem");

    const title = document.createElement("span");
    title.className = "plan-card-title";
    title.textContent = plan.title || "Improvement plan";

    const meta = document.createElement("span");
    meta.className = "plan-card-meta";
    const statusLabel = plan.status === "pending" ? "Pending review" : "Processed";
    meta.textContent = `${statusLabel} · ${formatPlanDate(plan.created_at)}`;

    button.append(title, meta);
    button.addEventListener("click", () => {
      void openPlanById(plan.id);
    });
    plansList.appendChild(button);
  }
}

async function loadPlans() {
  try {
    const response = await fetch("/api/improvement-plans");
    if (!response.ok) {
      return;
    }
    const plans = await response.json();
    renderPlans(plans);
  } catch (_error) {
    // Keep the current list if the request fails.
  }
}

async function processActivePlan() {
  if (activePlanId === null) {
    return;
  }
  const response = await fetch(`/api/improvement-plans/${activePlanId}/process`, {
    method: "POST",
  });
  if (!response.ok) {
    return;
  }
  closePlanReader();
  await loadPlans();
}

planReaderBack.addEventListener("click", closePlanReader);
planProcessButton.addEventListener("click", () => {
  void processActivePlan();
});

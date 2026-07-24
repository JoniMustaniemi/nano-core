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

function isPlanReaderOpen() {
  return activePlanId !== null && planReader && !planReader.hidden;
}

let planCopyResetTimer = null;

function updatePlanCopyButton() {
  if (!planCopyButton) {
    return;
  }
  const hasBody = Boolean(planReaderBody?.textContent?.trim());
  planCopyButton.disabled = !isPlanReaderOpen() || !hasBody;
}

function resetPlanCopyButtonLabel() {
  if (!planCopyButton) {
    return;
  }
  planCopyButton.setAttribute("aria-label", "Copy plan");
}

function closePlanReader() {
  activePlanId = null;
  activePlanKind = "drafted";
  planReader.hidden = true;
  plansList.hidden = false;
  nanoPanelPlans.classList.remove("reading");
  if (planCopyResetTimer) {
    clearTimeout(planCopyResetTimer);
    planCopyResetTimer = null;
  }
  resetPlanCopyButtonLabel();
  updatePlanCopyButton();
}

function openPlanReader(plan) {
  activePlanId = plan.id;
  activePlanKind = plan.kind || "drafted";
  planReaderTitle.textContent = planCardLabel(plan);
  planReaderBody.textContent = plan.body || "";
  planProcessButton.hidden = plan.status !== "pending" || activePlanKind !== "drafted";
  planProcessButton.disabled = plan.status !== "pending" || activePlanKind !== "drafted";
  plansList.hidden = true;
  planReader.hidden = false;
  nanoPanelPlans.classList.add("reading");
  resetPlanCopyButtonLabel();
  updatePlanCopyButton();
}

async function openPlanById(planId, kind = "drafted") {
  const path =
    kind === "suggestion"
      ? `/api/improvement-plans/suggestions/${planId}`
      : `/api/improvement-plans/${planId}`;
  const response = await fetch(path);
  if (!response.ok) {
    return;
  }
  const plan = await response.json();
  openPlanReader(plan);
}

function planCardLabel(plan) {
  const raw = plan.title || plan.goal || "Improvement plan";
  const cleaned = String(raw).replace(/\s+/g, " ").trim();
  if (cleaned.length <= 96) {
    return cleaned;
  }
  return `${cleaned.slice(0, 93)}...`;
}

function updatePlansTabCount(plans) {
  if (!plansTabCount) {
    return;
  }
  const pending = Array.isArray(plans)
    ? plans.filter((plan) => plan.status === "pending" || plan.status === "queued").length
    : 0;
  plansTabCount.hidden = pending === 0;
  plansTabCount.textContent = String(pending);
  plansTabCount.setAttribute(
    "aria-label",
    pending === 1 ? "1 pending plan" : `${pending} pending plans`,
  );
}

function renderPlans(plans) {
  updatePlansTabCount(plans);
  if (!plansList) {
    return;
  }
  plansList.replaceChildren();
  if (!Array.isArray(plans) || plans.length === 0) {
    if (!isPlanReaderOpen()) {
      plansList.hidden = false;
    }
    const empty = document.createElement("p");
    empty.className = "plans-empty";
    empty.textContent =
      "No improvement topics yet. Nano will queue ideas from codebase scans when idle.";
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
    title.textContent = planCardLabel(plan);

    const meta = document.createElement("span");
    meta.className = "plan-card-meta";
    meta.textContent = formatPlanDate(plan.created_at);

    const status = document.createElement("span");
    const isPending = plan.status === "pending";
    const isQueued = plan.status === "queued";
    status.className = `plan-card-status ${isPending ? "pending" : isQueued ? "queued" : "processed"}`;
    status.textContent = isPending ? "Pending" : isQueued ? "Queued" : "Done";

    button.append(title, meta, status);
    button.addEventListener("click", () => {
      void openPlanById(plan.id, plan.kind || "drafted");
    });
    plansList.appendChild(button);
  }
  plansList.hidden = isPlanReaderOpen();
}

async function loadPlans() {
  if (!plansList) {
    return;
  }
  try {
    const response = await fetch("/api/improvement-plans");
    if (!response.ok) {
      renderPlans([]);
      return;
    }
    const plans = await response.json();
    renderPlans(plans);
  } catch (_error) {
    renderPlans([]);
  }
}

async function processActivePlan() {
  if (activePlanId === null || activePlanKind !== "drafted") {
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

async function copyActivePlan() {
  if (!planReaderBody?.textContent?.trim() || !planCopyButton) {
    return;
  }
  try {
    await navigator.clipboard.writeText(planReaderBody.textContent);
    planCopyButton.setAttribute("aria-label", "Copied");
    if (planCopyResetTimer) {
      clearTimeout(planCopyResetTimer);
    }
    planCopyResetTimer = setTimeout(() => {
      resetPlanCopyButtonLabel();
      planCopyResetTimer = null;
    }, 1500);
  } catch (_error) {
    planCopyButton.setAttribute("aria-label", "Copy failed");
    if (planCopyResetTimer) {
      clearTimeout(planCopyResetTimer);
    }
    planCopyResetTimer = setTimeout(() => {
      resetPlanCopyButtonLabel();
      planCopyResetTimer = null;
    }, 1500);
  }
}

planProcessButton.addEventListener("click", () => {
  void processActivePlan();
});

if (planCopyButton) {
  planCopyButton.addEventListener("click", () => {
    void copyActivePlan();
  });
}

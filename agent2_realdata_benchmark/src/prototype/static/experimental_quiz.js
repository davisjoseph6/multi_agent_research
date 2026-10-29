"use strict";

// Development only. This browser script never selects the assistance
// policy. SQLite and Flask enforce the assigned experimental offer gate.
(() => {
  const API = "/api/v1/trial-dev";
  const SESSION_KEY = "ijcai2027_trial_dev_session";
  const PENDING_KEY = "ijcai2027_trial_dev_pending";
  const CONTINUED_KEY = "ijcai2027_trial_dev_continued";
  const ENROLLMENT_KEY = "ijcai2027_trial_dev_enrollment";

  const el = {
    start: document.getElementById("start-session"),
    refresh: document.getElementById("refresh-session"),
    retry: document.getElementById("retry-submission"),
    session: document.getElementById("session-label"),
    status: document.getElementById("status"),
    assistance: document.getElementById("assistance-panel"),
    offerTitle: document.getElementById("offer-title"),
    offerMessage: document.getElementById("offer-message"),
    decisionButtons: document.getElementById("offer-decision-buttons"),
    deliveryButtons: document.getElementById("offer-delivery-buttons"),
    accept: document.getElementById("accept-assistance"),
    decline: document.getElementById("decline-assistance"),
    view: document.getElementById("view-assistance"),
    resource: document.getElementById("resource-panel"),
    resourceBody: document.getElementById("resource-body"),
    continue: document.getElementById("continue-after-summary"),
    questionPanel: document.getElementById("question-panel"),
    complete: document.getElementById("completion-panel"),
    form: document.getElementById("answer-form"),
    fieldset: document.getElementById("answer-fieldset"),
    meta: document.getElementById("question-meta"),
    prompt: document.getElementById("question-prompt"),
    choices: document.getElementById("choice-list"),
    submit: document.getElementById("submit-answer")
  };

  let sessionId = localStorage.getItem(SESSION_KEY);
  let pending = null;
  let offer = null;
  let currentQuestion = null;
  let busy = false;

  try {
    pending = JSON.parse(sessionStorage.getItem(PENDING_KEY) || "null");
  } catch {
    sessionStorage.removeItem(PENDING_KEY);
  }
  if (!pending || pending.sessionId !== sessionId) {
    pending = null;
    sessionStorage.removeItem(PENDING_KEY);
  }

  function setStatus(message, isError = false) {
    el.status.textContent = message;
    el.status.className = isError ? "error" : "";
  }

  function offerKey(record) {
    return `${sessionId}:${record.source_position}`;
  }

  function updateControls() {
    el.start.disabled = busy || Boolean(pending);
    el.refresh.disabled = busy || !sessionId;
    el.retry.hidden = !pending;
    el.retry.disabled = busy;
    el.submit.disabled = busy || Boolean(pending) || !currentQuestion;
    el.fieldset.disabled = busy || Boolean(pending);
    el.accept.disabled = busy || Boolean(pending);
    el.decline.disabled = busy || Boolean(pending);
    el.view.disabled = busy || Boolean(pending);
    el.continue.disabled = busy || Boolean(pending);
  }

  async function requestJson(path, method = "GET", payload) {
    const options = {method, cache: "no-store", headers: {}};
    if (payload !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.error || `HTTP ${response.status}`);
      error.status = response.status;
      error.code = data.error;
      throw error;
    }
    return data;
  }

  function endpoint(suffix) {
    return `${API}/sessions/${encodeURIComponent(sessionId)}/${suffix}`;
  }

  function hideScreens() {
    el.assistance.hidden = true;
    el.questionPanel.hidden = true;
    el.complete.hidden = true;
    el.resource.hidden = true;
    el.resourceBody.textContent = "";
    el.decisionButtons.hidden = true;
    el.deliveryButtons.hidden = true;
    currentQuestion = null;
  }

  function renderQuestion(question, position) {
    currentQuestion = question;
    el.questionPanel.hidden = false;
    el.meta.textContent = `Question ${position + 1} · ${question.kind}`;
    el.prompt.textContent = question.prompt;
    el.choices.replaceChildren();
    question.choices.forEach((choice) => {
      const label = document.createElement("label");
      label.className = "choice";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "choice";
      input.value = choice.id;
      input.required = true;
      const span = document.createElement("span");
      span.textContent = `${choice.id}. ${choice.text}`;
      label.append(input, span);
      el.choices.append(label);
    });
  }

  function renderState(progress, latestOffer) {
    hideScreens();
    offer = latestOffer;
    el.session.textContent = `Local session: ${sessionId.slice(0, 12)}…`;

    if (progress.complete) {
      el.complete.hidden = false;
      updateControls();
      return;
    }

    const status = offer && offer.status;
    if (progress.assistance_pending && status !== "offered" && status !== "accepted") {
      setStatus("Assistance state is inconsistent. Refresh progress.", true);
      updateControls();
      return;
    }

    if (status === "offered" || status === "accepted" ||
        (status === "delivered" && sessionStorage.getItem(CONTINUED_KEY) !== offerKey(offer))) {
      el.assistance.hidden = false;
      el.offerTitle.textContent = offer.title;
      if (status === "offered") {
        el.offerMessage.textContent = "Would you like an optional concept summary before the next practice question?";
        el.decisionButtons.hidden = false;
      } else if (status === "accepted") {
        el.offerMessage.textContent = "You accepted the summary. Choose View accepted summary to request delivery.";
        el.deliveryButtons.hidden = false;
      } else {
        if (typeof offer.body !== "string" || !offer.body) {
          setStatus("Delivered summary content is unavailable. Refresh progress.", true);
          updateControls();
          return;
        }
        el.offerMessage.textContent = "The server has released the requested summary.";
        el.resourceBody.textContent = offer.body;
        el.resource.hidden = false;
      }
      updateControls();
      return;
    }

    if (progress.question) {
      renderQuestion(progress.question, progress.position);
    } else {
      setStatus("The next question is not available. Refresh progress.", true);
    }
    updateControls();
  }

  async function loadProgress() {
    if (!sessionId) return;
    const state = await requestJson(endpoint("question"));
    const assistance = await requestJson(endpoint("assistance"));
    renderState(state, assistance.offer);
  }

  async function submitPending() {
    if (!pending || busy) return;
    busy = true;
    updateControls();
    setStatus("Confirming your answer…");
    let receipt;
    try {
      receipt = await requestJson(endpoint("responses"), "POST", {
        item_id: pending.item_id,
        choice_id: pending.choice_id,
        request_id: pending.request_id
      });
    } catch (error) {
      // A definitive 4xx means the server rejected this submission.
      // Only unknown outcomes retain the same request_id for safe retry.
      if (error.status >= 400 && error.status < 500) {
        pending = null;
        sessionStorage.removeItem(PENDING_KEY);
        try { await loadProgress(); } catch { /* explicit Refresh remains available */ }
        setStatus(`Answer rejected (${error.message}). Review the current state.`, true);
      } else {
        setStatus(`Submission not confirmed (${error.message}). Retry the same answer.`, true);
      }
      busy = false;
      updateControls();
      return;
    }

    pending = null;
    sessionStorage.removeItem(PENDING_KEY);
    busy = false;
    updateControls();
    try {
      await loadProgress();
      setStatus(receipt.replayed ? "Previous answer confirmed; no duplicate recorded." :
        "Answer saved. Review the next step.");
    } catch (error) {
      setStatus(`Answer saved, but progress could not be loaded (${error.message}). Refresh.`, true);
    }
  }

  async function mutateAssistance(suffix, payload, message) {
    if (!sessionId || !offer || busy || pending) return;
    busy = true;
    updateControls();
    try {
      await requestJson(endpoint(`assistance/${suffix}`), "POST", payload);
      await loadProgress();
      setStatus(message);
    } catch (error) {
      setStatus(`Action not confirmed (${error.message}). Refresh progress before retrying.`, true);
    } finally {
      busy = false;
      updateControls();
    }
  }

  el.start.addEventListener("click", async () => {
    if (busy || pending) return;
    busy = true;
    updateControls();
    try {
      let enrollmentId = localStorage.getItem(
        ENROLLMENT_KEY
      );

      if (!enrollmentId) {
        enrollmentId = crypto.randomUUID();
        localStorage.setItem(
          ENROLLMENT_KEY,
          enrollmentId
        );
      }

      const data = await requestJson(
        `${API}/enroll`,
        "POST",
        {enrollment_request_id: enrollmentId}
      );
      sessionId = data.session_id;
      localStorage.setItem(SESSION_KEY, sessionId);
      sessionStorage.removeItem(CONTINUED_KEY);
      await loadProgress();
      setStatus("Development session started or restored.");
    } catch (error) {
      setStatus(`Could not start session (${error.message}).`, true);
    } finally {
      busy = false;
      updateControls();
    }
  });

  el.refresh.addEventListener("click", async () => {
    if (busy || !sessionId) return;
    busy = true;
    updateControls();
    try {
      await loadProgress();
      setStatus("Session progress refreshed.");
    } catch (error) {
      setStatus(`Refresh failed (${error.message}).`, true);
    } finally {
      busy = false;
      updateControls();
    }
  });

  el.retry.addEventListener("click", submitPending);

  el.accept.addEventListener("click", () => {
    if (offer?.status !== "offered") return;
    mutateAssistance("decision", {source_position: offer.source_position, accept: true},
      "Assistance accepted. The summary is not yet delivered.");
  });
  el.decline.addEventListener("click", () => {
    if (offer?.status !== "offered") return;
    mutateAssistance("decision", {source_position: offer.source_position, accept: false},
      "Assistance declined. You may continue without the summary.");
  });
  el.view.addEventListener("click", () => {
    if (offer?.status !== "accepted") return;
    mutateAssistance("delivery", {source_position: offer.source_position},
      "Summary released and displayed. Continue when ready.");
  });
  el.continue.addEventListener("click", async () => {
    if (offer?.status !== "delivered" || busy || pending) return;
    sessionStorage.setItem(CONTINUED_KEY, offerKey(offer));
    busy = true;
    updateControls();
    try {
      await loadProgress();
      setStatus("Continue with the next practice question.");
    } catch (error) {
      setStatus(`Could not load next question (${error.message}). Refresh.`, true);
    } finally {
      busy = false;
      updateControls();
    }
  });

  el.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || pending || !currentQuestion) return;
    const choice = el.form.querySelector('input[name="choice"]:checked');
    if (!choice) { setStatus("Select an answer.", true); return; }
    pending = {
      sessionId,
      item_id: currentQuestion.id,
      choice_id: choice.value,
      request_id: crypto.randomUUID()
    };
    sessionStorage.setItem(PENDING_KEY, JSON.stringify(pending));
    updateControls();
    await submitPending();
  });

  async function initialize() {
    updateControls();
    if (!sessionId) { setStatus("Start a local session to begin."); return; }
    if (pending) { await submitPending(); return; }
    try {
      await loadProgress();
      setStatus("Existing local session restored.");
    } catch (error) {
      setStatus(`Could not restore session (${error.message}). Start a new one or refresh.`, true);
    }
  }
  initialize();
})();

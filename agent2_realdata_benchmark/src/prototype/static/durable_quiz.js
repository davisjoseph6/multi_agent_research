"use strict";

(() => {
  const API = "/api/v1/durable";
  const SESSION_KEY = "ijcai2027_demo_session";
  const PENDING_KEY = "ijcai2027_demo_pending";

  const elements = {
    start: document.getElementById("start-session"),
    refresh: document.getElementById("refresh-session"),
    retry: document.getElementById("retry-submission"),
    session: document.getElementById("session-label"),
    status: document.getElementById("status"),
    panel: document.getElementById("question-panel"),
    complete: document.getElementById("completion-panel"),
    form: document.getElementById("answer-form"),
    fieldset: document.getElementById("answer-fieldset"),
    meta: document.getElementById("question-meta"),
    prompt: document.getElementById("question-prompt"),
    choices: document.getElementById("choice-list"),
    submit: document.getElementById("submit-answer")
  };

  let sessionId = sessionStorage.getItem(SESSION_KEY);
  let pending = null;
  let currentQuestion = null;
  let busy = false;

  try {
    pending = JSON.parse(
      sessionStorage.getItem(PENDING_KEY) || "null"
    );
  } catch {
    sessionStorage.removeItem(PENDING_KEY);
  }

  if (!pending || pending.sessionId !== sessionId) {
    pending = null;
    sessionStorage.removeItem(PENDING_KEY);
  }

  function status(message, isError = false) {
    elements.status.textContent = message;
    elements.status.className = isError ? "error" : "";
  }

  function updateControls() {
    elements.start.disabled = busy || Boolean(pending);
    elements.refresh.disabled =
      busy || Boolean(pending) || !sessionId;
    elements.retry.hidden = !pending;
    elements.retry.disabled = busy;
    elements.submit.disabled =
      busy || Boolean(pending) || !currentQuestion;
    elements.fieldset.disabled = busy || Boolean(pending);
  }

  async function requestJson(path, method = "GET", payload) {
    const options = {
      method,
      cache: "no-store",
      headers: {}
    };

    if (payload !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }

    const response = await fetch(path, options);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    return data;
  }

  function renderProgress(data) {
    currentQuestion = data.question;

    elements.session.textContent =
      `Local session: ${sessionId.slice(0, 12)}…`;

    if (data.complete) {
      elements.panel.hidden = true;
      elements.complete.hidden = false;
      updateControls();
      return;
    }

    elements.panel.hidden = false;
    elements.complete.hidden = true;

    elements.meta.textContent =
      `Question ${data.position + 1} · ${data.question.kind}`;

    elements.prompt.textContent = data.question.prompt;
    elements.choices.replaceChildren();

    data.question.choices.forEach((choice, index) => {
      const wrapper = document.createElement("label");
      wrapper.className = "choice";

      const input = document.createElement("input");
      input.type = "radio";
      input.name = "choice";
      input.value = choice.id;
      input.required = true;

      const description = document.createElement("span");
      description.textContent =
        `${choice.id}. ${choice.text}`;

      wrapper.append(input, description);
      elements.choices.append(wrapper);
    });

    updateControls();
  }

  async function loadProgress() {
    if (!sessionId) return;

    const data = await requestJson(
      `${API}/sessions/${encodeURIComponent(sessionId)}/question`
    );

    renderProgress(data);
  }

  async function submitPending() {
    if (!pending || busy) return;

    busy = true;
    updateControls();
    status("Confirming your answer…");

    let receipt;

    try {
      receipt = await requestJson(
        `${API}/sessions/${encodeURIComponent(sessionId)}/responses`,
        "POST",
        {
          item_id: pending.item_id,
          choice_id: pending.choice_id,
          request_id: pending.request_id
        }
      );
    } catch (error) {
      busy = false;
      updateControls();
      status(
        `Submission not confirmed (${error.message}). ` +
        "Retry using the same request identifier.",
        true
      );
      return;
    }

    pending = null;
    sessionStorage.removeItem(PENDING_KEY);

    busy = false;
    updateControls();

    try {
      await loadProgress();

      status(
        receipt.replayed
          ? "Previous submission confirmed; no duplicate recorded."
          : "Answer recorded. No assistance was delivered."
      );
    } catch (error) {
      status(
        "Answer recorded, but the next question could not " +
        "be loaded. Use Refresh progress.",
        true
      );
    }
  }

  async function startSession() {
    if (busy || pending) return;

    busy = true;
    updateControls();
    status("Creating local session…");

    try {
      const data = await requestJson(
        `${API}/sessions`,
        "POST"
      );

      sessionId = data.session_id;
      sessionStorage.setItem(SESSION_KEY, sessionId);

      await loadProgress();
      status("Local session created.");
    } catch (error) {
      status(`Could not start session: ${error.message}`, true);
    } finally {
      busy = false;
      updateControls();
    }
  }

  elements.start.addEventListener("click", startSession);

  elements.refresh.addEventListener("click", async () => {
    if (busy || pending || !sessionId) return;

    busy = true;
    updateControls();

    try {
      await loadProgress();
      status("Session progress refreshed.");
    } catch (error) {
      status(`Refresh failed: ${error.message}`, true);
    } finally {
      busy = false;
      updateControls();
    }
  });

  elements.retry.addEventListener("click", submitPending);

  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (busy || pending || !currentQuestion) return;

    const choice = elements.form.querySelector(
      'input[name="choice"]:checked'
    );

    if (!choice) {
      status("Select one answer.", true);
      return;
    }

    pending = {
      sessionId,
      item_id: currentQuestion.id,
      choice_id: choice.value,
      request_id: crypto.randomUUID()
    };

    sessionStorage.setItem(
      PENDING_KEY,
      JSON.stringify(pending)
    );

    updateControls();
    await submitPending();
  });

  async function initialize() {
    updateControls();

    if (!sessionId) {
      status("Start a local session to begin.");
      return;
    }

    if (pending) {
      await submitPending();
      return;
    }

    try {
      await loadProgress();
      status("Existing local session restored.");
    } catch (error) {
      status(
        `Could not restore session: ${error.message}. ` +
        "You can start a new local session.",
        true
      );
    }
  }

  initialize();
})();

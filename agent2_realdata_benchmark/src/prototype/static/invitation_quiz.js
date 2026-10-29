
"use strict";

// Save as:
// src/prototype/static/invitation_quiz.js

// Development-only browser. Invitation lives in JS memory.
(() => {
  const API = "/api/v1/trial-invite";
  const $ = (id) => document.getElementById(id);

  const els = {
    login: $("invitation-form"),
    secret: $("invitation-token"),
    quiz: $("quiz-shell"),
    status: $("status"),
    session: $("session-label"),
    refresh: $("refresh-progress"),
    close: $("close-session"),
    question: $("question-panel"),
    prompt: $("question-prompt"),
    meta: $("question-meta"),
    choices: $("choice-list"),
    answer: $("answer-form"),
    assistance: $("assistance-panel"),
    title: $("offer-title"),
    message: $("offer-message"),
    accept: $("accept-assistance"),
    decline: $("decline-assistance"),
    view: $("view-assistance"),
    resource: $("resource-panel"),
    body: $("resource-body"),
    next: $("continue-after-summary"),
    completed: $("completion-panel"),
    retry: $("retry-answer")
  };

  let invitation = null;
  let sessionId = null;
  let currentQuestion = null;
  let currentOffer = null;
  let currentProgress = null;
  let pendingAnswer = null;
  let busy = false;

  const continued = new Set();

  function status(message, error = false) {
    els.status.textContent = message;
    els.status.className = error ? "error" : "";
  }

  function controls() {
    document.querySelectorAll("button").forEach((button) => {
      button.disabled = busy;
    });

    els.retry.hidden = pendingAnswer === null;

    els.answer.querySelector("button").disabled =
      busy || Boolean(pendingAnswer);
  }

  async function api(path, method = "GET", payload = undefined) {
    if (!invitation) {
      throw new Error("Enter an invitation first");
    }

    const options = {
      method,
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      headers: {
        Authorization: `Bearer ${invitation}`
      }
    };

    if (payload !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }

    const response = await fetch(path, options);
    const data = await response.json();

    if (!response.ok) {
      const failure = new Error(
        `Request failed (HTTP ${response.status})`
      );
      failure.code = response.status;
      throw failure;
    }

    return data;
  }

  function endpoint(suffix) {
    return `${API}/sessions/${
      encodeURIComponent(sessionId)
    }/${suffix}`;
  }

  async function run(action) {
    if (busy) return;

    busy = true;
    controls();

    try {
      await action();
    } catch (failure) {
      status(failure.message || "Request failed", true);
    } finally {
      busy = false;
      controls();
    }
  }

  function hidePanels() {
    els.question.hidden = true;
    els.assistance.hidden = true;
    els.resource.hidden = true;
    els.completed.hidden = true;

    els.accept.hidden = true;
    els.decline.hidden = true;
    els.view.hidden = true;
    els.next.hidden = true;

    els.body.textContent = "";
    currentQuestion = null;
  }

  function showQuestion() {
    const question = currentProgress?.question;

    if (!question) {
      status(
        "The next question is unavailable. Refresh progress.",
        true
      );
      return;
    }

    hidePanels();

    currentQuestion = question;
    els.question.hidden = false;

    els.meta.textContent =
      `Question ${currentProgress.position + 1} — ${question.kind}`;

    els.prompt.textContent = question.prompt;
    els.choices.replaceChildren();

    for (const choice of question.choices) {
      const label = document.createElement("label");
      label.className = "choice";

      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "choice";
      radio.value = choice.id;
      radio.required = true;

      const description = document.createElement("span");
      description.textContent =
        `${choice.id}. ${choice.text}`;

      label.append(radio, description);
      els.choices.append(label);
    }
  }

  function render() {
    hidePanels();

    els.quiz.hidden = false;
    els.session.textContent =
      `Development session: ${sessionId.slice(0, 12)}…`;

    if (currentProgress.complete) {
      els.completed.hidden = false;
      return;
    }

    const offer = currentOffer;
    const state = offer?.status;

    const key = offer
      ? `${sessionId}:${offer.source_position}`
      : "";

    if (
      state === "offered" ||
      state === "accepted" ||
      (state === "delivered" && !continued.has(key))
    ) {
      els.assistance.hidden = false;
      els.title.textContent = offer.title;

      if (state === "offered") {
        els.message.textContent =
          "Would you like an optional concept summary?";

        els.accept.hidden = false;
        els.decline.hidden = false;
      } else if (state === "accepted") {
        els.message.textContent =
          "The resource has been accepted but not delivered.";

        els.view.hidden = false;
      } else {
        els.message.textContent =
          "The resource has been released by the server.";

        els.body.textContent = offer.body || "";
        els.resource.hidden = false;
        els.next.hidden = false;
      }

      return;
    }

    if (currentProgress.assistance_pending) {
      status(
        "Assistance must be resolved before continuing.",
        true
      );
      return;
    }

    showQuestion();
  }

  async function refresh() {
    currentProgress = await api(endpoint("question"));

    const detail = await api(endpoint("assistance"));
    currentOffer = detail.offer;

    render();
  }

  els.login.addEventListener("submit", (event) => {
    event.preventDefault();

    run(async () => {
      const supplied = els.secret.value.trim();
      els.secret.value = "";

      if (!/^inv1_[0-9a-f]{64}$/.test(supplied)) {
        status(
          "Enter a correctly formatted development invitation.",
          true
        );
        return;
      }

      invitation = supplied;

      try {
        const enrolled = await api(
          `${API}/enroll`,
          "POST"
        );

        if (sessionId !== enrolled.session_id) {
          continued.clear();
        }

        sessionId = enrolled.session_id;
        els.login.hidden = true;

        await refresh();

        status(
          enrolled.replayed
            ? "Session recovered."
            : "Development session started."
        );
      } catch (failure) {
        invitation = null;
        sessionId = null;

        els.quiz.hidden = true;
        els.login.hidden = false;

        throw failure;
      }
    });
  });

  els.refresh.addEventListener("click", () => {
    run(async () => {
      await refresh();
      status("Progress refreshed.");
    });
  });

  els.close.addEventListener("click", () => {
    if (busy) return;

    invitation = null;
    sessionId = null;
    currentOffer = null;
    currentProgress = null;
    pendingAnswer = null;

    continued.clear();
    hidePanels();

    els.quiz.hidden = true;
    els.login.hidden = false;
    els.secret.value = "";

    status(
      "Invitation cleared from this page. Re-enter it to resume."
    );

    controls();
  });

  els.answer.addEventListener("submit", (event) => {
    event.preventDefault();

    if (!currentQuestion || pendingAnswer) return;

    const selection = els.answer.querySelector(
      'input[name="choice"]:checked'
    );

    if (!selection) {
      status("Select an answer first.", true);
      return;
    }

    pendingAnswer = {
      item_id: currentQuestion.id,
      choice_id: selection.value,
      request_id: crypto.randomUUID()
    };

    sendPending();
  });

  async function sendPending() {
    await run(async () => {
      try {
        const result = await api(
          endpoint("responses"),
          "POST",
          pendingAnswer
        );

        pendingAnswer = null;
        await refresh();

        status(
          result.replayed
            ? "Earlier answer confirmed."
            : "Answer saved."
        );
      } catch (failure) {
        if (
          failure.code >= 400 &&
          failure.code < 500
        ) {
          pendingAnswer = null;

          try {
            await refresh();
          } catch {
            // Explicit refresh remains available.
          }
        }

        throw failure;
      }
    });
  }

  els.retry.addEventListener("click", () => {
    if (pendingAnswer) {
      sendPending();
    }
  });

  async function act(suffix, payload, message) {
    await run(async () => {
      await api(
        endpoint(`assistance/${suffix}`),
        "POST",
        payload
      );

      await refresh();
      status(message);
    });
  }

  els.accept.addEventListener("click", () => {
    if (currentOffer?.status === "offered") {
      act(
        "decision",
        {
          source_position: currentOffer.source_position,
          accept: true
        },
        "Summary accepted; delivery remains separate."
      );
    }
  });

  els.decline.addEventListener("click", () => {
    if (currentOffer?.status === "offered") {
      act(
        "decision",
        {
          source_position: currentOffer.source_position,
          accept: false
        },
        "Summary declined."
      );
    }
  });

  els.view.addEventListener("click", () => {
    if (currentOffer?.status === "accepted") {
      act(
        "delivery",
        {
          source_position: currentOffer.source_position
        },
        "Summary delivered. Reading or comprehension is not measured."
      );
    }
  });

  els.next.addEventListener("click", () => {
    if (
      currentOffer?.status !== "delivered" ||
      busy
    ) {
      return;
    }

    continued.add(
      `${sessionId}:${currentOffer.source_position}`
    );

    showQuestion();
    controls();

    status("Continue with the next practice question.");
  });

  controls();

  status(
    "Enter a synthetic development invitation to start or resume."
  );
})();


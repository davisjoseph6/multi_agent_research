"use strict";

// Fictional, unapproved, loopback-only rehearsal. No real students or study data.
// All externally sourced question/resource text is inserted via textContent,
// never as HTML. No third-party analytics or service calls.

const nonce = document.querySelector('meta[name="preview-nonce"]').content;
const fixtureControl = document.getElementById("fixture-select");
const reloadButton = document.getElementById("reload-button");
const statusBox = document.getElementById("participant-status");
const stageBox = document.getElementById("activity-stage");
const titleBox = document.getElementById("activity-title");
const descriptionBox = document.getElementById("activity-description");
const form = document.getElementById("answer-form");
const fields = document.getElementById("answer-fields");
const submitButton = document.getElementById("submit-button");

let action = null;
let busy = false;
// For an ambiguous network failure, retry the EXACT original synthetic
// response and request ID. Never invent a new ID for the same pending action.
let submissionAttempt = null;
const stageNames = {
  pretest: "Baseline assessment",
  practice: "Practice session",
  posttest: "Independent posttest",
  mvas_pre: "Before learning · proposed mental fatigue measure",
  mvas_post: "After learning · proposed mental fatigue measure",
};

function element(tag, value, className) {
  const node = document.createElement(tag);
  if (value !== null && value !== undefined) {
    node.textContent = String(value);
  }
  if (className) node.className = className;
  return node;
}

function currentFixture() {
  return fixtureControl.value;
}

function note(message, error) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", !!error);
}

async function requestPreview(route, body) {
  const response = await fetch("/unified/api/" + route, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Preview-Nonce": nonce,
    },
    credentials: "same-origin",
    cache: "no-store",
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Offline preview request failed");
  }
  return payload;
}

function stageTitle(value) {
  return stageNames[value] || value.replaceAll("_", " ");
}

function resetActivity(title, stage) {
  titleBox.textContent = title;
  stageBox.textContent = stage || "FICTIONAL SOFTWARE REHEARSAL";
  descriptionBox.replaceChildren();
  fields.replaceChildren();
  form.hidden = true;
  action = null;
}

function renderQuestion(payload) {
  const question = payload.question;
  if (!question || !Array.isArray(question.options)) {
    throw new Error("Expected a draft quiz question");
  }
  descriptionBox.append(
    element("p", "Concept: " + question.concept, "small-print"),
    element("p", question.prompt, "question-prompt"),
  );
  const legend = element("legend", "Choose one response");
  const group = document.createElement("fieldset");
  group.append(legend);
  for (const [key, text] of question.options) {
    const label = document.createElement("label");
    label.className = "answer-choice";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "choice";
    input.value = key;
    input.required = true;
    label.append(input, element("span", key + ". " + text));
    group.append(label);
  }
  fields.append(group);
  submitButton.textContent = "Submit draft quiz response";
  form.hidden = false;
}

function renderMvas(payload) {
  const point = payload.stage === "mvas_pre" ? "before" : "after";
  descriptionBox.append(
    element("p",
      "Proposed single-item state rating " + point +
      " this fictional learning session. This wording and digital response method are not yet approved.",
      "question-prompt"),
  );
  const label = document.createElement("label");
  label.setAttribute("for", "mvas-rating");
  label.textContent = "How mentally fatigued do you feel right now?";
  const input = document.createElement("input");
  input.type = "number";
  input.id = "mvas-rating";
  input.name = "mvas-rating";
  input.min = "0";
  input.max = "100";
  input.step = "1";
  input.required = true;
  input.placeholder = "Enter a rating from 0 to 100";
  input.setAttribute("aria-describedby", "mvas-anchor");
  const anchors = element("p",
    "0 = Not at all mentally fatigued; 100 = Completely exhausted. No response is preselected.",
    "small-print");
  anchors.id = "mvas-anchor";
  fields.append(label, input, anchors);
  submitButton.textContent = "Record fictional fatigue rating";
  form.hidden = false;
}

function renderResource(payload) {
  const resource = payload.resource;
  if (!resource || !resource.text) {
    throw new Error("Expected a draft recovery resource");
  }
  descriptionBox.append(
    element("p", "Optional Fixture A recovery activity · " + payload.action, "small-print"),
    element("p", resource.text, "resource-text"),
  );
  if (resource.source) {
    descriptionBox.append(element("p", "Draft source: " + resource.source, "small-print"));
  }
  if (payload.action === "DROP_2") {
    renderQuestion(payload);
    return;
  }
  const label = document.createElement("label");
  label.setAttribute("for", "resource-status");
  label.textContent = "What happened to this fictional resource?";
  const select = document.createElement("select");
  select.id = "resource-status";
  select.name = "resource-status";
  select.required = true;
  const none = document.createElement("option");
  none.value = "";
  none.disabled = true;
  none.selected = true;
  none.textContent = "Select an action";
  const done = new Option("Completed", "completed");
  const skipped = new Option("Skipped", "skipped");
  select.append(none, done, skipped);
  fields.append(label, select);
  submitButton.textContent = "Record fictional resource status";
  form.hidden = false;
}

async function present(payload) {
  // A refresh reconciles with the server's durable state. Any newly fetched
  // action is authoritative; a previous uncertain local attempt is discarded.
  submissionAttempt = null;
  if (payload.action === "AWAITING_SUPERVISOR") {
    resetActivity("Waiting for the next fictional supervised visit", "SESSION BREAK");
    descriptionBox.append(
      element("p",
        "Visit " + payload.visit + " has not been opened. No browser action can open a visit.",
        "question-prompt"),
      element("p",
        "Run the separate offline operator command for Fixture " +
        currentFixture() + ", then refresh this browser."),
    );
    return;
  }
  if (payload.action === "COMPLETE") {
    resetActivity("All three fictional visits completed", "SOFTWARE REHEARSAL COMPLETE");
    descriptionBox.append(
      element("p", "This is not a scientific learning result, participant enrollment, or institutional authorization."),
    );
    return;
  }
  action = payload;
  resetActivity(
    stageTitle(payload.stage) + " · Visit " + payload.session,
    "ACTION " + payload.action + " · FICTIONAL ONLY",
  );
  action = payload;
  if (payload.action === "MVAS") {
    renderMvas(payload);
  } else if (payload.action === "QUESTION") {
    renderQuestion(payload);
  } else if (payload.resource) {
    renderResource(payload);
  } else {
    throw new Error("Unsupported fictional action: " + payload.action);
  }
  // The selected action has been placed into the DOM before reporting render.
  await requestAnimationFramePromise();
  await requestPreview("rendered", {
    fixture: currentFixture(), action_id: payload.action_id,
  });
  titleBox.focus();
}

function requestAnimationFramePromise() {
  return new Promise(resolve => window.requestAnimationFrame(resolve));
}

async function refresh() {
  if (busy) return;
  busy = true;
  reloadButton.disabled = true;
  fixtureControl.disabled = true;
  form.hidden = true;
  try {
    const fixture = currentFixture();
    const state = await requestPreview("status", {fixture});
    note(
      "Fixture " + state.fixture + " · Visit " + state.session +
      " · " + stageTitle(state.stage) +
      " · " + state.completed_actions + " synthetic actions completed",
      false,
    );
    const next = await requestPreview("next", {fixture});
    await present(next);
  } catch (error) {
    note(error.message, true);
    resetActivity("Unable to load the fictional activity", "ERROR");
  } finally {
    busy = false;
    reloadButton.disabled = false;
    fixtureControl.disabled = false;
  }
}

function formResponse() {
  if (action.action === "MVAS") {
    const input = document.getElementById("mvas-rating");
    if (!input.value.trim()) throw new Error("Select a mental-fatigue rating");
    const rating = Number(input.value);
    if (!Number.isInteger(rating) || rating < 0 || rating > 100) {
      throw new Error("Choose a whole number from 0 through 100");
    }
    return {rating};
  }
  if (action.action === "QUESTION" || action.action === "DROP_2") {
    const option = fields.querySelector('input[name="choice"]:checked');
    if (!option) throw new Error("Choose one quiz response");
    return {choice_id: option.value};
  }
  const selection = document.getElementById("resource-status");
  if (!selection || !["completed", "skipped"].includes(selection.value)) {
    throw new Error("Select completed or skipped");
  }
  return {status: selection.value};
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (busy || !action) return;
  let submission;
  try {
    if (submissionAttempt &&
        submissionAttempt.action_id === action.action_id &&
        submissionAttempt.fixture === currentFixture()) {
      submission = submissionAttempt;
    } else {
      const response = formResponse();
      submissionAttempt = {
        fixture: currentFixture(),
        action_id: action.action_id,
        request_id: window.crypto.randomUUID(),
        response,
      };
      submission = submissionAttempt;
    }
  } catch (error) {
    note(error.message, true);
    return;
  }
  busy = true;
  reloadButton.disabled = true;
  fixtureControl.disabled = true;
  submitButton.disabled = true;
  try {
    const result = await requestPreview("act", submission);
    submissionAttempt = null;
    let message = result.replayed
      ? "Previously saved fictional response confirmed."
      : "Fictional response saved.";
    if ("correct" in result) {
      message += result.correct ? " Practice response correct." : " Practice response incorrect.";
    }
    note(message, false);
  } catch (error) {
    // The HTTP reply can be lost AFTER SQLite commits the response. Prevent
    // accidental editing and resubmit the exact original action/request ID.
    // Refresh is available to reconcile and start a fresh action if desired.
    for (const field of fields.querySelectorAll("input,select,textarea")) {
      field.disabled = true;
    }
    submitButton.textContent = "Retry the same fictional response";
    note(
      "Save confirmation unavailable. Retry will send the identical response " +
      "with the same request ID. Or select Refresh to check the server state. " +
      error.message,
      true,
    );
    busy = false;
    submitButton.disabled = false;
    reloadButton.disabled = false;
    fixtureControl.disabled = false;
    return;
  }
  busy = false;
  submitButton.disabled = false;
  reloadButton.disabled = false;
  fixtureControl.disabled = false;
  await refresh();
});

fixtureControl.addEventListener("change", refresh);
reloadButton.addEventListener("click", refresh);
refresh();

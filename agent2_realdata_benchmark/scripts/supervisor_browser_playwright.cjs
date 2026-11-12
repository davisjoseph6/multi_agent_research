"use strict";
/* Real Chromium smoke test for the localhost-only synthetic Group A flow.
 * This does not enroll humans, deliver mail, use real identities, or approve
 * the study. It checks that instructional text is actually visible to users.
 */
const assert = require("node:assert/strict");
const {spawn} = require("node:child_process");
const {chromium} = require("playwright");

const port = 8787;
const url = `http://127.0.0.1:${port}`;
const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));

async function waitForServer(proc) {
  for(let attempt=0;attempt<90;attempt++) {
    if(proc.exitCode!==null)throw new Error("Python preview exited unexpectedly");
    try {
      const response=await fetch(url);
      if(response.ok)return;
    } catch (_) { /* server is still starting */ }
    await sleep(250);
  }
  throw new Error("Local preview never became ready");
}

async function check() {
  const proc=spawn(
    process.env.PYTHON||"python",
    ["-m","scripts.supervisor_fictional_browser","--port",String(port)],
    {cwd:process.cwd(),env:process.env,stdio:["ignore","pipe","pipe"]}
  );
  let serverErrors="";
  proc.stderr.on("data",chunk=>{serverErrors+=String(chunk).slice(0,3000)});
  let browser=null;
  try {
    await waitForServer(proc);
    browser=await chromium.launch({headless:true});
    const page=await browser.newPage({viewport:{width:1200,height:900}});
    const pageErrors=[];
    page.on("pageerror",error=>pageErrors.push(String(error)));

    await page.goto(url,{waitUntil:"networkidle"});
    await page.locator("#information").waitFor({state:"visible"});
    await page.locator("#quick-recovery").click();

    await page.locator("#recovery-title").waitFor({state:"visible"});
    assert.equal(await page.locator("#recovery-title").innerText(),
                 "Concept summary: Loss Aversion");
    const summary=await page.locator("#recovery-paragraphs p").allInnerTexts();
    assert.equal(summary.length,2);
    assert.match(summary.join(" "),/loss aversion/i);
    assert.equal(await page.locator("#options").isHidden(),true);

    await page.locator("#continue").click();
    await page.waitForFunction(()=>
      document.querySelector("#question").textContent.startsWith("DROP_2"));
    assert.equal(await page.locator('#options input[type="radio"]').count(),2);
    await page.locator('#options input[type="radio"]').first().check();
    await page.locator("#answer").click();

    await page.waitForFunction(()=>
      document.querySelector("#recovery-title").textContent
      .startsWith("Worked example:"));
    const worked=await page.locator("#recovery-paragraphs p").allInnerTexts();
    assert.equal(worked.length,2);
    assert.match(worked.join(" "),/Step 1/i);
    await page.locator("#continue").click();

    await page.locator("#hint-next").waitFor({state:"visible"});
    assert.match(await page.locator("#hint-guidance").innerText(),
                 /Guiding question 1 of 2/);
    assert.equal(await page.locator("#options").isHidden(),true);
    assert.equal(await page.locator("#answer").isHidden(),true);

    // Empty reflection cannot skip straight to the four-choice answer.
    await page.locator("#hint-next").click();
    assert.match(await page.locator("#feedback").innerText(),
                 /Please enter a brief reflection/);
    assert.equal(await page.locator("#options").isHidden(),true);

    await page.locator("#hint-reflection")
      .fill("I should identify the reference point and the loss-versus-gain framing.");
    await page.locator("#hint-next").click();
    assert.match(await page.locator("#hint-guidance").innerText(),
                 /Guiding question 2 of 2/);
    assert.equal(await page.locator("#options").isHidden(),true);

    await page.locator("#hint-reflection")
      .fill("I should compare the options against that definition before selecting.");
    await page.locator("#hint-next").click();
    await page.locator("#answer").waitFor({state:"visible"});
    assert.equal(await page.locator('#options input[type="radio"]').count(),4);
    assert.match(await page.locator("#question").innerText(),
                 /Socratic re-attempt/);
    await page.locator('#options input[type="radio"]').first().check();
    await page.locator("#answer").click();

    // A scored Socratic re-attempt returns to regular practice without
    // consuming an additional regular block question.
    await page.waitForFunction(()=>
      document.querySelector("#question").textContent !== "" &&
      !document.querySelector("#question").textContent.includes("Socratic re-attempt"));
    assert.match(await page.locator("#progress").innerText(),/Session 1\/3 — QUIZ/);
    assert.deepEqual(pageErrors,[]);
    console.log("PASS Chromium Group A full recovery:");
    console.log("summary visible -> DROP_2 2 options -> worked example visible ->");
    console.log("Socratic prompt 1 -> prompt 2 -> original 4-option re-attempt.");
    console.log("All data were synthetic and kept on localhost.");
  } catch(error) {
    throw new Error(`${error.message}\nPython errors: ${serverErrors.slice(-2000)}`);
  } finally {
    if(browser)await browser.close();
    proc.kill("SIGTERM");
  }
}

check().catch(error=>{console.error(error);process.exitCode=1});

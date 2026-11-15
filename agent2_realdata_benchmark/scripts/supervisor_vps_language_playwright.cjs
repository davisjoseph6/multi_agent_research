"use strict";
/* Live Chromium regression for the operational STAGING portal's two-step
 * Socratic guidance and interactive language switching.
 * Fixture is localhost only and issues a reserved fictional identity.
 * No human registration, SMTP, real domain auth or consent approval.
 */
const assert=require("node:assert/strict");
const {spawn,execFileSync}=require("node:child_process");
const {chromium}=require("playwright");
const port=8794,base=`http://127.0.0.1:${port}`;
const python=process.env.PYTHON||"python";
const keys=JSON.parse(execFileSync(python,["-c",
  "import json;from src.prototype.supervisor_content import SupervisorBank;"+
  "bank=SupervisorBank('data/supervisor_20261111');"+
  "print(json.dumps({k:v.correct_answer for k,v in bank.by_id.items()}))",
],{cwd:process.cwd(),encoding:"utf8"}));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const responseFor=route=>r=>r.request().method()==="POST" &&
  r.url().endsWith("/study/api/"+route);

async function test(){
  const proc=spawn(python,["-m","scripts.supervisor_vps_dev","--port",String(port)],
    {cwd:process.cwd(),stdio:["ignore","pipe","pipe"]});
  let stdout="",stderr="",invites=null,browser;
  proc.stdout.on("data",b=>{
    stdout+=String(b);
    const m=stdout.match(/TEST_INVITES=(\{[^\n]+\})/);
    if(m)invites=JSON.parse(m[1]);
  });
  proc.stderr.on("data",b=>stderr+=String(b).slice(-1400));
  try{
    for(let t=0;t<120;t++){
      if(proc.exitCode!==null)throw Error("test server stopped");
      if(invites){try{if((await fetch(base+"/study/health")).ok)break}catch(_){}}
      if(t===119)throw Error("test server unavailable");
      await sleep(250);
    }
    browser=await chromium.launch({headless:true});
    const context=await browser.newContext({viewport:{width:390,height:844}});
    const page=await context.newPage();
    const pageErrors=[];
    page.on("pageerror",e=>pageErrors.push(String(e)));
    await page.goto(base+"/study/#invite="+invites.F1,{waitUntil:"networkidle"});
    await page.locator("#information").waitFor({state:"visible"});
    for(let i=0;i<5;i++)await page.locator("#consent-required input.required").nth(i).check();
    let next=page.waitForResponse(responseFor("screening"));
    await page.locator("#start-consent").click();
    const screening=(await next).json();
    assert.equal((await screening).questions.length,8);
    for(let i=0;i<8;i++){
      const q=(await screening).questions[i];
      const choice=i<4?keys[q.question_id]:"ABCD".split("").find(k=>k!==keys[q.question_id]);
      await page.locator('#screen-options input[value="'+choice+'"]').check();
      await page.locator("#screen-next").click();
    }
    await page.locator("#registration").waitFor({state:"visible"});
    await page.locator("#age").selectOption("23");
    await page.locator("#program").selectOption("Test student program");
    next=page.waitForResponse(responseFor("item"));
    await page.locator("#register").click();
    let item=await (await next).json();
    for(let i=0;i<16;i++){
      assert.equal(item.phase,"PRETEST");
      await page.locator('#choices input[value="'+keys[item.question_id]+'"]').check();
      next=page.waitForResponse(responseFor("item"));
      await page.locator("#answer").click();
      item=await (await next).json();
    }
    assert.equal(item.action,"QUESTION");
    // Real deterministic wrong-answer flow; do not plant or override a
    // recovery stage in the browser or skip the supervisor's trigger.
    let incorrect=0;
    while(item.action==="QUESTION" && incorrect<12){
      const chosen="ABCD".split("").find(k=>k!==keys[item.question_id]);
      await page.locator('#choices input[value="'+chosen+'"]').check();
      const submitted=page.waitForResponse(responseFor("answer"));
      await page.locator("#answer").click();
      const result=await (await submitted).json();
      assert.equal(result.previous_correct,false);
      await page.locator("#answer-feedback").waitFor({state:"visible"});
      next=page.waitForResponse(responseFor("item"));
      await page.locator("#feedback-next").click();
      item=await (await next).json();
      incorrect++;
    }
    assert.equal(item.kind,"recovery","group A did not enter recovery");
    assert.equal(item.action,"CONCEPT_SUMMARY");
    assert(incorrect>=2);
    await page.waitForFunction(()=>
      document.querySelector("#continue").hidden===false);

    // Localize first resource without moving to DROP_2.
    let translated=page.waitForResponse(responseFor("item"));
    await page.locator("#language").selectOption("fr");
    let french=await (await translated).json();
    assert.equal(french.action,"CONCEPT_SUMMARY");
    assert.equal(french.language,"fr");
    assert.equal(item.render_id,french.render_id);
    await page.waitForFunction(()=>
      document.querySelector("#teaching-title").textContent!=="" &&
      document.documentElement.lang==="fr");
    translated=page.waitForResponse(responseFor("item"));
    await page.locator("#language").selectOption("en");
    item=await (await translated).json();
    assert.equal(item.action,"CONCEPT_SUMMARY");

    next=page.waitForResponse(responseFor("item"));
    await page.locator("#continue").click();
    item=await (await next).json();
    assert.equal(item.action,"DROP_2");
    assert.equal(await page.locator("#choices input").count(),2);
    const drop=keys[item.question_id];
    await page.locator('#choices input[value="'+drop+'"]').check();
    const dropResult=page.waitForResponse(responseFor("answer"));
    await page.locator("#answer").click();
    assert.equal((await (await dropResult).json()).previous_correct,true);
    next=page.waitForResponse(responseFor("item"));
    await page.locator("#feedback-next").click();
    item=await (await next).json();
    assert.equal(item.action,"WORKED_EXAMPLE");

    next=page.waitForResponse(responseFor("item"));
    await page.locator("#continue").click();
    item=await (await next).json();
    assert.equal(item.action,"SOCRATIC_HINT");
    await page.locator("#hint-next").waitFor({state:"visible"});
    assert.match(await page.locator("#guidance").innerText(),/Guiding question 1 of 2/);

    const first="The reference point changes which outcome feels like a loss.";
    const second="I should compare the options using the loss/gain frame.";
    await page.locator("#reasoning").fill(first);
    await page.locator("#hint-next").click();
    assert.match(await page.locator("#guidance").innerText(),/Guiding question 2 of 2/);
    await page.locator("#reasoning").fill(second);

    // Regression: translating during the SECOND hint used to rewind to 1/2
    // and discard the first stored reflection and second unsubmitted draft.
    translated=page.waitForResponse(responseFor("item"));
    await page.locator("#language").selectOption("fr");
    french=await (await translated).json();
    assert.equal(french.action,"SOCRATIC_HINT");
    assert.equal(french.render_id,item.render_id);
    assert.match(await page.locator("#guidance").innerText(),/Question guidée 2 sur 2/);
    assert.equal(await page.locator("#reasoning").inputValue(),second);
    assert.equal(await page.locator("#answer").isHidden(),true);

    translated=page.waitForResponse(responseFor("item"));
    await page.locator("#language").selectOption("en");
    item=await (await translated).json();
    assert.match(await page.locator("#guidance").innerText(),/Guiding question 2 of 2/);
    assert.equal(await page.locator("#reasoning").inputValue(),second);

    await page.locator("#hint-next").click();
    await page.locator("#answer").waitFor({state:"visible"});
    assert.equal(await page.locator("#choices input").count(),4);
    const chosen=keys[item.question_id];
    await page.locator('#choices input[value="'+chosen+'"]').check();

    // Once both reflections exist, switching must not re-display either hint.
    translated=page.waitForResponse(responseFor("item"));
    await page.locator("#language").selectOption("fr");
    item=await (await translated).json();
    assert.equal(item.action,"SOCRATIC_HINT");
    assert.equal(await page.locator("#answer").isVisible(),true);
    assert.equal(await page.locator("#reflection").isHidden(),true);
    assert.equal(await page.locator('#choices input[value="'+chosen+'"]').isChecked(),true);

    const submitted=page.waitForResponse(responseFor("answer"));
    await page.locator("#answer").click();
    const result=await (await submitted).json();
    assert.equal(result.previous_correct,true);
    await page.locator("#answer-feedback").waitFor({state:"visible"});
    assert.deepEqual(pageErrors,[]);
    console.log("PASS operational staging language regression: screening consent and "+incorrect+
      " incorrect Group A questions -> Summary -> DROP_2 -> Worked Example -> "+
      "Socratic hint 2/2 remains intact, drafts preserved and reattempt committed.");
    await context.close();
  }catch(e){
    throw Error((e.stack||String(e))+"\nTest server errors: "+stderr.slice(-3200));
  }finally{
    if(browser)await browser.close();
    proc.kill("SIGTERM");
  }
}
test().catch(e=>{console.error(e);process.exitCode=1});

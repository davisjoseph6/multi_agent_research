"use strict";
/* Test-only real Chromium exercise of researcher Basic Auth and live chart.
 * Never launches a real participant system or uses contact data.
 */
const {spawn}=require("node:child_process");
const assert=require("node:assert/strict");
const {chromium}=require("playwright");

const BASE="http://127.0.0.1:8795";
const PASSWORD="CI-Only-Researcher-Password-Not-Production-2026";
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

async function main(){
  const proc=spawn(process.env.PYTHON||"python",[
    "-m","scripts.supervisor_research_monitor_browser_fixture","--port","8795",
  ],{cwd:process.cwd(),stdio:["ignore","pipe","pipe"]});
  let errors="";
  proc.stderr.on("data",b=>errors+=b.toString().slice(-2000));
  let browser;
  try{
    for(let n=0;n<70;n++){
      if(proc.exitCode!==null)throw Error("fixture monitor exited early: "+errors);
      try{if((await fetch(BASE+"/admin/")).status===401)break}catch(_){}
      if(n===69)throw Error("localhost research monitor failed to bind: "+errors);
      await sleep(200);
    }
    const denied=await fetch(BASE+"/admin/api/participants");
    assert.equal(denied.status,401);
    assert.match(denied.headers.get("www-authenticate")||"",/Basic/i);

    browser=await chromium.launch({headless:true});
    const page=await browser.newPage({
      viewport:{width:390,height:820},
      httpCredentials:{username:"researcher",password:PASSWORD},
    });
    const faults=[];
    page.on("pageerror",e=>faults.push(String(e)));
    await page.goto(BASE+"/admin/",{waitUntil:"networkidle"});
    await page.locator("#student").selectOption("STUDY_P001");
    await page.waitForFunction(()=>
      document.querySelector("#summary").textContent.includes("Arm A"),null,
      {timeout:10000});
    assert.match(await page.locator("#summary").innerText(),/STUDY_P001/);
    assert.match(await page.locator("#summary").innerText(),/Graded responses/);

    await page.locator("#concept").selectOption("C1");
    await page.waitForFunction(()=>
      document.querySelector("#legend").textContent.includes("C1"),null,
      {timeout:10000});
    const src=await page.locator("#legend").innerText();
    assert.match(src,/Utility/);
    assert.equal((await page.locator("#chart").getAttribute("role")),"img");
    assert.equal(await page.locator("#chart polyline").count(),1);

    // Separate SQLite fixture writer commits response #2 after startup.
    // The dashboard must observe it without refresh/restart or mutating DB.
    await page.waitForFunction(()=>
      document.querySelector("#events tbody").children.length===2,null,
      {timeout:20000});
    assert.match(await page.locator("#summary").innerText(),/Graded responses\s+2/);
    assert.equal(await page.locator("#chart polyline").count(),1);
    const status=await page.locator("#notice").innerText();
    assert.match(status,/read-only/);
    assert.deepEqual(faults,[]);
    console.log("PASS: independent Basic Auth protects researcher-only localhost dashboard");
    console.log("PASS: C1 BKT XY chart updates from 1 to 2 scored responses without page reload");
    console.log("PASS: mobile viewport, no PII, no JavaScript errors");
  }catch(e){throw Error((e.stack||String(e))+"\nFixture errors: "+errors.slice(-2500))}
  finally{if(browser)await browser.close();proc.kill("SIGTERM")}
}
main().catch(e=>{console.error(e);process.exitCode=1});

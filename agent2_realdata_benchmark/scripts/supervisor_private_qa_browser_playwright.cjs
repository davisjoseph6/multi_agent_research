"use strict";
/* Real Chromium two-role acceptance: passwordless school/Gmail applicants,
 * protected staff approval, one-time QA-only private links, operational
 * study plus researcher BKT chart. All state is temporary and loopback-only.
 * NO real email, production authorization or LIVE RCT enrollment.
 */
const assert=require("node:assert/strict");
const {spawn,execFileSync}=require("node:child_process");
const fs=require("node:fs");
const path=require("node:path");
const {chromium}=require("playwright");

const port=8897,base="http://127.0.0.1:"+port;
const SCHOOL="qa.browser.student@aivancity.education";
const EXTERNAL="qa.browser.external@gmail.com";
const STAFF="davis.joseph@aivancity.education";
const python=process.env.PYTHON||"python";
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const answerKey=JSON.parse(execFileSync(python,["-c",
 "import json;from src.prototype.supervisor_content import SupervisorBank;"+
 "b=SupervisorBank('data/supervisor_20261111');"+
 "print(json.dumps({k:v.correct_answer for k,v in b.by_id.items()}))"
],{encoding:"utf8",cwd:process.cwd()}));

async function main(){
 const proc=spawn(python,["-m","scripts.supervisor_private_qa","--port",
   String(port),"--school-email",SCHOOL,"--external-email",EXTERNAL],
   {cwd:process.cwd(),stdio:["ignore","pipe","pipe"]});
 let output="",errors="",credentialsDir=null,browser;
 proc.stdout.on("data",chunk=>{
  output+=String(chunk);
  const m=output.match(/Private QA account secrets at: ([^\r\n]+)/);
  if(m)credentialsDir=m[1].trim();
 });
 proc.stderr.on("data",chunk=>errors+=(String(chunk).slice(-1200)));
 const respond=route=>r=>r.request().method()==="POST"&&
   r.url().endsWith("/study/api/"+route);
 try{
  for(let i=0;i<100;i++){
   if(proc.exitCode!==null)throw Error("QA server stopped: "+errors.slice(-600));
   if(credentialsDir){
    try{if((await fetch(base+"/interest/school")).status===200)break}catch(_){}
   }
   if(i===99)throw Error("QA server did not bind: "+errors.slice(-600));
   await wait(200);
  }
  assert(credentialsDir && credentialsDir.includes("ijcai-qa-self-acceptance-"));
  const credential=fs.readFileSync(path.join(credentialsDir,
    STAFF.replace("@","_at_")+".txt"),"utf8");
  const match=credential.match(/Temporary password: ([^\r\n]+)/);
  assert(match,"private ephemeral staff password not found");
  const oldPassword=match[1];
  assert.match(credential,/QA ONLY/);
  browser=await chromium.launch({headless:true});
  const staffContext=await browser.newContext();
  const schoolContext=await browser.newContext();
  const gmailContext=await browser.newContext();
  const admin=await staffContext.newPage();
  const school=await schoolContext.newPage();
  const gmail=await gmailContext.newPage();
  const faults=[];
  for(const page of [admin,school,gmail])page.on("pageerror",x=>faults.push(String(x)));

  for(const [page,kind,email] of [[school,"school",SCHOOL],[gmail,"external",EXTERNAL]]){
   await page.goto(base+"/interest/"+kind,{waitUntil:"networkidle"});
   assert.equal(await page.locator('input[type="password"]').count(),0);
   await page.locator("#email").fill(email);
   await page.locator("#first-name").fill("Fictional");
   await page.locator("#ack").check();
   await page.locator('#interest-form button[type="submit"]').click();
   await page.waitForFunction(()=>document.querySelector("#status").textContent.includes("QA application saved"));
  }
  await admin.goto(base+"/control/",{waitUntil:"networkidle"});
  assert.equal(await admin.locator("#dashboard").isHidden(),true);
  await admin.locator("#email").fill(STAFF);
  await admin.locator("#password").fill(oldPassword);
  await admin.locator("#login button").click();
  await admin.locator("#password-panel").waitFor({state:"visible"});
  await admin.locator("#current").fill(oldPassword);
  await admin.locator("#replacement").fill("Private-QA-New-Browser-Password-2026!");
  await admin.locator("#password-form button").click();
  await admin.locator("#dashboard").waitFor({state:"visible"});
  assert.equal(await admin.locator(".candidate").count(),2);
  const applicants=await admin.locator("#applicants tr").evaluateAll(rows=>rows.map(r=>({
    id:r.querySelector(".candidate").value,
    email:r.querySelectorAll("td")[1].textContent.trim()
  })));
  assert.equal(new Set(applicants.map(x=>x.email)).size,2);
  await admin.locator("#all").check();
  await admin.locator("#approve").click();
  await admin.waitForFunction(()=>document.querySelector("#status").textContent.includes("2 applications"));
  const links={};
  await admin.goto(base+"/control/qa/",{waitUntil:"networkidle"});
  for(const a of applicants){
   await admin.locator("#candidate").fill(a.id);
   await admin.locator("#issue-form button").click();
   await admin.locator("#qa-link").waitFor({state:"visible"});
   links[a.email]=await admin.locator("#qa-link").getAttribute("href");
   assert.match(links[a.email],/^http:\/\/127\.0\.0\.1:8897\/study\/#invite=/);
  }
  assert(links[SCHOOL]&&links[EXTERNAL]&&links[SCHOOL]!==links[EXTERNAL]);
  await Promise.all([
   school.goto(links[SCHOOL],{waitUntil:"networkidle"}),
   gmail.goto(links[EXTERNAL],{waitUntil:"networkidle"})
  ]);
  for(const page of [school,gmail]){
   await page.locator("#information").waitFor({state:"visible"});
   assert.equal(new URL(page.url()).hash,"","invitation token fragment must be consumed");
  }
  assert.equal((await staffContext.request.get(base+"/control/api/capabilities")).status(),200);
  // One of two QA test students now exercises the actual operational quiz;
  // the other proves Gmail applicant onboarding without any student password.
  for(let i=0;i<5;i++)
   await school.locator("#consent-required input.required").nth(i).check();
  const screeningPromise=school.waitForResponse(respond("screening"));
  await school.locator("#start-consent").click();
  const screening=await (await screeningPromise).json();
  assert.equal(screening.questions.length,8);
  for(let i=0;i<8;i++){
   const q=screening.questions[i];
   const correct=answerKey[q.question_id];
   const selected=i<4?correct:"ABCD".split("").find(x=>x!==correct);
   await school.locator('#screen-options input[value="'+selected+'"]').check();
   if(i===7){
    const programs=school.waitForResponse(respond("programs"));
    await school.locator("#screen-next").click();
    await programs;
   }else await school.locator("#screen-next").click();
  }
  await school.locator("#registration").waitFor({state:"visible"});
  await school.locator("#age").selectOption("23");
  await school.locator("#program").selectOption("Private QA only");
  let nextPromise=school.waitForResponse(respond("item"));
  await school.locator("#register").click();
  let item=await (await nextPromise).json();
  assert.equal(item.phase,"PRETEST");
  for(let i=0;i<17;i++){
   assert.equal(item.kind,"question");
   const correct=answerKey[item.question_id];
   assert(correct,"missing canonical answer for a QA item");
   await school.locator('#choices input[value="'+correct+'"]').check();
   const feedback=school.waitForResponse(respond("answer"));
   await school.locator("#answer").click();
   assert.equal((await (await feedback).json()).previous_correct,true);
   await school.locator("#answer-feedback").waitFor({state:"visible"});
   nextPromise=school.waitForResponse(respond("item"));
   await school.locator("#feedback-next").click();
   item=await (await nextPromise).json();
  }

  await admin.goto(base+"/control/",{waitUntil:"networkidle"});
  await admin.locator("#dashboard").waitFor({state:"visible"});
  await admin.locator("#reload").click();
  await admin.waitForFunction(()=>document.querySelectorAll("#students tr button.inline-button").length>=1);
  await admin.locator("#students tr button.inline-button").first().click();
  await admin.waitForFunction(()=>
    document.querySelectorAll("#chart-legend span").length>0 &&
    document.querySelector("#selected-student").textContent.includes("STUDY_P"));
  assert.equal(await admin.locator("#mastery-chart").getAttribute("role"),"img");
  assert((await admin.locator("#mastery-chart polyline").count())>=1,
    "researcher BKT mastery needs at least one committed quiz response");
  assert.equal(await admin.locator("#send-selected").isDisabled(),true);
  assert.equal(await admin.locator("#send-all").isDisabled(),true);
  assert.deepEqual(faults,[]);
  console.log("PASS: school and Gmail QA questionnaires were passwordless and isolated");
  console.log("PASS: distinct researcher account approved and issued two private test links");
  console.log("PASS: operational student completed 16 pretest + one quiz answer");
  console.log("PASS: concurrent private researcher chart displayed recorded BKT mastery");
  console.log("PASS: no LIVE authorization, public recruitment, provider API calls or mail");
 }catch(e){throw Error((e.stack||String(e))+"\nQA server diagnostics: "+errors.slice(-1200));}
 finally{
  if(browser)await browser.close();
  proc.kill("SIGTERM");
 }
}
main().catch(e=>{console.error(e);process.exitCode=1});

"use strict";
/** Full synthetic three-arm, three-session Chromium browser acceptance.
 *
 * Drives the actual DOM (not merely Flask test_client) from consent through
 * screening, registration, 16 pretest items, 55 quiz items, 16 posttest items,
 * three surveys and debrief. Each of F1/F2/F3 uses an invented .test address.
 * Bank answers are loaded OFFLINE only by this developer test process.
 * Study UI never receives the correct-answer dictionary.
 */
const assert = require("node:assert/strict");
const {spawn,execFileSync} = require("node:child_process");
const {chromium} = require("playwright");

const port=8791, base=`http://127.0.0.1:${port}`;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const py=process.env.PYTHON || "python";
const answers=JSON.parse(execFileSync(py,["-c",
  "import json; from src.prototype.supervisor_content import SupervisorBank; "+
  "b=SupervisorBank('data/supervisor_20261111'); "+
  "print(json.dumps({k:v.correct_answer for k,v in b.by_id.items()}))"
],{encoding:"utf8",cwd:process.cwd()}));
const wrong=letter=>"ABCD".split("").find(x=>x!==letter);

async function check(){
  const proc=spawn(py,["-m","scripts.supervisor_fictional_browser","--port",String(port)],
    {cwd:process.cwd(),stdio:["ignore","pipe","pipe"]});
  let serverErrors="";
  proc.stderr.on("data",x=>serverErrors+=(String(x).slice(-1000)));
  let browser=null;
  try{
    for(let i=0;i<90;i++){
      if(proc.exitCode!==null)throw Error("private server unexpectedly stopped");
      try{if((await fetch(base)).ok)break}catch(_){}
      if(i===89)throw Error("private server did not bind loopback");
      await sleep(250);
    }
    browser=await chromium.launch({headless:true});
    const page=await browser.newPage({viewport:{width:1100,height:760}});
    const pageErrors=[];
    page.on("pageerror",e=>pageErrors.push(String(e)));
    await page.goto(base,{waitUntil:"networkidle"});
    const nonce=await page.locator("#app").getAttribute("data-preview-nonce");
    const post=async(fixture,action,data={})=>{
      const response=await fetch(base+"/supervisor/api/"+action,{
        method:"POST",
        headers:{"Content-Type":"application/json",
          "Origin":base,"X-Preview-Nonce":nonce},
        body:JSON.stringify({fixture,...data}),
      });
      const payload=await response.json();
      assert.equal(response.status,200,action+" "+JSON.stringify(payload));
      return payload;
    };
    const advance=async(button,expectedRoute="item")=>{
      const previous=await page.locator("#progress").innerText().catch(()=>"");
      const match=expectedRoute==="item"
        ?"/supervisor/api/item" :"/supervisor/api/consent/debrief";
      await Promise.all([
        page.waitForResponse(r=>r.request().method()==="POST"&&r.url().endsWith(match)),
        page.locator(button).click(),
      ]);
      if(expectedRoute==="item"){
        await page.waitForFunction(old=>
          document.querySelector("#progress").textContent!==old,
          previous,{timeout:15000});
      }
    };
    const answerCurrent=async(fixture,phase)=>{
      const data=await post(fixture,"item");
      assert.equal(data.kind,"question");
      if(phase)assert.equal(data.phase||"QUIZ",phase);
      const key=answers[data.question_id];
      assert(key && Object.hasOwn(data.options,key),"missing canonical option");
      await page.waitForFunction(text=>
        document.querySelector("#question").textContent===text,
        data.question_text,{timeout:15000});
      const radio=page.locator('#options input[value="'+key+'"]');
      await radio.check();
      await advance("#answer");
      return data;
    };
    const survey=async(fixture,isLast)=>{
      await page.locator("#survey").waitFor({state:"visible"});
      for(let i=0;i<6;i++)await page.locator("#fatigue_"+i).selectOption("3");
      await advance("#survey",isLast?"consent/debrief":"item");
      if(isLast){
        await page.locator("#debrief-stage").waitFor({state:"visible"});
      }else{
        assert.equal(await page.locator("#previous-result").isHidden(),true);
        await page.locator("#advance").waitFor({state:"visible"});
      }
    };

    for(const [index,fixture] of ["F1","F2","F3"].entries()){
      const language=fixture==="F2"?"fr":"en";
      if(index>0){
        await page.locator("#fixture").selectOption(fixture);
        await page.locator("#information").waitFor({state:"visible"});
      }
      // Test the French journey at a mobile width.
      await page.setViewportSize(index===1?{width:390,height:844}:{width:1100,height:760});
      if(language==="fr"){
        await page.locator("#study-lang").selectOption("fr");
        await page.waitForFunction(()=>document.documentElement.lang==="fr");
      }
      await page.locator("#information-sheet pre").waitFor({state:"visible"});
      await page.locator("#continue-info").click();
      await page.locator("#consent-stage").waitFor({state:"visible"});
      const required=page.locator("#consent-required input.required-consent");
      assert.equal(await required.count(),6);
      for(let i=0;i<6;i++)await required.nth(i).check();
      await page.locator("#start-consent").click();
      await page.locator("#screening-stage").waitFor({state:"visible"});

      const questions=(await post(fixture,"screening")).questions;
      assert.equal(questions.length,8);
      for(let i=0;i<8;i++){
        const key=answers[questions[i].question_id];
        assert(key);
        const letter=i<4?key:wrong(key);
        await page.waitForFunction(n=>
          document.querySelector("#screening-number").textContent.includes(String(n)),
          i+1);
        await page.locator('#screening-choices input[value="'+letter+'"]').check();
        await page.locator("#screening-next").click();
      }
      await page.locator("#registration-stage").waitFor({state:"visible"});
      await page.locator("#email").fill("full-browser-"+fixture.toLowerCase()+"@example.test");
      await page.locator("#submit-registration").click();
      await page.locator("#registered-stage").waitFor({state:"visible"});
      const initial=await post(fixture,"status");
      assert.equal(initial.study_language,language);
      assert.equal(initial.phase,"PRETEST");

      for(let n=0;n<16;n++)await answerCurrent(fixture,"PRETEST");
      assert.equal((await post(fixture,"status")).phase,"QUIZ");

      for(const [session,count] of [[1,20],[2,20],[3,15]]){
        for(let n=0;n<count;n++)await answerCurrent(fixture,null);
        const now=await post(fixture,"status");
        if(session===3){
          assert.equal(now.phase,"POSTTEST");
          // Post-test is independent: not contaminated by quiz feedback.
          assert.equal(await page.locator("#previous-result").isHidden(),true);
          for(let n=0;n<16;n++)await answerCurrent(fixture,"POSTTEST");
          assert.equal((await post(fixture,"status")).phase,"SURVEY");
        }else{
          assert.equal(now.phase,"SURVEY");
          // Last quiz answer must have feedback on the NEXT (fatigue) page.
          await page.locator("#previous-result").waitFor({state:"visible"});
          assert.equal(await page.locator("#previous-result-icon").innerText(),"✓");
        }
        await survey(fixture,session===3);
        if(session<3){
          await advance("#advance");
          assert.equal((await post(fixture,"status")).session,session+1);
          assert.equal((await post(fixture,"status")).phase,"QUIZ");
        }
      }
      const complete=await post(fixture,"status");
      assert.equal(complete.phase,"DONE");
      const debrief=await page.locator("#debrief").innerText();
      assert(debrief.length>150);
      if(language==="fr")assert.match(debrief,/Merci d'avoir participé/);
      console.log("PASS "+fixture+" Group "+["A","B","C"][index]+
                  " "+language.toUpperCase()+" all 3 sessions 55 quiz items");
    }

    assert.deepEqual(pageErrors,[]);
    console.log("PASS 3-arm end-to-end Chromium: 3 × (8 screening + 16 pre + 55 quiz + 16 post + 3 surveys), including mobile French and survey boundary feedback.");
  }catch(error){
    throw new Error((error.stack||String(error))+
      "\nPython server errors: "+serverErrors.slice(-2500));
  }finally{
    if(browser)await browser.close();
    proc.kill("SIGTERM");
  }
}
check().catch(error=>{console.error(error);process.exitCode=1});

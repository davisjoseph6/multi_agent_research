"use strict";
/* Browser acceptance against the operational HTTPS-route API on localhost.
 * Every identity is an invented @example.example address; no SMTP or humans.
 */
const assert=require("node:assert/strict");
const {spawn,execFileSync}=require("node:child_process");
const {chromium}=require("playwright");
const port=8792,base=`http://127.0.0.1:${port}`;
const python=process.env.PYTHON||"python";
const answerKey=JSON.parse(execFileSync(python,["-c",
  "import json;from src.prototype.supervisor_content import SupervisorBank;"+
  "b=SupervisorBank('data/supervisor_20261111');"+
  "print(json.dumps({k:v.correct_answer for k,v in b.by_id.items()}))"
],{encoding:"utf8",cwd:process.cwd()}));
const wait=ms=>new Promise(r=>setTimeout(r,ms));

async function run(){
  const proc=spawn(python,["-m","scripts.supervisor_vps_dev","--port",String(port)],
    {cwd:process.cwd(),stdio:["ignore","pipe","pipe"]});
  let output="",errors="",tokens=null,browser;
  proc.stdout.on("data",chunk=>{
    output+=String(chunk);
    const m=output.match(/TEST_INVITES=(\{[^\n]+\})/);
    if(m)tokens=JSON.parse(m[1]);
  });
  proc.stderr.on("data",chunk=>errors+=(String(chunk).slice(-1600)));
  const respond=route=>r=>r.request().method()==="POST"&&
                             r.url().endsWith("/study/api/"+route);
  try{
    for(let t=0;t<120;t++){
      if(proc.exitCode!==null)throw Error("operational server stopped");
      if(tokens){
        try{if((await fetch(base+"/study/health")).ok)break}catch(_){}
      }
      if(t===119)throw Error("operational server unavailable");
      await wait(250);
    }
    browser=await chromium.launch({headless:true});
    for(const [index,fixture] of ["F1","F2","F3"].entries()){
      const isFrench=fixture==="F2";
      const context=await browser.newContext({
        viewport:isFrench?{width:390,height:844}:{width:1200,height:900}
      });
      const page=await context.newPage();
      const pageErrors=[];
      page.on("pageerror",e=>pageErrors.push(String(e)));
      await page.goto(base+"/study/#invite="+tokens[fixture],
                      {waitUntil:"networkidle"});
      await page.locator("#information").waitFor({state:"visible"});
      assert.equal(new URL(page.url()).hash,"");
      assert.match(await page.locator("#ai-rule").innerText(),/generative AI/i);
      assert.equal(await page.locator("#info-copy h2").count()>5,true);
      if(isFrench){
        await page.locator("#language").selectOption("fr");
        await page.waitForFunction(()=>
          document.querySelector("#info-title").textContent
          .includes("consentement"));
      }
      assert.equal(await page.locator("#consent-required input.required").count(),5);
      for(let i=0;i<5;i++){
        await page.locator("#consent-required input.required").nth(i).check();
      }
      const screeningPromise=page.waitForResponse(respond("screening"));
      await page.locator("#start-consent").click();
      const screening=(await screeningPromise).json();
      const qlist=(await screening).questions;
      assert.equal(qlist.length,8);
      await page.locator("#screening").waitFor({state:"visible"});
      for(let i=0;i<8;i++){
        const q=qlist[i],key=answerKey[q.question_id];
        assert(key);
        const chosen=i<4?key:"ABCD".split("").find(x=>x!==key);
        await page.locator('#screen-options input[value="'+chosen+'"]').check();
        if(isFrench && i===2){
          // Regression: a consented learner changes only the screen language
          // at question 3/8; the prior selections and the current choice
          // must survive, and the question text must really translate.
          const english=page.waitForResponse(respond("screening"));
          await page.locator("#language").selectOption("en");
          const translated=(await english).json();
          assert.equal((await translated).language,"en");
          await page.waitForFunction(expected=>
            document.querySelector("#screen-number").textContent==="Question 3 of 8" &&
            document.querySelector("#screen-prompt").textContent===expected,
          (await translated).questions[2].question_text);
          assert.notEqual((await translated).questions[2].question_text,q.question_text);
          assert.equal(await page.locator('#screen-options input[value="'+chosen+'"]').isChecked(),true);
          const french=page.waitForResponse(respond("screening"));
          await page.locator("#language").selectOption("fr");
          await french;
          await page.waitForFunction(expected=>
            document.querySelector("#screen-number").textContent==="Question 3 sur 8" &&
            document.querySelector("#screen-prompt").textContent===expected,
          q.question_text);
          assert.equal(await page.locator('#screen-options input[value="'+chosen+'"]').isChecked(),true);
        }
        const next=page.locator("#screen-next");
        if(i===7){
          const registration=page.waitForResponse(respond("programs"));
          await next.click();
          await registration;
        }else await next.click();
      }
      await page.locator("#registration").waitFor({state:"visible"});
      await page.locator("#age").selectOption("23");
      await page.locator("#program").selectOption("Test student program");
      let nextItem=page.waitForResponse(respond("item"));
      await page.locator("#register").click();
      let item=await (await nextItem).json();
      assert.equal(item.phase,"PRETEST");
      await page.locator("#learning").waitFor({state:"visible"});
      if(isFrench){
        // A locale change must keep the same pretest question, render
        // capability and the choice already selected by the learner.
        const correct=answerKey[item.question_id];
        await page.locator('#choices input[value="'+correct+'"]').check();
        let change=page.waitForResponse(respond("item"));
        await page.locator("#language").selectOption("en");
        const english=(await change).json();
        assert.equal((await english).question_id,item.question_id);
        assert.equal((await english).render_id,item.render_id);
        assert.equal(await page.locator('#choices input[value="'+correct+'"]').isChecked(),true);
        change=page.waitForResponse(respond("item"));
        await page.locator("#language").selectOption("fr");
        const french=(await change).json();
        assert.equal((await french).question_id,item.question_id);
        assert.equal((await french).render_id,item.render_id);
        assert.equal(await page.locator('#choices input[value="'+correct+'"]').isChecked(),true);
      }
      let checkedFeedbackSwitch=false;
      async function submitCorrect(expectedKind){
        assert.equal(item.kind,expectedKind);
        assert(item.render_id&&item.question_id);
        const correct=answerKey[item.question_id];
        assert(Object.hasOwn(item.options,correct));
        await page.waitForFunction(question=>
          document.querySelector("#question").textContent===question,
          item.question_text);
        await page.locator('#choices input[value="'+correct+'"]').check();
        if(item.action==="QUESTION"){
          const answerRes=page.waitForResponse(respond("answer"));
          await page.locator("#answer").click();
          const feedback=await (await answerRes).json();
          assert.equal(feedback.correct_choice,correct);
          assert.equal(feedback.previous_correct,true);
          await page.locator("#answer-feedback").waitFor({state:"visible"});
          assert.match(await page.locator("#feedback-explanation").innerText(),/Explanation|Explication/);
          if(isFrench && item.phase===undefined && !checkedFeedbackSwitch){
            // Quiz response has already been committed. Changing language
            // must NOT fetch the next question or dismiss the explanation.
            checkedFeedbackSwitch=true;
            const prompt=await page.locator("#question").innerText();
            await page.locator("#language").selectOption("en");
            assert.equal(await page.locator("#answer-feedback").isVisible(),true);
            assert.equal(await page.locator("#question").innerText(),prompt);
            await page.waitForFunction(()=>document.querySelector("#feedback-title").textContent==="Correct");
            await page.locator("#language").selectOption("fr");
            assert.equal(await page.locator("#answer-feedback").isVisible(),true);
            await page.waitForFunction(()=>document.querySelector("#feedback-title").textContent==="Bonne réponse");
          }
          nextItem=page.waitForResponse(respond("item"));
          await page.locator("#feedback-next").click();
        }else{
          nextItem=page.waitForResponse(respond("item"));
          await page.locator("#answer").click();
        }
        item=await (await nextItem).json();
      }
      for(let i=0;i<16;i++)await submitCorrect("question");
      assert.equal(item.action,"QUESTION");
      assert.equal(await page.locator("#previous-result").isHidden(),true);
      for(let i=0;i<20;i++)await submitCorrect("question");
      assert.equal(item.kind,"survey");
      await page.locator("#fatigue-0").waitFor({state:"visible"});
      assert.equal(await page.locator("#previous-result").isHidden(),true);
      assert.match(await page.locator("#phase-intro").innerText(),/Quiz|quiz/);
      for(let i=0;i<5;i++){
        assert.equal(await page.locator("#surveys input[type=range]").count(),1);
        assert.equal(await page.locator("#fatigue-"+i).getAttribute("min"),"1");
        assert.equal(await page.locator("#fatigue-"+i).getAttribute("max"),"7");
        if(isFrench&&i===2){
          await page.locator("#fatigue-2").evaluate(el=>{
            el.value="6";el.dispatchEvent(new Event("input",{bubbles:true}));
          });
          await page.locator("#language").selectOption("en");
          assert.equal(await page.locator("#fatigue-2").inputValue(),"6");
          await page.locator("#language").selectOption("fr");
          assert.equal(await page.locator("#fatigue-2").inputValue(),"6");
        }
        await page.locator("#fatigue-next").click();
      }
      assert.equal(await page.locator("#fatigue-5").count(),1);
      await page.locator("#submit-survey").waitFor({state:"visible"});
      nextItem=page.waitForResponse(respond("item"));
      await page.locator("#submit-survey").click();
      item=await (await nextItem).json();
      assert.equal(item.kind,"waiting_next_session");
      assert.equal(await page.locator("#previous-result").isHidden(),true);
      await page.locator("#session-summary").waitFor({state:"visible"});
      assert.match(await page.locator("#session-summary").innerText(),/20/);
      assert.deepEqual(pageErrors,[]);
      console.log("PASS "+fixture+" / "+["A","B","C"][index]+" / "+
                  (isFrench?"French mobile":"English desktop")+
                  ": consent → screening → registration → 16 pretest → "+
                  "20 practice → survey → scheduled wait");
      await context.close();
    }
    console.log("PASS full persistent operational participant browser API smoke: all three arms, zero human subjects.");
  }catch(e){
    throw Error((e.stack||String(e))+"\nServer errors: "+errors.slice(-2700));
  }finally{
    if(browser)await browser.close();
    proc.kill("SIGTERM");
  }
}
run().catch(e=>{console.error(e);process.exitCode=1});

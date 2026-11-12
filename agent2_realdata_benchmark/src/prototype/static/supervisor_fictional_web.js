"use strict";
(() => {
 const root=document.getElementById("app"),nonce=root.dataset.previewNonce;
 const $=id=>document.getElementById(id);
 const fixture=$("fixture");
 let item=null,working=false,questions=[],screenIndex=0,screenAnswers={};
 let currentLanguage="en";
 const sections=["information","consent-stage","screening-stage","registration-stage",
   "excluded-stage","registered-stage","withdraw-stage","debrief-stage"];
 const quizButtons=["answer","continue","survey","advance"];
 function message(text){$("feedback").textContent=text||""}
 function showSection(id){for(const s of sections)$(s).hidden=s!==id}
 function buttons(...visible){for(const b of quizButtons)$(b).hidden=!visible.includes(b)}
 function requestId(){return "fictional_"+crypto.randomUUID().replaceAll("-","")}
 async function call(action,data={}){
   const r=await fetch("/supervisor/api/"+action,{
     method:"POST",headers:{"Content-Type":"application/json",
       "Origin":window.location.origin,"X-Preview-Nonce":nonce},
     body:JSON.stringify({fixture:fixture.value,...data}),
   });
   const body=await r.json();
   if(!r.ok)throw new Error(body.error||"Private preview refused request");
   return body;
 }
 function options(parent,choiceMap,name){
   parent.replaceChildren();
   const legend=document.createElement("legend");
   legend.textContent="Select one answer";parent.append(legend);
   for(const [key,text] of Object.entries(choiceMap)){
     const label=document.createElement("label"),input=document.createElement("input");
     input.type="radio";input.name=name;input.value=key;
     label.append(input,document.createTextNode(key+". "+text));parent.append(label);
   }
 }
 function selected(name){
   const input=document.querySelector('input[name="'+name+'"]:checked');
   if(!input)throw new Error("Select an answer first.");
   return input.value;
 }
 async function renderInformation(){
   const lang=$("info-lang").value;
   currentLanguage=lang;
   $("footer-information").href="/content/consent/"+lang+"/info";
   $("french-link").href="/content/consent/fr/info";
   $("pdf-link").href="/content/consent/"+lang+"/pdf";
   const r=await fetch("/content/consent/"+lang+"/info",{cache:"no-store"});
   if(!r.ok)throw new Error("Versioned information sheet unavailable");
   const html=await r.text();
   const doc=new DOMParser().parseFromString(html,"text/html");
   const source=doc.querySelector("article pre, main pre, pre");
   if(!source)throw new Error("Information sheet text missing");
   const target=$("information-sheet");
   target.replaceChildren();
   const block=document.createElement("pre");
   block.textContent=source.textContent;
   target.append(block);
   const copy=await call("consent/copy",{language:lang});
   const required=$("consent-required");required.replaceChildren();
   const legend=document.createElement("legend");
   legend.textContent=lang==="en"?"I confirm that:":"Je déclare :";
   required.append(legend);
   copy.required.forEach((text,i)=>{
     const label=document.createElement("label"),input=document.createElement("input");
     input.type="checkbox";input.className="required-consent";
     input.id="required-"+i;input.checked=false;
     label.append(input,document.createTextNode(text));
     required.append(label);
   });
   const optional=$("consent-optional");optional.replaceChildren();
   const optLegend=document.createElement("legend");
   optLegend.textContent=lang==="en"?"Optional (no effect on participation):":
       "Facultatif (sans effet sur la participation) :";
   optional.append(optLegend);
   const optLabel=document.createElement("label"),opt=document.createElement("input");
   opt.type="checkbox";opt.id="open-data-choice";opt.checked=false;
   optLabel.append(opt,document.createTextNode(copy.optional));
   optional.append(optLabel);
   $("start-consent").disabled=true;
   required.addEventListener("change",()=>{
     $("start-consent").disabled=!(
       [...required.querySelectorAll('input[type="checkbox"]')].length===6 &&
       [...required.querySelectorAll('input[type="checkbox"]')].every(x=>x.checked)
     );
   },{once:false});
 }
 async function getScreening(){
   const result=await call("screening");
   questions=result.questions;
   if(questions.length!==8)throw new Error("Expected 8 screening questions");
   screenIndex=0;screenAnswers={};
   showScreening();
 }
 function showScreening(){
   showSection("screening-stage");
   const q=questions[screenIndex];
   $("screening-number").textContent="Question "+(screenIndex+1)+" of 8";
   $("screening-prompt").textContent=q.question_text;
   options($("screening-choices"),q.options,"screening-current");
   $("screening-next").textContent=screenIndex===7?"Finish screening":"Next";
 }
 function showCurrent(data){
   item=data;
   $("question").textContent="";
   $("options").replaceChildren();buttons();
   if(data.kind==="question"){
     $("question").textContent=data.question_text;
     options($("options"),data.options,"current");buttons("answer");
   }else if(data.kind==="recovery"){
     if(data.question_id){
       $("question").textContent=data.action+" — "+data.question_text;
       options($("options"),data.options,"current");buttons("answer");
     }else{
       $("question").textContent=data.action+
         " — synthetic teaching resource; text requires academic review.";
       buttons("continue");
     }
   }else if(data.kind==="survey"){
     $("question").textContent="Six provisional 1–7 fatigue responses. "+
       "Exact NASA-TLX wording requires supervisor approval.";
     for(let i=0;i<6;i++){
       const label=document.createElement("label");
       label.textContent="Fatigue item Q"+(i+1);
       const select=document.createElement("select");select.id="fatigue_"+i;
       for(let v=1;v<=7;v++){
         const option=document.createElement("option");
         option.value=String(v);option.textContent=String(v);select.append(option);
       }
       label.append(select);$("options").append(label);
     }
     buttons("survey");
   }else if(data.kind==="waiting_next_session"){
     $("question").textContent="Next fictional visit: "+data.scheduled_for;
     buttons("advance");
   }else if(data.kind==="done"){
     $("question").textContent="Three fictional sessions completed.";
   }else $("question").textContent=data.kind||"No fictional step";
 }
 async function refresh(){
   if(working)return;working=true;
   try{
     message("");
     const status=await call("status");
     if(!status.registered){
       const stage=status.consent_stage||"information";
       if(stage==="excluded"){showSection("excluded-stage");}
       else if(stage==="screening"){
         await getScreening();
       }else if(stage==="registration"){
         showSection("registration-stage");
       }else{
         await renderInformation();
         showSection(new URLSearchParams(window.location.search).has("consent")
                     ? "consent-stage" : "information");
       }
     }else{
       currentLanguage=status.consent_lang||"en";
       $("footer-information").href="/content/consent/"+currentLanguage+"/info";
       $("progress").textContent="Fictional "+fixture.value+" — Session "+
          status.session+"/3 — "+status.phase+" — step "+status.index;
       if(status.phase==="DONE"){
         const deb=await call("consent/debrief");
         $("debrief").textContent=deb.text;
         showSection("debrief-stage");
       }else{
         showSection(new URLSearchParams(window.location.search).has("stop")
                     ? "withdraw-stage" : "registered-stage");
         showCurrent(await call("item"));
       }
     }
   }catch(e){message(e.message);buttons()}finally{working=false}
 }
 async function act(action,data={}){
   if(working)return;working=true;
   try{message("");await call(action,data)}
   catch(e){message(e.message);working=false;return}
   working=false;await refresh();
 }
 $("continue-info").addEventListener("click",()=>showSection("consent-stage"));
 $("info-lang").addEventListener("change",async()=>{
   try{await renderInformation()}catch(e){message(e.message)}
 });
 $("start-consent").addEventListener("click",()=>{
   const checkboxes=[...$("consent-required").querySelectorAll('input[type="checkbox"]')];
   if(checkboxes.length!==6||!checkboxes.every(x=>x.checked))return;
   act("consent/start",{
     language:currentLanguage,checks:checkboxes.map(x=>x.checked),
     optional:$("open-data-choice").checked,
   });
 });
 $("econ-course-link").addEventListener("click",event=>{
   event.preventDefault();act("consent/economics");
 });
 $("screening-next").addEventListener("click",async()=>{
   try{
     const q=questions[screenIndex];
     screenAnswers[q.question_id]=selected("screening-current");
     if(screenIndex<7){screenIndex++;showScreening()}
     else await act("consent/screen",{answers:screenAnswers});
   }catch(e){message(e.message)}
 });
 $("submit-registration").addEventListener("click",()=>{
   act("consent/register",{
     email:$("email").value.trim(),age:Number($("age").value),
     program:$("program").value,
   });
 });
 $("footer-stop").addEventListener("click",async event=>{
   event.preventDefault();
   try{
     const stat=await call("status");
     if(!stat.registered){
       message("No registered fictional participant data to withdraw.");
       return;
     }
     showSection("withdraw-stage");
   }catch(e){message(e.message)}
 });
 async function withdraw(deleteData){
   if(!window.confirm(
     "Confirm stop participating? No AI points are awarded before completion of Session 3."
   ))return;
   if(working)return;working=true;
   try{
     const outcome=await call("consent/withdraw",{
       delete:deleteData,confirmed:true,
     });
     showSection("excluded-stage");
     $("excluded-stage").querySelector("p").textContent=outcome.message;
     message("Fictional withdrawal completed; no real email was sent.");
   }catch(e){message(e.message)}
   finally{working=false}
 }
 $("withdraw-keep").addEventListener("click",()=>withdraw(false));
 $("withdraw-delete").addEventListener("click",()=>withdraw(true));
 $("withdraw-cancel").addEventListener("click",refresh);
 $("answer").addEventListener("click",()=>{
   try{act("answer",{question_id:item.question_id||null,
     choice:selected("current"),request_id:requestId()})}
   catch(e){message(e.message)}
 });
 $("continue").addEventListener("click",()=>{
   act("answer",{question_id:null,choice:null,request_id:requestId()})
 });
 $("survey").addEventListener("click",()=>{
   const values=[];for(let i=0;i<6;i++)values.push(Number($("fatigue_"+i).value));
   act("survey",{values,request_id:requestId()});
 });
 $("advance").addEventListener("click",()=>act("advance-fictional-clock"));
 $("load").addEventListener("click",refresh);
 fixture.addEventListener("change",refresh);
 refresh();
})();
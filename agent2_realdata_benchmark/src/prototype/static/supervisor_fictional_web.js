"use strict";
(() => {
 const root=document.getElementById("app"),nonce=root.dataset.previewNonce;
 const $=id=>document.getElementById(id);
 const fixture=$("fixture");
 let item=null,working=false,questions=[],screenIndex=0,screenAnswers={};
 let currentLanguage="en";
 let hintIndex=0,hintResponses=[],previousFeedback=null;
 const COPY=window.SupervisorCopy;
 if(!COPY || !COPY.fr || !COPY.en)throw new Error("Bilingual copy is missing");
 function t(key,...args){
   const entry=COPY[currentLanguage][key];
   if(entry===undefined)throw new Error("Missing translation: "+currentLanguage+"/"+key);
   return typeof entry==="function"?entry(...args):entry;
 }
 function applyLanguage(){
   document.documentElement.lang=currentLanguage;
   document.title=t("page_title");
   $("study-lang").value=currentLanguage;
   $("info-lang").value=currentLanguage;
   $("hint-reflection").lang=currentLanguage;
   for(const element of document.querySelectorAll("[data-i18n]")){
     element.textContent=t(element.dataset.i18n);
   }
   const legend=$("options").querySelector("legend");
   if(legend)legend.textContent=t("answer_choice");
   const screeningLegend=$("screening-choices").querySelector("legend");
   if(screeningLegend)screeningLegend.textContent=t("answer_choice");
 }
 function renderPreviousFeedback(){
   const panel=$("previous-result");
   const valid=typeof previousFeedback==="boolean";
   panel.hidden=!valid;
   panel.classList.toggle("correct",valid&&previousFeedback);
   panel.classList.toggle("incorrect",valid&&!previousFeedback);
   $("previous-result-icon").textContent=!valid?"":previousFeedback?"✓":"✕";
   $("previous-result-text").textContent=!valid?"":t(
     previousFeedback?"previous_correct":"previous_incorrect"
   );
 }
 const sections=["information","consent-stage","screening-stage","registration-stage",
   "excluded-stage","registered-stage","withdraw-stage","debrief-stage"];
 const quizButtons=["answer","continue","survey","advance","hint-next"];
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
   if(!r.ok){
      let error=body.error||t("server_failed");
      if(currentLanguage==="fr"){
        if(/already registered|duplicate/i.test(error))
          error=t("server_duplicate");
        else if(/eligible|excluded/i.test(error))
          error=t("screening_ineligible");
        else if(/required|missing|invalid|unsupported|refus|wrong|not due/i.test(error))
          error=t("other_error");
      }
      throw new Error(error);
    }
   return body;
 }
 function options(parent,choiceMap,name){
   parent.replaceChildren();
   const legend=document.createElement("legend");
   legend.textContent=t("answer_choice");parent.append(legend);
   for(const [key,text] of Object.entries(choiceMap)){
     const label=document.createElement("label"),input=document.createElement("input");
     input.type="radio";input.name=name;input.value=key;
     label.append(input,document.createTextNode(key+". "+text));parent.append(label);
   }
 }
 function selected(name){
   const input=document.querySelector('input[name="'+name+'"]:checked');
   if(!input)throw new Error(t("choose_first"));
   return input.value;
 }
 async function renderInformation(){
   const lang=$("info-lang").value;
   currentLanguage=lang;
   applyLanguage();
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
   legend.textContent=t("required");
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
   optLegend.textContent=t("optional");
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
   $("screening-number").textContent=t("question_count",screenIndex+1);
   $("screening-prompt").textContent=q.question_text;
   options($("screening-choices"),q.options,"screening-current");
   $("screening-next").textContent=screenIndex===7?t("finish_screening"):t("next");
 }
 function showSocraticPrompt(){
   const resource=item.resource;
   $("recovery-content").hidden=false;
   $("options").hidden=true;
   $("question").textContent=t("socratic_reflect");
   $("recovery-title").textContent=resource.title;
   $("recovery-paragraphs").replaceChildren();
   const intro=document.createElement("p");
   intro.textContent=resource.intro;
   $("recovery-paragraphs").append(intro);
   $("hint-guidance").hidden=false;
   $("hint-guidance").textContent=
     "Guiding question "+(hintIndex+1)+" of "+resource.prompts.length+
     ": "+resource.prompts[hintIndex];
   $("hint-label").hidden=false;
   $("hint-reflection").hidden=false;
   $("hint-reflection").value="";
   $("hint-next").textContent=(hintIndex+1===resource.prompts.length)
     ? t("reveal_re_ask") : t("next_hint");
   buttons("hint-next");
 }
 function showCurrent(data){
   item=data;hintIndex=0;hintResponses=[];
   $("question").textContent="";
   $("options").replaceChildren();
   $("options").hidden=false;
   $("recovery-content").hidden=true;
   $("recovery-paragraphs").replaceChildren();
   $("hint-guidance").hidden=true;
   $("hint-label").hidden=true;
   $("hint-reflection").hidden=true;
   buttons();
   if(data.kind==="question"){
     $("question").textContent=data.question_text;
     options($("options"),data.options,"current");buttons("answer");
   }else if(data.kind==="recovery"){
     if(data.action==="SOCRATIC_HINT"){
       if(!data.question_id||!data.resource ||
          !Array.isArray(data.resource.prompts) ||
          data.resource.prompts.length!==2)
         throw new Error("Socratic text missing; refusing unhinted re-attempt");
       showSocraticPrompt();
     }else if(data.action==="DROP_2"){
       $("question").textContent="DROP_2 — "+data.question_text;
       options($("options"),data.options,"current");buttons("answer");
     }else if(data.action==="CONCEPT_SUMMARY"||
              data.action==="WORKED_EXAMPLE"){
       if(!data.resource || !Array.isArray(data.resource.paragraphs) ||
          data.resource.paragraphs.length<2)
         throw new Error("Required teaching text is missing");
       $("question").textContent=data.action.replaceAll("_"," ");
       $("options").hidden=true;
       $("recovery-content").hidden=false;
       $("recovery-title").textContent=data.resource.title;
       for(const paragraph of data.resource.paragraphs){
         const p=document.createElement("p");
         p.textContent=paragraph;
         $("recovery-paragraphs").append(p);
       }
       buttons("continue");
     }else throw new Error("Unknown recovery action");
   }else if(data.kind==="survey"){
     $("question").textContent=t("provisional_survey");
     for(let i=0;i<6;i++){
       const label=document.createElement("label");
       label.textContent=t("survey_item",i+1);
       const select=document.createElement("select");select.id="fatigue_"+i;
       for(let v=1;v<=7;v++){
         const option=document.createElement("option");
         option.value=String(v);option.textContent=String(v);select.append(option);
       }
       label.append(select);$("options").append(label);
     }
     buttons("survey");
   }else if(data.kind==="waiting_next_session"){
     $("question").textContent=t("next_visit",data.scheduled_for);
     buttons("advance");
   }else if(data.kind==="done"){
     $("question").textContent=t("completed_3");
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
       currentLanguage=status.study_language||"en";
       applyLanguage();
       $("footer-information").href="/content/consent/"+currentLanguage+"/info";
       $("progress").textContent=t("session_progress",fixture.value,status.session,status.phase,status.index);
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
   try{
     message("");
     const outcome=await call(action,data);
     if(action==="consent/register"&&outcome.message){
       $("registered-message").textContent=t("register_done");
     }
   }catch(e){message(e.message);working=false;return}
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
       message(t("no_consent"));
       return;
     }
     showSection("withdraw-stage");
   }catch(e){message(e.message)}
 });
 async function withdraw(deleteData){
   if(!window.confirm(
     t("withdrawal_confirm")
   ))return;
   if(working)return;working=true;
   try{
     const outcome=await call("consent/withdraw",{
       delete:deleteData,confirmed:true,
     });
     showSection("excluded-stage");
     $("excluded-stage").querySelector("p").textContent=t(
       deleteData?"delete_confirm":"keep_confirm"
     );
     message(t("withdrawal_done"));
   }catch(e){message(e.message)}
   finally{working=false}
 }
 $("withdraw-keep").addEventListener("click",()=>withdraw(false));
 $("withdraw-delete").addEventListener("click",()=>withdraw(true));
 $("withdraw-cancel").addEventListener("click",refresh);
 $("hint-next").addEventListener("click",()=>{
   if(!item || item.kind!=="recovery" || item.action!=="SOCRATIC_HINT")
     return;
   const response=$("hint-reflection").value.trim();
   if(!response || response.length>500){
     message(t("enter_reflection"));
     return;
   }
   hintResponses.push(response);
   message("");
   if(hintIndex+1<item.resource.prompts.length){
     hintIndex++;
     showSocraticPrompt();
   }else{
     $("recovery-content").hidden=true;
     $("question").textContent=
       t("socratic_reask")+item.question_text;
     $("options").hidden=false;
     options($("options"),item.options,"current");
     buttons("answer");
   }
 });
 $("answer").addEventListener("click",()=>{
   try{
     const data={question_id:item.question_id||null,
                 choice:selected("current"),request_id:requestId()};
     if(item.kind==="recovery"&&item.action==="SOCRATIC_HINT"){
       if(hintResponses.length!==2)
         throw new Error(t("finish_reflections"));
       data.reflection=hintResponses.slice();
     }
     act("answer",data);
   }catch(e){message(e.message)}
 });
 $("continue").addEventListener("click",()=>{
   act("answer",{question_id:null,choice:null,request_id:requestId()})
 });
 $("survey").addEventListener("click",()=>{
   const values=[];for(let i=0;i<6;i++)values.push(Number($("fatigue_"+i).value));
   act("survey",{values,request_id:requestId()});
 });
 $("advance").addEventListener("click",()=>act("advance-fictional-clock"));
 $("quick-recovery").addEventListener("click",async()=>{
   if(working)return;
   fixture.value="F1";
   working=true;
   try{
     message("");
     const outcome=await call("demo/prime-recovery");
     if(!outcome.prepared||outcome.next_action!=="CONCEPT_SUMMARY")
       throw new Error("Recovery preparation did not complete");
     $("registered-message").textContent=
       t("loss_aversion_demo");
   }catch(e){message(e.message);working=false;return}
   working=false;
   await refresh();
 });
 $("load").addEventListener("click",refresh);
 fixture.addEventListener("change",refresh);
 refresh();
})();
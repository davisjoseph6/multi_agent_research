"use strict";
(()=>{
 const $=id=>document.getElementById(id);
 let lang="en",current=null,screening=[],screenIndex=0,answers={};
 let hintIndex=0,reflections=[],previous=null,phase=null,busy=false,registered=false;
 const copy={
  en:{
   site:"Adaptive Learning Study",info:"Information and consent",
   begin:"I agree and continue",course:"I previously took an economics course",
   screen:"Eligibility screening",next:"Next",finish:"Finish screening",
   nofeedback:"No correctness feedback is provided for screening.",
   registration:"Registration",regInfo:"Your invitation verified your email address. No name is requested.",
   age:"Age",program:"Academic program",register:"Register and start session 1",
   activity:"Current activity",choice:"Choose one answer",
   reasoning:"Your own reasoning",answer:"Submit answer",continue:"Continue",
   hintNext:"Next guiding question",survey:"Submit six ratings",
   nextSession:"Begin next scheduled session",refresh:"Refresh current activity",
   completed:"Study completed",stop:"Stop participating",
   stopInfo:"You may stop at any time. Choose whether to retain your pseudonymized responses or delete your data.",
   keep:"Stop and retain answers",erase:"Stop and erase data",cancel:"Cancel",
   correct:"Previous answer was correct",incorrect:"Previous answer was incorrect",
   required:"Six required declarations",optional:"Optional data sharing",
   missing:"Choose an answer before continuing.",
   reasonMissing:"Please explain your reasoning briefly.",
   questionNumber:i=>"Question "+i+" of 8",
   fatigue:"Six provisional 1–7 fatigue items. Wording and scoring require academic approval.",
   surveyItem:i=>"Fatigue item "+i,
   hint:(n,total)=>"Guiding question "+n+" of "+total,
   reattempt:"Answer the original question again.",
   waiting:date=>"Next scheduled visit: "+date+" (no early entry).",
   noInvite:"Open the invitation link sent by the study coordinator.",
   confirmed:"Your participation has ended.",
   error:"The request could not be completed.",
   progress:(s,p,i)=>"Session "+s+"/3 — "+p+" — step "+i,
   noStudy:"No active study invitation.",
   reveal:"Show original question",
  },
  fr:{
   site:"Étude sur l'apprentissage adaptatif",info:"Information et consentement",
   begin:"J'accepte et je continue",course:"J'ai déjà suivi un cours d'économie",
   screen:"Test de présélection",next:"Suivant",finish:"Terminer la présélection",
   nofeedback:"La présélection ne donne aucune indication de justesse.",
   registration:"Inscription",regInfo:"Votre invitation a confirmé votre adresse. Aucun nom n'est demandé.",
   age:"Âge",program:"Formation",register:"S'inscrire et commencer la séance 1",
   activity:"Activité en cours",choice:"Choisissez une réponse",
   reasoning:"Votre raisonnement",answer:"Valider la réponse",continue:"Continuer",
   hintNext:"Question guidée suivante",survey:"Envoyer les six évaluations",
   nextSession:"Commencer la prochaine séance prévue",refresh:"Actualiser l'activité",
   completed:"Étude terminée",stop:"Arrêter la participation",
   stopInfo:"Vous pouvez arrêter à tout moment. Choisissez de conserver vos réponses pseudonymisées ou de supprimer vos données.",
   keep:"Arrêter en conservant les réponses",erase:"Arrêter et supprimer les données",
   cancel:"Annuler",correct:"La réponse précédente était correcte",
   incorrect:"La réponse précédente était incorrecte",
   required:"Six déclarations obligatoires",optional:"Partage de données facultatif",
   missing:"Choisissez d'abord une réponse.",
   reasonMissing:"Expliquez brièvement votre raisonnement.",
   questionNumber:i=>"Question "+i+" sur 8",
   fatigue:"Six items provisoires de fatigue notés de 1 à 7. Le libellé et le calcul doivent être approuvés.",
   surveyItem:i=>"Item de fatigue "+i,
   hint:(n,total)=>"Question guidée "+n+" sur "+total,
   reattempt:"Répondez de nouveau à la question d'origine.",
   waiting:date=>"Séance suivante prévue : "+date+" (accès anticipé impossible).",
   noInvite:"Ouvrez le lien d'invitation envoyé par le responsable de l'étude.",
   confirmed:"Votre participation est terminée.",
   error:"La demande n'a pas pu être traitée.",
   progress:(s,p,i)=>"Séance "+s+"/3 — "+p+" — étape "+i,
   noStudy:"Aucune invitation active.",
   reveal:"Afficher la question d'origine",
  }
 };
 const t=(key,...args)=>{
   const val=copy[lang][key];
   if(val===undefined)throw Error("Missing UI copy "+key);
   return typeof val==="function"?val(...args):val;
 };
 function error(s){$("error").textContent=s||""}
 function notice(s){$("notice").textContent=s||""}
 function show(id){
   for(const p of ["entry","information","screening","registration",
                   "learning","finished","excluded","stop"])$(p).hidden=p!==id;
 }
 function visibility(...ids){
   for(const id of ["answer","continue","hint-next","submit-survey","next-session"])
     $(id).hidden=!ids.includes(id);
 }
 async function api(route,body={}){
   const res=await fetch("/study/api/"+route,{
     method:"POST",credentials:"same-origin",
     headers:{"Content-Type":"application/json","X-Study-Request":"1"},
     body:JSON.stringify(body),cache:"no-store",
   });
   let data={};
   try{data=await res.json()}catch(_){}
   if(!res.ok)throw Error((data.error||t("error")).slice(0,250));
   return data;
 }
 function updateLanguage(){
   document.documentElement.lang=lang;
   document.title=t("site");
   $("site-title").textContent=t("site");
   $("info-title").textContent=t("info");
   $("start-consent").textContent=t("begin");
   $("exclude-course").textContent=t("course");
   $("screen-title").textContent=t("screen");
   $("screen-explanation").textContent=t("nofeedback");
   $("reg-title").textContent=t("registration");
   $("reg-info").textContent=t("regInfo");
   $("age-label").textContent=t("age");
   $("program-label").textContent=t("program");
   $("register").textContent=t("register");
   $("phase").textContent=t("activity");
   $("reasoning-label").textContent=t("reasoning");
   $("answer").textContent=t("answer");
   $("continue").textContent=t("continue");
   $("submit-survey").textContent=t("survey");
   $("next-session").textContent=t("nextSession");
   $("refresh").textContent=t("refresh");
   $("finished-title").textContent=t("completed");
   $("stop-title").textContent=t("stop");
   $("stop-open").textContent=t("stop");
   $("stop-info").textContent=t("stopInfo");
   $("withdraw-keep").textContent=t("keep");
   $("withdraw-delete").textContent=t("erase");
   $("stop-cancel").textContent=t("cancel");
   $("language").value=lang;
   $("full-sheet").href="/study/info/"+lang;
   feedback();
 }
 function feedback(){
   const valid=typeof previous==="boolean",p=$("previous-result");
   p.hidden=!valid;
   p.className=valid?(previous?"correct":"incorrect"):"";
   $("previous-result-icon").textContent=!valid?"":previous?"✓":"✕";
   $("previous-result-text").textContent=!valid?"":t(previous?"correct":"incorrect");
 }
 function selectChoices(container,options,name){
   container.replaceChildren();
   const legend=document.createElement("legend");
   legend.textContent=t("choice");container.append(legend);
   for(const [key,text] of Object.entries(options)){
     const label=document.createElement("label"),input=document.createElement("input");
     input.type="radio";input.name=name;input.value=key;
     label.append(input,document.createTextNode(key+". "+text));
     container.append(label);
   }
 }
 function selected(name){
   const checked=document.querySelector('input[name="'+name+'"]:checked');
   if(!checked)throw Error(t("missing"));
   return checked.value;
 }
 async function info(){
   const result=await api("consent-copy",{language:lang});
   const r=await fetch("/study/info/"+lang,{cache:"no-store"});
   if(!r.ok)throw Error("Information sheet unavailable");
   const page=new DOMParser().parseFromString(await r.text(),"text/html");
   const content=page.querySelector("article pre, main pre, pre");
   if(!content)throw Error("Approved information sheet is missing");
   $("info-copy").replaceChildren();
   const pre=document.createElement("pre");
   pre.textContent=content.textContent;
   $("info-copy").append(pre);
   const field=$("consent-required");field.replaceChildren();
   const legend=document.createElement("legend");
   legend.textContent=t("required");field.append(legend);
   for(const text of result.required){
     const label=document.createElement("label"),check=document.createElement("input");
     check.type="checkbox";check.className="required";
     label.append(check,document.createTextNode(text));field.append(label);
   }
   const optional=$("consent-optional");optional.replaceChildren();
   const optLegend=document.createElement("legend");
   optLegend.textContent=t("optional");optional.append(optLegend);
   const label=document.createElement("label"),input=document.createElement("input");
   input.type="checkbox";input.id="optional-choice";
   label.append(input,document.createTextNode(result.optional));
   optional.append(label);
 }
 async function screen(){
   const response=await api("screening");
   screening=response.questions;screenIndex=0;answers={};
   if(screening.length!==8)throw Error("Expected eight screening questions");
   drawScreen();
 }
 function drawScreen(){
   show("screening");
   const q=screening[screenIndex];
   $("screen-number").textContent=t("questionNumber",screenIndex+1);
   $("screen-prompt").textContent=q.question_text;
   selectChoices($("screen-options"),q.options,"screen-choice");
   $("screen-next").textContent=screenIndex===7?t("finish"):t("next");
 }
 async function programs(){
   const resp=await api("programs");
   const selection=$("program");selection.replaceChildren();
   for(const v of resp.programs){
     const opt=document.createElement("option");
     opt.value=v;opt.textContent=v;selection.append(opt);
   }
 }
 function socratic(){
   const resource=current.resource;
   $("teaching").hidden=false;$("choices").hidden=true;
   $("teaching-title").textContent=resource.title;
   $("teaching-body").replaceChildren();
   const intro=document.createElement("p");intro.textContent=resource.intro;
   $("teaching-body").append(intro);
   $("reflection").hidden=false;
   $("guidance").textContent=t("hint",hintIndex+1,resource.prompts.length)+
     ": "+resource.prompts[hintIndex];
   $("reasoning").value="";
   $("hint-next").textContent=hintIndex===1?t("reveal"):t("hintNext");
   visibility("hint-next");
 }
 function renderItem(data){
   current=data;hintIndex=0;reflections=[];
   $("question").textContent="";
   $("teaching").hidden=true;$("reflection").hidden=true;
   $("choices").hidden=true;$("surveys").hidden=true;
   $("teaching-body").replaceChildren();
   visibility();
   if(data.kind==="question"){
     $("question").textContent=data.question_text;
     selectChoices($("choices"),data.options,"answer-choice");
     $("choices").hidden=false;visibility("answer");
   }else if(data.kind==="recovery"){
     if(data.action==="SOCRATIC_HINT"){
       if(!data.resource || data.resource.prompts?.length!==2)
         throw Error("Socratic content missing");
       $("question").textContent=data.resource.title;
       socratic();
     }else if(data.action==="DROP_2"){
       $("question").textContent="DROP_2 — "+data.question_text;
       selectChoices($("choices"),data.options,"answer-choice");
       $("choices").hidden=false;visibility("answer");
     }else if(["CONCEPT_SUMMARY","WORKED_EXAMPLE"].includes(data.action)){
       if(!data.resource || data.resource.paragraphs?.length<2)
         throw Error("Recovery content missing");
       $("question").textContent=data.resource.title;
       $("teaching").hidden=false;
       $("teaching-title").textContent=data.resource.title;
       for(const text of data.resource.paragraphs){
         const p=document.createElement("p");p.textContent=text;
         $("teaching-body").append(p);
       }
       visibility("continue");
     }else throw Error("Unknown recovery stage");
   }else if(data.kind==="survey"){
     $("question").textContent=t("fatigue");
     $("surveys").replaceChildren();$("surveys").hidden=false;
     for(let i=0;i<6;i++){
       const label=document.createElement("label");
       label.textContent=t("surveyItem",i+1);
       const input=document.createElement("select");input.id="fatigue-"+i;
       for(let k=1;k<=7;k++){
         const opt=document.createElement("option");
         opt.value=String(k);opt.textContent=String(k);input.append(opt);
       }
       label.append(input);$("surveys").append(label);
     }
     visibility("submit-survey");
   }else if(data.kind==="waiting_next_session"){
     $("question").textContent=t("waiting",data.scheduled_for);
     visibility("next-session");
   }else if(data.kind==="done"){
     $("question").textContent=t("completed");
   }else throw Error("Unexpected stage "+data.kind);
 }
 async function refresh(){
   if(busy)return;
   busy=true;error("");
   try{
     const status=await api("status");
     registered=status.stage==="participant";
     if(status.study_language||status.language){
       lang=status.study_language||status.language;updateLanguage();
     }
     if(status.stage==="invited"){
       await info();show("information");
     }else if(status.stage==="consented"){
       await screen();
     }else if(status.stage==="screened"){
       await programs();show("registration");
     }else if(registered){
       phase=status.phase;
       $("progress").textContent=t("progress",status.session,status.phase,status.index);
       if(status.phase==="DONE"){
         previous=null;feedback();
         const result=await api("debrief");
         $("debrief").textContent=result.text;show("finished");
       }else{
         if(!["QUIZ","SURVEY"].includes(status.phase))previous=null;
         feedback();
         renderItem(await api("item"));
         show("learning");
       }
     }else show("entry");
   }catch(e){error(e.message);show("entry")}
   finally{busy=false}
 }
 async function act(route,payload={},onDone=null){
   if(busy)return;
   busy=true;error("");notice("");
   try{
     const resp=await api(route,payload);
     if(onDone)onDone(resp);
   }catch(e){error(e.message);busy=false;return}
   busy=false;await refresh();
 }
 $("start-consent").addEventListener("click",()=>{
   const checks=[...$("consent-required").querySelectorAll("input.required")].map(x=>x.checked);
   act("consent",{checks,optional:$("optional-choice").checked,language:lang});
 });
 $("exclude-course").addEventListener("click",()=>{
   act("course-exclusion",{},()=>{show("excluded")});
 });
 $("screen-next").addEventListener("click",async()=>{
   try{
     const q=screening[screenIndex];
     answers[q.question_id]=selected("screen-choice");
     if(screenIndex<7){screenIndex++;drawScreen();return}
     await act("screen",{answers},r=>{if(!r.eligible)show("excluded")});
   }catch(e){error(e.message)}
 });
 $("register").addEventListener("click",()=>{
   act("register",{age:Number($("age").value),program:$("program").value});
 });
 $("language").addEventListener("change",async()=>{
   const desired=$("language").value;
   try{
     if(registered){
       await api("language",{language:desired});
       lang=desired;updateLanguage();await refresh();
     }else if(phase===null){
       lang=desired;updateLanguage();await refresh();
     }else{
       lang=desired;updateLanguage();
     }
   }catch(e){error(e.message);$("language").value=lang}
 });
 function reply(choice,reflection=null){
   return act("answer",{
     render_id:current.render_id,
     request_id:"submit_"+crypto.randomUUID().replaceAll("-",""),
     question_id:current.question_id||null,
     choice,reflection,
   },resp=>{
     previous=typeof resp.previous_correct==="boolean"?resp.previous_correct:null;
   });
 }
 $("answer").addEventListener("click",()=>{
   try{reply(selected("answer-choice"))}catch(e){error(e.message)}
 });
 $("continue").addEventListener("click",()=>reply(null));
 $("hint-next").addEventListener("click",()=>{
   const value=$("reasoning").value.trim();
   if(!value){error(t("reasonMissing"));return}
   reflections.push(value);
   hintIndex++;
   if(hintIndex<2){socratic();return}
   $("reflection").hidden=true;
   $("teaching").hidden=true;
   $("question").textContent=t("reattempt")+" "+current.question_text;
   selectChoices($("choices"),current.options,"answer-choice");
   $("choices").hidden=false;visibility("answer");
   $("answer").onclick=null;
   // Avoid modifying callback identity; reply() takes the two reflections.
   $("answer").dataset.socratic="1";
 });
 $("answer").addEventListener("click",()=>{
   // The normal answer listener uses this flag to submit both reflections.
 });
 $("submit-survey").addEventListener("click",()=>{
   const values=Array.from({length:6},(_,i)=>Number($("fatigue-"+i).value));
   act("survey",{render_id:current.render_id,request_id:"survey_"+crypto.randomUUID().replaceAll("-",""),values},
       ()=>{previous=null});
 });
 $("next-session").addEventListener("click",()=>act("next-session"));
 $("refresh").addEventListener("click",refresh);
 $("stop-open").addEventListener("click",()=>{if(registered)show("stop")});
 $("stop-cancel").addEventListener("click",refresh);
 const withdraw=deleteData=>{
   if(!window.confirm(lang==="fr"?"Confirmer l'arrêt de la participation ?":
                     "Confirm that you want to stop participating?"))return;
   act("withdraw",{delete:deleteData},()=>{
     previous=null;show("excluded");notice(t("confirmed"));
   });
 };
 $("withdraw-keep").addEventListener("click",()=>withdraw(false));
 $("withdraw-delete").addEventListener("click",()=>withdraw(true));
 async function initial(){
   updateLanguage();
   const params=new URLSearchParams(window.location.hash.slice(1));
   const token=params.get("invite");
   if(token){
     try{
       await api("exchange",{token});
       history.replaceState(null,"",location.pathname+location.search);
     }catch(e){error(e.message);show("entry");return}
   }
   await refresh();
 }
 initial().catch(e=>{error(e.message);show("entry")});
})();

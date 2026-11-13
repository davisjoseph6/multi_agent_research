"use strict";
(()=>{
 const $=id=>document.getElementById(id);
 let lang="en",current=null,screening=[],screenIndex=0,answers={};
 let hintIndex=0,reflections=[],previous=null,phase=null,busy=false,registered=false;
 let activeSession=1,quizIndex=0,surveyStep=0,surveyValues=Array(6).fill(4),surveySeen=false;
 let lastFeedback=null;
 const copy={
  en:{
   site:"Adaptive Learning Study",info:"Information and consent",
   roadmap:"Four study activities: pre-test (session 1), learning quiz (sessions 1–3), post-test (session 3), and fatigue questionnaire (sessions 1–3). Eligibility screening comes before registration.",
   aiRule:"Please answer independently. Do not use generative AI tools to solve the questions.",
   ageInfo:"Only adults may participate. Select an age from 18 to 99.",
   programInfo:"Your academic program describes the study sample; it does not determine your experimental group.",
   feedbackNext:"Next question",fatigueNext:"Next fatigue question",
   correctAnswer:"Correct answer",why:"Explanation",explanationEnglish:"Bank explanation (English)",
   quizIntro:"Learning quiz — you will see feedback after each answer.",
   preIntro:"Pre-test — answer 16 questions. Correctness feedback is not shown here.",
   postIntro:"Post-test — answer 16 questions. Correctness feedback is not shown here.",
   surveyIntro:"Fatigue questionnaire — rate the quiz you just completed; there are no right or wrong answers.",
   fatigueCount:i=>"Fatigue question "+i+" of 6",
   sessionSummary:s=>"Session "+s+" result",
   correctCount:(a,b)=>"Regular quiz score: "+a+" of "+b+" correct",
   timeAnswer:s=>"Time answering scored questions: "+s+" seconds",
   timeElapsed:s=>"Elapsed session time (including breaks): "+s+" seconds",
   fatigueQuestions:[
    ["Mental demand. How mentally demanding was the quiz?","Very low","Very high"],
    ["Physical demand. How physically demanding was the quiz?","Very low","Very high"],
    ["Time pressure. How hurried or rushed did you feel?","Very low","Very high"],
    ["Performance. How successful were you in doing what you were asked to do?","Perfect","Failure"],
    ["Effort. How hard did you have to work to reach your level of performance?","Very low","Very high"],
    ["Frustration. How insecure, discouraged, irritated or stressed did you feel?","Very low","Very high"],
   ],
   begin:"I agree and continue",course:"I previously took an economics course",
   screen:"Eligibility screening",next:"Next",finish:"Finish screening",
   nofeedback:"No correctness feedback is provided for screening.",
   registration:"Registration",regInfo:"Your invitation verified your email address. No name is requested.",
   age:"Age",program:"Academic program",register:"Register and start session 1",
   activity:"Current activity",choice:"Choose one answer",
   reasoning:"Your own reasoning",answer:"Submit answer",continue:"Continue",
   hintNext:"Next guiding question",survey:"Submit six ratings",
   nextSession:"Begin next scheduled session",refresh:"Refresh current activity",
   testNextSession:"TEST ONLY — start next session now",
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
   waiting:date=>"Next scheduled visit: "+date+" (Paris time; no early entry).",
   noInvite:"Open the invitation link sent by the study coordinator.",
   confirmed:"Your participation has ended.",
   error:"The request could not be completed.",
   progress:(s,p,i)=>"Session "+s+"/3 — "+p+" — step "+i,
   noStudy:"No active study invitation.",
   reveal:"Show original question",
  },
  fr:{
   site:"Étude sur l'apprentissage adaptatif",info:"Information et consentement",
   roadmap:"Quatre activités : pré-test (séance 1), quiz d’apprentissage (séances 1 à 3), post-test (séance 3) et questionnaire de fatigue (séances 1 à 3). La présélection précède l’inscription.",
   aiRule:"Répondez de façon autonome. N'utilisez pas d'outils d'IA générative pour résoudre les questions.",
   ageInfo:"Seuls les adultes peuvent participer. Choisissez un âge entre 18 et 99 ans.",
   programInfo:"Votre formation sert à décrire l'échantillon ; elle ne détermine pas le groupe expérimental.",
   feedbackNext:"Question suivante",fatigueNext:"Question de fatigue suivante",
   correctAnswer:"Bonne réponse",why:"Explication",explanationEnglish:"Explication de la banque (en anglais)",
   quizIntro:"Quiz d’apprentissage — une explication apparaîtra après chaque réponse.",
   preIntro:"Pré-test — 16 questions, sans indication de justesse des réponses.",
   postIntro:"Post-test — 16 questions, sans indication de justesse des réponses.",
   surveyIntro:"Questionnaire de fatigue — évaluez le quiz terminé ; il n’y a ni bonne ni mauvaise réponse.",
   fatigueCount:i=>"Question de fatigue "+i+" sur 6",
   sessionSummary:s=>"Résultat de la séance "+s,
   correctCount:(a,b)=>"Score du quiz ordinaire : "+a+" bonnes réponses sur "+b,
   timeAnswer:s=>"Temps de réponse aux questions notées : "+s+" secondes",
   timeElapsed:s=>"Durée totale de la séance (pauses incluses) : "+s+" secondes",
   fatigueQuestions:[
    ["Exigence mentale. Le quiz vous a-t-il demandé beaucoup d'effort mental ?","Très faible","Très élevée"],
    ["Exigence physique. Le quiz vous a-t-il demandé beaucoup d'effort physique ?","Très faible","Très élevée"],
    ["Pression temporelle. Vous êtes-vous senti pressé ou bousculé ?","Très faible","Très élevée"],
    ["Performance. Dans quelle mesure avez-vous réussi les tâches proposées ?","Parfaite","Échec"],
    ["Effort. Quelle quantité de travail a été nécessaire pour votre performance ?","Très faible","Très élevée"],
    ["Frustration. Vous êtes-vous senti inquiet, découragé, irrité ou stressé ?","Très faible","Très élevée"],
   ],
   begin:"J'accepte et je continue",course:"J'ai déjà suivi un cours d'économie",
   screen:"Test de présélection",next:"Suivant",finish:"Terminer la présélection",
   nofeedback:"La présélection ne donne aucune indication de justesse.",
   registration:"Inscription",regInfo:"Votre invitation a confirmé votre adresse. Aucun nom n'est demandé.",
   age:"Âge",program:"Formation",register:"S'inscrire et commencer la séance 1",
   activity:"Activité en cours",choice:"Choisissez une réponse",
   reasoning:"Votre raisonnement",answer:"Valider la réponse",continue:"Continuer",
   hintNext:"Question guidée suivante",survey:"Envoyer les six évaluations",
   nextSession:"Commencer la prochaine séance prévue",refresh:"Actualiser l'activité",
   testNextSession:"TEST UNIQUEMENT — commencer la séance suivante maintenant",
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
   waiting:date=>"Séance suivante prévue : "+date+" (heure de Paris ; accès anticipé impossible).",
   noInvite:"Ouvrez le lien d'invitation envoyé par le responsable de l'étude.",
   confirmed:"Votre participation est terminée.",
   error:"La demande n'a pas pu être traitée.",
   progress:(s,p,i)=>"Séance "+s+"/3 — "+p+" — étape "+i,
   noStudy:"Aucune invitation active.",
   reveal:"Afficher la question d'origine",
  }
 };
 const studyParts=["PRETEST","QUIZ","POSTTEST","SURVEY"];
 const partNames={
  en:["Pre-test (session 1)","Learning quiz (sessions 1–3)",
      "Post-test (session 3)","Fatigue questionnaire (sessions 1–3)"],
  fr:["Pré-test (séance 1)","Quiz d’apprentissage (séances 1–3)",
      "Post-test (séance 3)","Questionnaire de fatigue (séances 1–3)"],
 };
 function updateStudyParts(stage,session){
  const list=$("session-parts");
  if(!list)return;
  list.hidden=false;
  list.setAttribute("aria-label",lang==="fr"?
    "Quatre activités réparties sur trois séances":
    "Four study activities across three sessions");
  // The post-test is in session 3 only. The pre-test is in session 1 only.
  // Fatigue occurs after each session's quiz, not after a session-1 post-test.
  const sequence=session===1?["PRETEST","QUIZ","SURVEY"]:
                 session===2?["QUIZ","SURVEY"]:
                 ["QUIZ","POSTTEST","SURVEY"];
  const index=sequence.indexOf(stage);
  const finished=stage==="WAITING_NEXT_SESSION"||stage==="DONE";
  for(const [position,item] of [...list.children].entries()){
   const part=studyParts[position];
   item.textContent=(position+1)+". "+partNames[lang][position];
   let state;
   if(part==="PRETEST"&&session>1)state="complete";
   else if(part==="POSTTEST"&&session<3)state="later";
   else if(finished)state="complete";
   else if(part===stage)state="active";
   else state=sequence.indexOf(part)<index?"complete":"upcoming";
   item.className=state;
   if(state==="active")item.setAttribute("aria-current","step");
   else item.removeAttribute("aria-current");
  }
 }
 function parisVisit(value){
  // Render the API's UTC instant in Paris, independent of browser location.
  const date=new Date(value);
  if(!Number.isFinite(date.getTime()))
   return lang==="fr"?"date indisponible":"date unavailable";
  return new Intl.DateTimeFormat(lang==="fr"?"fr-FR":"en-GB",{
   timeZone:"Europe/Paris",weekday:"long",day:"numeric",
   month:"long",year:"numeric",hour:"2-digit",minute:"2-digit",
   hourCycle:"h23",
  }).format(date);
 }
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
   for(const id of ["answer","continue","hint-next","submit-survey","next-session","staging-next-session","feedback-next","fatigue-next"])
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
   $("study-roadmap").textContent=t("roadmap");
   if(registered && phase)updateStudyParts(phase,activeSession);
   $("ai-rule").textContent=t("aiRule");
   $("age-info").textContent=t("ageInfo");
   $("program-info").textContent=t("programInfo");
   $("feedback-next").textContent=t("feedbackNext");
   $("fatigue-next").textContent=t("fatigueNext");
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
   $("staging-next-session").textContent=t("testNextSession");
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
   const content=page.querySelector("main");
   if(!content)throw Error("Information sheet is missing");
   $("info-copy").replaceChildren();
   // Trusted same-origin, version-controlled sheet: keep semantic headings,
   // paragraph spacing, bold words and links instead of printing raw Markdown.
   for(const element of content.children){
     if(["H1","H2","H3","P","SECTION","UL","OL","PRE","A"].includes(element.tagName))
       $("info-copy").append(document.importNode(element,true));
   }
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
 async function screen(preserve=false){
   // The server translates only the displayed wording. Question identifiers,
   // answer letters and signed consent remain unchanged.
   const priorId=screening[screenIndex]?.question_id;
   const priorChoice=document.querySelector('#screen-options input[name="screen-choice"]:checked')?.value;
   const response=await api("screening",{language:lang});
   const questions=response.questions;
   if(questions.length!==8)throw Error("Expected eight screening questions");
   if(preserve){
     if(screening.length!==8 || questions.some((q,i)=>
       q.question_id!==screening[i].question_id) ||
       questions[screenIndex].question_id!==priorId)
       throw Error("Screening question identity changed during translation");
   }else{
     screenIndex=0;answers={};
   }
   screening=questions;
   drawScreen();
   if(preserve && priorChoice){
     const option=$("screen-options").querySelector('input[value="'+priorChoice+'"]');
     if(option)option.checked=true;
   }
 }
 function drawScreen(){
   show("screening");
   const q=screening[screenIndex];
   $("screen-number").textContent=t("questionNumber",screenIndex+1);
   $("screen-meter").value=screenIndex+1;
   $("screen-prompt").textContent=q.question_text;
   selectChoices($("screen-options"),q.options,"screen-choice");
   $("screen-next").textContent=screenIndex===7?t("finish"):t("next");
 }
 async function programs(){
   const ages=$("age");ages.replaceChildren();
   const prompt=document.createElement("option");prompt.value="";
   prompt.textContent=lang==="fr"?"Choisissez un âge (18–99)":"Choose an age (18–99)";
   ages.append(prompt);
   for(let n=18;n<=99;n++){
     const option=document.createElement("option");
     option.value=String(n);option.textContent=String(n);ages.append(option);
   }
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
 function showSurveyQuestion(){
   const item=t("fatigueQuestions")[surveyStep];
   const panel=$("surveys");panel.replaceChildren();panel.hidden=false;
   const heading=document.createElement("h3");
   heading.textContent=t("fatigueCount",surveyStep+1);
   const question=document.createElement("p");question.textContent=item[0];
   const control=document.createElement("div");control.className="scale";
   const low=document.createElement("span"),high=document.createElement("span");
   low.textContent="1 — "+item[1];high.textContent="7 — "+item[2];
   const input=document.createElement("input");
   input.type="range";input.min="1";input.max="7";input.step="1";
   input.value=String(surveyValues[surveyStep]);
   input.id="fatigue-"+surveyStep;
   input.setAttribute("aria-label",item[0]);
   const output=document.createElement("output");
   output.htmlFor=input.id;
   output.textContent=String(surveyValues[surveyStep]);
   input.addEventListener("input",()=>{
     surveyValues[surveyStep]=Number(input.value);
     output.textContent=input.value;
   });
   control.append(low,input,high,output);
   panel.append(heading,question,control);
   $("progress").textContent=(lang==="fr"?
     "Séance "+activeSession+"/3 — Questionnaire de fatigue — ":
     "Session "+activeSession+"/3 — Fatigue questionnaire — ")+t("fatigueCount",surveyStep+1);
   $("phase-meter").hidden=false;$("phase-meter").max=6;
   $("phase-meter").value=surveyStep+1;
   $("phase-intro").textContent=t("surveyIntro");
   visibility(surveyStep===5?"submit-survey":"fatigue-next");
 }
 function renderItem(data){
   current=data;hintIndex=0;reflections=[];
   $("answer-feedback").hidden=true;
   $("session-summary").hidden=true;
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
     if(!surveySeen){
       surveySeen=true;surveyStep=0;surveyValues=Array(6).fill(4);
     }
     showSurveyQuestion();
   }else if(data.kind==="waiting_next_session"){
     $("question").textContent=t("waiting",parisVisit(data.scheduled_for));
     visibility($("mode-warning").hidden?"next-session":"staging-next-session");
   }else if(data.kind==="done"){
     $("question").textContent=t("completed");
   }else throw Error("Unexpected stage "+data.kind);
 }
 function showSocraticReattempt(){
   $("reflection").hidden=true;
   $("teaching").hidden=true;
   $("question").textContent=t("reattempt")+" "+current.question_text;
   selectChoices($("choices"),current.options,"answer-choice");
   $("choices").hidden=false;
   visibility("answer");
 }
 function itemDraft(){
   if(!current)return null;
   return {
     kind:current.kind,action:current.action,
     questionId:current.question_id,renderId:current.render_id,
     selected:document.querySelector('#choices input[name="answer-choice"]:checked')?.value,
     hintIndex,reflections:reflections.slice(),
     reasoning:$("reasoning").value,
     surveyStep,surveyValues:surveyValues.slice(),surveySeen,
   };
 }
 function renderKeepingDraft(data){
   const saved=itemDraft();
   const same=Boolean(saved && saved.renderId && data.render_id===saved.renderId &&
     data.kind===saved.kind && data.action===saved.action &&
     data.question_id===saved.questionId);
   renderItem(data);
   if(!same)return;
   if(data.kind==="recovery"&&data.action==="SOCRATIC_HINT"){
     hintIndex=saved.hintIndex;reflections=saved.reflections.slice();
     if(hintIndex>=2)showSocraticReattempt();
     else{
       socratic();
       $("reasoning").value=saved.reasoning;
     }
   }
   if(data.kind==="survey"){
     surveyStep=saved.surveyStep;
     surveyValues=saved.surveyValues.slice();
     surveySeen=saved.surveySeen;
     showSurveyQuestion();
   }
   if(saved.selected){
     const option=$("choices").querySelector('input[name="answer-choice"][value="'+saved.selected+'"]');
     if(option)option.checked=true;
   }
 }
 function showProgress(status,data){
   updateStudyParts(status.phase,status.session);
   if(data.kind==="survey")return;
   const meter=$("phase-meter"),tip=$("phase-intro");
   meter.hidden=false;
   if(status.phase==="PRETEST" || status.phase==="POSTTEST" ||
      status.phase==="QUIZ"){
     const total=status.phase==="QUIZ"?(status.session===3?15:20):16;
     meter.max=total;
     meter.value=Math.min(total,status.index+1);
     if(data.kind==="recovery"){
       // Recovery happens BETWEEN ordinary quiz questions, not as a new Q.
       $("progress").textContent=lang==="fr"?
         "Séance "+status.session+"/3 — Quiz d’apprentissage — aide pédagogique (sans numéro)":
         "Session "+status.session+"/3 — Learning quiz — learning support (unnumbered)";
       meter.hidden=true;
     }else{
       $("progress").textContent=lang==="fr"?
         "Séance "+status.session+"/3 — "+partNames[lang][studyParts.indexOf(status.phase)]+" — question "+(status.index+1)+" sur "+total:
         "Session "+status.session+"/3 — "+partNames[lang][studyParts.indexOf(status.phase)]+" — Question "+(status.index+1)+" of "+total;
     }
     tip.textContent=t(status.phase==="PRETEST"?"preIntro":
                       status.phase==="POSTTEST"?"postIntro":"quizIntro");
   }else{
     meter.hidden=true;
     $("progress").textContent=lang==="fr"?
       "Séance "+status.session+"/3 terminée":
       "Session "+status.session+"/3 completed";
     tip.textContent=lang==="fr"?
       "Le questionnaire est terminé. Résultats du quiz ci-dessous.":
       "The questionnaire is complete. Quiz results appear below.";
   }
 }
 function showAnswerFeedback(resp,chosen){
   lastFeedback={response:resp,chosen};
   if(!["A","B","C","D"].includes(resp.correct_choice))
     throw Error("Server did not return authorized post-answer feedback");
   const panel=$("answer-feedback");panel.hidden=false;
   panel.className="feedback "+(resp.previous_correct?"correct":"incorrect");
   $("feedback-title").textContent=resp.previous_correct?
     (lang==="fr"?"Bonne réponse":"Correct"):
     (lang==="fr"?"Réponse incorrecte":"Incorrect");
   const answerText=current.options[resp.correct_choice];
   $("feedback-answer").textContent=t("correctAnswer")+": "+
     resp.correct_choice+". "+(answerText||"");
   $("feedback-explanation").textContent=t(resp.explanation_language===lang?
     "why":"explanationEnglish")+": "+(resp.explanation||"");
   for(const label of $("choices").querySelectorAll("label")){
     const input=label.querySelector("input");
     if(!input)continue;
     input.disabled=true;
     if(input.value===resp.correct_choice)label.classList.add("correct-option");
     else if(input.value===chosen&&!resp.previous_correct)
       label.classList.add("incorrect-option");
   }
   $("previous-result").hidden=true;
   visibility("feedback-next");
   panel.scrollIntoView({behavior:"smooth",block:"nearest"});
 }
 async function showCompletedSummary(id){
   const node=$(id);node.replaceChildren();
   const results=await api("session-summary");
   if(!results.sessions?.length){node.hidden=true;return}
   node.hidden=false;
   for(const row of results.sessions){
     const section=document.createElement("section");
     const h=document.createElement("h3");h.textContent=t("sessionSummary",row.session);
     const score=document.createElement("p");
     score.textContent=t("correctCount",row.quiz_correct,row.quiz_questions)+
       " ("+row.quiz_percentage+"%)";
     const answered=document.createElement("p");
     answered.textContent=t("timeAnswer",row.question_answer_seconds);
     const elapsed=document.createElement("p");
     elapsed.textContent=t("timeElapsed",row.elapsed_seconds);
     section.append(h,score,answered,elapsed);node.append(section);
   }
 }
 async function refresh(){
   if(busy)return;
   busy=true;error("");
   try{
     const status=await api("status");
     registered=status.stage==="participant";
     // A screening translation does NOT alter the signed consent locale.
     // Do not force the consent language back onto an active screening page.
     if(status.stage==="participant"&&status.study_language){
       lang=status.study_language;updateLanguage();
     }else if(status.stage==="consented"&&!screening.length&&status.language){
       lang=status.language;updateLanguage();
     }
     if(status.stage==="invited"){
       await info();show("information");
     }else if(status.stage==="consented"){
       await screen();
     }else if(status.stage==="screened"){
       await programs();show("registration");
     }else if(registered){
       phase=status.phase;activeSession=status.session;quizIndex=status.index;
       previous=null;feedback();
       if(status.phase==="DONE"){
         surveySeen=false;
         const result=await api("debrief");
         $("debrief").textContent=result.text;show("finished");
         await showCompletedSummary("finished-summary");
       }else{
         if(status.phase!=="SURVEY")surveySeen=false;
         const item=await api("item");
         renderKeepingDraft(item);
         showProgress(status,item);
         show("learning");
         if(status.phase==="WAITING_NEXT_SESSION")
           await showCompletedSummary("session-summary");
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
     if(onDone)await onDone(resp);
   }catch(e){error(e.message);busy=false;return}
   busy=false;await refresh();
 }
 $("start-consent").addEventListener("click",()=>{
   const checks=[...$("consent-required").querySelectorAll("input.required")].map(x=>x.checked);
   act("consent",{checks,optional:$("optional-choice").checked,language:lang});
 });
 $("exclude-course").addEventListener("click",async()=>{
   try{
     await api("course-exclusion");
     registered=false;show("excluded");notice(t("confirmed"));error("");
   }catch(e){error(e.message)}
 });
 $("screen-next").addEventListener("click",async()=>{
   try{
     const q=screening[screenIndex];
     answers[q.question_id]=selected("screen-choice");
     if(screenIndex<7){screenIndex++;drawScreen();return}
     const result=await api("screen",{answers});
     if(!result.eligible){
       show("excluded");notice(t("confirmed"));
     }else{
       await refresh();
     }
   }catch(e){error(e.message)}
 });
 $("register").addEventListener("click",()=>{
   const age=Number($("age").value);
   if(!Number.isInteger(age)||age<18||age>99){
     error(lang==="fr"?"Choisissez un âge entre 18 et 99.":"Select an age from 18 to 99.");
     return;
   }
   act("register",{age,program:$("program").value},
       async()=>{await api("language",{language:lang})});
 });
 async function changeLanguage(desired){
   if(desired!=="en"&&desired!=="fr")throw Error("Invalid display language");
   if(desired===lang)return;
   const original=lang;
   let serverChanged=false;
   try{
     if(registered){
       // Server owns the language of subsequent answers/events; this does
       // not submit, skip or repeat any scored question or hint.
       await api("language",{language:desired});
       serverChanged=true;
       lang=desired;updateLanguage();
       if(!$("learning").hidden){
         if(!$("answer-feedback").hidden && lastFeedback){
           // The answer is ALREADY committed: /item now points to the NEXT
           // question. Never fetch it before the learner presses Next.
           showAnswerFeedback(lastFeedback.response,lastFeedback.chosen);
         }else{
           const item=await api("item");
           renderKeepingDraft(item);
           showProgress({phase,session:activeSession,index:quizIndex},item);
           if(phase==="WAITING_NEXT_SESSION")await showCompletedSummary("session-summary");
         }
       }else if(!$("finished").hidden){
         await showCompletedSummary("finished-summary");
       }
     }else if(!$("screening").hidden){
       lang=desired;updateLanguage();
       await screen(true);
     }else if(!$("information").hidden){
       const checks=[...$("consent-required").querySelectorAll("input.required")].map(x=>x.checked);
       const optional=$("optional-choice")?.checked||false;
       lang=desired;updateLanguage();
       await info();
       const required=[...$("consent-required").querySelectorAll("input.required")];
       if(required.length===checks.length){
         required.forEach((box,i)=>box.checked=checks[i]);
       }
       $("optional-choice").checked=optional;
     }else{
       // Registration is still local UI state. Preserve age and program.
       lang=desired;updateLanguage();
       if(!$("registration").hidden){
         const label=$("age").querySelector('option[value=""]');
         if(label)label.textContent=lang==="fr"?
           "Choisissez un âge (18–99)":"Choose an age (18–99)";
       }
     }
   }catch(e){
     // A successful /language request is authoritative: do not lie about
     // the server locale if the subsequent local render failed.
     if(!serverChanged){
       lang=original;updateLanguage();
     }
     error(e.message);
   }
 }
 $("language").addEventListener("change",async()=>{
   if(busy){$("language").value=lang;return}
   const desired=$("language").value;
   busy=true;error("");
   try{await changeLanguage(desired)}
   finally{busy=false}
 });
 async function reply(choice,reflection=null){
   if(busy)return;
   busy=true;error("");notice("");
   try{
     const resp=await api("answer",{
       render_id:current.render_id,
       request_id:"submit_"+crypto.randomUUID().replaceAll("-",""),
       question_id:current.question_id||null,
       choice,reflection,
     });
     if(resp.feedback_phase==="QUIZ"&&typeof resp.previous_correct==="boolean"){
       showAnswerFeedback(resp,choice);
       busy=false;return;
     }
   }catch(e){busy=false;error(e.message);return}
   busy=false;await refresh();
 }
 $("answer").addEventListener("click",()=>{
   try{
     const reflection=current?.action==="SOCRATIC_HINT"?reflections:null;
     if(current?.action==="SOCRATIC_HINT"&&reflection?.length!==2)
       throw Error(t("reasonMissing"));
     reply(selected("answer-choice"),reflection);
   }catch(e){error(e.message)}
 });
 $("continue").addEventListener("click",()=>reply(null));
 $("hint-next").addEventListener("click",()=>{
   const value=$("reasoning").value.trim();
   if(!value){error(t("reasonMissing"));return}
   reflections.push(value);
   hintIndex++;
   if(hintIndex<2){socratic();return}
   showSocraticReattempt();
   // The main answer handler submits the two typed reflections alongside
   // the graded four-option re-attempt. No answer is revealed before then.
 });
 $("fatigue-next").addEventListener("click",()=>{
   surveyStep++;
   if(surveyStep>=6)return;
   showSurveyQuestion();
 });
 $("submit-survey").addEventListener("click",()=>{
   if(surveyStep!==5)return;
   act("survey",{render_id:current.render_id,
       request_id:"survey_"+crypto.randomUUID().replaceAll("-"),
       values:surveyValues.slice()},
       ()=>{previous=null;surveySeen=false});
 });
 $("feedback-next").addEventListener("click",refresh);
 $("next-session").addEventListener("click",()=>act("next-session"));
 $("staging-next-session").addEventListener("click",()=>{
   if(!$("mode-warning").hidden)act("staging-next-session");
 });
 $("refresh").addEventListener("click",refresh);
 $("stop-open").addEventListener("click",()=>{if(registered)show("stop")});
 $("stop-cancel").addEventListener("click",refresh);
 const withdraw=deleteData=>{
   if(!window.confirm(lang==="fr"?"Confirmer l'arrêt de la participation ?":
                     "Confirm that you want to stop participating?"))return;
   (async()=>{
     try{
       await api("withdraw",{delete:deleteData});
       registered=false;previous=null;feedback();
       show("excluded");notice(t("confirmed"));error("");
     }catch(e){error(e.message)}
   })();
 };
 $("withdraw-keep").addEventListener("click",()=>withdraw(false));
 $("withdraw-delete").addEventListener("click",()=>withdraw(true));
 async function initial(){
   const logo=$("school-logo"),fallback=$("school-wordmark");
   const loaded=()=>{logo.hidden=false;fallback.hidden=true};
   logo.addEventListener("load",loaded);
   logo.addEventListener("error",()=>{logo.hidden=true;fallback.hidden=false});
   if(logo.complete&&logo.naturalWidth>0)loaded();
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

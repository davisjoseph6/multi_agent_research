"use strict";
(()=>{
 const el=id=>document.getElementById(id);
 const group=location.pathname.endsWith("/school")?"school":"external";
 const messages={
  en:{
   eyebrow:"Learn. Explore. Have fun.",
   title:"Ready to explore how you learn?",
   sub:"Take a quick step toward our adaptive-learning study. This is an interest form, not an exam or registration.",
   encourageTitle:"Your curiosity is what counts!",
   encourage:"Your quiz answers are not graded by how many you get right. What matters is taking part and completing the activities. Enjoy discovering something new!",
   noAi:"Please try the learning activities independently, without generative AI tools such as ChatGPT, so the results reflect your own thinking.",
   step:"A QUICK INTRODUCTION",formTitle:"Tell us how to reach you",
   group:group==="school"?"For institutional student email addresses.":"For personal or other external email addresses.",
   emailLabel:"Your email address *",firstLabel:"First name (optional)",lastLabel:"Family name (optional)",
   emailHint:"Use the exact address authorized for this rehearsal. No student password is needed.",
   ackLabel:"I understand this is only a private software test using draft information, not approved research participation or consent.",
   submit:"Submit my interest",
   footer:"No emails are sent by this private test. The supervisor distributes the real questionnaire personally; invitations are separate.",
   qaWarning:"PRIVATE QA ONLY — NOT real research enrollment or valid research consent.",
   received:"Thank you! Your QA application was saved. A researcher can now review it.",
   rejected:"The QA application could not be accepted. Check the permitted email and questionnaire type."
  },
  fr:{
   eyebrow:"Apprenez. Explorez. Amusez-vous !",
   title:"Prêt(e) à découvrir votre façon d'apprendre ?",
   sub:"Un premier pas vers notre étude sur l'apprentissage adaptatif. Il s'agit d'une manifestation d'intérêt, pas d'un examen ni d'une inscription.",
   encourageTitle:"C'est votre curiosité qui compte !",
   encourage:"Vos réponses au quiz ne sont pas notées selon le nombre de bonnes réponses. L'essentiel est de participer et de terminer les activités. Amusez-vous !",
   noAi:"Essayez de réaliser les activités par vous-même, sans outils d'IA générative comme ChatGPT, afin que les résultats reflètent votre propre raisonnement.",
   step:"PRÉSENTATION RAPIDE",formTitle:"Comment pouvons-nous vous contacter ?",
   group:group==="school"?"Pour les adresses e-mail étudiantes de l'établissement.":"Pour les adresses e-mail personnelles ou externes.",
   emailLabel:"Votre adresse e-mail *",firstLabel:"Prénom (facultatif)",lastLabel:"Nom de famille (facultatif)",
   emailHint:"Utilisez l'adresse autorisée pour cette répétition. Aucun mot de passe étudiant n'est nécessaire.",
   ackLabel:"Je comprends qu'il s'agit uniquement d'un essai privé du logiciel avec des informations provisoires, et non d'une participation ni d'un consentement approuvés.",
   submit:"Envoyer ma candidature",
   footer:"Ce test privé n'envoie aucun e-mail. Le responsable distribue personnellement le véritable questionnaire ; les invitations sont distinctes.",
   qaWarning:"TEST PRIVÉ UNIQUEMENT — ni inscription réelle à la recherche ni consentement valable.",
   received:"Merci ! Votre candidature d'essai est enregistrée. Un chercheur peut maintenant l'examiner.",
   rejected:"La candidature d'essai a été refusée. Vérifiez l'adresse autorisée et le type de questionnaire."
  }
 };
 const idMap={eyebrow:"eyebrow",title:"title",sub:"sub",encourageTitle:"encourage-title",
  encourage:"encourage",noAi:"no-ai-note",step:"step",formTitle:"form-title",group:"group",
  emailLabel:"email-label",firstLabel:"first-label",lastLabel:"last-label",
  emailHint:"email-hint",ackLabel:"ack-label",submit:"submit",footer:"footer",qaWarning:"qa-warning"};
 function current(){return el("language").value==="fr"?"fr":"en"}
 function redraw(){
  const lang=current();document.documentElement.lang=lang;
  const copy=messages[lang];
  for(const [key,id] of Object.entries(idMap))el(id).textContent=copy[key];
 }
 el("language").addEventListener("change",redraw);
 el("interest-form").addEventListener("submit",async event=>{
  event.preventDefault();const lang=current();const button=el("submit");
  el("status").textContent="";button.disabled=true;
  const payload={email:el("email").value,first_name:el("first-name").value,
   last_name:el("last-name").value,language:lang,questionnaire:group,
   qa_acknowledged:el("ack").checked};
  try{
   const response=await fetch("/interest/api/apply",{method:"POST",
    credentials:"same-origin",cache:"no-store",
    headers:{"Content-Type":"application/json","X-Study-Request":"1"},
    body:JSON.stringify(payload)});
   if(!response.ok)throw Error("rejected");
   el("status").textContent=messages[lang].received;
  }catch(_){el("status").textContent=messages[lang].rejected}
  finally{button.disabled=false}
 });
 redraw();
})();

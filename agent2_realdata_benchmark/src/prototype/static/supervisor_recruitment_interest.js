"use strict";
(()=>{
 const $=id=>document.getElementById(id);
 const type=location.pathname.endsWith("/school")?"school":"external";
 const copy={
  en:{
   eyebrow:"Learn. Explore. Have fun.",
   title:"Curious about how you learn?",
   sub:"Share your interest in our adaptive-learning study. This is an invitation to learn, not an exam or an enrollment.",
   encourageTitle:"Your participation matters more than the score.",
   encourage:"Your quiz answers are not graded by how many you get right. What matters is participating and completing the activities. Relax, explore and have fun!",
   noAi:"Please take the learning activities independently, without generative AI tools such as ChatGPT, so the study reflects your own thinking.",
   step:"STEP 1 · EXPRESSION OF INTEREST",formTitle:"Tell us a little about you",
   group:type==="school"?"For aivancity.education student email accounts.":"For personal and other email addresses.",
   email:"Email address (required)",first:"First name (optional)",last:"Family name (optional)",
   emailHint:"No username or password is required to submit this form. Private study invitations are issued separately to approved applicants.",
   privacy:"I have read the approved recruitment privacy information and agree to be contacted about this study.",
   privacyLink:"Read the approved recruitment privacy notice (PDF)",
   submit:"Submit my interest",
   received:"Thank you! Your expression of interest has been recorded. A researcher may contact you with a separate invitation.",
   error:"Please check the information and try again.",
   footer:"The supervisor personally distributes questionnaire links. This form never issues a private study token."
  },
  fr:{
   eyebrow:"Apprenez. Explorez. Amusez-vous !",
   title:"Envie de découvrir votre façon d'apprendre ?",
   sub:"Manifestez votre intérêt pour notre étude sur l'apprentissage adaptatif. Il ne s'agit ni d'un examen ni d'une inscription.",
   encourageTitle:"Votre participation compte plus que le score.",
   encourage:"Vos réponses ne sont pas notées selon le nombre de bonnes réponses. L'essentiel est de participer et de terminer les activités. Détendez-vous et amusez-vous !",
   noAi:"Réalisez les activités par vous-même, sans outils d'IA générative comme ChatGPT, afin que l'étude reflète votre propre raisonnement.",
   step:"ÉTAPE 1 · MANIFESTATION D'INTÉRÊT",formTitle:"Faisons connaissance",
   group:type==="school"?"Pour les adresses étudiantes aivancity.education.":"Pour les adresses e-mail personnelles ou autres.",
   email:"Adresse e-mail (obligatoire)",first:"Prénom (facultatif)",last:"Nom de famille (facultatif)",
   emailHint:"Aucun identifiant ni mot de passe n'est nécessaire. Une invitation privée est envoyée séparément aux personnes approuvées.",
   privacy:"J'ai lu l'avis de confidentialité approuvé et j'accepte d'être contacté(e) au sujet de cette étude.",
   privacyLink:"Lire l'avis de confidentialité approuvé (PDF)",
   submit:"Envoyer ma candidature",
   received:"Merci ! Votre manifestation d'intérêt a été enregistrée. Un chercheur pourra vous envoyer une invitation distincte.",
   error:"Veuillez vérifier les informations et réessayer.",
   footer:"Le responsable distribue personnellement les liens du questionnaire. Ce formulaire ne délivre jamais de lien privé d'étude."
  }
 };
 function language(){return $("language").value==="fr"?"fr":"en"}
 function redraw(){
  const lang=language(),c=copy[lang];document.documentElement.lang=lang;
  for(const [id,key] of [
   ["eyebrow","eyebrow"],["title","title"],["sub","sub"],
   ["encourage-title","encourageTitle"],["encourage","encourage"],["no-ai-note","noAi"],
   ["step","step"],["form-title","formTitle"],["group","group"],
   ["email-label","email"],["first-label","first"],["last-label","last"],
   ["email-hint","emailHint"],["privacy-label","privacy"],
   ["submit","submit"],["footer","footer"]])$(id).textContent=c[key];
  $("privacy-link").href="/interest/privacy/"+lang;
  $("privacy-link").textContent=c.privacyLink;
 }
 $("language").addEventListener("change",redraw);
 $("apply").addEventListener("submit",async event=>{
  event.preventDefault();
  const lang=language(),submit=$("submit");
  $("status").textContent="";submit.disabled=true;
  const payload={
   email:$("email").value,first_name:$("first-name").value,last_name:$("last-name").value,
   questionnaire:type,language:lang,privacy_accepted:$("privacy").checked};
  try{
   const response=await fetch("/interest/api/apply",{
    method:"POST",credentials:"same-origin",cache:"no-store",
    headers:{"Content-Type":"application/json","X-Study-Request":"1"},
    body:JSON.stringify(payload)});
   if(!response.ok)throw Error("invalid");
   $("apply").hidden=true;$("status").textContent=copy[lang].received;
  }catch(_){$("status").textContent=copy[lang].error;submit.disabled=false}
 });
 redraw();
})();

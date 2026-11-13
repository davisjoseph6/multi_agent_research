"use strict";
(()=>{
 const $=id=>document.getElementById(id);
 const type=location.pathname.endsWith("/school")?"school":"external";
 let lang="en";
 const copy={
  en:{title:"Study interest questionnaire",sub:"This is an expression of interest, not enrollment into the study.",
    group:"Questionnaire for "+(type==="school"?"aivancity.education email accounts":"other email addresses"),
    email:"Email (required)",first:"First name (optional)",last:"Family name (optional)",
    privacy:"I have read the approved recruitment privacy information and agree to be contacted about this study.",
    note:"The institution-approved recruitment privacy notice must be linked here before public activation.",
    submit:"Submit interest",received:"Thank you. Your expression of interest has been recorded.",
    error:"Please verify the information and try again."},
  fr:{title:"Questionnaire de candidature à l'étude",sub:"Il s'agit d'une manifestation d'intérêt, et non d'une inscription à l'étude.",
    group:"Questionnaire pour "+(type==="school"?"les adresses aivancity.education":"les autres adresses e-mail"),
    email:"Adresse e-mail (obligatoire)",first:"Prénom (facultatif)",last:"Nom de famille (facultatif)",
    privacy:"J'ai lu les informations de confidentialité approuvées et j'accepte d'être contacté(e) au sujet de cette étude.",
    note:"L'avis de confidentialité approuvé par l'établissement doit être lié ici avant toute ouverture au public.",
    submit:"Envoyer ma candidature",received:"Merci. Votre candidature a été enregistrée.",
    error:"Veuillez vérifier les informations et réessayer."}
 };
 function redraw(){
  const c=copy[lang];document.documentElement.lang=lang;
  for(const id of ["title","sub","group","privacy","submit"]){
   const node=$(id==="privacy"?"privacy-label":id);
   if(id==="privacy")node.textContent=c.privacy;else node.textContent=c[id];
  }
  $("email-label").firstChild.textContent=c.email;
  $("first-label").firstChild.textContent=c.first;
  $("last-label").firstChild.textContent=c.last;
  const privacy=$("privacy-link");
  privacy.href="/interest/privacy/"+lang;
  privacy.textContent=lang==="fr"?
   "Lire l’avis de confidentialité approuvé (PDF)":
   "Read the approved recruitment privacy notice (PDF)";
 }
 $("language").addEventListener("change",()=>{lang=$("language").value;redraw()});
 $("apply").addEventListener("submit",async e=>{
  e.preventDefault();$("status").textContent="";
  const values={email:$("email").value,first_name:$("first-name").value,
   last_name:$("last-name").value,questionnaire:type,language:lang,
   privacy_accepted:$("privacy").checked};
  try{
   const res=await fetch("/interest/api/apply",{
    method:"POST",credentials:"same-origin",cache:"no-store",
    headers:{"Content-Type":"application/json","X-Study-Request":"1"},
    body:JSON.stringify(values),
   });
   if(!res.ok)throw Error("validation");
   $("apply").hidden=true;$("status").textContent=copy[lang].received;
  }catch(_){$("status").textContent=copy[lang].error}
 });
 redraw();
})();

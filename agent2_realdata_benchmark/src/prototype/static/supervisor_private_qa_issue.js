"use strict";
(()=>{
 const el=id=>document.getElementById(id);
 const csrf=()=>{
  const token=document.cookie.split("; ").find(value=>value.startsWith("recruitment_csrf="));
  return token?decodeURIComponent(token.slice(token.indexOf("=")+1)):"";
 };
 async function post(endpoint,body){
  const res=await fetch(endpoint,{method:"POST",credentials:"same-origin",cache:"no-store",
   headers:{"Content-Type":"application/json","X-Study-Request":"1","X-CSRF-Token":csrf()},
   body:JSON.stringify(body)});
  if(!res.ok)throw Error("Denied");
  return res.json();
 }
 el("issue-form").addEventListener("submit",async e=>{
  e.preventDefault();el("qa-link").hidden=true;
  try{
   const d=await post("/control/api/qa-issue",{candidate_id:Number(el("candidate").value)});
   el("qa-link").href=d.test_link;el("qa-link").hidden=false;
   el("status").textContent="One QA link issued; no mail was sent.";
  }catch(_){el("status").textContent="Denied. Sign in, change your temporary password, approve the candidate, and use a not-yet-issued ID."}
 });
 el("qa-all").addEventListener("click",async()=>{
  if(!window.confirm("Generate a separate local QA link for ALL new approved test applicants? No email will be sent."))return;
  el("qa-links").replaceChildren();
  el("bulk-status").textContent="";
  el("qa-all").disabled=true;
  try{
   const result=await post("/control/api/qa-issue-all",{confirm:true});
   el("bulk-status").textContent=result.issued+
     " QA links created. No emails were sent. Previously issued links were skipped.";
   for(const entry of result.links){
    const li=document.createElement("li"),a=document.createElement("a");
    a.href=entry.test_link;
    a.dataset.email=entry.email;
    a.textContent="Open test invitation for candidate ID "+entry.candidate_id+" ("+entry.email+")";
    a.rel="noreferrer noopener";
    li.append(a);el("qa-links").append(li);
   }
  }catch(_){el("bulk-status").textContent="Denied. Sign in and approve your QA candidates first."}
  finally{el("qa-all").disabled=false}
 });
})();

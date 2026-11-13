"use strict";
(()=>{
const $=id=>document.getElementById(id);
let csrf="";
const status=t=>$("status").textContent=t;
function getCsrf(){
 const field=document.cookie.split("; ").find(s=>s.startsWith("recruitment_csrf="));
 return field?decodeURIComponent(field.split("=")[1]):"";
}
async function api(route,body){
 const options={credentials:"same-origin",cache:"no-store"};
 if(body!==undefined){
  options.method="POST";
  options.headers={"Content-Type":"application/json",
   "X-Study-Request":"1","X-CSRF-Token":getCsrf()};
  options.body=JSON.stringify(body);
 }
 const response=await fetch("/control/api/"+route,options);
 let data={};
 try{data=await response.json()}catch(_){}
 if(!response.ok)throw Error(data.error||"Action denied");
 return data;
}
function element(tag,value){
 const n=document.createElement(tag);
 n.textContent=value==null?"—":String(value);
 return n;
}
function rows(target,arr,render){
 const n=$(target);n.replaceChildren();
 if(!arr.length){const tr=document.createElement("tr"),td=element("td","No records yet");
  td.colSpan=7;tr.append(td);n.append(tr);return}
 for(const value of arr){const tr=document.createElement("tr");render(value,tr);n.append(tr)}
}
function display(data){
 const candidates=data.candidates,students=data.participants;
 $("potential-count").textContent=candidates.filter(c=>c.invitation_status==="potential").length;
 $("active-count").textContent=students.filter(s=>s.status==="active").length;
 $("completed-count").textContent=students.filter(s=>s.step==="DONE").length;
 $("incomplete-count").textContent=students.filter(s=>s.status==="active"&&s.step!=="DONE").length;
 rows("applicants",candidates,(c,tr)=>{
  const td=document.createElement("td"),input=document.createElement("input");
  input.type="checkbox";input.className="candidate";input.value=String(c.candidate_id);
  td.append(input);tr.append(td);
  [c.email,[c.first_name,c.last_name].filter(Boolean).join(" ")||"—",
   c.questionnaire,c.approved_for_invitation?"Approved":c.invitation_status,
   c.submitted_at].forEach(v=>tr.append(element("td",v)));
 });
 rows("students",students,(s,tr)=>{
  [s.learner_id,s.email||"—",
   [s.first_name,s.last_name].filter(Boolean).join(" ")||"—",
   s.session_no,s.step,s.status,s.updated_at].forEach(v=>tr.append(element("td",v)));
 });
}
async function refresh(){
 const [r,p]=await Promise.all([api("overview"),api("reminder-policy")]);
 display(r);$("auto-reminder").checked=p.automatic_reminders_enabled;
 $("dashboard").hidden=false;$("reload").hidden=false;$("login-panel").hidden=true;
 status("Researcher records updated. Contact information is confidential.");
}
$("login").addEventListener("submit",async e=>{
 e.preventDefault();
 try{
  const r=await api("login",{email:$("email").value,password:$("password").value});
  $("login-panel").hidden=true;$("password").value="";
  if(r.must_change_password){$("password-panel").hidden=false;status("Replace your temporary password before accessing records.")}
  else await refresh();
 }catch(err){status(err.message)}
});
$("password-form").addEventListener("submit",async e=>{
 e.preventDefault();
 try{
  await api("change-password",{current:$("current").value,
   replacement:$("replacement").value});
  $("current").value="";$("replacement").value="";
  $("password-panel").hidden=true;await refresh();
 }catch(err){status(err.message)}
});
$("reload").addEventListener("click",()=>refresh().catch(e=>status(e.message)));
$("all").addEventListener("change",()=>{
 document.querySelectorAll(".candidate").forEach(x=>x.checked=$("all").checked);
});
$("approve").addEventListener("click",async ()=>{
 const ids=[...document.querySelectorAll(".candidate:checked")].map(x=>Number(x.value));
 if(!ids.length){status("Select at least one applicant");return}
 try{const v=await api("approve",{candidate_ids:ids});
  status(v.approved+" applications marked approved; no email was sent.");await refresh();
 }catch(e){status(e.message)}
});
$("auto-reminder").addEventListener("change",async ()=>{
 try{await api("reminder-policy",{enabled:$("auto-reminder").checked});
  status("Reminder preference saved. No emails were sent.");
 }catch(err){status(err.message)}
});
api("me").then(u=>{
 if(u.must_change_password){$("login-panel").hidden=true;$("password-panel").hidden=false}
 else return refresh();
}).catch(()=>{});
})();

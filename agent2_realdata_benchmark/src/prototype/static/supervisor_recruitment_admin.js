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
  const label=document.createElement("td"),button=document.createElement("button");
  button.type="button";button.className="inline-button";
  button.textContent=s.learner_id;
  button.addEventListener("click",()=>selectStudent(s).catch(e=>status(e.message)));
  label.append(button);tr.append(label);
  [s.email||"—",
   [s.first_name,s.last_name].filter(Boolean).join(" ")||"—",
   s.session_no,s.step,s.status,s.updated_at].forEach(v=>tr.append(element("td",v)));
 });
}
const NS="http://www.w3.org/2000/svg";
const colors=["#237b8b","#ba4e68","#a47b27","#6747a1",
              "#357250","#cc6850","#3b63af","#8b4d78"];
function nodeSVG(name,attributes){
 const node=document.createElementNS(NS,name);
 for(const [k,v] of Object.entries(attributes))node.setAttribute(k,String(v));
 return node;
}
function drawMastery(data){
 const svg=$("mastery-chart");svg.replaceChildren();
 const dots=data.points||[],width=950,height=370;
 svg.append(nodeSVG("rect",{x:0,y:0,width,height,fill:"#fbfdff"}));
 for(let tick=0;tick<=4;tick++){
  const y=315-tick*72;
  svg.append(nodeSVG("line",{x1:48,y1:y,x2:920,y2:y,
   stroke:"#dae2eb","stroke-width":1}));
  const text=nodeSVG("text",{x:10,y:y+5,"font-size":15,fill:"#516578"});
  text.textContent=(tick/4).toFixed(2);svg.append(text);
 }
 const count=Math.max(1,dots.length-1);
 svg.append(nodeSVG("line",{x1:48,y1:315,x2:920,y2:315,
  stroke:"#314a59","stroke-width":1}));
 for(const [index,concept] of (data.concepts||[]).entries()){
  const values=dots.map((dot,i)=>{
   const raw=dot.mastery[concept];
   if(typeof raw!=="number")return null;
   return [48+(i/count)*872,315-(raw*288)];
  }).filter(Boolean);
  if(!values.length)continue;
  const points=values.map(p=>p.map(n=>n.toFixed(2)).join(",")).join(" ");
  svg.append(nodeSVG("polyline",{points,fill:"none",stroke:colors[index%colors.length],
   "stroke-width":2.7,"stroke-linejoin":"round"}));
 }
 const caption=nodeSVG("text",{x:430,y:358,"font-size":14,fill:"#516578"});
 caption.textContent="Scored quiz and recovery response index";
 svg.append(caption);
 const legend=$("chart-legend");legend.replaceChildren();
 for(const [i,concept] of (data.concepts||[]).entries()){
  const text=document.createElement("span");
  const dot=document.createElement("span");dot.className="legend-dot";
  dot.style.backgroundColor=colors[i%colors.length];
  text.append(dot,document.createTextNode(concept));legend.append(text);
 }
}
async function selectStudent(student){
 const [r,t]=await Promise.all([
  api("mastery/"+encodeURIComponent(student.learner_id)),
  api("question-intervals?learner_id="+encodeURIComponent(student.learner_id))
 ]);
 const info=r.learner_id+" — "+(r.email||"unknown email")+" — "+
  [r.first_name,r.last_name].filter(Boolean).join(" ")+" — "+r.stage;
 $("selected-student").textContent=info;
 drawMastery(r);
 rows("intervals",t.intervals,(v,tr)=>{
  [v.session,v.phase,v.question_id,
   v.between_answers_ms,v.between_answers_seconds,
   v.between_answers_hours,v.between_answers_days
  ].forEach(x=>tr.append(element("td",x)));
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

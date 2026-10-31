"use strict";
(() => {
  const el = id => document.getElementById(id);
  const key = "ijcai_rct_candidate_session_v1";
  let token = null, pending = null, infoVersion = null, busy = false;
  try { const saved = JSON.parse(sessionStorage.getItem(key) || "null"); if (saved) { token = saved.token; pending = saved.pending; } } catch (_) {}
  function persist() { if (token) sessionStorage.setItem(key, JSON.stringify({token,pending})); else sessionStorage.removeItem(key); }
  function say(text) { el("notice").textContent = text; }
  function add(tag,text,parent,cls) { const node=document.createElement(tag);node.textContent=text;if(cls)node.className=cls;parent.append(node);return node; }
  function lock(value) { busy=value;document.querySelectorAll("button").forEach(b=>b.disabled=value); }
  async function run(fn) { if(busy)return;lock(true);try{await fn();}catch(e){say(e.message || "Request failed. Resume to retry safely.");}finally{lock(false);} }
  async function call(route,data={}) {
    const response=await fetch(`/api/rct/${route}`,{method:"POST",credentials:"omit",redirect:"error",cache:"no-store",
      headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},body:JSON.stringify(data)});
    const result=await response.json();if(!response.ok)throw Error(result.error || `Request failed (${response.status})`);return result;
  }
  function button(text,parent,handler) { const b=add("button",text,parent);b.type="button";b.addEventListener("click",()=>run(handler));return b; }
  async function send(action,response) {
    if(!pending){pending={request_id:crypto.randomUUID(),action_id:action.action_id,response};persist();}
    const result=await call("act",pending);pending=null;persist();
    say(typeof result.correct === "boolean" ? (result.correct ? "Answer saved: correct." : "Answer saved: incorrect.") : "Response saved.");
    await refresh();
  }
  async function refresh() {
    if(pending){await call("act",pending);pending=null;persist();say("Previous response confirmed.");}
    const a=await call("next");el("activity").replaceChildren();el("agreement").hidden=true;el("study").hidden=false;
    const parent=el("activity");
    if(a.action==="COMPLETE"){el("progress").textContent="Complete";const h=add("h2","Thank you. Your session is complete.",parent);h.tabIndex=-1;h.focus();return;}
    el("progress").textContent=`${a.stage === "practice" ? `Learning session ${a.session} · ${a.index} practice questions completed` : a.stage === "fatigue" ? `Session ${a.session} questionnaire` : `${a.stage === "pretest" ? "Initial" : "Final"} assessment · question ${a.index+1} of 16`}`;
    if(a.resource){add("h2",a.action.replaceAll("_"," ").toLowerCase(),parent);add("p",a.resource.text,parent,"resource-text");if(a.resource.source)add("p",a.resource.source,parent,"source");}
    if(a.question){
      add("h2",a.question.prompt,parent);
      const form=document.createElement("form"),field=document.createElement("fieldset");form.append(field);add("legend","Choose one answer",field);
      for(const [id,text] of a.question.options){const label=document.createElement("label");label.className="choice";const radio=document.createElement("input");Object.assign(radio,{type:"radio",name:"choice",value:id,required:true});label.append(radio,document.createTextNode(` ${text}`));field.append(label);}
      const submit=add("button","Save answer",form);submit.type="submit";
      form.addEventListener("submit",e=>{e.preventDefault();const selected=form.querySelector('input:checked');if(selected)run(()=>send(a,{choice_id:selected.value}));});parent.append(form);
    } else if(a.action==="FATIGUE") {
      add("h2","How do you feel after this session?",parent);
      const form=document.createElement("form"),selects=[];
      for(const text of a.questionnaire.items){const label=add("label",text,form);const select=document.createElement("select");select.required=true;const blank=add("option","Choose a response",select);blank.value="";
        for(const [value,labelText] of Object.entries(a.questionnaire.labels)){const option=add("option",labelText,select);option.value=value;}label.append(select);selects.push(select);}
      const submit=add("button","Save responses",form);submit.type="submit";form.addEventListener("submit",e=>{e.preventDefault();if(form.reportValidity())run(()=>send(a,{values:selects.map(s=>Number(s.value))}));});parent.append(form);
    } else if(a.resource) {
      button("I have finished this resource",parent,()=>send(a,{status:"completed"}));button("Skip this resource",parent,()=>send(a,{status:"skipped"}));
    } else { throw Error("Unexpected activity. Contact the study team."); }
    // The previous submit button was removed by replaceChildren(): move
    // keyboard/screen-reader focus to the newly presented activity heading.
    const heading=parent.querySelector("h2");
    if(heading){heading.tabIndex=-1;heading.focus();}
    // Client telemetry means DOM delivery was reported, not that learning occurred.
    await call("rendered",{action_id:a.action_id});
  }
  async function open() {
    const info=await call("information");infoVersion=info.information_version;el("login").hidden=true;el("controls").hidden=false;
    if(info.status==="withdrawn"){el("study").hidden=true;el("agreement").hidden=true;say("Participation has stopped.");return;}
    if(info.status==="invited"){el("information").textContent=info.information;el("agreement").hidden=false;el("study").hidden=true;say("Read the information before deciding.");}
    else await refresh();
  }
  el("login").addEventListener("submit",e=>{e.preventDefault();run(async()=>{token=el("invitation").value.trim();el("invitation").value="";pending=null;persist();await open();});});
  el("consent").addEventListener("submit",e=>{e.preventDefault();run(async()=>{await call("enroll",{agreed:el("agree").checked,information_version:infoVersion});say("Session started.");await refresh();});});
  el("resume").addEventListener("click",()=>run(open));
  el("clear").addEventListener("click",()=>{if(busy)return;token=null;pending=null;persist();el("login").hidden=false;el("agreement").hidden=true;el("study").hidden=true;el("controls").hidden=true;say("Signed out. Re-enter your invitation to resume.");});
  el("stop").addEventListener("click",()=>run(async()=>{if(!window.confirm("Stop participation? You will no longer be able to continue this session."))return;const result=await call("withdraw");pending=null;persist();el("study").hidden=true;el("agreement").hidden=true;say(result.message);}));
  if(token)run(open);
})();

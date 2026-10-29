"use strict";
(() => {
  const element = id => document.getElementById(id);
  const start = element("start-form"), status = element("status"), study=element("study"),
    progress=element("progress"), activity=element("activity");
  let token=null, pid=null, pending=null, busy=false;
  function say(message){ status.textContent=message; }
  function lock(value){ busy=value; document.querySelectorAll("button").forEach(b=>b.disabled=value); }
  async function call(route, content){
    if(!token) throw Error("Enter local development credential");
    const response=await fetch(`/api/v3/${route}`,{
      method:"POST",credentials:"omit",redirect:"error",cache:"no-store",
      headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},
      body:JSON.stringify({participant_id:pid,...content})
    });
    const result=await response.json();
    if(!response.ok) throw Error(result.error||`HTTP ${response.status}`);
    return result;
  }
  async function run(fn){if(busy)return;lock(true);try{await fn();}catch(e){say(e.message||"Request failed");}finally{lock(false);}}
  function actionButton(label,fn){ const b=document.createElement("button");b.textContent=label;b.type="button";b.addEventListener("click",()=>run(fn));return b;}
  async function respond(data){
    if(!pending)pending={request_id:crypto.randomUUID(),response:data};
    const result=await call("act",pending);
    pending=null;
    say(result.replayed?"Previous response confirmed":"Synthetic action saved");
    await refresh();
  }
  async function refresh(){
    const s=await call("status",{});
    const a=await call("next",{});
    progress.textContent=`Arm ${s.arm}; stage ${s.stage}; session ${s.session}; position ${s.index}; POMCP resources ${s.resources_spent}`;
    activity.replaceChildren();
    if(a.action==="COMPLETE"){
      const p=document.createElement("p");p.textContent="Synthetic protocol complete. No human learning result was measured.";
      activity.append(p);return;
    }
    if(a.action==="FATIGUE"){
      const form=document.createElement("form");
      const desc=document.createElement("p");desc.textContent="Six SYNTHETIC fatigue responses; this is not a validated instrument.";form.append(desc);
      const fields=[];
      for(let i=0;i<6;i++){
        const l=document.createElement("label");l.textContent=`Fixture fatigue item ${i+1}: `;
        const select=document.createElement("select");
        for(let v=1;v<=5;v++){const o=document.createElement("option");o.value=String(v);o.textContent=String(v);select.append(o);}
        l.append(select);form.append(l);fields.push(select);
      }
      const submit=actionButton("Submit synthetic fatigue form",async()=>respond({values:fields.map(f=>Number(f.value))}));
      form.append(submit);activity.append(form);return;
    }
    const title=document.createElement("h2");title.textContent=`${a.action} — ${a.concept}`;activity.append(title);
    if(a.question){
      const q=document.createElement("p");q.textContent=a.question.prompt;activity.append(q);
      const form=document.createElement("form");const field=document.createElement("fieldset");
      const legend=document.createElement("legend");legend.textContent="Choose one answer";field.append(legend);
      for(const [id,text] of a.question.options){
        const label=document.createElement("label");label.className="choice";
        const radio=document.createElement("input");radio.type="radio";radio.name="choice";radio.value=id;radio.required=true;
        label.append(radio,document.createTextNode(`${id}: ${text}`));field.append(label);
      }
      form.append(field);
      const submit=document.createElement("button");submit.type="submit";submit.textContent="Submit synthetic answer";form.append(submit);
      form.addEventListener("submit",e=>{e.preventDefault();const selected=form.querySelector('input[name="choice"]:checked');
        if(selected)run(async()=>respond({item_id:a.question.item_id,choice_id:selected.value}));});
      activity.append(form);return;
    }
    const note=document.createElement("p");note.textContent=`SYNTHETIC PLACEHOLDER — ${a.action} for ${a.concept}. No educational resource has been authored or reviewed.`;activity.append(note);
    activity.append(actionButton("Acknowledge development-only resource",async()=>respond({acknowledged:true})));
  }
  start.addEventListener("submit",e=>{e.preventDefault();run(async()=>{
    token=element("token").value.trim();element("token").value="";
    pid=element("pid").value.trim();
    await call("enroll",{arm:element("arm").value});
    start.hidden=true;study.hidden=false;say("Synthetic session open; no real learner data.");await refresh();
  });});
  element("refresh").addEventListener("click",()=>run(refresh));
  element("forget").addEventListener("click",()=>{
    if(busy)return;token=null;pid=null;pending=null;study.hidden=true;start.hidden=false;
    activity.replaceChildren();say("Credential cleared from JavaScript memory. Re-enter to resume.");
  });
})();

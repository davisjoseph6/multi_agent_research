"use strict";
(() => {
 const root=document.getElementById("app"), nonce=root.dataset.previewNonce;
 const $=id=>document.getElementById(id);
 const fixture=$("fixture");
 let item=null, working=false, screening=[];
 function message(s){$("feedback").textContent=s||""}
 function buttons(...visible){for(const id of ["answer","continue","survey","advance"])$(id).hidden=!visible.includes(id)}
 function requestId(){return "fictional_"+crypto.randomUUID().replaceAll("-","")}
 async function call(action,data={}){
   const res=await fetch("/supervisor/api/"+action,{
     method:"POST",headers:{"Content-Type":"application/json",
       "X-Preview-Nonce":nonce},
     body:JSON.stringify({fixture:fixture.value,...data})
   });
   const body=await res.json();
   if(!res.ok)throw new Error(body.error||"Local preview refused this action");
   return body;
 }
 function options(parent,choiceMap,name){
   parent.replaceChildren();
   const legend=document.createElement("legend");
   legend.textContent="Select one answer";parent.append(legend);
   for(const [key,text] of Object.entries(choiceMap)){
     const label=document.createElement("label"),input=document.createElement("input");
     input.type="radio";input.name=name;input.value=key;
     label.append(input,document.createTextNode(key+". "+text));parent.append(label);
   }
 }
 function selected(name){
   const x=document.querySelector('input[name="'+name+'"]:checked');
   if(!x)throw new Error("Select one answer first.");
   return x.value;
 }
 function createScreening(questions){
   screening=questions;
   const wrapper=$("screening");wrapper.replaceChildren();
   for(let i=0;i<questions.length;i++){
     const q=questions[i],article=document.createElement("article");
     const p=document.createElement("p");p.textContent=(i+1)+". "+q.question_text;
     const field=document.createElement("fieldset");
     options(field,q.options,"screening_"+q.question_id);
     article.append(p,field);wrapper.append(article);
   }
 }
 function showCurrent(data){
   item=data;
   $("question").textContent="";
   $("options").replaceChildren();buttons();
   if(data.kind==="question"){
     $("question").textContent=data.question_text+" (independent or quiz question)";
     options($("options"),data.options,"current");
     buttons("answer");
   } else if(data.kind==="recovery"){
     if(data.question_id){
       $("question").textContent=(
         data.action+" — graded bank question, not part of the 20/20/15 block: "+
         data.question_text
       );
       options($("options"),data.options,"current");buttons("answer");
     } else {
       $("question").textContent=(
         data.action+" — text resource requires academic content review. "+
         "This synthetic preview records an acknowledgment only."
       );
       buttons("continue");
     }
   } else if(data.kind==="survey"){
     $("question").textContent="Six provisional 1–7 fatigue responses. "+
       "Item wording and validation require supervisor approval.";
     const map={};for(let i=1;i<=7;i++)map[String(i)]=String(i);
     for(let i=0;i<6;i++){
       const label=document.createElement("label");
       label.textContent="Fatigue item Q"+(i+1);
       const select=document.createElement("select");select.id="fatigue_"+i;
       for(const [key,value] of Object.entries(map)){
         const o=document.createElement("option");o.value=key;o.textContent=value;
         select.append(o);
       }
       label.append(select);$("options").append(label);
     }
     buttons("survey");
   } else if(data.kind==="waiting_next_session"){
     $("question").textContent="Next simulated visit: "+data.scheduled_for;
     buttons("advance");
   } else if(data.kind==="done"){
     $("question").textContent="All three fictional sessions completed.";
   } else {
     $("question").textContent=data.kind||"No fictional step";
   }
 }
 async function refresh(){
   if(working)return;working=true;
   try{
     message("");
     const status=await call("status");
     if(!status.registered){
       $("registration").hidden=false;
       const data=await call("screening");
       createScreening(data.questions);
       $("progress").textContent="Not registered: fictional screening";
       showCurrent({kind:"await_registration"});
     }else{
       $("registration").hidden=true;
       $("progress").textContent="Fictional "+fixture.value+" — Session "+
         status.session+"/3 — "+status.phase+" — step "+status.index;
       showCurrent(await call("item"));
     }
   }catch(e){message(e.message);buttons()}finally{working=false}
 }
 async function act(action,data){
   if(working)return;working=true;
   try{message("");await call(action,data)}
   catch(e){message(e.message);working=false;return}
   working=false;await refresh();
 }
 $("register").addEventListener("click",()=>{
   try{
     const consent=$("consent").checked, econ_course=$("econ").checked;
     const answers={};
     if(!econ_course){
       for(const q of screening)answers[q.question_id]=selected("screening_"+q.question_id);
     }
     act("register",{consent,econ_course,screening_answers:answers});
   }catch(e){message(e.message)}
 });
 $("answer").addEventListener("click",()=>{
   try{act("answer",{question_id:item.question_id||null,
     choice:selected("current"),request_id:requestId()})}
   catch(e){message(e.message)}
 });
 $("continue").addEventListener("click",()=>{
   act("answer",{question_id:null,choice:null,request_id:requestId()})
 });
 $("survey").addEventListener("click",()=>{
   const values=[];for(let i=0;i<6;i++)values.push(Number($("fatigue_"+i).value));
   act("survey",{values,request_id:requestId()});
 });
 $("advance").addEventListener("click",()=>act("advance-fictional-clock"));
 $("load").addEventListener("click",refresh);
 fixture.addEventListener("change",refresh);
 refresh();
})();

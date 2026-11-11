"use strict";
(() => {
 const root=document.getElementById("app"), nonce=root.dataset.previewNonce;
 const $=id=>document.getElementById(id);
 const fixture=$("fixture"), language=$("language");
 let screen=null, waiting=false;
 const buttons=["submit","ack","continue","after-pause","pause","resume","finish","next"];
 function show(...names){for(const id of buttons)$(id).hidden=!names.includes(id)}
 function message(t){$("message").textContent=t||""}
 async function call(path, payload){
   const response=await fetch("/research-v2/api/"+path,{
     method:"POST",
     headers:{"Content-Type":"application/json",
              "Origin":window.location.origin,"X-Preview-Nonce":nonce},
     body:JSON.stringify({fixture:fixture.value,...payload})
   });
   const data=await response.json();
   if(!response.ok)throw new Error(data.error||"Request denied");
   return data;
 }
 function choices(options){
   const parent=$("choices");parent.replaceChildren();
   const legend=document.createElement("legend");
   legend.textContent="Select one answer (fictional)";parent.append(legend);
   options.forEach((option,index)=>{
      const i=option.choice_index===undefined?index:option.choice_index;
      const label=document.createElement("label");
      const input=document.createElement("input");
      input.type="radio";input.name="answer";input.value=String(i);
      label.append(input,document.createTextNode(option.text===undefined?option:option.text));
      parent.append(label);
   });
 }
 function answerIndex(){
   const node=document.querySelector('input[name="answer"]:checked');
   if(!node)throw new Error("Select an answer before submitting.");
   return Number(node.value);
 }
 function draw(data){
   screen=data;
   $("prompt").textContent=data.prompt||"";
   $("choices").replaceChildren();
   if(data.kind==="question"){
      choices(data.options);show("submit","pause");
   }else if(data.kind==="recovery"){
      if(data.action==="DROP_2"){choices(data.options);show("submit","pause")}
      else show("ack","pause");
   }else if(data.kind==="awaiting_continue")show("continue","after-pause");
   else if(data.kind==="paused")show("resume");
   else if(data.kind==="period_complete")show("finish");
   else if(data.kind==="between_periods")show("next");
   else if(data.kind==="finished")show();
   else show("pause");
 }
 async function load(){
   if(waiting)return;waiting=true;
   try{
     message("");
     const info=await call("status",{});
     $("status").textContent="Learner "+info.fixture+" — period "+Math.min(info.period,3)+"/3; "+
       "pretest "+info.counts.pretest+"/16, practice "+info.counts.practice+"/55, posttest "+info.counts.posttest+"/16";
     draw(await call("item",{language:language.value}));
     if(info.paused||info.finished||info.between_periods){
       $("mastery").textContent="Mastery unavailable outside an active fictional period";
     }else{
       const result=await call("mastery",{});
       if(result.available===false){
         $("mastery").textContent="Assessment in progress: mastery feedback withheld.";
       }else{
         const last=result.points[result.points.length-1];
         $("mastery").textContent=JSON.stringify({
           provisional_mastery:last.mastery,
           answered:last.answered,
           independent_scores:result.independent_scores,
           synthetic_only:true
         },null,2);
       }
     }
   }catch(e){message(e.message);show()}finally{waiting=false}
 }
 async function act(kind,payload){
   try{
     if(waiting)return;waiting=true;
     message("");
     await call(kind,payload);
   }catch(e){message(e.message);waiting=false;return}
   waiting=false;
   await load();
 }
 $("submit").addEventListener("click",()=>{
   try{
     const choice=answerIndex();
     if(screen.kind==="question"){
       act("answer",{item_id:screen.item_id,selected_index:choice,
         request_id:"fictional_"+crypto.randomUUID().replaceAll("-","")});
     }else if(screen.kind==="recovery"&&screen.action==="DROP_2"){
       act("recovery/drop2",{item_id:screen.item_id,selected_index:choice,
         request_id:"fictional_"+crypto.randomUUID().replaceAll("-","")});
     }
   }catch(e){message(e.message)}
 });
 $("ack").addEventListener("click",()=>act("recovery/ack",{
   request_id:"fictional_"+crypto.randomUUID().replaceAll("-","")}));
 $("continue").addEventListener("click",()=>act("decision",{decision:"continue"}));
 $("after-pause").addEventListener("click",()=>act("decision",{decision:"pause"}));
 $("pause").addEventListener("click",()=>act("pause",{}));
 $("resume").addEventListener("click",()=>act("resume",{}));
 $("finish").addEventListener("click",()=>act("finish",{}));
 $("next").addEventListener("click",()=>act("start-next",{}));
 $("refresh").addEventListener("click",load);
 fixture.addEventListener("change",load);
 language.addEventListener("change",load);
 load();
})();
"use strict";
(()=>{
 const $=id=>document.getElementById(id);
 const concepts=["C1","C2","C3","C4","C5","C6","C7","C8"];
 const labels=["Utility","Loss aversion","Anchoring","Sunk cost","Framing",
               "Heuristics","Prospect theory","Nudge theory"];
 const colors=["#0073a8","#cc4b34","#7352ae","#237c53","#a35a00",
               "#bc2c7b","#4d6578","#835d1c"];
 const svgNs="http://www.w3.org/2000/svg";
 let current="",inFlight=false;
 function svg(tag,attributes={},text=""){
   const el=document.createElementNS(svgNs,tag);
   for(const [k,v] of Object.entries(attributes))el.setAttribute(k,String(v));
   if(text)el.textContent=text;
   return el;
 }
 async function fetchData(path){
   const response=await fetch(path,{credentials:"same-origin",cache:"no-store"});
   if(!response.ok)throw Error("Request failed ("+response.status+"). Check researcher authentication.");
   return response.json();
 }
 function draw(points){
   const root=$("chart");root.replaceChildren();
   const x0=68,x1=910,y0=22,y1=337;
   root.append(svg("rect",{x:x0,y:y0,width:x1-x0,height:y1-y0,
                            fill:"#fbfcff",stroke:"#d5dfeb"}));
   for(let tick=0;tick<=4;tick++){
     const y=y1-tick*(y1-y0)/4;
     root.append(svg("line",{x1:x0,y1:y,x2:x1,y2:y,
                              stroke:"#e0e5ec","stroke-width":"1"}));
     root.append(svg("text",{x:x0-12,y:y+4,"text-anchor":"end",
                             "font-size":"12",fill:"#43576b"},(tick/4).toFixed(2)));
   }
   const xmax=Math.max(1,points.length);
   for(let i=0;i<6;i++){
     const value=1+Math.round((xmax-1)*i/5);
     const x=x0+(x1-x0)*(value-1)/Math.max(1,xmax-1);
     root.append(svg("text",{x,y:y1+20,"font-size":"11",
                             "text-anchor":"middle",fill:"#43576b"},String(value)));
   }
   root.append(svg("text",{x:(x0+x1)/2,y:379,"font-size":"13",
                            "text-anchor":"middle",fill:"#243f58"},"Scored response number"));
   root.append(svg("text",{x:15,y:(y0+y1)/2,"font-size":"13",
                            transform:"rotate(-90 15 "+((y0+y1)/2)+")",
                            "text-anchor":"middle",fill:"#243f58"},"BKT mastery (0–1)"));
   const selected=$("concept").value;
   const shown=concepts.filter(c=>selected==="all"||selected===c);
   for(const concept of shown){
     const n=concepts.indexOf(concept);
     const coords=points.map((p,i)=>{
       const x=x0+(x1-x0)*(i/Math.max(1,points.length-1));
       const y=y1-(y1-y0)*p.mastery[concept];
       return x+","+y;
     }).join(" ");
     if(points.length>0){
       root.append(svg("polyline",{points:coords,fill:"none",stroke:colors[n],
                  "stroke-width":"2.5","stroke-linejoin":"round","stroke-linecap":"round"}));
       if(points.length===1){
         const [cx,cy]=coords.split(",");
         root.append(svg("circle",{cx,cy,r:4,fill:colors[n]}));
       }
     }
   }
   if(!points.length)root.append(svg("text",{x:450,y:180,
                      "text-anchor":"middle",fill:"#42536c"},
                      "No graded quiz answers recorded yet."));
   $("legend").replaceChildren();
   for(const c of shown){
     const n=concepts.indexOf(c),span=document.createElement("span"),
           swatch=document.createElement("i");
     swatch.className="swatch";swatch.style.backgroundColor=colors[n];
     span.append(swatch,document.createTextNode(c+" — "+labels[n]));
     $("legend").append(span);
   }
 }
 function showHistory(data){
   const body=$("events").querySelector("tbody");body.replaceChildren();
   for(const event of data.points.slice(-250).reverse()){
     const tr=document.createElement("tr");
     const values=[event.x,event.session,event.action,event.concept,
                   event.answered_at,concepts.map(c=>
                     c+": "+event.mastery[c].toFixed(3)).join(" · ")];
     for(const v of values){
       const td=document.createElement("td");
       td.textContent=String(v);tr.append(td);
     }
     body.append(tr);
   }
 }
 function showSummary(data){
   const section=$("summary");section.replaceChildren();
   const title=document.createElement("h2");
   title.textContent="Pseudonym: "+data.learner_id+" · Arm "+data.arm;
   const dl=document.createElement("dl");
   const fields=[
     ["Study status",data.status],
     ["Visit",String(data.session)+" / 3"],
     ["Current stage",data.stage],
     ["Graded responses",data.points.length],
     ["Last recorded change",data.last_update],
   ];
   for(const [name,value] of fields){
     const item=document.createElement("div");
     const dt=document.createElement("dt"),dd=document.createElement("dd");
     dt.textContent=name;dd.textContent=String(value);item.append(dt,dd);dl.append(item);
   }
   section.append(title,dl);
 }
 async function update(){
   if(inFlight)return;
   inFlight=true;
   try{
     const list=await fetchData("/admin/api/participants");
     const selection=$("student"),prior=selection.value;
     selection.replaceChildren();
     const blank=document.createElement("option");blank.value="";
     blank.textContent="Select a pseudonymous participant";
     selection.append(blank);
     for(const p of list.participants){
       const opt=document.createElement("option");
       opt.value=p.learner_id;
       opt.textContent=p.learner_id+" · Arm "+p.grp+" · Visit "+p.session_no+
                       " · "+p.step;
       selection.append(opt);
     }
     if(list.participants.some(p=>p.learner_id===prior))selection.value=prior;
     current=selection.value;
     if(current){
       const payload=await fetchData("/admin/api/mastery/"+encodeURIComponent(current));
       showSummary(payload);showHistory(payload);draw(payload.points);
     }else{
       $("summary").textContent="Select a pseudonymous participant.";
       $("events").querySelector("tbody").replaceChildren();draw([]);
     }
     $("notice").textContent="Updated "+new Date().toLocaleTimeString()+
       " — read-only, no participant data modified.";
   }catch(error){$("notice").textContent=error.message}
   finally{inFlight=false}
 }
 const selector=$("concept");
 for(let i=0;i<concepts.length;i++){
   const option=document.createElement("option");
   option.value=concepts[i];option.textContent=concepts[i]+" — "+labels[i];
   selector.append(option);
 }
 $("student").addEventListener("change",update);
 $("concept").addEventListener("change",update);
 $("refresh").addEventListener("click",update);
 update();
 setInterval(()=>{if(!document.hidden)update()},5000);
})();

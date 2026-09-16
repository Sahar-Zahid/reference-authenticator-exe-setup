const API_BASE="/api";
const tabs=document.querySelectorAll(".tab");
const panels={single:document.getElementById("single-panel"),list:document.getElementById("list-panel"),pdf:document.getElementById("pdf-panel")};
const loading=document.getElementById("loading"),message=document.getElementById("message"),resultsSection=document.getElementById("results-section"),resultsBox=document.getElementById("results"),downloadLink=document.getElementById("download-link");
tabs.forEach(tab=>tab.addEventListener("click",()=>{tabs.forEach(t=>t.classList.remove("active"));tab.classList.add("active");Object.entries(panels).forEach(([m,p])=>p.classList.toggle("hidden",m!==tab.dataset.mode));clearOutput();}));
function clearOutput(){resultsSection.classList.add("hidden");message.classList.add("hidden");message.textContent="";resultsBox.innerHTML="";downloadLink.classList.add("hidden");downloadLink.removeAttribute("href");}
function setLoading(active){loading.classList.toggle("hidden",!active);document.querySelectorAll(".verify-btn").forEach(b=>b.disabled=active);}
function showMessage(text){message.textContent=text;message.classList.remove("hidden");}
function escapeHtml(v){return String(v??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");}
function statusStyle(s){return {"VERIFIED":{color:"#28a745",bg:"#d4edda",icon:"✅"},"UNCERTAIN":{color:"#856404",bg:"#fff3cd",icon:"⚠️"},"NOT VERIFIED":{color:"#721c24",bg:"#f8d7da",icon:"❌"}}[s]||{color:"#383d41",bg:"#e2e3e5",icon:"❔"};}
// Renders one submitted-vs-matched field row (e.g. Title, Authors, Year, DOI)
// with an optional similarity percentage. Skipped entirely if the pipeline
// never produced either side of the comparison for this field.
function fieldRow(label,submitted,matched,score){
  const hasSubmitted=submitted!==undefined&&submitted!==null&&submitted!=="";
  const hasMatched=matched!==undefined&&matched!==null&&matched!=="";
  if(!hasSubmitted&&!hasMatched)return "";
  const scoreText=(typeof score==="number")?` <span class="field-score">(${Math.round(score)}% similar)</span>`:"";
  return `<div class="field-row"><span class="field-label">${escapeHtml(label)}</span><span class="field-submitted">${escapeHtml(hasSubmitted?submitted:"—")}</span><span class="field-arrow">vs. database</span><span class="field-matched">${escapeHtml(hasMatched?matched:"—")}</span>${scoreText}</div>`;
}

// Renders a result card. For VERIFIED references this stays simple; for
// UNCERTAIN/NOT VERIFIED references it surfaces exactly what the backend's
// verification pipeline flagged - the short reason category, the full
// explanation text, a field-by-field submitted-vs-matched comparison with
// similarity scores, and which databases were checked/agreed - all sourced
// directly from the fields the backend already computed (reason_category,
// verification_reason, submitted_*/matched_*, *_similarity, sources_checked,
// sources_agreeing, manual_check_needed). Nothing here is guessed on the
// frontend; it only displays what the backend already decided and why.
function renderCard(r){
  const status=String(r.status||"UNKNOWN").toUpperCase();
  const style=statusStyle(status);
  const reference=r.original_reference||"";
  const explanation=r.verification_reason||r.explanation||r.reason||"No explanation available.";
  const reasonCategory=r.reason_category||"";
  const source=r.verification_source||r.source||"unknown";
  const refNum=r.reference_id??"?";
  const sourcesAgreeing=Array.isArray(r.sources_agreeing)?r.sources_agreeing:[];
  const sourcesChecked=Array.isArray(r.sources_checked)?r.sources_checked:[];
  const manualCheck=(typeof r.manual_check_needed==="boolean")?r.manual_check_needed:(status==="UNCERTAIN"||status==="NOT VERIFIED");
  const submittedAuthors=Array.isArray(r.submitted_authors)?r.submitted_authors.join(", "):(r.submitted_authors||"");
  const matchedAuthors=Array.isArray(r.matched_authors)?r.matched_authors.join(", "):(r.matched_authors||"");

  const reasonBadge=(manualCheck&&reasonCategory)?`<div class="reason-badge" style="background:${style.color};">${escapeHtml(reasonCategory)}</div>`:"";

  const comparisonRows=manualCheck?[
    fieldRow("Title",r.submitted_title,r.matched_title,r.title_similarity),
    fieldRow("Authors",submittedAuthors,matchedAuthors,r.author_similarity),
    fieldRow("Year",r.submitted_year,r.matched_year),
    fieldRow("DOI",r.submitted_doi,r.matched_doi),
  ].filter(Boolean).join(""):"";
  const comparisonBlock=comparisonRows?`<div class="field-compare"><div class="field-compare-title">Submitted vs. database record</div>${comparisonRows}</div>`:"";

  const sourcesBlock=[
    sourcesChecked.length?`<div class="result-sources"><b>Databases checked:</b> ${sourcesChecked.map(escapeHtml).join(", ")}</div>`:"",
    sourcesAgreeing.length?`<div class="result-sources"><b>Databases agreeing:</b> ${sourcesAgreeing.map(escapeHtml).join(", ")}</div>`:"",
  ].join("");

  return `<div class="result-card" style="border-left-color:${style.color};background:${style.bg};"><div class="result-title" style="color:${style.color};">[#${escapeHtml(refNum)}] ${style.icon} ${escapeHtml(status)} <span class="result-meta">(via ${escapeHtml(source)})</span></div><div class="result-reference"><b>Reference:</b> ${escapeHtml(reference)}</div>${reasonBadge}<div class="result-why"><b>Why:</b> ${escapeHtml(explanation)}</div>${comparisonBlock}${sourcesBlock}</div>`;
}
function showResults(results,url){if(!Array.isArray(results)||!results.length){showMessage("No verification results were returned.");return;}resultsBox.innerHTML=`<p><b>Found ${results.length} reference(s).</b></p>${results.map(renderCard).join("")}`;resultsSection.classList.remove("hidden");if(url){downloadLink.href=url;downloadLink.classList.remove("hidden");}}
async function postJson(endpoint,body){const response=await fetch(`${API_BASE}${endpoint}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!response.ok){let d=`Server error (${response.status})`;try{const x=await response.json();d=x.detail||x.message||d;}catch(_){}throw Error(d);}return response.json();}
async function postPdf(file){const fd=new FormData();fd.append("file",file);const response=await fetch(`${API_BASE}/verify/pdf`,{method:"POST",body:fd});if(!response.ok){let d=`Server error (${response.status})`;try{const x=await response.json();d=x.detail||x.message||d;}catch(_){}throw Error(d);}return response.json();}
async function verifySingle(){clearOutput();const reference=document.getElementById("single-input").value.trim();if(!reference)return showMessage("Please enter a reference.");setLoading(true);try{const d=await postJson("/verify/single",{reference});showResults(d.results,d.download_url);}catch(e){showMessage(`❌ ${e.message}`);}finally{setLoading(false);}}
async function verifyList(){clearOutput();const reference_text=document.getElementById("list-input").value.trim();if(!reference_text)return showMessage("Please enter a reference list.");setLoading(true);try{const d=await postJson("/verify/list",{reference_text});showResults(d.results,d.download_url);}catch(e){showMessage(`❌ ${e.message}`);}finally{setLoading(false);}}
async function verifyPdf(){clearOutput();const file=document.getElementById("pdf-input").files[0];if(!file)return showMessage("Please select a PDF.");setLoading(true);try{const d=await postPdf(file);showResults(d.results,d.download_url);}catch(e){showMessage(`❌ ${e.message}`);}finally{setLoading(false);}}
document.getElementById("single-button").addEventListener("click",verifySingle);document.getElementById("list-button").addEventListener("click",verifyList);document.getElementById("pdf-button").addEventListener("click",verifyPdf);
const pdfInput=document.getElementById("pdf-input"),dropZone=document.getElementById("drop-zone"),fileName=document.getElementById("file-name");
pdfInput.addEventListener("change",()=>fileName.textContent=pdfInput.files[0]?pdfInput.files[0].name:"No file selected");
["dragenter","dragover"].forEach(n=>dropZone.addEventListener(n,e=>{e.preventDefault();dropZone.classList.add("dragover");}));
["dragleave","drop"].forEach(n=>dropZone.addEventListener(n,e=>{e.preventDefault();dropZone.classList.remove("dragover");}));
dropZone.addEventListener("drop",e=>{const f=e.dataTransfer.files[0];if(f&&f.type==="application/pdf"){const dt=new DataTransfer();dt.items.add(f);pdfInput.files=dt.files;fileName.textContent=f.name;}else showMessage("Please drop a PDF file.");});

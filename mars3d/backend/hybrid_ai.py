"""hybrid_ai.py — NAM hybrid AI engine.

Architecture (the "hybrid" the user asked for):
  1. LOCAL classifier (TF-IDF + L1 logistic regression, trained offline via
     nam_train/) decides intent + confidence. Cheap, on-process, no network.
  2. LOCAL retrieval (TF-IDF cosine) over the embedded gazetteer (features,
     mission sites, instruments, targets, planet facts) grounds the answer.
  3. OPTIONAL remote LLM (OpenAI-compatible API, env-configured, default OFF):
     only refines the natural-language phrasing, fed EXACTLY the retrieved
     facts as context so it cannot hallucinate beyond the catalog. If the
     remote call fails or is off, a local template answer is returned.

So "engine" in the response is one of: "local" (classifier+retrieval+template),
"remote" (LLM phrased), "hybrid" (local intent+retrieval fed to remote LLM).

This minimizes load: the cheap local path handles routing & grounding; the
remote API is only touched when configured and only to phrase, not to reason.
"""
import os, json, math, re, urllib.request, urllib.error
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "..", "data")
MODEL_PATH = os.path.join(_DATA, "nam_model.json")
GAZ_PATH = os.path.join(_DATA, "gazetteer.json")

# ---- model load (lazy, fault-tolerant) ------------------------------------
_M = None; _GAZ = None
def _model():
    global _M
    if _M is None:
        try:
            _M = json.load(open(MODEL_PATH, encoding="utf-8"))
        except Exception as e:
            _M = {"_err": str(e)}
    return _M

def _gaz():
    global _GAZ
    if _GAZ is None:
        _GAZ = json.load(open(GAZ_PATH, encoding="utf-8"))
    return _GAZ

def ready():
    m=_model(); return "classifier" in m

# ---- tokenizer (mirrors train_model.py / nam_nlp_block.js exactly) --------
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_WORD = re.compile(r"[A-Za-z0-9_\u00c0-\u00ff\u0100-\u024f\u0400-\u04ff\u0600-\u06ff\u0900-\u097f]+")
def tokenize(s):
    s=(s or "").lower(); toks=_WORD.findall(s)
    cjk=[c for c in s if _CJK.match(c)]
    toks += cjk
    for i in range(len(cjk)-1): toks.append(cjk[i]+cjk[i+1])
    return toks

# ---- classifier inference (same math as the browser runtime) --------------
def classify(q):
    m=_model()
    if "classifier" not in m: return {"intent":None,"conf":0.0,"top":[],"error":m.get("_err","no model")}
    cl=m["classifier"]; vocab=cl["vocab"]; idf=cl["idf"]; classes=cl["classes"]
    intercept=cl["intercept"]; wbt=cl["weights_by_token"]
    tf=Counter()
    for t in tokenize(q):
        idx=vocab.get(t)
        if idx is not None: tf[idx]+=1
    vec={}; n2=0.0
    for idx,cnt in tf.items():
        v=(1.0+math.log(cnt))*idf[idx]; vec[idx]=v; n2+=v*v
    norm=math.sqrt(n2) or 1.0
    scores=list(intercept)
    for idx,v in vec.items():
        col=wbt.get(str(idx))
        if not col: continue
        v/=norm
        for ci,w in col: scores[ci]+=v*w
    mx=max(scores); Z=sum(math.exp(s-mx) for s in scores)
    probs=[math.exp(s-mx)/Z for s in scores]
    best=max(range(len(probs)), key=lambda i: probs[i])
    top=sorted(zip(classes,probs), key=lambda x:-x[1])[:5]
    return {"intent":classes[best],"conf":probs[best],"top":[{"intent":c,"p":p} for c,p in top]}

# ---- retrieval over the gazetteer -----------------------------------------
_CORPUS=None
def _corpus():
    global _CORPUS
    if _CORPUS is not None: return _CORPUS
    g=_gaz(); docs=[]
    for f in g["FEATURES"]:
        docs.append({"type":"feature","id":f.get("id"),"name":f["name"],
                     "lat":f.get("lat"),"lon":f.get("lon"),"elev":f.get("elev"),
                     "text":(f.get("desc","")+" "+f.get("interesting","")+" "+f.get("type","")),
                     "src":f.get("src",[]),"obj":f})
    for s in g["SITES"]:
        docs.append({"type":"site","id":s.get("id"),"name":s["name"],
                     "lat":s.get("lat"),"lon":s.get("lon"),
                     "text":(s.get("desc","")+" "+s.get("kind","")+" "+s.get("status","")+" "+s.get("agency","")),
                     "src":s.get("src",[]),"obj":s})
    for i in g["INSTRUMENTS"]:
        docs.append({"type":"instrument","name":i["inst"],
                     "text":(i.get("data","")+" "+i.get("mission","")+" "+i.get("access","")),
                     "src":i.get("src",[]),"obj":i})
    for t in g["TARGETS"]:
        docs.append({"type":"target","id":t.get("id"),"name":t["name"],
                     "lat":t.get("lat"),"lon":t.get("lon"),
                     "text":(t.get("obs","")+" "+t.get("kind","")), "src":t.get("src",[]),"obj":t})
    # idf
    df=Counter()
    for d in docs:
        for t in set(tokenize(d["text"])): df[t]+=1
    N=len(docs) or 1
    idf={t: math.log((1+N)/(1+c))+1 for t,c in df.items()}
    for d in docs:
        tf=Counter(tokenize(d["text"]))
        vec={}; n2=0.0
        for t,c in tf.items():
            v=(1.0+math.log(c))*idf[t]; vec[t]=v; n2+=v*v
        norm=math.sqrt(n2) or 1.0
        d["_vec"]={t:v/norm for t,v in vec.items()}
    _CORPUS=(docs,idf); return _CORPUS

def retrieve(q, k=3):
    docs,idf=_corpus()
    tf=Counter(tokenize(q))
    qv={}; n2=0.0
    for t,c in tf.items():
        if t in idf:
            v=(1.0+math.log(c))*idf[t]; qv[t]=v; n2+=v*v
    norm=math.sqrt(n2) or 1.0
    for t in qv: qv[t]/=norm
    scored=[]
    for d in docs:
        s=sum(qv[t]*d["_vec"].get(t,0) for t in qv)
        if d["name"] and d["name"].lower() in q.lower(): s+=0.4
        if s>0.02: scored.append((s,d))
    scored.sort(key=lambda x:-x[0])
    out=[]
    for s,d in scored[:k]:
        out.append({"type":d["type"],"name":d["name"],"lat":d.get("lat"),"lon":d.get("lon"),
                    "elev":d.get("elev"),"score":round(s,3),
                    "desc":d["obj"].get("desc","") or d["obj"].get("obs",""),
                    "src":d.get("src",[])})
    return out

# ---- planet facts (deterministic KB) --------------------------------------
def planet_fact(q):
    ql=q.lower(); P=_gaz()["PLANET"]
    if "gravity" in ql: return "Mars surface gravity is 3.71 m/s² (~38% of Earth's).", ["https://science.nasa.gov/mars/facts/"]
    if any(w in ql for w in ["day","sol","rotation"]): return "A Martian sol is 24 h 39 min 35 s.", ["NASA Mars facts"]
    if "year" in ql or "orbit" in ql: return "A Mars year is 687 Earth days (≈668 sols); axial tilt 25.2°.", ["NASA Mars facts"]
    if "pressure" in ql or "atmos" in ql: return "Mean surface pressure ≈6.36 mbar at the areoid (<1% of Earth's).", ["Viking/REM; NASA Mars facts"]
    if "radiation" in ql or "dose" in ql: return "MSL RAD surface dose ≈0.64–0.7 mSv/day (Hassler et al. 2014).", ["doi:10.1126/science.1244797"]
    if "temperature" in ql: return "Global mean surface T ≈210 K (−63 °C).", ["NASA Mars facts; REMS"]
    if any(w in ql for w in ["sun","distance","au","far"]): return "Mars orbits at 1.38–1.67 AU from the Sun.", ["NASA Mars facts"]
    return (f"Mars: gravity {P['gravity']} m/s² · sol 24.66 h · year 687 d · pressure ~{P['datumPressure_mbar']} mbar.", ["NASA Mars facts"])

# ---- remote LLM (OpenAI-compatible, optional) -----------------------------
def _remote_llm(prompt, system):
    url=os.environ.get("NAM_LLM_API_URL")
    key=os.environ.get("NAM_LLM_API_KEY","")
    model=os.environ.get("NAM_LLM_MODEL","gpt-4o-mini")
    if not url: return None
    body=json.dumps({"model":model,"messages":[{"role":"system","content":system},
                                               {"role":"user","content":prompt}],
                     "temperature":0.2,"max_tokens":400}).encode()
    req=urllib.request.Request(url, data=body, headers={
        "Content-Type":"application/json",
        "Authorization":f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data=json.loads(r.read())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[remote LLM unavailable: {type(e).__name__}]"

# ---- main entry -----------------------------------------------------------
def answer(q, lang="en"):
    q=(q or "").strip()
    if not q: return {"error":"empty query"}
    cls=classify(q)
    intent=cls["intent"]; conf=cls["conf"]
    docs=retrieve(q, k=3)
    # local answer
    local_text, src = _local_answer(intent, q, docs)
    engine="local"
    text=local_text
    # hybrid: feed grounding to remote LLM only if configured
    remote=os.environ.get("NAM_LLM_API_URL")
    if remote and intent and conf>=0.4:
        facts="\n".join(f"- {d['name']}: {d['desc'][:160]}" for d in docs) or "(no matching catalog entries)"
        sysp=("You are NAM, a Mars navigation assistant. Answer the user using ONLY the "
              "grounding facts provided. If they are insufficient, say so plainly. "
              "Cite sources by name. Never invent coordinates, elevations or observations.")
        prompt=f"User question: {q}\nDetected intent: {intent}\nGrounding facts:\n{facts}\nAnswer:"
        r=_remote_llm(prompt, sysp)
        if r and not r.startswith("[remote"):
            text=r; engine="hybrid"; src=list(src)
            for d in docs: src += d.get("src",[])
    return {"query":q,"lang":lang,"intent":intent,"confidence":round(conf,4),
            "engine":engine,"answer":text,"sources":list(dict.fromkeys(src)),
            "retrieved":docs,"top_intents":cls["top"]}

def _local_answer(intent, q, docs):
    P=_gaz()["PLANET"]
    if intent=="planet_fact": return planet_fact(q)
    if intent=="feature_info" and docs:
        d=docs[0]
        s=f"{d['name']} ({d['type']}"+(f", {d['elev']} m" if d.get('elev') is not None else "")+"): "+d['desc']
        return s, d.get('src',[])
    if intent=="mission_site_info" and docs:
        d=docs[0]; return f"{d['name']}: {d['desc']}", d.get('src',[])
    if intent=="instrument_info" and docs:
        d=docs[0]; return f"{d['name']}: {d['desc']}", d.get('src',[])
    if intent=="tallest_deepest":
        return ("Olympus Mons is the tallest known volcano (~21.3 km above the MOLA areoid). "
                "Hellas Planitia is the deepest large basin (~-8 km)."), ["MOLA: Smith et al. 2001","IAU Gazetteer"]
    if intent in ("greet","help","thanks","model_info"):
        return ("NAM hybrid AI: local TF-IDF+LogReg classifier + retrieval over the embedded "
                "Mars catalog" + (" + remote LLM phrasing" if os.environ.get("NAM_LLM_API_URL") else " (local-only)") +
                ". Ask about features, terrain, routes, landing sites, or planet facts."), []
    if intent:
        return f"Understood — intent '{intent}' (confidence {int(round(classify(q)['conf']*100))}%). "+(
            "Relevant catalog entries: "+", ".join(d['name'] for d in docs) if docs else
            "Use the /terrain, /route/plan or /landing/score endpoints for the action."), []
    return ("I couldn't confidently classify that. I can answer about Mars features, terrain, "
            "routes, landing sites and planet facts, in 9 languages."), []

if __name__=="__main__":
    import sys
    for q in sys.argv[1:] or ["What is the gravity on Mars","Tell me about Olympus Mons","带我去奥林匹斯山"]:
        print("\nQ:",q)
        print(json.dumps(answer(q, "en" if re.match(r"[A-Za-z]",q) else "zh"), ensure_ascii=False, indent=1)[:700])

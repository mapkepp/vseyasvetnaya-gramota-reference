#!/usr/bin/env python3
"""Free/optional external-AI router for the research toolbox.

The router is deliberately capability-first: use free/public/local backends when
available, escalate only when a task needs it, and never require a paid API.
Supported backends:
- local Ollama (no API key, when a self-hosted runner exposes OLLAMA_HOST)
- Hugging Face Inference (optional HF_TOKEN)
- OpenAI-compatible endpoint (optional EXTERNAL_AI_BASE_URL + EXTERNAL_AI_API_KEY)
The GitHub Actions worker can run without any backend; discovery remains functional.
"""
import json, os, sys, urllib.request, urllib.error

def post_json(url, payload, headers=None, timeout=45):
    h={"Content-Type":"application/json","User-Agent":"vseyasvetnaya-toolbox/ai-router"}
    if headers: h.update(headers)
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers=h,method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8","replace"))

def ollama(prompt):
    host=os.getenv("OLLAMA_HOST","").rstrip("/")
    if not host: return None
    model=os.getenv("OLLAMA_MODEL","qwen3:8b")
    try:
        d=post_json(host+"/api/chat",{"model":model,"messages":[{"role":"user","content":prompt}],"stream":False})
        return {"provider":"ollama","model":model,"text":d.get("message",{}).get("content","")}
    except Exception as e:
        return {"provider":"ollama","status":"ERROR","error":type(e).__name__}

def huggingface(prompt):
    token=os.getenv("HF_TOKEN")
    model=os.getenv("HF_MODEL","Qwen/Qwen3-8B")
    if not token: return None
    url="https://router.huggingface.co/v1/chat/completions"
    try:
        d=post_json(url,{"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":1200},
                    {"Authorization":"Bearer "+token})
        text=d.get("choices",[{}])[0].get("message",{}).get("content","")
        return {"provider":"huggingface","model":model,"text":text}
    except Exception as e:
        return {"provider":"huggingface","status":"ERROR","error":type(e).__name__}

def compatible(prompt):
    base=os.getenv("EXTERNAL_AI_BASE_URL","").rstrip("/")
    key=os.getenv("EXTERNAL_AI_API_KEY")
    model=os.getenv("EXTERNAL_AI_MODEL","")
    if not base or not key or not model: return None
    try:
        d=post_json(base+"/chat/completions",{"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":1200},
                    {"Authorization":"Bearer "+key})
        text=d.get("choices",[{}])[0].get("message",{}).get("content","")
        return {"provider":"openai-compatible","model":model,"text":text}
    except Exception as e:
        return {"provider":"openai-compatible","status":"ERROR","error":type(e).__name__}

def ask(prompt):
    # Cheap-first: local -> optional HF -> optional compatible endpoint.
    for fn in (ollama, huggingface, compatible):
        result=fn(prompt)
        if result and result.get("text"): return result
    return {"provider":"none","status":"UNAVAILABLE","text":""}

if __name__=="__main__":
    prompt=" ".join(sys.argv[1:]).strip()
    print(json.dumps(ask(prompt),ensure_ascii=False))

"""Lab-only OpenAI-compatible embedding provider; not an MCP server.
Run with uvicorn on an explicitly selected lab interface. Production reuses
an approved embedding endpoint. Token usage is not measured here.
"""
from fastapi import FastAPI, HTTPException
from sentence_transformers import SentenceTransformer
import torch, base64, struct
from pydantic import BaseModel

torch.set_num_threads(2)
model=SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2',revision='1110a243fdf4706b3f48f1d95db1a4f5529b4d41',device='cpu')
app=FastAPI()
class Request(BaseModel):
    model: str
    input: str | list[str]
    encoding_format: str = "float"
@app.get('/health')
def health(): return {'ready':True,'dimension':384}
@app.post('/v1/embeddings')
def embeddings(req:Request):
    if req.model != 'all-MiniLM-L6-v2': raise HTTPException(400,'unknown model')
    texts=[req.input] if isinstance(req.input,str) else req.input
    if len(texts)>64 or any(len(t)>32000 for t in texts): raise HTTPException(413,'input limit')
    vectors=model.encode(texts,normalize_embeddings=True).tolist()
    return {'object':'list','model':req.model,'data':[{'object':'embedding','index':i,'embedding':base64.b64encode(struct.pack('<384f',*v)).decode() if req.encoding_format=='base64' else v} for i,v in enumerate(vectors)]}

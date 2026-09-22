import fs from 'node:fs';
import path from 'node:path';
export default async function handler(req,res){
  res.setHeader('Cache-Control','no-store');
  const incoming=new URL(req.url,'https://store.invalid');
  const routedPath=incoming.searchParams.get('route');
  const requestPath=routedPath?'/api/'+routedPath:incoming.pathname;
  const origin=process.env.AWS_BACKEND_ORIGIN;
  if(!origin){
    if(req.method==='GET'&&/\/api\/catalog\/?$/.test(requestPath)){
      const catalog=JSON.parse(fs.readFileSync(path.join(process.cwd(),'api','catalog-preview.json'),'utf8'));
      return res.status(200).json({...catalog,preview_only:true,payments_ready:false});
    }
    if(req.method==='GET'&&/\/api\/session\/?$/.test(requestPath))return res.status(200).json({user:null,csrf:'',preview_only:true});
    return res.status(503).json({detail:'The store backend is not connected yet. Accounts, checkout and feedback will open after setup.'});
  }
  try{
    const base=new URL(origin);
    if(base.protocol!=='https:')throw new Error('HTTPS backend required');
    if(!requestPath.startsWith('/api/'))return res.status(404).end();
    const target=new URL(requestPath.endsWith('/')?requestPath:requestPath+'/',base.origin);
    incoming.searchParams.delete('route');target.search=incoming.searchParams.toString();
    target.host=base.host;target.protocol=base.protocol;
    const headers={Accept:'application/json','Content-Type':'application/json'};
    for(const key of ['cookie','x-csrftoken','origin','referer'])if(req.headers[key])headers[key]=req.headers[key];
    const upstream=await fetch(target,{method:req.method,headers,redirect:'manual',signal:AbortSignal.timeout(25000),...(!['GET','HEAD'].includes(req.method)?{body:typeof req.body==='string'?req.body:JSON.stringify(req.body??{})}:{})});
    const cookies=upstream.headers.getSetCookie();
    if(cookies.length)res.setHeader('Set-Cookie',cookies);
    res.setHeader('Content-Type',upstream.headers.get('content-type')||'application/json');
    return res.status(upstream.status).send(Buffer.from(await upstream.arrayBuffer()));
  }catch{return res.status(502).json({detail:'The store service is temporarily unavailable. Please try again.'});}
}

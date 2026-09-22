let csrf='';
export function setCsrf(value){csrf=value;}
function errorText(value){if(typeof value==='string')return value;if(Array.isArray(value))return value.map(errorText).join(' ');return Object.entries(value).map(([k,v])=>`${k==='detail'?'':k+': '}${errorText(v)}`).join(' ');}
export async function api(path,method='GET',body){
 const response=await fetch('/api/'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},...(body===undefined?{}:{body:JSON.stringify(body)})});
 let data;try{data=await response.json();}catch{throw new Error('The store service is unavailable. Please try again.');}
 if(!response.ok)throw new Error(errorText(data));if(data.csrf)csrf=data.csrf;return data;
}

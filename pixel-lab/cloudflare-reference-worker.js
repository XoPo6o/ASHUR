export default {
 async fetch(request, env) {
  const origin=request.headers.get("Origin")||"";
  const allowed=new Set(["https://xopo6o.github.io"]);
  const cors={"Access-Control-Allow-Origin":allowed.has(origin)?origin:"https://xopo6o.github.io","Access-Control-Allow-Methods":"GET,POST,OPTIONS","Access-Control-Allow-Headers":"Authorization,Content-Type","Vary":"Origin"};
  if(request.method==="OPTIONS") return new Response(null,{headers:cors});
  const url=new URL(request.url);
  if(request.method==="GET"&&url.pathname==="/api/list"){
   const listed=await env.ASHUR_REFERENCES.list({limit:1000});
   return Response.json({objects:listed.objects.map(o=>({key:o.key,title:o.customMetadata?.title||o.key,category:o.customMetadata?.category||"other"}))},{headers:cors});
  }
  if(request.method==="GET"&&url.pathname.startsWith("/files/")){
   const key=decodeURIComponent(url.pathname.slice(7)); if(!key||key.includes("..")) return new Response("Bad key",{status:400,headers:cors});
   const obj=await env.ASHUR_REFERENCES.get(key); if(!obj)return new Response("Not found",{status:404,headers:cors});
   const h=new Headers(cors);obj.writeHttpMetadata(h);h.set("etag",obj.httpEtag);h.set("Cache-Control","public, max-age=3600");return new Response(obj.body,{headers:h});
  }
  if(request.method==="POST"&&url.pathname==="/api/upload"){
   if(!env.UPLOAD_TOKEN||(request.headers.get("Authorization")||"")!=="Bearer "+env.UPLOAD_TOKEN)return new Response("Unauthorized",{status:401,headers:cors});
   const form=await request.formData(),file=form.get("file"),category=String(form.get("category")||"other").slice(0,32),title=String(form.get("title")||"").slice(0,100);
   if(!(file instanceof File))return new Response("Missing file",{status:400,headers:cors});
   if(file.size>10*1024*1024)return new Response("File too large",{status:413,headers:cors});
   const types={"image/png":"png","image/jpeg":"jpg","image/webp":"webp","image/gif":"gif"},ext=types[file.type];if(!ext)return new Response("Unsupported image type",{status:415,headers:cors});
   const safe=title.replace(/[^a-zA-Z0-9а-яА-ЯёЁ_-]+/g,"-").replace(/^-+|-+$/g,"").slice(0,60)||"reference";
   const key=category+"/"+Date.now()+"-"+crypto.randomUUID().slice(0,8)+"-"+safe+"."+ext;
   await env.ASHUR_REFERENCES.put(key,file.stream(),{httpMetadata:{contentType:file.type},customMetadata:{title,category}});
   return Response.json({ok:true,key,url:url.origin+"/files/"+encodeURIComponent(key)},{headers:cors});
  }
  return new Response("ASHUR Reference Library",{headers:cors});
 }
};
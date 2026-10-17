const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const listeners={},entries=new Map(),deleted=[];
const base='https://example.test/Max-Min/';let mode='ok',calls=0,options;
const key=r=>typeof r==='string'?new URL(r,base).href:r.url;
const good={ok:true,clone(){return this;}};
const cache={addAll:async()=>{},put:async(r,v)=>entries.set(key(r),v),keys:async()=>[...entries.keys()].map(url=>({url})),delete:async r=>entries.delete(key(r))};
const caches={open:async()=>cache,keys:async()=>['maxmin-old','other-app'],delete:async k=>deleted.push(k),match:async r=>entries.get(key(r))};
const self={location:{origin:'https://example.test',href:base+'sw.js'},addEventListener:(type,fn)=>listeners[type]=fn,skipWaiting:async()=>{},clients:{claim:async()=>{}}};
vm.runInNewContext(fs.readFileSync('sw.js','utf8'),{self,caches,URL,Response,fetch:async(r,o)=>{calls++;options=o;if(mode==='offline')throw new Error('offline');return mode==='503'?{ok:false}:good;},setTimeout,clearTimeout});
async function request(url,kind){let response;const pending=[];listeners.fetch({request:{url,method:'GET',mode:kind},respondWith:r=>response=r,waitUntil:p=>pending.push(p)});if(!response)return undefined;const r=await response;await Promise.all(pending);return r;}
(async()=>{
 let pending;listeners.activate({waitUntil:p=>pending=p});await pending;assert.deepEqual(deleted,['maxmin-old']);
 for(const path of ['updates/incoming/Max.csv','sources/Directorio.xlsx'])assert.equal(await request(base+path),undefined);
 const data=base+'data/stores_01/38101.json?v=revision1';entries.set(data,{old:true});
 assert.equal(await request(data),good);assert.equal(options.cache,'no-store');assert.equal(entries.get(data),good);
 mode='503';assert.equal(await request(data),good);assert.equal(entries.get(data),good);
 mode='offline';assert.equal(await request(data),good);assert.equal((await request(base+'data/stores_01/99999.json')).type,'error');
 entries.set(base+'index.html',good);assert.equal(await request(base,'navigate'),good);
 mode='ok';for(let n=0;n<205;n++)entries.set(base+'data/stores_01/'+n+'.json?v=x',good);
 await request(data);assert([...entries.keys()].filter(x=>/stores_/.test(x)).length<=200);
 const js=base+'js/app.js';entries.set(js,good);const before=calls;assert.equal(await request(js),good);assert.equal(calls,before);
 console.log(JSON.stringify({status:'ok',checks:12,maximumStoreCache:200}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});

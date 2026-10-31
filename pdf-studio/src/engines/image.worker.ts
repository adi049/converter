/// <reference lib="webworker" />
import { PDFDocument, rgb } from 'pdf-lib';
const scope=self as unknown as DedicatedWorkerGlobalScope;
scope.onmessage=async(event:MessageEvent)=>{
 const {id,operation,file,options:o}=event.data;
 try{
  let blob:Blob,name:string;
  if(operation==='images-pdf'){
   const pdf=await PDFDocument.create();const sizes:Record<string,[number,number]>={a4:[595.28,841.89],a3:[841.89,1190.55],letter:[612,792],legal:[612,1008],a5:[419.53,595.28]};
   for(let k=0;k<o.files.length;k++){
    const f=o.files[k];const bitmap=await createImageBitmap(f);const canvas=new OffscreenCanvas(bitmap.width,bitmap.height);const ctx=canvas.getContext('2d')!;ctx.drawImage(bitmap,0,0);const bytes=await canvas.convertToBlob({type:'image/png'}).then(b=>b.arrayBuffer());const image=await pdf.embedPng(bytes);
    let size=sizes[o.pageSize]||sizes.a4;if(o.pageSize==='custom')size=[Number(o.width||210)*72/25.4,Number(o.height||297)*72/25.4];if(o.orientation==='landscape')size=[size[1],size[0]];
    const fit=o.fitPage!==false;const w=fit?size[0]:image.width,h=fit?size[1]:image.height;const page=pdf.addPage([w,h]);const scale=Math.min(w/image.width,h/image.height,fit?Infinity:1);const iw=image.width*scale,ih=image.height*scale;page.drawImage(image,{x:(w-iw)/2,y:(h-ih)/2,width:iw,height:ih});bitmap.close();scope.postMessage({id,progress:Math.round((k+1)/o.files.length*100)});
   }
   blob=new Blob([await pdf.save()],{type:'application/pdf'});name=(o.filename||'Images document')+'.pdf';
  }else{
   const source=await createImageBitmap(file);let sw=source.width,sh=source.height,sx=0,sy=0;
   if(o.crop){sx=Math.round(o.crop.x*sw);sy=Math.round(o.crop.y*sh);const nw=Math.round(o.crop.width*sw),nh=Math.round(o.crop.height*sh);if(sx>=source.width||sy>=source.height||nw<1||nh<1)throw new Error('Crop area is empty.');sw=Math.min(nw,source.width-sx);sh=Math.min(nh,source.height-sy);}
   let tw=sw,th=sh;
   if(o.width||o.height){tw=o.width?Number(o.width):Math.round(sw*Number(o.height)/sh);th=o.height?Number(o.height):Math.round(sh*Number(o.width)/sw);if(o.keepAspect!==false){const scale=Math.min(o.width?Number(o.width)/sw:Infinity,o.height?Number(o.height)/sh:Infinity);tw=Math.round(sw*scale);th=Math.round(sh*scale);}}
   if(tw<1||th<1||tw>12000||th>12000||tw*th>40000000)throw new Error('Output must be under 40 megapixels and 12,000 pixels per side.');
   const rotate=Number(o.rotation||0),rad=rotate*Math.PI/180;const rw=Math.ceil(Math.abs(tw*Math.cos(rad))+Math.abs(th*Math.sin(rad))),rh=Math.ceil(Math.abs(tw*Math.sin(rad))+Math.abs(th*Math.cos(rad)));
   if(rw>12000||rh>12000||rw*rh>40000000)throw new Error('Rotated output exceeds the 40 megapixel safety limit.');
   const canvas=new OffscreenCanvas(rw,rh),ctx=canvas.getContext('2d',{willReadFrequently:true})!;
   if(o.format==='jpg'){ctx.fillStyle=o.background||'#ffffff';ctx.fillRect(0,0,rw,rh);}
   ctx.translate(rw/2,rh/2);ctx.rotate(rad);ctx.filter=`brightness(${Number(o.brightness??100)}%) contrast(${Number(o.contrast??100)}%)`;ctx.drawImage(source,sx,sy,sw,sh,-tw/2,-th/2,tw,th);ctx.filter='none';ctx.rotate(-rad);ctx.translate(-rw/2,-rh/2);
   if(o.removeBackground){
    const image=ctx.getImageData(0,0,rw,rh),d=image.data;const threshold=Number(o.tolerance??35);const seen=new Uint8Array(rw*rh),q=new Int32Array(rw*rh);let head=0,tail=0;
    const add=(p:number)=>{if(p<0||p>=rw*rh||seen[p])return;seen[p]=1;const j=p*4;if(Math.min(d[j],d[j+1],d[j+2])>255-threshold&&Math.max(d[j],d[j+1],d[j+2])-Math.min(d[j],d[j+1],d[j+2])<threshold){q[tail++]=p;d[j+3]=0;}};
    for(let x=0;x<rw;x++){add(x);add((rh-1)*rw+x);}for(let y=0;y<rh;y++){add(y*rw);add(y*rw+rw-1);}
    while(head<tail){const p=q[head++];if(p%rw>0)add(p-1);if(p%rw<rw-1)add(p+1);add(p-rw);add(p+rw);}ctx.putImageData(image,0,0);
   }
   if(o.watermark||o.logo){ctx.save();ctx.translate(rw*Number(o.x??50)/100,rh*Number(o.y??50)/100);ctx.rotate(Number(o.angle??30)*Math.PI/180);ctx.globalAlpha=Math.max(0,Math.min(1,Number(o.opacity??.3)));const size=Math.max(12,Number(o.fontSize??Math.round(rw/12)));if(o.logo){const logo=await createImageBitmap(o.logo);const w=Math.min(rw*.8,size*4),h=w*logo.height/logo.width;ctx.drawImage(logo,-w/2,-h/2,w,h);logo.close();}else{ctx.fillStyle=o.color||'#7657dc';ctx.font=`bold ${size}px ${o.font||'Arial'}`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(o.watermark),0,0);}ctx.restore();}
   const format:string=o.removeBackground?'png':modeFormat(o.format);const mime=format==='jpg'?'image/jpeg':format==='webp'?'image/webp':'image/png';blob=await canvas.convertToBlob({type:mime,quality:Number(o.quality??85)/100});name=(file.name.replace(/\.[^.]+$/,''))+(o.suffix||'-edited')+'.'+format;source.close();
  }
  scope.postMessage({id,result:{blob,name,size:blob.size}});
 }catch(e){scope.postMessage({id,error:e instanceof Error?e.message:'Image processing failed.'});}
};

function modeFormat(value:string){return value==='jpeg'?'jpg':['png','jpg','webp'].includes(value)?value:'png';}

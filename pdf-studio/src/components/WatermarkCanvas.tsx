import {useEffect,useRef,useState} from 'react';
import type {Watermark} from '../lib/types';
import {watermarkTiles} from '../lib/watermarkGeometry';
export function WatermarkCanvas({wm,width,height,logoUrl,fontUrl}:{wm:Watermark;width:number;height:number;logoUrl?:string;fontUrl?:string}){
 const ref=useRef<HTMLCanvasElement>(null);const [fontReady,setFontReady]=useState(0);
 useEffect(()=>{if(!fontUrl){setFontReady(x=>x+1);return;}let live=true;const face=new FontFace('StudioWatermark',`url(${fontUrl})`);face.load().then(f=>{if(live){document.fonts.add(f);setFontReady(x=>x+1);}}).catch(()=>{});return()=>{live=false;document.fonts.delete(face);};},[fontUrl]);
 useEffect(()=>{const c=ref.current;if(!c||!wm.enabled)return;const ctx=c.getContext('2d')!;const dpr=Math.min(devicePixelRatio||1,2);c.width=width*dpr;c.height=height*dpr;ctx.scale(dpr,dpr);ctx.clearRect(0,0,width,height);let cancelled=false;let image:HTMLImageElement|null=null;
  const draw=()=>{if(cancelled)return;const scale=width/620; // normalized against PDF point dimensions supplied below
  };
  const render=(pw:number,ph:number)=>{if(cancelled)return;const s=width/pw;ctx.clearRect(0,0,width,height);ctx.save();ctx.scale(s,s);ctx.globalAlpha=wm.opacity;ctx.fillStyle=wm.color;ctx.font=`${wm.fontSize}px ${fontUrl?'StudioWatermark':wm.font==='Times'?'Liberation Serif,serif':wm.font==='Courier'?'Liberation Mono,monospace':'Liberation Sans,Arial,sans-serif'}`;ctx.textAlign='center';ctx.textBaseline='middle';const tw=wm.type==='image'&&image?wm.imageWidth:ctx.measureText(wm.text).width;const th=wm.type==='image'&&image?wm.imageWidth*image.naturalHeight/image.naturalWidth:wm.fontSize;
   for(const [x,y] of watermarkTiles(wm,pw,ph,tw,th)){ctx.save();ctx.translate(x,y);ctx.rotate(wm.rotation*Math.PI/180);if(wm.type==='image'&&image)ctx.drawImage(image,-tw/2,-th/2,tw,th);else ctx.fillText(wm.text,0,wm.fontSize*.08);ctx.restore();}ctx.restore();};
  // Width/height props are the actual PDF page dimensions, not CSS pixels.
  if(wm.type==='image'&&logoUrl){image=new Image();image.onload=()=>render(width,height);image.src=logoUrl;}else render(width,height);
  return()=>{cancelled=true;};
 },[wm,width,height,logoUrl,fontUrl,fontReady]);
 return <canvas ref={ref} className="watermark-overlay" aria-label="Live watermark placement preview" style={{width:'100%',height:'100%',mixBlendMode:wm.layer==='under'?'multiply':'normal'}}/>;
}

import type {Watermark} from './types';
export function watermarkGeometry(w:Watermark,pw:number,ph:number,tw:number,th:number){
 const margin=Math.max(0,Math.min(w.margin??24,Math.min(pw,ph)/3));const align=w.align||'center',valign=w.valign||'middle';
 let x=({left:margin+tw/2,center:pw/2,right:pw-margin-tw/2} as Record<string,number>)[align]??pw/2;
 let y=({top:margin+th/2,middle:ph/2,bottom:ph-margin-th/2} as Record<string,number>)[valign]??ph/2;
 if(w.position==='custom'){x=w.unit==='pt'?w.x:w.x/100*pw;y=w.unit==='pt'?w.y:w.y/100*ph;}
 else if(['top','bottom','left','right','center','diagonal'].includes(w.position)){[x,y]=({top:[pw/2,margin+th/2],bottom:[pw/2,ph-margin-th/2],left:[margin+tw/2,ph/2],right:[pw-margin-tw/2,ph/2],center:[pw/2,ph/2],diagonal:[pw/2,ph/2]} as Record<string,number[]>)[w.position];}
 const a=w.rotation*Math.PI/180,bw=Math.abs(tw*Math.cos(a))+Math.abs(th*Math.sin(a)),bh=Math.abs(tw*Math.sin(a))+Math.abs(th*Math.cos(a));
 x=Math.max(margin+bw/2,Math.min(pw-margin-bw/2,x));y=Math.max(margin+bh/2,Math.min(ph-margin-bh/2,y));return {x,y,bw,bh};
}
export function watermarkTiles(w:Watermark,pw:number,ph:number,tw:number,th:number){const g=watermarkGeometry(w,pw,ph,tw,th);if(!w.tile)return [[g.x,g.y]];const cols=Math.min(30,Math.max(1,Math.ceil(pw/(g.bw+(w.gap||0))))),rows=Math.min(30,Math.max(1,Math.ceil(ph/(g.bh+(w.gap||0)))));return Array.from({length:rows*cols},(_,i)=>[(i%cols+.5)*pw/cols,(Math.floor(i/cols)+.5)*ph/rows]);}

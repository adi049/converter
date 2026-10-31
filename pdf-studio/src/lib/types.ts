export type Page = 'dashboard'|'tools'|'library'|'history'|'create'|'watermark'|'editor'|'organize'|'images'|'templates'|'settings'|'tool';
export interface StudioFile { id:string; name:string; size:number; created:number; modified:number; ext?:string; pages?:number|null; encrypted?:boolean; kind?:string; originalSize?:number; reduction?:number; [key:string]:unknown; }
export interface Job { id:string; operation:string; fileIds:string[]; status:'queued'|'running'|'complete'|'error'|'cancelled'; message:string; percent:number|null; created:number; finished?:number; results:StudioFile[]; notes:string[]; error?:string; }
export interface HistoryItem { id:string; tool:string; filename:string; date:number; status:string; outputs:number; bytes:number; notes?:string[]; }
export interface LibraryItem { id:string; name:string; size:number; type:string; created:number; modified:number; opened:number; sourceCreated?:number; sourceModified?:number; folder:string; favorite:boolean; blob:Blob; }
export interface Folder { id:string; name:string; }
export interface ToolOptions { [key:string]:any; }
export interface Watermark { enabled:boolean; type:'text'|'image'; text:string; font:string; fontSize:number; color:string; opacity:number; rotation:number; position:string; x:number; y:number; tile:boolean; gap:number; imageWidth:number; align?:string; valign?:string; margin?:number; layer?:'over'|'under'; fontId?:string; fontName?:string; unit?:'percent'|'pt'; imageId?:string; imageName?:string; }
export interface Preset { id:string; name:string; watermark:Watermark; }
export interface Settings { theme?:'studio'; history:boolean; defaultDpi:number; defaultQuality:number; ocrLanguage:string; reduceMotion:boolean; }
export interface Capability { engines:Record<string,{available:boolean;version?:string}>; languages:string[]; limits:{fileMB:number;sessionMB:number;concurrentJobs:number;tempTTLMinutes:number}; }
export interface Annotation { id:string; page:number; type:string; rect?:number[]; points?:number[][]; text?:string; color:string; width:number; fontSize?:number; fileId?:string; }
export interface ToolDefinition { id:string; operation:string; title:string; description:string; category:string; icon:string; accept:string; multiple?:boolean; minFiles?:number; maxFiles?:number; badge?:string; limitation?:string; fields?:Field[]; defaults?:ToolOptions; }
export interface Field { key:string; label:string; type?:'text'|'textarea'|'number'|'select'|'checkbox'|'color'|'password'|'json'; placeholder?:string; options?:{value:string;label:string}[]; default?:any; min?:number; max?:number; help?:string; }

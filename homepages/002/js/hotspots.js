(() => {
'use strict';
const $ = id => document.getElementById(id);
const moduleBase = new URL('../', document.currentScript.src);
const editingEnabled = new URLSearchParams(location.search).get('edit') === '1';
const STORAGE_KEY = 'map-viewer-v003-hotspots';
let viewer, config, homeZoom, data=[], overlays=new Map(), selected=null, editorOpen=editingEnabled, lastActive=null;
const editor=$('editor'), form=$('hotspot-form'), pop=$('hotspot-popover');
let popoverCloseTimer=null;
// A hotspot press may also trigger an OpenSeadragon canvas-click.
// Remember it briefly so selecting an existing dot cannot add a second dot.
let lastHotspotPress=0;
function cancelPopoverClose(){if(popoverCloseTimer!==null){clearTimeout(popoverCloseTimer);popoverCloseTimer=null;}}
function schedulePopoverClose(){cancelPopoverClose();popoverCloseTimer=setTimeout(()=>{closePopover();popoverCloseTimer=null;},180);}
const status=message => $('editor-status').textContent=message;
const key=p=>`${p.region}:${p.x}:${p.y}:${p.label}`;
const regionId=(x,y)=>`x${x}_y${y}`;
const knownRegion=region=>config.regions.some(r=>region===regionId(r.x,r.y));
const validUrl=url=>{try{const u=new URL(url,location.href);return ['https:','http:','mailto:'].includes(u.protocol);}catch{return false;}};
const text=(node,value)=>{node.textContent=value||'';};
function normalize(h){
 const region=String(h.region||'');const x=Number(h.x),y=Number(h.y);
 if(!knownRegion(region)||!Number.isFinite(x)||!Number.isFinite(y)||x<0||x>=config.regionSize||y<0||y>=config.regionSize)throw Error(`Invalid hotspot coordinates: ${region} ${x},${y}`);
 const action=h.action==='modal'?'modal':'link';const url=String(h.url||'').trim();
 if(action==='link'&&!validUrl(url))throw Error('Link hotspots need a valid http(s) or mailto URL.');
 return {id:String(h.id||`spot-${Date.now()}-${Math.random().toString(36).slice(2,7)}`),region,x:Math.round(x),y:Math.round(y),label:String(h.label||'Artwork detail').slice(0,140),action,url:action==='link'?url:'',content:action==='modal'?String(h.content||''):'',minZoom:Math.max(1,Number(h.minZoom)||1.5),reveal:Math.max(.1,Math.min(1.5,Number(h.reveal)||.9))};
}
function worldPoint(h){const m=/^x(-?\d+)_y(-?\d+)$/.exec(h.region);return new OpenSeadragon.Point(Number(m[1])+h.x/config.regionSize,Number(m[2])+h.y/config.regionSize);}
function positionPopover(h){const xy=viewer.viewport.pixelFromPoint(worldPoint(h),true);const box=viewer.element.getBoundingClientRect();pop.style.left=`${Math.max(110,Math.min(window.innerWidth-110,box.left+xy.x))}px`;pop.style.top=`${Math.max(85,box.top+xy.y-15)}px`;}
function closePopover(){cancelPopoverClose();pop.hidden=true;lastActive=null;}
function showPopover(h){closePopover();pop.replaceChildren();const strong=document.createElement('strong');text(strong,h.label);pop.append(strong);const action=document.createElement(h.action==='link'?'a':'button');text(action,h.action==='link'?'Open link':'View details');if(h.action==='link'){action.href=h.url;action.rel='noopener noreferrer';if(/^https?:/.test(new URL(h.url,location.href).protocol))action.target='_blank';}else{action.type='button';action.addEventListener('click',()=>showModal(h));}pop.append(action);pop.hidden=false;lastActive=h;positionPopover(h);}
function showModal(h){closePopover();text($('modal-title'),h.label);text($('modal-body'),h.content);$('hotspot-modal').hidden=false;$('close-modal').focus();}
function updateVisibility(){if(!viewer)return;const ratio=viewer.viewport.getZoom(true)/homeZoom;const width=viewer.element.clientWidth||1,height=viewer.element.clientHeight||1;
 for(const h of data){const el=overlays.get(h.id);if(!el)continue;const pt=viewer.viewport.pixelFromPoint(worldPoint(h),true);const norm=Math.sqrt(((pt.x-width/2)/(width/2))**2+((pt.y-height/2)/(height/2))**2);const fade=Math.min(1,Math.max(0,(h.reveal-norm)/.35));const zoomFade=Math.min(1,Math.max(0,(ratio-h.minZoom)/.3));const alpha=editorOpen?1:fade*zoomFade;el.style.opacity=String(alpha);el.style.pointerEvents=alpha>.2?'auto':'none';el.tabIndex=alpha>.2?0:-1;}
 if(lastActive&&!editorOpen){const h=lastActive;const el=overlays.get(h.id);if(!el||Number(el.style.opacity)<.2)closePopover();else positionPopover(h);}
}
function render(){for(const el of overlays.values())viewer.removeOverlay(el);overlays.clear();closePopover();
 for(const h of data){const el=document.createElement('button');el.type='button';el.className='hotspot';el.setAttribute('aria-label',h.label);el.title=editorOpen?'Edit: '+h.label:h.label;
 el.addEventListener('pointerdown',ev=>{lastHotspotPress=Date.now();ev.stopPropagation();});
 el.addEventListener('click',ev=>{lastHotspotPress=Date.now();ev.preventDefault();ev.stopPropagation();if(editorOpen)edit(h.id);else showPopover(h);});
 el.addEventListener('mouseenter',()=>{cancelPopoverClose();if(!editorOpen&&Number(el.style.opacity)>.2)showPopover(h);});
 el.addEventListener('mouseleave',schedulePopoverClose);
 el.addEventListener('focus',()=>{if(!editorOpen)showPopover(h);});
 viewer.addOverlay({element:el,location:worldPoint(h),placement:OpenSeadragon.Placement.CENTER,checkResize:false});overlays.set(h.id,el);
 }updateVisibility();}
function saveLocal(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(data));}catch{status('Local save unavailable. Export a file to preserve edits.');}}
function edit(id){const h=data.find(p=>p.id===id);if(!h)return;selected=id;form.hidden=false;for(const name of ['region','x','y','label','action','url','content','minZoom','reveal'])form.elements[name].value=h[name];toggleAction();status('Editing '+h.label);}
function toggleAction(){const isLink=form.elements.action.value==='link';$('url-label').hidden=!isLink;$('content-label').hidden=isLink;}
function setEditor(on){editorOpen=on;editor.hidden=!on;$('show-editor').hidden=!editingEnabled||on;document.body.classList.toggle('editing',on);/* Panning remains available in editor; a brief click or tap places a dot. */render();}
function addAt(position){const p=viewer.viewport.pointFromPixel(position,true);const rx=Math.floor(p.x),ry=Math.floor(p.y),region=regionId(rx,ry);
 if(!knownRegion(region)){status('Click within an occupied region to place a dot.');return;}
 const x=Math.max(0,Math.min(4095,Math.round((p.x-rx)*config.regionSize))),y=Math.max(0,Math.min(4095,Math.round((p.y-ry)*config.regionSize)));
 const h={id:`spot-${Date.now()}-${Math.random().toString(36).slice(2,7)}`,region,x,y,label:'Artwork detail',action:'link',url:'https://example.com',content:'',minZoom:1.5,reveal:.9};data.push(h);saveLocal();render();edit(h.id);}
function escapeMD(s){return String(s||'').replace(/\r/g,'').replace(/\n/g,'\\n');}
function markdown(){return '# Map Hotspots\n\n'+data.map(h=>`## ${escapeMD(h.label)}\n\nID: ${h.id}\nREGION: ${h.region}\nX: ${h.x}\nY: ${h.y}\nACTION: ${h.action}\nURL: ${escapeMD(h.url)}\nCONTENT: ${escapeMD(h.content)}\nMIN_ZOOM: ${h.minZoom}\nREVEAL: ${h.reveal}\n`).join('\n');}
function parseMD(md){return md.split(/^## /m).slice(1).map(section=>{const lines=section.split(/\r?\n/);const h={label:lines.shift().trim()};for(const line of lines){const m=/^([A-Z_]+):\s*(.*)$/.exec(line);if(!m)continue;const prop={ID:'id',REGION:'region',X:'x',Y:'y',ACTION:'action',URL:'url',CONTENT:'content',MIN_ZOOM:'minZoom',REVEAL:'reveal'}[m[1]];if(prop)h[prop]=m[2].replace(/\\n/g,'\n');}return normalize(h);});}
function download(name,content,type){const blob=new Blob([content],{type});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function initialize(e){({viewer,config,homeZoom}=e.detail);try{const r=await fetch(new URL('config/hotspots.json',moduleBase),{cache:'no-store'});if(r.ok){const list=await r.json();if(!Array.isArray(list))throw Error('hotspots.json must be an array');data=list.map(normalize);}}catch(error){console.warn('Hotspots file:',error);}
 if(editingEnabled){try{const saved=localStorage.getItem(STORAGE_KEY);if(saved)data=JSON.parse(saved).map(normalize);}catch(error){status('Could not restore local edits: '+error.message);}}
 render();viewer.addHandler('animation',updateVisibility);viewer.addHandler('zoom',updateVisibility);viewer.addHandler('pan',updateVisibility);window.addEventListener('resize',updateVisibility);
 if(editingEnabled){setEditor(true);status(`${data.length} dots loaded. Click artwork to add.`);viewer.addHandler('canvas-click',event=>{if(!editorOpen)return;event.preventDefaultAction=true;if(!event.quick)return;const target=event.originalEvent?.target;if(target?.closest?.('.hotspot'))return;if(Date.now()-lastHotspotPress<650)return;addAt(event.position);});}
 pop.addEventListener('mouseenter',cancelPopoverClose);
 pop.addEventListener('mouseleave',schedulePopoverClose);
 document.addEventListener('pointerdown',ev=>{if(!pop.hidden&&!pop.contains(ev.target)&&![...overlays.values()].some(el=>el.contains(ev.target)))closePopover();});
 $('close-modal').addEventListener('click',()=>{$('hotspot-modal').hidden=true;});$('hotspot-modal').addEventListener('click',ev=>{if(ev.target===$('hotspot-modal'))$('hotspot-modal').hidden=true;});
 document.addEventListener('keydown',ev=>{if(ev.key==='Escape'){closePopover();$('hotspot-modal').hidden=true;}});
 window.mapHotspots={getAll:()=>structuredClone(data)};
}
window.addEventListener('map-ready',initialize);
if(editingEnabled){
 $('toggle-editor').addEventListener('click',()=>setEditor(false));$('show-editor').addEventListener('click',()=>setEditor(true));form.elements.action.addEventListener('change',toggleAction);
 form.addEventListener('submit',ev=>{ev.preventDefault();const i=data.findIndex(h=>h.id===selected);if(i<0)return;try{const input={...data[i]};for(const field of ['region','x','y','label','action','url','content','minZoom','reveal'])input[field]=form.elements[field].value;data[i]=normalize(input);saveLocal();render();edit(data[i].id);status('Dot saved locally. Export to publish.');}catch(error){status(error.message);}});
 $('delete-hotspot').addEventListener('click',()=>{data=data.filter(h=>h.id!==selected);selected=null;form.hidden=true;saveLocal();render();status('Dot deleted locally. Export to publish.');});
 $('cancel-hotspot').addEventListener('click',()=>{selected=null;form.hidden=true;status('Selection cleared.');});
 $('export-md').addEventListener('click',()=>download('hotspots.md',markdown(),'text/markdown'));
 $('export-json').addEventListener('click',()=>download('hotspots.json',JSON.stringify(data,null,2)+'\n','application/json'));
 $('import-hotspots').addEventListener('change',async ev=>{const file=ev.target.files?.[0];if(!file)return;try{const content=await file.text();const parsed=(file.name.toLowerCase().endsWith('.json')?JSON.parse(content).map(normalize):parseMD(content));if(!confirm(`Replace local editor dots with ${parsed.length} imported dots?`))return;data=parsed;selected=null;form.hidden=true;saveLocal();render();status(`Imported ${data.length} dots.`);}catch(error){status('Import error: '+error.message);}finally{ev.target.value='';}});
}
})();

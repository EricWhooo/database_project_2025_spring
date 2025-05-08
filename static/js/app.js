/* ------------- static/js/app.js ------------- */
import {Awesomplete} from './awesomplete.min.js';

let airportCache;

/* 读取全部机场列表（一次缓存） */
async function getAirports(){
  if(airportCache) return airportCache;
  const r = await fetch('/api/airports');   // 后端空查询返回全部/前 N
  airportCache = await r.json();            // ["ATL","BOS",...]
  return airportCache;
}

/* 在文本框上启用自动补全 */
window.attachTypeahead = async selector =>{
  const el = document.querySelector(selector);
  if(!el) return;
  const list = await getAirports();
  new Awesomplete(el,{ list, minChars:1 });
};

/* Toast & flatpickr（flatpickr 可能已被其他页面使用） */
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('.toast').forEach(t=>new bootstrap.Toast(t).show());
});
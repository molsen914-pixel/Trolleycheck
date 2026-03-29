#!/usr/bin/env python3
"""
TrolleyCheck — AU Grocery Price Comparer
Scrapes Coles, Woolworths, Foodland and Aldi using Playwright.

Local:  pip install -r requirements.txt && playwright install chromium
        python3 server.py

Render build command:  pip install -r requirements.txt && playwright install chromium
Render start command:  gunicorn server:app
"""

import os, re, asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.async_api import async_playwright

app = Flask(__name__)
CORS(app)

STORES = [
    {
        "key":   "coles",
        "label": "Coles",
        "url":   "https://www.coles.com.au/search?q={q}",
        "tile":  "section[data-testid='product-tile']",
        "name":  "[data-testid='product-title']",
        "price": "[data-testid='product-pricing']",
    },
    {
        "key":   "woolies",
        "label": "Woolworths",
        "url":   "https://www.woolworths.com.au/shop/search/products?searchTerm={q}",
        "tile":  ".product-tile-v2, article.product-tile",
        "name":  "[data-automation='product-title'], h2",
        "price": "[data-automation='product-price'], .primary",
    },
    {
        "key":   "foodland",
        "label": "Foodland",
        "url":   "https://shop.foodland.com.au/search?q={q}",
        "tile":  ".product-list-item, [class*='ProductTile'], [class*='product-item']",
        "name":  "[class*='product-name'], [class*='ProductName'], h2, h3",
        "price": "[class*='product-price'], [class*='ProductPrice'], [class*='price']",
    },
    {
        "key":   "aldi",
        "label": "Aldi",
        "url":   "https://www.aldi.com.au/search?q={q}",
        "tile":  ".product-item, [class*='product'], article",
        "name":  "[class*='product-name'], [class*='title'], h2, h3",
        "price": "[class*='price'], [class*='Price']",
    },
]


def extract_price(text):
    m = re.search(r"\$?\s*(\d{1,3}(?:\.\d{2})?)", text or "")
    if m:
        price = float(m.group(1))
        if 0.50 <= price <= 120:
            return round(price, 2)
    return None


def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


async def scrape_store(store, query):
    print(f"  [{store['label']}] scraping...")
    results = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                viewport={"width": 390, "height": 844},
            )
            url = store["url"].format(q=query.replace(" ", "+"))
            print(f"    URL: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            try:
                await page.wait_for_selector(store["tile"], timeout=8000)
            except:
                print(f"    No tiles found for {store['label']}")
                await browser.close()
                return []
            tiles = await page.query_selector_all(store["tile"])
            print(f"    Found {len(tiles)} tiles")
            for tile in tiles[:5]:
                try:
                    name_el  = await tile.query_selector(store["name"])
                    price_el = await tile.query_selector(store["price"])
                    name_txt  = clean(await name_el.inner_text())  if name_el  else ""
                    price_txt = clean(await price_el.inner_text()) if price_el else ""
                    price = extract_price(price_txt)
                    if name_txt and price:
                        results.append({"name": name_txt[:65], "price": price})
                        if len(results) >= 2:
                            break
                except:
                    continue
            await browser.close()
    except Exception as e:
        print(f"    ERROR {store['label']}: {e}")
    print(f"    -> {len(results)} prices found")
    return results


def run_scrape(store, query):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(scrape_store(store, query))
    finally:
        loop.close()


@app.route("/ping")
def ping():
    return jsonify({"ok": True})


@app.route("/search")
def search():
    item = request.args.get("q", "").strip()
    if not item:
        return jsonify({"error": "Missing ?q="}), 400
    print(f"\n=== Searching: {item} ===")
    results = {s["key"]: run_scrape(s, item) for s in STORES}
    return jsonify({"query": item, "results": results})


@app.route("/")
def index():
    return PAGE


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#1a1a18">
<title>TrolleyCheck</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@700;900&family=Archivo+Narrow:wght@400;600&display=swap');
:root{--bg:#f5f2eb;--sur:#fff;--sur2:#edeae2;--bdr:#d8d4c8;--txt:#1a1a18;--mut:#88887f;--grn:#2d6a4f;--r:8px;--col:#cc0000;--wol:#1a7a45;--fod:#d4700a;--ald:#1a3d8f}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font-family:'Archivo Narrow',sans-serif;font-size:14px;min-height:100vh}
.hdr{background:var(--txt);color:var(--bg);padding:14px 20px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:10}
.logo{font-family:'Archivo',sans-serif;font-weight:900;font-size:22px;letter-spacing:-1px;line-height:1}
.logo span{color:#c8f135}
.logo-sub{font-size:9px;letter-spacing:.14em;color:rgba(245,242,235,.4);text-transform:uppercase;margin-top:2px}
.pills{display:flex;gap:5px;margin-left:auto;flex-wrap:wrap}
.pill{padding:3px 8px;border-radius:2px;font-family:'Archivo',sans-serif;font-size:9px;font-weight:700;text-transform:uppercase}
.pc{background:var(--col);color:#fff}.pw{background:var(--wol);color:#fff}.pf{background:var(--fod);color:#fff}.pa{background:var(--ald);color:#fff}
.wrap{display:flex;min-height:calc(100vh - 60px)}
.side{width:260px;flex-shrink:0;background:var(--sur);border-right:1px solid var(--bdr);display:flex;flex-direction:column;padding:18px 16px;gap:16px}
.main{flex:1;padding:20px;display:flex;flex-direction:column;gap:18px;overflow-y:auto}
@media(max-width:680px){.wrap{flex-direction:column}.side{width:100%;border-right:none;border-bottom:1px solid var(--bdr)}.pills{display:none}.store-grid{grid-template-columns:repeat(2,1fr)!important}}
@media(max-width:400px){.store-grid{grid-template-columns:1fr!important}}
.lbl{font-family:'Archivo',sans-serif;font-size:9px;font-weight:700;letter-spacing:.14em;color:var(--mut);text-transform:uppercase}
.add-row{display:flex;gap:7px}
.add-row input{flex:1;background:var(--sur2);border:1px solid var(--bdr);border-radius:var(--r);padding:9px 11px;font-family:'Archivo Narrow',sans-serif;font-size:14px;color:var(--txt);outline:none}
.add-row input::placeholder{color:var(--mut)}
.btn-add{background:var(--txt);color:var(--bg);border:none;border-radius:var(--r);width:38px;font-size:22px;cursor:pointer;display:flex;align-items:center;justify-content:center}
.list-scroll{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:5px;max-height:300px}
.li{display:flex;align-items:center;gap:8px;padding:9px 11px;border-radius:var(--r);border:1px solid var(--bdr);background:var(--sur2);cursor:pointer}
.li:hover,.li.active{border-color:var(--txt)}.li.active{background:#e4e0d5}
.li-name{flex:1;font-size:13px}
.li-win{font-size:10px;font-family:'Archivo',sans-serif;font-weight:700;color:var(--grn);white-space:nowrap}
.li-win.na{color:var(--mut);font-weight:400}
.btn-x{background:none;border:none;cursor:pointer;color:var(--mut);font-size:12px;padding:2px 4px}
.list-btns{display:flex;gap:6px}
.btn-sm{flex:1;background:var(--sur2);border:1px solid var(--bdr);border-radius:var(--r);padding:9px 4px;color:var(--txt);font-family:'Archivo',sans-serif;font-size:10px;font-weight:700;cursor:pointer}
.saved-panel{display:flex;flex-direction:column;gap:6px}
.saved-item{background:var(--sur2);border:1px solid var(--bdr);border-radius:var(--r);padding:8px 10px;display:flex;justify-content:space-between;align-items:center;cursor:pointer;font-size:12px}
.saved-meta{font-size:10px;color:var(--mut);margin-top:2px}
.search-row{display:flex;gap:8px}
.search-input{flex:1;background:var(--sur);border:2px solid var(--bdr);border-radius:var(--r);padding:12px 14px;font-family:'Archivo Narrow',sans-serif;font-size:15px;color:var(--txt);outline:none}
.search-input:focus{border-color:var(--txt)}
.btn-search{background:var(--txt);color:var(--bg);border:none;border-radius:var(--r);padding:12px 18px;font-family:'Archivo',sans-serif;font-weight:700;font-size:13px;cursor:pointer;white-space:nowrap}
.btn-search:disabled{opacity:.4;cursor:not-allowed}
.loading{display:flex;flex-direction:column;align-items:center;gap:18px;padding:48px 0;text-align:center}
.ld-stores{display:flex;gap:16px}
.ld-store{display:flex;flex-direction:column;align-items:center;gap:7px}
.ld-dot{width:10px;height:10px;border-radius:50%}
.ld-lbl{font-family:'Archivo',sans-serif;font-size:10px;font-weight:700}
.ld-store:nth-child(1) .ld-dot{animation:ldp 1.1s ease-in-out infinite 0s}
.ld-store:nth-child(2) .ld-dot{animation:ldp 1.1s ease-in-out infinite .18s}
.ld-store:nth-child(3) .ld-dot{animation:ldp 1.1s ease-in-out infinite .36s}
.ld-store:nth-child(4) .ld-dot{animation:ldp 1.1s ease-in-out infinite .54s}
@keyframes ldp{0%,100%{transform:scale(.5);opacity:.3}50%{transform:scale(1.3);opacity:1}}
.ld-txt{font-size:13px;color:var(--mut)}
.res-hdr{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.res-title{font-family:'Archivo',sans-serif;font-size:18px;font-weight:900;letter-spacing:-.5px}
.res-query{font-size:13px;color:var(--mut)}
.store-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.card{background:var(--sur);border:1px solid var(--bdr);border-radius:var(--r);padding:14px;display:flex;flex-direction:column;gap:10px}
.card.best-c{border:2px solid var(--col);box-shadow:0 3px 14px rgba(204,0,0,.1)}
.card.best-w{border:2px solid var(--wol);box-shadow:0 3px 14px rgba(26,122,69,.1)}
.card.best-f{border:2px solid var(--fod);box-shadow:0 3px 14px rgba(212,112,10,.1)}
.card.best-a{border:2px solid var(--ald);box-shadow:0 3px 14px rgba(26,61,143,.1)}
.card-hd{display:flex;align-items:center;justify-content:space-between}
.card-nm{font-family:'Archivo',sans-serif;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.nc{color:var(--col)}.nw{color:var(--wol)}.nf{color:var(--fod)}.na{color:var(--ald)}
.best-tag{font-family:'Archivo',sans-serif;font-size:8px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:2px 6px;border-radius:2px;background:var(--txt);color:var(--bg)}
.prods{display:flex;flex-direction:column;gap:8px}
.prod-row{display:flex;align-items:flex-start;justify-content:space-between;gap:6px}
.prod-name{font-size:11px;color:var(--mut);flex:1;line-height:1.3}
.prod-price{font-family:'Archivo',sans-serif;font-weight:700;font-size:15px;white-space:nowrap}
.no-res{font-size:11px;color:var(--mut);font-style:italic}
.summary{background:var(--txt);color:var(--bg);border-radius:var(--r);padding:14px 18px;display:flex;align-items:center;flex-wrap:wrap}
.sum-item{padding:0 16px}.sum-item:first-child{padding-left:0}
.sum-lbl{font-size:9px;letter-spacing:.12em;color:rgba(245,242,235,.45);text-transform:uppercase;font-family:'Archivo',sans-serif;margin-bottom:3px}
.sum-val{font-family:'Archivo',sans-serif;font-weight:900;font-size:20px;letter-spacing:-.5px}
.vc{color:#ff6b6b}.vw{color:#5dd49a}.vf{color:#ffb347}.va{color:#7aadff}.vs{color:#c8f135}
.sum-sep{width:1px;height:36px;background:rgba(255,255,255,.12)}
.disc{font-size:11px;color:var(--mut);line-height:1.6;border-top:1px solid var(--bdr);padding-top:10px}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:60px 0;color:var(--mut);text-align:center}
.empty-icon{font-size:36px;opacity:.3}
.empty-title{font-family:'Archivo',sans-serif;font-size:16px;font-weight:900;color:var(--bdr)}
.toast{position:fixed;bottom:20px;right:20px;background:var(--txt);color:var(--bg);padding:10px 16px;border-radius:var(--r);font-family:'Archivo',sans-serif;font-weight:600;font-size:12px;z-index:99;transform:translateY(60px);opacity:0;transition:transform .25s,opacity .25s;pointer-events:none}
.toast.show{transform:translateY(0);opacity:1}
.modal-bg{position:fixed;inset:0;background:rgba(26,26,24,.6);z-index:200;display:flex;align-items:center;justify-content:center;padding:20px;opacity:0;pointer-events:none;transition:opacity .2s}
.modal-bg.open{opacity:1;pointer-events:all}
.modal{background:var(--sur);border:1px solid var(--bdr);border-radius:var(--r);padding:22px;width:100%;max-width:320px;display:flex;flex-direction:column;gap:12px;box-shadow:0 8px 40px rgba(0,0,0,.15);transform:scale(.96);transition:transform .2s}
.modal-bg.open .modal{transform:scale(1)}
.modal-title{font-family:'Archivo',sans-serif;font-size:15px;font-weight:700}
.modal input{background:var(--sur2);border:1px solid var(--bdr);border-radius:var(--r);padding:10px 12px;color:var(--txt);font-family:'Archivo Narrow',sans-serif;font-size:14px;outline:none;width:100%}
.modal-row{display:flex;gap:8px}
.btn-ok{flex:1;background:var(--txt);color:var(--bg);border:none;border-radius:var(--r);padding:11px;font-family:'Archivo',sans-serif;font-weight:700;font-size:13px;cursor:pointer}
.btn-no{flex:1;background:none;border:1px solid var(--bdr);border-radius:var(--r);padding:11px;color:var(--mut);font-family:'Archivo',sans-serif;font-weight:600;font-size:13px;cursor:pointer}
</style>
</head>
<body>
<div class="hdr">
  <div><div class="logo">Trolley<span>Check</span></div><div class="logo-sub">AU Grocery Price Comparer</div></div>
  <div class="pills"><span class="pill pc">Coles</span><span class="pill pw">Woolworths</span><span class="pill pf">Foodland</span><span class="pill pa">Aldi</span></div>
</div>
<div class="wrap">
  <aside class="side">
    <div class="lbl">🛒 Shopping List</div>
    <div class="add-row">
      <input id="itemInput" type="text" placeholder="Add item…" autocomplete="off"/>
      <button class="btn-add" onclick="addItem()">+</button>
    </div>
    <div class="list-scroll" id="listEl"></div>
    <div class="list-btns">
      <button class="btn-sm" onclick="openSave()">💾 Save</button>
      <button class="btn-sm" onclick="toggleLoad()">📂 Load</button>
      <button class="btn-sm" onclick="clearList()">✕ Clear</button>
    </div>
    <div id="savedPanel" style="display:none" class="saved-panel">
      <div class="lbl">Saved Lists</div><div id="savedItems"></div>
    </div>
  </aside>
  <main class="main">
    <div class="search-row">
      <input class="search-input" id="searchInput" type="search" placeholder="Search a product — e.g. free range eggs…" autocomplete="off"/>
      <button class="btn-search" id="searchBtn" onclick="doSearch()">Compare</button>
    </div>
    <div id="results">
      <div class="empty">
        <div class="empty-icon">🛍️</div>
        <div class="empty-title">Nothing compared yet</div>
        <div>Search above to compare prices across all four stores.</div>
      </div>
    </div>
  </main>
</div>
<div class="toast" id="toastEl"></div>
<div class="modal-bg" id="modalBg">
  <div class="modal">
    <div class="modal-title">Save Shopping List</div>
    <input type="text" id="saveNameInput" placeholder="e.g. Weekly Shop"/>
    <div class="modal-row">
      <button class="btn-ok" onclick="confirmSave()">Save</button>
      <button class="btn-no" onclick="closeModal()">Cancel</button>
    </div>
  </div>
</div>
<script>
const STORES=[{key:'coles',label:'Coles',cls:'c',color:'#cc0000'},{key:'woolies',label:'Woolworths',cls:'w',color:'#1a7a45'},{key:'foodland',label:'Foodland',cls:'f',color:'#d4700a'},{key:'aldi',label:'Aldi',cls:'a',color:'#1a3d8f'}];
let list=JSON.parse(localStorage.getItem('tc_list')||'[]');
let saved=JSON.parse(localStorage.getItem('tc_saved')||'{}');
let active=null;
async function doSearch(){
  const q=document.getElementById('searchInput').value.trim();
  if(!q)return;
  active=q;
  const btn=document.getElementById('searchBtn');
  btn.disabled=true;btn.textContent='Searching…';
  document.getElementById('results').innerHTML=`<div class="loading"><div class="ld-stores">${STORES.map(s=>`<div class="ld-store"><div class="ld-dot" style="background:${s.color}"></div><div class="ld-lbl" style="color:${s.color}">${s.label}</div></div>`).join('')}</div><div class="ld-txt">Searching for <strong>"${q}"</strong>…<br><small>This takes about 30–60 seconds</small></div></div>`;
  try{
    const res=await fetch(`/search?q=${encodeURIComponent(q)}`);
    if(!res.ok)throw new Error('Server error '+res.status);
    const data=await res.json();
    renderResults(data.query,data.results);
    updateWinner(q,data.results);
  }catch(e){
    document.getElementById('results').innerHTML=`<div style="background:#fff3cd;border:1px solid #f0c040;border-radius:8px;padding:14px;font-size:13px;line-height:1.7">⚠️ <strong>Search failed:</strong> ${e.message}</div>`;
  }
  btn.disabled=false;btn.textContent='Compare';
}
function renderResults(query,results){
  let cheapKey=null,cheapPrice=Infinity;
  for(const s of STORES){const p=(results[s.key]||[]);if(p.length>0&&p[0].price<cheapPrice){cheapPrice=p[0].price;cheapKey=s.key;}}
  const cards=STORES.map(s=>{
    const p=results[s.key]||[];
    const best=s.key===cheapKey&&p.length>0;
    const body=p.length===0?`<div class="no-res">No prices found</div>`:`<div class="prods">${p.map((x,i)=>`<div class="prod-row"><div class="prod-name">${x.name}</div><div class="prod-price" style="color:${i===0&&best?'var(--grn)':'var(--txt)'}">$${x.price.toFixed(2)}</div></div>`).join('')}</div>`;
    return`<div class="card${best?' best-'+s.cls:''}"><div class="card-hd"><div class="card-nm n${s.cls}">${s.label}</div>${best?'<span class="best-tag">Cheapest</span>':''}</div>${body}</div>`;
  }).join('');
  const done=STORES.filter(s=>(results[s.key]||[]).length>0).sort((a,b)=>results[a.key][0].price-results[b.key][0].price);
  let summary='';
  if(done.length>=2){
    const saving=results[done[done.length-1].key][0].price-results[done[0].key][0].price;
    summary=`<div class="summary">${done.map((s,i)=>`${i>0?'<div class="sum-sep"></div>':''}<div class="sum-item"><div class="sum-lbl">${s.label}</div><div class="sum-val v${s.cls}">$${results[s.key][0].price.toFixed(2)}</div></div>`).join('')}<div class="sum-sep"></div><div class="sum-item"><div class="sum-lbl">Potential saving</div><div class="sum-val vs">$${saving.toFixed(2)}</div></div></div>`;
  }
  document.getElementById('results').innerHTML=`<div class="res-hdr"><div class="res-title">Price Comparison</div><div class="res-query">"${query}"</div></div><div class="store-grid">${cards}</div>${summary}<div class="disc">⚡ Prices scraped directly from store websites. Always confirm before shopping.</div>`;
}
function updateWinner(query,results){
  let cheapKey=null,cheapPrice=Infinity;
  for(const s of STORES){const p=results[s.key]||[];if(p.length>0&&p[0].price<cheapPrice){cheapPrice=p[0].price;cheapKey=s.key;}}
  if(!cheapKey)return;
  const label=STORES.find(s=>s.key===cheapKey).label;
  list=list.map(item=>item.name.toLowerCase()===query.toLowerCase()?{...item,cheapest:`${label} $${cheapPrice.toFixed(2)}`}:item);
  persist();renderList();
}
function addItem(){const v=document.getElementById('itemInput').value.trim();if(!v)return;list.push({name:v,cheapest:null});document.getElementById('itemInput').value='';persist();renderList();showToast(`"${v}" added`);}
function removeItem(i){list.splice(i,1);persist();renderList();}
function clearList(){if(!list.length)return;list=[];persist();renderList();showToast('Cleared');}
function renderList(){
  const el=document.getElementById('listEl');
  if(!list.length){el.innerHTML=`<div style="color:var(--mut);font-size:12px;text-align:center;padding:16px 0">Your list is empty</div>`;return;}
  el.innerHTML=list.map((item,i)=>`<div class="li${active===item.name?' active':''}" onclick="searchFromList('${esc(item.name)}')"><span class="li-name">${item.name}</span><span class="li-win${item.cheapest?'':' na'}">${item.cheapest||'—'}</span><button class="btn-x" onclick="event.stopPropagation();removeItem(${i})">✕</button></div>`).join('');
}
function searchFromList(name){document.getElementById('searchInput').value=name;doSearch();}
function persist(){localStorage.setItem('tc_list',JSON.stringify(list));}
function openSave(){if(!list.length){showToast('Add items first');return;}document.getElementById('modalBg').classList.add('open');document.getElementById('saveNameInput').value='';setTimeout(()=>document.getElementById('saveNameInput').focus(),80);}
function closeModal(){document.getElementById('modalBg').classList.remove('open');}
function confirmSave(){const name=document.getElementById('saveNameInput').value.trim();if(!name){showToast('Enter a name');return;}saved[name]={items:[...list],date:new Date().toLocaleDateString('en-AU')};localStorage.setItem('tc_saved',JSON.stringify(saved));closeModal();showToast(`"${name}" saved!`);}
function toggleLoad(){const panel=document.getElementById('savedPanel');if(!Object.keys(saved).length){showToast('No saved lists yet');return;}panel.style.display=panel.style.display==='none'?'flex':'none';panel.style.flexDirection='column';panel.style.gap='6px';document.getElementById('savedItems').innerHTML=Object.keys(saved).map(k=>`<div class="saved-item" onclick="loadList('${esc(k)}')"><div><div>${k}</div><div class="saved-meta">${saved[k].items.length} items · ${saved[k].date}</div></div><button class="btn-x" onclick="event.stopPropagation();deleteSaved('${esc(k)}')">✕</button></div>`).join('');}
function loadList(name){list=[...saved[name].items];persist();renderList();document.getElementById('savedPanel').style.display='none';showToast(`"${name}" loaded`);}
function deleteSaved(name){delete saved[name];localStorage.setItem('tc_saved',JSON.stringify(saved));toggleLoad();toggleLoad();}
let tt;
function showToast(msg){const el=document.getElementById('toastEl');el.textContent=msg;el.classList.add('show');clearTimeout(tt);tt=setTimeout(()=>el.classList.remove('show'),2200);}
const esc=s=>s.replace(/'/g,"\\'");
document.getElementById('itemInput').addEventListener('keydown',e=>e.key==='Enter'&&addItem());
document.getElementById('searchInput').addEventListener('keydown',e=>e.key==='Enter'&&doSearch());
document.getElementById('saveNameInput').addEventListener('keydown',e=>e.key==='Enter'&&confirmSave());
document.getElementById('modalBg').addEventListener('click',e=>e.target===document.getElementById('modalBg')&&closeModal());
renderList();
</script>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5432))
    print(f"TrolleyCheck running -> http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

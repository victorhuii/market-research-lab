const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const html = fs.readFileSync('web/index.html','utf8');
const source = fs.readFileSync('web/app.js','utf8');
const demo = JSON.parse(fs.readFileSync('docs/demo/research.json','utf8'));

function harness() {
  const elements = new Map();
  const element = (id) => ({id,hidden:false,disabled:false,value:'',innerHTML:'',textContent:'',dataset:{},listeners:{},
    classList:{add(){},remove(){},toggle(){}},setAttribute(){},addEventListener(name,fn){this.listeners[name]=fn;}});
  for(const match of html.matchAll(/\bid="([^"]+)"/g))elements.set(match[1],element(match[1]));
  const settings = new Map();
  for(const name of Object.keys(demo.settings))settings.set(name,element(name));
  elements.get('settings-form').elements={namedItem:(name)=>settings.get(name)};
  elements.get('strategy-select').value='signal';elements.get('fill-select').value='through';
  const tabs = ['research','exchange','history'].map((view)=>({...element(view),dataset:{view}}));
  const requests=[];
  const context=vm.createContext({console,crypto,clearInterval,setInterval,
    document:{getElementById(id){assert.ok(elements.has(id),`missing HTML element ${id}`);return elements.get(id);},
      querySelectorAll(selector){return selector==='.tab'?tabs:[...elements.values()];},body:element('body')},
    fetch:async(path,options)=>{requests.push({path,options});return {ok:true,json:async()=>demo};}});
  vm.runInContext(source,context);
  return {elements,context,requests};
}

test('initial fetch renders all result views and reenables controls',async()=>{
  const h=harness();
  await new Promise(setImmediate);
  assert.equal(h.requests[0].path,'/api/research');
  assert.match(h.elements.get('source-label').textContent,/Synthetic demo/);
  assert.match(h.elements.get('prediction-table').innerHTML,/Logistic regression/);
  assert.match(h.elements.get('sensitivity-table').innerHTML,/Trade-through/);
  assert.match(h.elements.get('equity-chart').innerHTML,/<path/);
  assert.doesNotMatch(h.elements.get('equity-chart').innerHTML,/NaN|Infinity/);
  assert.equal(h.elements.get('replay-slider').disabled,false);
  vm.runInContext('position=0;renderFrame()',h.context);
  assert.equal(h.elements.get('event-label').textContent,`1 / ${demo.frames.length}`);
  vm.runInContext('position=research.frames.length-1;renderFrame()',h.context);
  assert.match(h.elements.get('probability-bars').innerHTML,/prob-row/);
});

test('participant and imported session text is escaped in generated markup',async()=>{
  const h=harness();await new Promise(setImmediate);
  h.context.unsafeState={sequence:1,bids:[],asks:[],orders:[{order_id:'<script>x</script>',participant:'<img src=x>',side:'buy',price:100,quantity:1}],trades:[],balances:{'<img src=x>':{cash:0,inventory:0}}};
  vm.runInContext('renderExchange(unsafeState)',h.context);
  assert.doesNotMatch(h.elements.get('orders-table').innerHTML,/<script>|<img/);
  assert.match(h.elements.get('orders-table').innerHTML,/&lt;img/);
  assert.match(h.elements.get('balances-table').innerHTML,/&lt;img/);
  const data=structuredClone(demo);data.splits.test=['<img src=x>'];
  h.context.imported=data;
  vm.runInContext('renderResearch(imported)',h.context);
  assert.doesNotMatch(h.elements.get('method-content').innerHTML,/<img/);
});

test('API failure shows an error and restores disabled controls',async()=>{
  const h=harness();await new Promise(setImmediate);
  h.context.fetch=async()=>({ok:false,status:400,json:async()=>({error:'invalid dataset'})});
  await vm.runInContext("task(async()=>{await api('/api/import',{csv:'bad'})})",h.context);
  assert.equal(h.elements.get('message').className,'error');
  assert.equal(h.elements.get('message').textContent,'invalid dataset');
  assert.equal(h.elements.get('replay-slider').disabled,false);
});

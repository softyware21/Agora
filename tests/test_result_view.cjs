const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {renderAnswer} = require('../web/answer.js');
const AgoraDiscussion = require('../web/discussion.js');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  set innerHTML(_) { throw new Error('Untrusted output must remain text'); }
}
const doc = {createElement: tag => new Element(tag), createTextNode: text => Object.assign(new Element('#text'), {textContent:text})};
const root = new Element('div');
const source = fs.readFileSync(require.resolve('../web/app.js'), 'utf8');
const context = vm.createContext({document:doc, AgoraDiscussion, $:() => root,
  t:value => value, providerName:value => value,
  renderAnswer:(text,t) => renderAnswer(text,t,doc)});
vm.runInContext(source.slice(source.indexOf('function node('), source.indexOf('function error(')), context);
vm.runInContext(source.slice(source.indexOf('function renderConclusion('), source.indexOf('function setDiscussionView(')), context);
const all = node => [node,...node.children.flatMap(all)];
const card = {version:1, conclusion:'Wait.', conditions:['Capacity is unknown.'], reasons:['Reports conflict.'], next_steps:[], answer_state:'conditional', decision_state:'conflicting_evidence'};
const summary = value => 'Full original.\n```agora-result\n'+JSON.stringify(value)+'\n```';
const issues = [{status:'agreed',topic:'Readiness',positions:[{provider:'codex',quote:'Proceed now.'},{provider:'claude',quote:'Do not proceed.'}]}];
context.renderConclusion(summary(card), issues);
assert.equal(root.children[0].textContent, 'Wait.');
const review = root.children.find(n => n.className === 'notice');
assert.ok(review && review.tag !== 'details');
assert.deepEqual(all(review).filter(n => n.tag === 'blockquote').map(n => n.textContent), ['codex: Proceed now.','claude: Do not proceed.']);
assert.ok(all(root).some(n => n.textContent.includes('Reported decision state: Evidence conflicts')));
context.renderConclusion(summary({...card,decision_state:'authorized'}), issues);
assert.ok(all(root).some(n => n.tag === 'pre' && n.textContent === summary({...card,decision_state:'authorized'})));
context.renderConclusion('Legacy <script>alert(1)</script>', issues);
assert.equal(all(root).filter(n => n.tag === 'script').length, 0);
assert.ok(all(root).some(n => n.tag === 'pre' && n.textContent === 'Legacy <script>alert(1)</script>'));
context.renderConclusion(summary({...card,conclusion:'<img src=x onerror=alert(1)>'}), []);
assert.equal(root.children[0].textContent, '<img src=x onerror=alert(1)>');
assert.equal(all(root).filter(n => n.tag === 'img').length, 0);
console.log('Reported states, visible opposing quotes, and full-source fallback passed.');

const direct = {status:'different_categories', positions:[
  {provider:'codex',turn_id:'T003',status:'declared',disposition:'ready',conclusion:'Proceed.',conditions:['Capacity is sufficient.']},
  {provider:'claude',turn_id:'T004',status:'declared',disposition:'blocked',conclusion:'Do not proceed.',conditions:['Capacity is insufficient.']}
]};
context.renderConclusion(summary(card), [], direct);
const panel = root.children.find(n => n.className === 'participant-positions');
assert.ok(panel && panel.tag !== 'details');
assert.ok(all(panel).some(n => n.textContent === 'Do not proceed.'));
assert.ok(all(panel).some(n => n.textContent === 'Capacity is insufficient.'));
context.renderConclusion('Legacy answer.', [], direct);
assert.ok(root.children.some(n => n.className === 'participant-positions'));

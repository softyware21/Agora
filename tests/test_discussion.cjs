const assert = require('node:assert/strict');
const view = require('../web/discussion.js');
const issues = [{id:'a', status:'agreed'}, {id:'b', status:'unverified', model_status:'agreed'}, {id:'c', status:'disputed'}];
assert.deepEqual(view.issueGroups(issues).agreed.map(x => x.id), ['a']);
assert.deepEqual(view.issueGroups(issues).open.map(x => x.id), ['b','c']);
assert.deepEqual(view.issueGroups(), {agreed:[], open:[]});
const turns = [
  {provider:'codex', phase:'initial', text:'First'},
  {provider:'claude', phase:'initial', text:'Second'},
  {provider:'codex', phase:'review', round:1, text:'Third'},
  {provider:'claude', phase:'review', round:1, text:'Fourth'},
  {provider:'claude', phase:'summary', round:1, text:'Summary'}
];
const before = JSON.stringify(turns);
const rounds = view.rounds(turns);
assert.equal(rounds.length, 2);
assert.equal(rounds[1].turns[0].id, 'T003');
assert.equal(rounds[1].turns[1].text, 'Fourth');
assert.equal(JSON.stringify(turns), before);
assert.deepEqual(view.stages({rounds:1,turns:turns.slice(0,3)}), [true,false,false]);
assert.deepEqual(view.stages({rounds:1,turns}), [true,true,true]);
assert.deepEqual(view.stages({rounds:2,turns:turns.slice(0,4)}), [true,false,false]);
assert.deepEqual(view.activity('claude: review'), {provider:'claude',step:'review'});
assert.equal(view.activity('fetching').step, 'preparing');
assert.equal(view.shortTitle('  A\n question  '), 'A question');
assert.equal(view.shortTitle('A long question', 6), 'A long…');
assert.equal(view.excerpt('# Heading\n**Keep** `text`\n```json\n{}'), 'Heading Keep text');
console.log('Issue classification, round provenance, and progress checks passed.');

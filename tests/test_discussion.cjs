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

assert.equal(view.purposeRules('Existing rules', 'general'), 'Existing rules');
assert.ok(view.purposeRules('Existing rules', 'verify').startsWith('Existing rules\n\nDiscussion purpose: verify.'));
assert.equal(view.purposeRules('Existing rules', 'unknown'), 'Existing rules');
const checks = view.checksFor({calculation_checks:[{turn:1,checks:[{status:'arithmetic_match'}]},{turn:2,checks:[{status:'arithmetic_mismatch'}]}], source_checks:[{turn:2,checks:[{status:'quote_found'}]}], attribution_checks:[{checks:[{turn_id:'T002',responds_to:'T001',status:'context_not_available'}, {turn_id:'T002',responds_to:'T001',status:'quote_and_context_match'}]}]}, 'T002');
assert.deepEqual(checks.calculations, [{status:'arithmetic_mismatch'}]);
assert.equal(checks.sources.length, 1);
assert.equal(checks.responses.length, 1);
assert.deepEqual(view.checksFor({}, 'T001'), {calculations:[],sources:[],responses:[]});

const result = {version:1, conclusion:'Choose A.', conditions:['Only within the stated budget.'], reasons:['A meets the requirement.'], next_steps:[]};
const block = value => '```agora-result\n' + JSON.stringify(value) + '\n```';
assert.deepEqual(view.resultCard(block(result)), {conclusion:result.conclusion, conditions:result.conditions, reasons:result.reasons, next_steps:[]});
assert.equal(view.resultCard('A legacy summary.'), null);
assert.equal(view.resultCard(block(result) + '\n' + block(result)), null);
assert.equal(view.resultCard('```agora-result\n{broken}\n```'), null);
assert.equal(view.resultCard('```agora-result\n' + JSON.stringify(result)), null);
for (const change of [{version:2}, {conditions:[]}, {conditions:['']}, {conclusion:'x'.repeat(601)}, {reasons:'not a list'}, {next_steps:[{}]}, {warnings:['A hidden important condition']}]) {
  assert.equal(view.resultCard(block({...result,...change})), null);
}
const hostile = {...result, conclusion:'<img src=x onerror=alert(1)>'};
assert.equal(view.resultCard(block(hostile)).conclusion, hostile.conclusion);
assert.ok(view.resultInstruction.includes('material assumptions'));
console.log('Concise results reject incomplete, duplicate, and unexpected structures.');

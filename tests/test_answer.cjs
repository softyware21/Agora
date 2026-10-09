const assert = require('node:assert/strict');
const {renderAnswer} = require('../web/answer.js');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; }
  append(...children) { this.children.push(...children); }
  set innerHTML(_) { throw new Error('HTML must not be interpreted'); }
}
const doc = {createElement: tag => new Element(tag), createTextNode: text => Object.assign(new Element('#text'), {textContent: text})};
const all = node => [node, ...node.children.flatMap(all)];
const render = text => renderAnswer(text, x => x, doc);
let root = render('# Decision\n**Keep** `x`\n- one\n- two\n\n| A | B |\n| --- | --- |\n| 1 | 2 |');
for (const tag of ['h2', 'strong', 'code', 'ul', 'li', 'table', 'th', 'td']) assert.ok(all(root).some(x => x.tag === tag), tag);
root = render('<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n[x](javascript:alert(1))\n[ok](https://example.org/path)');
assert.equal(all(root).filter(x => ['script', 'img'].includes(x.tag)).length, 0);
const links = all(root).filter(x => x.tag === 'a');
assert.equal(links.length, 1); assert.equal(links[0].href, 'https://example.org/path'); assert.equal(links[0].rel, 'noopener noreferrer');
const raw = 'Before\n```agora-issues\n{"status":"disputed"}\n```\nAfter';
root = render(raw);
assert.equal(all(root).filter(x => x.tag === 'details').length, 2);
assert.ok(all(root).some(x => x.tag === 'pre' && x.textContent === raw));
assert.ok(all(root).some(x => x.tag === 'p' && x.children.some(c => c.textContent === 'After')));
root = render('```\n# Not a heading\n<script>');
assert.equal(all(root).filter(x => x.tag === 'h2').length, 0);
assert.ok(all(root).some(x => x.tag === 'code' && x.textContent.includes('<script>')));
console.log('Answer formatting and unsafe-output checks passed.');
